import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


_MAIN_URL = "https://www.gov.br/capes/pt-br/assuntos/editais-e-resultados-capes"
_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"}

_ANNEX_KEYWORDS = {"anexo", "termo", "declara", "modelo", "comunicado", "portaria"}


def _is_main_edital(text: str) -> bool:
    low = text.lower()
    if "edital" not in low:
        return False
    for kw in _ANNEX_KEYWORDS:
        if kw in low:
            return False
    return True


def _extract_deadline(text: str) -> str:
    m = re.search(r"Prazo.*?(\d{2}/\d{2}/\d{4})", text)
    if m:
        return m.group(1)
    dates = re.findall(r"(\d{2}/\d{2}/\d{4})", text)
    if dates:
        return dates[-1]
    return ""


def _sanitize_pdf_url(raw: str) -> str:
    if not raw.startswith("http"):
        raw = "https://www.gov.br" + raw
    return raw.split("/view")[0]


class CapesParser:
    def __init__(self, max_items: Optional[int] = 100):
        self.institution = "CAPES"
        self.max_items = max_items

    async def parse(self, db, max_items: Optional[int] = None) -> Dict[str, Any]:
        item_limit = self.max_items if max_items is None else max_items

        inserted_count = 0
        duplicate_count = 0
        error_count = 0
        processed = 0

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            try:
                main_r = await client.get(_MAIN_URL, headers=_HEADERS)
                main_r.raise_for_status()
                main_soup = BeautifulSoup(main_r.text, "html.parser")
                program_urls = self._get_program_urls(main_soup)
                direct_editais = self._get_direct_editais(main_soup)
            except Exception as e:
                logger.exception("Failed to fetch CAPES main page: %s", e)
                error_count += 1
                program_urls = []
                direct_editais = []

            logger.info("Found %d CAPES program pages, %d direct editais", len(program_urls), len(direct_editais))

            # Insere editais listados diretamente na página principal
            for title, link, desc_text in direct_editais:
                if item_limit is not None and inserted_count >= item_limit:
                    break
                processed += 1
                try:
                    deadline = _extract_deadline(desc_text)
                    result = db.add_opportunity_with_result(
                        institution=self.institution,
                        title=title.strip(),
                        link=link,
                        description=desc_text[:500].strip(),
                        deadline=deadline,
                    )
                    if result == "inserted":
                        inserted_count += 1
                    else:
                        duplicate_count += 1
                except Exception as e:
                    error_count += 1
                    logger.exception("Error inserting CAPES edital: %s", e)

            sem = asyncio.Semaphore(5)

            async def visit(prog_name: str, prog_url: str):
                nonlocal inserted_count, duplicate_count, error_count, processed
                async with sem:
                    try:
                        editais = await self._scrape_program_page(client, prog_url)
                    except Exception as e:
                        logger.exception("Error scraping %s: %s", prog_name, e)
                        error_count += 1
                        return

                    for title, link, desc_text in editais:
                        if item_limit is not None and inserted_count >= item_limit:
                            break
                        processed += 1
                        try:
                            deadline = _extract_deadline(desc_text)
                            result = db.add_opportunity_with_result(
                                institution=self.institution,
                                title=title.strip(),
                                link=link,
                                description=desc_text[:500].strip(),
                                deadline=deadline,
                            )
                            if result == "inserted":
                                inserted_count += 1
                            else:
                                duplicate_count += 1
                        except Exception as e:
                            error_count += 1
                            logger.exception("Error inserting CAPES edital: %s", e)

                    if item_limit is not None and inserted_count >= item_limit:
                        return

            tasks = [visit(name, url) for name, url in program_urls]
            await asyncio.gather(*tasks)

        return {
            "institution": self.institution,
            "processed": processed,
            "new": inserted_count,
            "duplicates": duplicate_count,
            "errors": error_count,
        }

    def _get_program_urls(self, soup: BeautifulSoup):
        urls = []
        seen = set()
        # A página mudou: os links de programas não ficam mais em .tile-content;
        # agora são links diretos com "acoes-e-programas" no href.
        for a in soup.select('a[href*="acoes-e-programas"]'):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if not href or not text or href in seen:
                continue
            seen.add(href)
            full = href if href.startswith("http") else "https://www.gov.br" + href
            urls.append((text, full))
        return urls

    def _get_direct_editais(self, soup: BeautifulSoup):
        """Editais (PDFs) listados diretamente na página principal da CAPES."""
        results = []
        for a in soup.select('a[href*=".pdf"]'):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if not text or not _is_main_edital(text):
                continue
            link = _sanitize_pdf_url(href)
            parent_text = (a.parent.get_text(strip=True) if a.parent else "") or text
            results.append((text, link, parent_text))
        return results

    async def _scrape_program_page(self, client: httpx.AsyncClient, url: str):
        r = await client.get(url, headers=_HEADERS)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        results = []
        for a in soup.select("a[href*=\".pdf\"]"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if not text or not _is_main_edital(text):
                continue
            link = _sanitize_pdf_url(href)
            parent_text = (a.parent.get_text(strip=True) if a.parent else "") or text
            results.append((text, link, parent_text))

        return results


if __name__ == "__main__":
    from crawler.database import OpportunityDatabase

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    db = OpportunityDatabase(str(PROJECT_ROOT / "oportunidades.db"))
    parser = CapesParser(max_items=200)
    result = asyncio.run(parser.parse(db))
    db.export_to_spreadsheet(
        str(PROJECT_ROOT / "editais.csv"), str(PROJECT_ROOT / "editais.xlsx")
    )
    logger.info("Done: %s", result)
