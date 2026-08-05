import asyncio
import html
import logging
import re
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"

# Lista de editais: API REST do WordPress (categoria "Edital"), mais recentes
# primeiro. A data de publicação vem do campo `date` (estável — o HTML da
# página varia por cache/CDN e a listagem não preenche "LANÇAMENTO:").
_API_URL = "https://www.fapesb.ba.gov.br/wp-json/wp/v2/posts?categories=1&per_page=20&page=1&orderby=date&order=desc"

# Prazo real de inscrição, no corpo da página ou no texto do PDF do edital.
# O widget "⏰ Início/Encerramento" é template fixo (mesmas datas em todas as
# páginas) — NÃO usar. Padrões reais vistos:
#   "encerra-se em DD/MM/AAAA", "Após as 17h do dia DD/MM/AAAA",
#   "Prazo de submissão ... DD/MM/AAAA", "Inscrições até DD/MM/AAAA".
# O rodapé das páginas tem datas velhas (2022/2024) — filtro de ano >= 2025.
_DEADLINE_PATTERNS = (
    re.compile(r"encerra[-\s]?se\s+em\s+(\d{2}/\d{2}/\d{4})", re.I),
    re.compile(
        r"ap[óo]s as [\d:.h]+[^0-9]{0,25}?do dia (\d{2}/\d{2}/\d{4})",
        re.I,
    ),
    re.compile(r"prazo de submiss[ãa]o[^0-9]{0,90}?(\d{2}/\d{2}/\d{4})", re.I),
    re.compile(r"encerramento do prazo.{0,250}?(\d{2}/\d{2}/\d{4})", re.I),
    re.compile(
        r"(?:inscri[çc][õo]es|prazo)[^0-9]{0,90}?"
        r"(?:at[ée]|termina|encerra)[^0-9]{0,50}?(\d{2}/\d{2}/\d{4})",
        re.I,
    ),
)
_MIN_DEADLINE_YEAR = 2025

# PDFs que NÃO são o edital em si (erratas, retificações, resultados, anexos)
_PDF_SKIP = re.compile(r"errata|retific|resultad|anexo", re.I)


def _extract_deadline(text: str) -> str:
    """Procura a data-limite real no texto (HTML ou PDF), ou vazio."""
    if not text:
        return ""
    # normaliza quebras de linha (texto de PDF) para os padrões funcionarem
    text = re.sub(r"\s+", " ", text)
    for pat in _DEADLINE_PATTERNS:
        m = pat.search(text)
        if m and int(m.group(1)[-4:]) >= _MIN_DEADLINE_YEAR:
            return m.group(1)
    return ""


def _pdf_text(data: bytes) -> str:
    try:
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
        return "\n".join((pg.extract_text() or "") for pg in reader.pages[:15])
    except Exception:
        return ""


class FapesbParser:
    def __init__(self, max_items: int | None = 50):
        self.api_url = _API_URL
        self.institution = "FAPESB"
        self.max_items = max_items

    async def _fetch_deadline(self, client, link: str) -> str:
        """Prazo de inscrição: página do edital (best-effort) e, se preciso,
        texto do PDF do edital (cronograma)."""
        if not link or "fapesb.ba.gov.br" not in link:
            return ""
        try:
            r = await client.get(link, headers={"User-Agent": _UA})
            if r.status_code != 200:
                return ""
            # padrões validados em texto sem tags HTML
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))

            deadline = _extract_deadline(text)
            if deadline:
                return deadline

            # fallback: PDF do edital (cronograma com datas oficiais)
            pdf_urls = []
            for href in re.findall(r'href="([^"]+\.pdf[^"]*)"', r.text, re.I):
                if not href.startswith("http"):
                    from urllib.parse import urljoin

                    href = urljoin(link, href)
                if href not in pdf_urls and not _PDF_SKIP.search(href):
                    pdf_urls.append(href)
            if pdf_urls:
                pr = await client.get(pdf_urls[0], headers={"User-Agent": _UA}, timeout=60)
                if pr.status_code == 200 and pr.content[:5] == b"%PDF-":
                    return _extract_deadline(_pdf_text(pr.content))
        except Exception:
            logger.debug("Falha ao obter prazo FAPESB: %s", link)
        return ""

    async def parse(self, db, max_items: int | None = None) -> dict[str, Any]:
        import httpx

        item_limit = self.max_items if max_items is None else max_items

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                r = await client.get(self.api_url, headers={"User-Agent": _UA})
                r.raise_for_status()
                posts = r.json()

                inserted_count = 0
                duplicate_count = 0
                error_count = 0

                iterable = posts if item_limit is None else posts[:item_limit]
                for post in iterable:
                    try:
                        title = html.unescape(post.get("title", {}).get("rendered", "") or "")
                        title = re.sub(r"\s+", " ", title).strip().rstrip(" -–—")
                        if not title:
                            continue

                        link = post.get("link", "")
                        pub_date = (post.get("date") or "")[:10]

                        deadline = await self._fetch_deadline(client, link)

                        content = re.sub(
                            r"<[^>]+>",
                            " ",
                            post.get("content", {}).get("rendered", "") or "",
                        )
                        content = re.sub(r"\s+", " ", content).strip()

                        result = db.add_opportunity_with_result(
                            institution=self.institution,
                            title=title,
                            link=link,
                            description=content[:200] or title,
                            pub_date=pub_date,
                            deadline=deadline,
                        )
                        if result == "inserted":
                            inserted_count += 1
                        else:
                            duplicate_count += 1
                    except Exception as e:
                        error_count += 1
                        logger.exception("Error parsing FAPESB item: %s", e)

                return {
                    "institution": self.institution,
                    "processed": len(iterable),
                    "new": inserted_count,
                    "duplicates": duplicate_count,
                    "errors": error_count,
                }
        except Exception as e:
            logger.exception("FAPESB API request failed: %s", e)
            return {
                "institution": self.institution,
                "processed": 0,
                "new": 0,
                "duplicates": 0,
                "errors": 1,
            }


if __name__ == "__main__":
    from crawler.database import OpportunityDatabase

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    db = OpportunityDatabase(str(PROJECT_ROOT / "oportunidades.db"))
    parser = FapesbParser()
    result = asyncio.run(parser.parse(db))
    db.export_to_spreadsheet(str(PROJECT_ROOT / "editais.csv"), str(PROJECT_ROOT / "editais.xlsx"))
    logger.info("Done: %s", result)
