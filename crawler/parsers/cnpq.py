import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawler.http_utils import fetch_text, make_client


class CnpqParser:
    def __init__(self, max_items: int | None = 50):
        # O CNPq migrou do Liferay (memoria2.cnpq.br) para o portal gov.br.
        self.url = "https://www.gov.br/cnpq/pt-br/chamadas/abertas-para-submissao"
        self.institution = "CNPq"
        self.max_items = max_items

    async def parse(self, db, max_items: int | None = None) -> dict[str, Any]:
        item_limit = self.max_items if max_items is None else max_items

        inserted_count = 0
        duplicate_count = 0
        error_count = 0
        processed = 0

        async with make_client() as client:
            try:
                html = await fetch_text(client, self.url)
            except Exception as e:
                logger.exception("CNPq page fetch failed: %s", e)
                return {
                    "institution": self.institution,
                    "processed": 0,
                    "new": 0,
                    "duplicates": 0,
                    "errors": 1,
                }

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("#content div.item")

        iterable = items if item_limit is None else items[:item_limit]
        for item in iterable:
            try:
                title_el = item.select_one("h2.headline a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                link = title_el.get("href", "")
                if not title or not link:
                    continue

                text_content = item.get_text(" ", strip=True)

                # Data de publicação: "Publicado em DD/MM/AAAA HHhMM"
                pub_date = ""
                pub_el = item.select_one(".documentPublished .value")
                if pub_el:
                    m = re.search(r"(\d{2}/\d{2}/\d{4})", pub_el.get_text(strip=True))
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
    db.export_to_spreadsheet(str(PROJECT_ROOT / "editais.csv"), str(PROJECT_ROOT / "editais.xlsx"))
    logger.info("Done: %s", result)
