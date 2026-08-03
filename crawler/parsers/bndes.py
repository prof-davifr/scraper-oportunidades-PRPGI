import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class BndesParser:
    def __init__(self, max_items: Optional[int] = 50):
        # O site foi reestruturado: a página antiga de chamadas públicas retorna
        # 404. Os editais/chamadas ativos são destacados na página inicial.
        self.url = "https://www.bndes.gov.br/"
        self.institution = "BNDES"
        self.max_items = max_items

    async def _goto_with_retry(
        self, page, attempts: int = 3, base_delay: float = 1.0
    ) -> None:
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                await page.goto(self.url, timeout=45000, wait_until="domcontentloaded")
                await page.wait_for_timeout(4000)
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

            # Cards de destaque da home que apontam para editais/chamadas/seleções.
            cards = await page.locator('a[href*="urile"]').all()

            inserted_count = 0
            duplicate_count = 0
            error_count = 0
            processed = 0

            for card in cards:
                if item_limit is not None and processed >= item_limit:
                    break
                try:
                    h2 = card.locator("figcaption h2")
                    if await h2.count() == 0:
                        continue
                    title = (await h2.inner_text()).strip()
                    if not title:
                        continue

                    href = await card.get_attribute("href")
                    if not href:
                        continue
                    link = urljoin(page.url, href)

                    # Filtra apenas conteúdos de edital/chamada/seleção
                    if not re.search(
                        r"edital|chamada|sele[çc][ãa]o", title + " " + link, re.IGNORECASE
                    ):
                        continue

                    text_content = await card.inner_text()
                    processed += 1

                    deadline = ""
                    deadline_match = re.search(r"(\d{2}/\d{2}/\d{4})", text_content)
                    if deadline_match:
                        deadline = deadline_match.group(1)

                    result = db.add_opportunity_with_result(
                        institution=self.institution,
                        title=title,
                        link=link,
                        description=text_content[:200].strip().replace("\n", " ") + "...",
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
    parser = BndesParser()
    result = asyncio.run(parser.parse(db))
    db.export_to_spreadsheet(
        str(PROJECT_ROOT / "editais.csv"), str(PROJECT_ROOT / "editais.xlsx")
    )
    logger.info("Done: %s", result)