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


class BndesParser:
    def __init__(self, max_items: Optional[int] = 50):
        self.url = "https://www.bndes.gov.br/wps/portal/site/home/onde-atuamos/inovacao/chamadas-publicas"
        self.institution = "BNDES"
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
                        "BNDES navigation failed (attempt %s/%s): %s. Retrying in %.1fs",
                        attempt,
                        attempts,
                        exc,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
        raise RuntimeError(f"BNDES navigation failed after {attempts} attempts") from last_exc

    async def parse(self, db, max_items: Optional[int] = None) -> Dict[str, Any]:
        item_limit = self.max_items if max_items is None else max_items
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await self._goto_with_retry(page)

            items = await page.locator(".item").all()
            if not items:
                items = await page.locator("li").all()

            inserted_count = 0
            duplicate_count = 0
            error_count = 0

            iterable = items if item_limit is None else items[:item_limit]
            for item in iterable:
                try:
                    title_locator = item.locator("a")
                    if await title_locator.count() == 0:
                        title_locator = item.locator("h3 a")
                    if await title_locator.count() == 0:
                        continue

                    title = await title_locator.inner_text()
                    if not title.strip():
                        continue

                    link = await title_locator.get_attribute("href")
                    if link and not link.startswith("http"):
                        link = f"https://www.bndes.gov.br{link}"

                    desc_text = await item.inner_text()

                    deadline = ""
                    deadline_match = re.search(r"(\d{2}/\d{2}/\d{4})", desc_text)
                    if deadline_match:
                        deadline = deadline_match.group(1)

                    result = db.add_opportunity_with_result(
                        institution=self.institution,
                        title=title.strip(),
                        link=link,
                        description=desc_text[:200].strip().replace("\n", " ") + "...",
                        deadline=deadline,
                    )
                    if result == "inserted":
                        inserted_count += 1
                    else:
                        duplicate_count += 1
                except Exception as e:
                    error_count += 1
                    logger.exception("Error parsing BNDES item: %s", e)

            await browser.close()
            return {
                "institution": self.institution,
                "processed": len(iterable),
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
    parser = BndesParser()
    result = asyncio.run(parser.parse(db))
    db.export_to_spreadsheet(
        str(PROJECT_ROOT / "editais.csv"), str(PROJECT_ROOT / "editais.xlsx")
    )
    logger.info("Done: %s", result)