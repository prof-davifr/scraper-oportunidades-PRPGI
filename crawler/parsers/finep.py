import asyncio
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FinepParser:
    # siteId do Liferay da FINEP, usado nas URLs públicas de chamada:
    # https://www.finep.gov.br/e/chamada-publica/{siteId}/{chamadaId}
    # Extraído da home quando possível; este é o valor atual (constante no template do site).
    _SITE_ID_FALLBACK = "222684"
    # A home expõe o template: href="/e/chamada-publica/{siteId}/${{item.id}}"
    _SITE_ID_RE = re.compile(r"/e/[a-z0-9-]+/(\d+)/\$\{item\.id\}")

    def __init__(self, max_items: int | None = 50):
        self.home_url = "https://www.finep.gov.br/"
        self.api_url = "https://www.finep.gov.br/o/c/chamadapublicas?sort=dataDePublicacao:desc&pageSize=250"
        self.institution = "FINEP"
        self.max_items = max_items

    async def _fetch_site_id(self, client) -> str:
        """Descobre o siteId do Liferay a partir da home (auto-recuperável)."""
        try:
            r = await client.get(self.home_url, timeout=30)
            text = r.text
            if isinstance(text, str):
                m = self._SITE_ID_RE.search(text)
                if m:
                    return m.group(1)
        except Exception:
            logger.exception("Falha ao extrair siteId da home FINEP")
        return self._SITE_ID_FALLBACK

    async def parse(self, db, max_items: int | None = None) -> dict[str, Any]:
        import httpx

        item_limit = self.max_items if max_items is None else max_items

        inserted_count = 0
        duplicate_count = 0
        error_count = 0

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                site_id = await self._fetch_site_id(client)
                response = await client.get(
                    self.api_url,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.exception("FINEP API request failed: %s", e)
            return {
                "institution": self.institution,
                "processed": 0,
                "new": 0,
                "duplicates": 0,
                "errors": 1,
            }

        items = data.get("items", [])
        open_items = [item for item in items if item.get("situacao", {}).get("key") == "aberta"]

        processed = 0
        for item in open_items:
            if item_limit is not None and processed >= item_limit:
                break
            try:
                title = item.get("titulo", "")
                if not title or not title.strip():
                    continue
                title = title.strip()

                chamada_id = item.get("id")
                link = f"https://www.finep.gov.br/e/chamada-publica/{site_id}/{chamada_id}"

                descricao = item.get("descricaoRawText") or item.get("descricao", "")
                descricao = re.sub(r"<[^>]+>", "", descricao)
                descricao = re.sub(r"\s+", " ", descricao).strip()

                pub_date = ""
                publicacao = item.get("dataDePublicacao") or item.get("dataPublicacao") or ""
                if publicacao:
                    try:
                        dt = datetime.fromisoformat(str(publicacao).replace("Z", "+00:00"))
                        pub_date = dt.strftime("%Y-%m-%d")
                    except ValueError:
                        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(publicacao))
                        if m:
                            pub_date = m.group(0)

                deadline = ""
                prazo = item.get("prazoProposto", "")
                if prazo:
                    try:
                        dt = datetime.fromisoformat(prazo.replace("Z", "+00:00"))
                        deadline = dt.strftime("%d/%m/%Y")
                    except ValueError:
                        pass

                result = db.add_opportunity_with_result(
                    institution=self.institution,
                    title=title,
                    link=link,
                    description=descricao[:200].strip().replace("\n", " ") + "...",
                    pub_date=pub_date,
                    deadline=deadline,
                )
                processed += 1
                if result == "inserted":
                    inserted_count += 1
                else:
                    duplicate_count += 1
            except Exception as e:
                error_count += 1
                logger.exception("Error parsing FINEP item: %s", e)

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
    parser = FinepParser()
    result = asyncio.run(parser.parse(db))
    db.export_to_spreadsheet(str(PROJECT_ROOT / "editais.csv"), str(PROJECT_ROOT / "editais.xlsx"))
    logger.info("Done: %s", result)
