import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class CnpqParser:
    def __init__(self, max_items: Optional[int] = 50):
        # O CNPq migrou do Liferay (memoria2.cnpq.br) para o portal gov.br.
        self.url = "https://www.gov.br/cnpq/pt-br/chamadas/abertas-para-submissao"
        self.institution = "CNPq"
        self.max_items = max_items

    async def _goto_with_retry(
        self, page, attempts: int = 4, base_delay: float = 3.0
    ) -> None:
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                await page.goto(self.url, timeout=45000, wait_until="domcontentloaded")
                await page.wait_for_selector("#content div.item", timeout=25000)
                return
            except Exception as exc:
                last_exc = exc
                if attempt < attempts:
                    sleep_time = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "CNPq navigation failed (attempt %s/%s): %s. Retrying in %.1fs",
                        attempt,
                        attempts,
                        exc,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
        raise RuntimeError(f"CNPq navigation failed after {attempts} attempts") from last_exc

    async def parse(self, db, max_items: Optional[int] = None) -> Dict[str, Any]:
        item_limit = self.max_items if max_items is None else max_items
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await self._goto_with_retry(page)

            items = await page.locator("#content div.item").all()

            inserted_count = 0
            duplicate_count = 0
            error_count = 0
            processed = 0

            iterable = items if item_limit is None else items[:item_limit]
            for item in iterable:
                try:
                    title_locator = item.locator("h2.headline a")
                    if await title_locator.count() == 0:
                        continue

                    title = (await title_locator.inner_text()).strip()
                    if not title:
                        continue

                    link = await title_locator.get_attribute("href")
                    if not link:
                        continue

                    text_content = (await item.inner_text()).strip()

                    # Data de publicação: "Publicado em DD/MM/AAAA HHhMM"
                    pub_date = ""
                    pub_loc = item.locator(".documentPublished .value")
                    if await pub_loc.count() > 0:
                        pub_raw = (await pub_loc.inner_text()).strip()
                        m = re.search(r"(\d{2}/\d{2}/\d{4})", pub_raw)
                        if m:
                            d = m.group(1)
                            pub_date = f"{d[6:]}-{d[3:5]}-{d[:2]}"

                    # Prazo: "Inscrições: DD/MM/AAAA a DD/MM/AAAA" (ou INSCRIÇÕES:)
                    deadline = ""
                    m_insc = re.search(
                        r"[Ii]nscri[çc][õo]es?:?\s*(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})",
                        text_content,
                    )
                    if m_insc:
                        deadline = m_insc.group(2)
                    else:
                        m_insc2 = re.search(
                            r"[Ii]nscri[çc][õo]es?:?\s*(\d{2}/\d{2}/\d{4})",
                            text_content,
                        )
                        if m_insc2:
                            deadline = m_insc2.group(1)

                    processed += 1
                    result = db.add_opportunity_with_result(
                        institution=self.institution,
                        title=title,
                        link=link,
                        description=text_content[:200].strip().replace("\n", " ") + "...",
                        pub_date=pub_date,
                        deadline=deadline,
                    )
                    if result == "inserted":
                        inserted_count += 1
                    else:
                        duplicate_count += 1
                except Exception as e:
                    error_count += 1
                    logger.exception("Error parsing CNPq item: %s", e)

            await browser.close()
            return {
                "institution": self.institution,
                "processed": processed,
                "new": inserted_count,
                "duplicates": duplicate_count,
                "errors": error_count,
            }


if __name__ == "__main__":
    from crawler.database import OpportunityDatabase

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    db = OpportunityDatabase(str(PROJECT_ROOT / "oportunidades.db"))
    parser = CnpqParser()
    result = asyncio.run(parser.parse(db))
    db.export_to_spreadsheet(
        str(PROJECT_ROOT / "editais.csv"), str(PROJECT_ROOT / "editais.xlsx")
    )
    logger.info("Done: %s", result)
