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
        self, page, url: str, attempts: int = 3, base_delay: float = 1.0
    ) -> None:
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                return
            except Exception as exc:
                last_exc = exc
                if attempt < attempts:
                    sleep_time = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "SETEC navigation failed (attempt %s/%s): %s. Retrying in %.1fs",
                        attempt,
                        attempts,
                        exc,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
        raise RuntimeError(f"SETEC navigation failed after {attempts} attempts") from last_exc

    async def _get_year_links(self, page) -> list[str]:
        links = await page.locator(
            'a[href*="/centrais-de-conteudo/editais/202"], '
            'a[href*="/centrais-de-conteudo/editais/Anterior"]'
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

            pdf_links = await page.locator('a[href*="/editais/pdf/"]').all()
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
                if link_text.lower() in ("clique aqui", "aqui", ""):
                    parent = link.locator("..")
                    strong = parent.locator("strong").first
                    if await strong.count() > 0:
                        title = (await strong.text_content() or "").strip()
                    else:
                        title = href.rsplit("/", 1)[-1].replace(".pdf", "").replace("-", " ").replace("_", " ").title()
                else:
                    title = link_text

                if not title:
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
