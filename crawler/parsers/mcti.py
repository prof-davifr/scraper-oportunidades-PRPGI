import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup

from crawler.http_utils import fetch_text, make_client

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class MctiParser:
    def __init__(self, max_items: Optional[int] = 50):
        self.url = "https://www.gov.br/mcti/pt-br/acesso-a-informacao/editais"
        self.institution = "MCTI"
        self.max_items = max_items

    async def parse(self, db, max_items: Optional[int] = None) -> Dict[str, Any]:
        item_limit = self.max_items if max_items is None else max_items

        inserted_count = 0
        duplicate_count = 0
        error_count = 0
        processed = 0

        async with make_client() as client:
            try:
                html = await fetch_text(client, self.url)
            except Exception as e:
                logger.exception("MCTI page fetch failed: %s", e)
                return {
                    "institution": self.institution,
                    "processed": 0,
                    "new": 0,
                    "duplicates": 0,
                    "errors": 1,
                }

        soup = BeautifulSoup(html, "html.parser")

        # Os editais do MCTI ficam no conteúdo principal e no submenu
        # "Editais" da navegação lateral — links .state-published com
        # "editais" no href (ou DOU via in.gov.br).
        items = soup.select("main a[href], ul.submenu.navTree a[href]")

        iterable = items if item_limit is None else items[:item_limit]
        seen_links = set()
        for a in iterable:
            try:
                title = a.get_text(" ", strip=True)
                link = a.get("href", "")
                if not title or not link:
                    continue

                # Mantém apenas links de editais/chamadas (ou DOU).
                if not re.search(
                    r"editais|edital|chamada|in\.gov\.br",
                    link + " " + title,
                    re.IGNORECASE,
                ):
                    continue

                if link in seen_links:
                    continue
                seen_links.add(link)

                if link.startswith("/"):
                    link = "https://www.gov.br" + link

                processed += 1

                deadline = ""
                deadline_match = re.search(r"(\d{2}/\d{2}/\d{4})", title)
                if deadline_match:
                    deadline = deadline_match.group(1)

                result = db.add_opportunity_with_result(
                    institution=self.institution,
                    title=title,
                    link=link,
                    description=title[:200].strip().replace("\n", " ") + "...",
                    deadline=deadline,
                )
                if result == "inserted":
                    inserted_count += 1
                else:
                    duplicate_count += 1
            except Exception as e:
                error_count += 1
                logger.exception("Error parsing MCTI item: %s", e)

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
    parser = MctiParser()
    result = asyncio.run(parser.parse(db))
    db.export_to_spreadsheet(
        str(PROJECT_ROOT / "editais.csv"), str(PROJECT_ROOT / "editais.xlsx")
    )
    logger.info("Done: %s", result)
