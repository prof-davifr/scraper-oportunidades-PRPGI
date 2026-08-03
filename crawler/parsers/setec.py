import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""


async def _create_stealth_context(browser):
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
    )
    await context.add_init_script(STEALTH_JS)
    return context


class SetecParser:
    def __init__(self, max_items: int | None = 50):
        self.base_url = "https://www.gov.br/mec/pt-br/acesso-a-informacao/institucional/estrutura-organizacional/orgaos-especificos-singulares/secretaria-de-educacao-profissional/editais"
        self.institution = "SETEC"
        self.max_items = max_items

    async def _goto_with_retry(
        self, page, url: str, attempts: int = 6, base_delay: float = 8.0
    ) -> None:
        """Navega com retry. O gov.br/MEC aplica CAPTCHA intermitente
        ("human visitor") — detecta o bloqueio e espera antes de tentar de novo."""
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                await page.wait_for_timeout(4000)
                try:
                    body = await page.locator("body").inner_text()
                except Exception:
                    body = ""
                if "human visitor" in body or "What code is in the image" in body:
                    raise RuntimeError("CAPTCHA/anti-bot detected by gov.br/MEC")
                return
            except Exception as exc:
                last_exc = exc
                if attempt < attempts:
                    sleep_time = base_delay * attempt
                    logger.warning(
                        "SETEC blocked (attempt %s/%s): %s. Aguardando %.1fs",
                        attempt,
                        attempts,
                        exc,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
        raise RuntimeError(f"SETEC navigation failed after {attempts} attempts") from last_exc

    async def _get_year_links(self, page) -> list[str]:
        # A estrutura mudou: os links de ano ficam sob o caminho da secretaria
        # (antes eram /centrais-de-conteudo/editais/).
        links = await page.locator(
            'a[href*="/editais/202"], '
            'a[href*="/editais/anterior-a-2021"]'
        ).all()
        seen = set()
        result = []
        for link in links:
            href = await link.get_attribute("href")
            if href and href not in seen:
                seen.add(href)
                result.append(href)
        return result

    async def _scrape_year_page(
        self, context, year_url: str, item_limit: int | None
    ) -> list[dict]:
        page = await context.new_page()
        try:
            await self._goto_with_retry(page, year_url)

            # Editais agora são links .pdf diretos (ex.: SEI_6991254_chamada.pdf)
            pdf_links = await page.locator('#content a[href*=".pdf"]').all()
            items = []
            seen_hrefs = set()

            for link in pdf_links:
                if item_limit is not None and len(items) >= item_limit:
                    break

                href = await link.get_attribute("href")
                if not href or href in seen_hrefs:
                    continue
                seen_hrefs.add(href)

                link_text = (await link.text_content() or "").strip()
                # Título vago ("Edital", "Retificação", "(documento Nº ...)"):
                # usa o texto do item pai (li/div) para dar contexto.
                if (
                    not link_text
                    or len(link_text) < 12
                    or link_text.lower().startswith("(")
                ):
                    parent = link.locator("xpath=ancestor::li[1] | ancestor::div[1]")
                    parent_text = ""
                    try:
                        parent_text = (await parent.first.inner_text() or "").strip()
                    except Exception:
                        parent_text = ""
                    if parent_text:
                        title = parent_text.split("\n")[0].strip()[:200]
                    else:
                        title = href.rsplit("/", 1)[-1].replace(".pdf", "").replace("-", " ").replace("_", " ").title()
                else:
                    title = link_text

                if not title:
                    continue

                # Exclui documentos de apoio (anexos/modelos) — não são editais.
                low = title.lower()
                if any(kw in low for kw in ("anexo", "modelo do formulário", "modelo de formulário", "termo de autorização")):
                    continue

                items.append({
                    "title": title,
                    "link": href,
                    "deadline": "",
                    "description": title,
                })

            return items
        finally:
            await page.close()

    async def parse(self, db, max_items: int | None = None) -> dict[str, Any]:
        item_limit = self.max_items if max_items is None else max_items

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = await _create_stealth_context(browser)
            page = await context.new_page()

            try:
                await self._goto_with_retry(page, self.base_url)

                year_links = await self._get_year_links(page)
                logger.info("SETEC found %s year sub-pages", len(year_links))

                inserted_count = 0
                duplicate_count = 0
                error_count = 0
                processed = 0

                for year_url in year_links:
                    if item_limit is not None and processed >= item_limit:
                        break

                    items = await self._scrape_year_page(context, year_url, item_limit)

                    for item in items:
                        if item_limit is not None and processed >= item_limit:
                            break
                        try:
                            result = db.add_opportunity_with_result(
                                institution=self.institution,
                                title=item["title"],
                                link=item["link"],
                                description=item["description"],
                                deadline=item["deadline"],
                            )
                            processed += 1
                            if result == "inserted":
                                inserted_count += 1
                            else:
                                duplicate_count += 1
                        except Exception as e:
                            error_count += 1
                            logger.exception("Error parsing SETEC item: %s", e)

                return {
                    "institution": self.institution,
                    "processed": processed,
                    "new": inserted_count,
                    "duplicates": duplicate_count,
                    "errors": error_count,
                }
            finally:
                await page.close()
                await browser.close()


if __name__ == "__main__":
    from crawler.database import OpportunityDatabase

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    db = OpportunityDatabase(str(PROJECT_ROOT / "oportunidades.db"))
    parser = SetecParser()
    result = asyncio.run(parser.parse(db))
    db.export_to_spreadsheet(
        str(PROJECT_ROOT / "editais.csv"), str(PROJECT_ROOT / "editais.xlsx")
    )
    logger.info("Done: %s", result)
