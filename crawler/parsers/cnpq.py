import asyncio
import logging
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

class CnpqParser:
    def __init__(self, max_items: Optional[int] = 50):
        self.url = "http://memoria2.cnpq.br/web/guest/chamadas-publicas"
        self.institution = "CNPq"
        self.max_items = max_items

    async def _goto_with_retry(
        self, page, attempts: int = 3, base_delay: float = 1.0
    ) -> None:
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                await page.goto(self.url, timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_selector("ol.list-chamadas li", timeout=20000)
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

            items = await page.locator("ol.list-chamadas > li").all()

            inserted_count = 0
            duplicate_count = 0
            error_count = 0

            iterable = items if item_limit is None else items[:item_limit]
            for item in iterable:
                try:
                    title_locator = item.locator("h4")
                    if await title_locator.count() == 0:
                        continue

                    title = await title_locator.inner_text()
                    if not title.strip():
                        continue

                    text_content = await item.inner_text()

                    # Link: a página de detalhe é construída com o idDivulgacao
                    # presente nos links de compartilhamento (a.facebook).
                    link = ""
                    share_url = await item.locator('a.facebook').first.get_attribute("href")
                    m = re.search(r"idDivulgacao=(\d+)", urllib.parse.unquote(share_url or ""))
                    if m:
                        divulgacao_id = m.group(1)
                        link = (
                            "http://memoria2.cnpq.br/web/guest/chamadas-publicas?"
                            "p_p_id=resultadosportlet_WAR_resultadoscnpqportlet_INSTANCE_0ZaM"
                            "&filtro=abertas&detalha=chamadaDivulgada"
                            f"&idDivulgacao={divulgacao_id}"
                        )

                    if not link:
                        continue

                    deadline = ""
                    if "Inscrições:" in text_content or "Inscri\u00e7\u00f5es:" in text_content:
                        dates = re.findall(r"(\d{2}/\d{2}/\d{4})", text_content)
                        if len(dates) >= 2:
                            deadline = dates[1]
                        elif len(dates) == 1:
                            deadline = dates[0]

                    result = db.add_opportunity_with_result(
                        institution=self.institution,
                        title=title.strip(),
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
                    logger.exception("Error parsing CNPq item: %s", e)

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
    parser = CnpqParser()
    result = asyncio.run(parser.parse(db))
    db.export_to_spreadsheet(
        str(PROJECT_ROOT / "editais.csv"), str(PROJECT_ROOT / "editais.xlsx")
    )
    logger.info("Done: %s", result)
