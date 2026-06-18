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


class ConfapParser:
    def __init__(self, max_items: Optional[int] = 50):
        self.url = "https://news.confap.org.br/tag/editais/"
        self.institution = "CONFAP"
        self.max_items = max_items

    async def _goto_with_retry(
        self, page, attempts: int = 3, base_delay: float = 1.0
    ) -> None:
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                await page.goto(self.url, timeout=30000, wait_until="domcontentloaded")
                return
            except Exception as exc:
                last_exc = exc
                if attempt < attempts:
                    sleep_time = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "CONFAP navigation failed (attempt %s/%s): %s. Retrying in %.1fs",
                        attempt,
                        attempts,
                        exc,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
        raise RuntimeError(f"CONFAP navigation failed after {attempts} attempts") from last_exc

    async def parse(self, db, max_items: Optional[int] = None) -> Dict[str, Any]:
        item_limit = self.max_items if max_items is None else max_items
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await self._goto_with_retry(page)

            await page.wait_for_load_state("networkidle")

            article_links = await page.locator(
                'a.d-flex.flex-wrap.p-3.p-md-4.text-white'
            ).all()

            inserted_count = 0
            duplicate_count = 0
            error_count = 0
            processed = 0

            for link in article_links:
                if item_limit is not None and processed >= item_limit:
                    break
                try:
                    href = await link.get_attribute("href")
                    if not href:
                        continue

                    title_el = link.locator("h2")
                    if await title_el.count() == 0:
                        continue
                    title = await title_el.text_content()
                    if not title or not title.strip():
                        continue
                    title = re.sub(r"\s+", " ", title).strip()

                    date_el = link.locator("small")
                    deadline = ""
                    if await date_el.count() > 0:
                        date_text = await date_el.text_content()
                        date_match = re.search(r"(\d{2}/\d{2}/\d{4})", date_text or "")
                        if date_match:
                            deadline = date_match.group(1)

                    result = db.add_opportunity_with_result(
                        institution=self.institution,
                        title=title,
                        link=href,
                        description=title,
                        deadline=deadline,
                    )
                    processed += 1
                    if result == "inserted":
                        inserted_count += 1
                    else:
                        duplicate_count += 1
                except Exception as e:
                    error_count += 1
                    logger.exception("Error parsing CONFAP item: %s", e)

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
    parser = ConfapParser()
    result = asyncio.run(parser.parse(db))
    db.export_to_spreadsheet(
        str(PROJECT_ROOT / "editais.csv"), str(PROJECT_ROOT / "editais.xlsx")
    )
    logger.info("Done: %s", result)
