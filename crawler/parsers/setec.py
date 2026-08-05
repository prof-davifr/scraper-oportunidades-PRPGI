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

# Palavras que identificam o título de um edital/chamada
_EDITAL_KEYWORDS = (
    "edital",
    "chamada",
    "chamamento",
    "seleção",
    "selecao",
    "termo de referência",
    "tr nº",
    "processo seletivo",
)


class SetecParser:
    def __init__(self, max_items: int | None = 200):
        self.base_url = "https://www.gov.br/mec/pt-br/acesso-a-informacao/institucional/estrutura-organizacional/orgaos-especificos-singulares/secretaria-de-educacao-profissional/editais"
        self.institution = "SETEC"
        self.max_items = max_items

    def _get_year_links(self, soup: BeautifulSoup) -> list[str]:
        # Links de ano ficam sob o caminho da secretaria (ex.: .../editais/2026)
        links = []
        seen = set()
        for a in soup.select('a[href*="/editais/202"], a[href*="/editais/anterior-a-2021"]'):
            href = a.get("href", "")
            if href and href not in seen:
                seen.add(href)
                links.append(href)
        return links

    @staticmethod
    def _extract_edital_blocks(soup: BeautifulSoup) -> list[dict]:
        """Extrai blocos de edital da página de ano.

        Cada edital é um <p> (título, às vezes com link do PDF embutido)
        seguido de uma <ul> com anexos/documentos. Retorna um dict por
        edital com título real e link principal (PDF do edital)."""
        container = soup.select_one("#parent-fieldname-text") or soup.select_one("#content")
        if not container:
            return []

        out: list[dict] = []
        for el in container.children:
            if not getattr(el, "name", None):
                continue
            if el.name == "p":
                current = {
                    "title": el.get_text(" ", strip=True),
                    "primaryLink": "",
                    "primaryText": "",
                    "links": [],
                }
                a = el.find("a", href=True)
                if a:
                    href = a["href"]
                    if re.search(r"\.pdf|/pdf/", href, re.I) or re.search(
                        r"edital|chamada|chamamento", a.get_text(" ", strip=True), re.I
                    ):
                        current["primaryLink"] = href
                        current["primaryText"] = a.get_text(" ", strip=True).strip()
                out.append(current)
            elif el.name == "ul" and out:
                for li in el.find_all("li"):
                    a = li.find("a", href=True)
                    if not a:
                        continue
                    out[-1]["links"].append({"text": li.get_text(" ", strip=True), "href": a["href"]})
        return out

    def _pick_edital(self, block: dict) -> dict | None:
        """Decide se o bloco é um edital e qual link usar."""
        title = self._clean_title(block.get("title", ""))
        if not title:
            return None
        low = title.lower()

        # Só considera blocos que parecem editais
        if not any(kw in low for kw in _EDITAL_KEYWORDS):
            return None
        # Título que começa com "Acesse/Clique" é link de documento, não edital
        if re.match(r"^(acesse|clique|baixe)\b", low):
            return None

        # Nomes de arquivo que indicam documento de apoio (não o edital)
        def _is_support_link(href: str) -> bool:
            fname = (href or "").lower().split("/")[-1]
            return any(
                kw in fname
                for kw in (
                    "retifica",
                    "anexo",
                    "_modelo",
                    "formulario",
                    "formulário",
                    "declaracao",
                    "termo",
                    "planodetrabalho",
                    "plano_de_trabalho",
                )
            )

        links = block.get("links", [])

        def _primary():
            link = block.get("primaryLink", "") or ""
            if link and not _is_support_link(link):
                return link
            # link "Edital"/"Chamada" na lista de anexos
            for item in links:
                t = item.get("text", "").lower()
                if re.match(r"^(edital|chamada|chamamento)", t):
                    return item["href"]
            # primeiro link PDF que não seja documento de apoio
            for item in links:
                h = item.get("href", "")
                if re.search(r"\.pdf", h, re.IGNORECASE) and not _is_support_link(h):
                    return h
            return ""

        link = _primary()
        if not link:
            return None

        return {"title": title, "link": link}

    @staticmethod
    def _clean_title(raw: str) -> str:
        """Normaliza e corta o título do edital, removendo texto de itens
        seguintes (anexos, resultados) concatenados via textContent."""
        title = re.sub(r"\s+", " ", raw or "").strip()
        if not title:
            return ""

        # 1) Remove duplicação "Edital nº X ... Edital nº X ...": mantém até a
        # 2ª ocorrência do marcador de edital (texto de blocos concatenados)
        marks = [
            mm.start()
            for mm in re.finditer(
                r"(?i)(?:edital\s+n[º°]?\s*\d+|chamada\s+p[úu]blica\s*n[º°]?\s*\d+|chamada\s+n[º°]?\s*\d+)",
                title,
            )
        ]
        if len(marks) >= 2:
            title = title[: marks[1]].strip()

        # 2) Corta em itens de lista concatenados: "Anexo X - ...",
        # "Resultado (Preliminar/Final/...) ..." (podem vir colados ao título)
        m = re.search(
            r"(?i)(?:anexo\s+[ivx\d]+\s*[-–]|resultado\s+(?:preliminar|final|parcial))",
            title,
        )
        if m and m.start() > 25:
            title = title[: m.start()].strip()

        # 3) Remove sufixos de navegação/a11y (pode ser repetido: "Acesse o Edital Acesse o")
        for _ in range(2):
            title = re.sub(
                r"(?i)\s*(?:acesse\s+o\s+edital\.?|acesse\s+o\s+documento\.?|acesse\s+o\.?|clique\s+aqui\.?|baixar\s+o\s+edital\.?)\s*$",
                "",
                title,
            ).strip()
            title = re.sub(r"(?i)\s*acesse\s+o\s*$", "", title).strip()
        title = re.sub(r"(?i)\s*accessibility-anchor\s*", "", title).strip()
        # remove separador residual antes de sufixo cortado ("- " solto)
        title = re.sub(r"\s*[-–]\s*$", "", title).strip()

        # Remove "Anexo I" / "Anexo II" residuais no fim
        title = re.sub(r"(?i)\s*[-–:]?\s*(?:anexo\s+[ivx\d]+)\s*$", "", title).strip()
        return title

    async def parse(self, db, max_items: int | None = None) -> dict[str, Any]:
        item_limit = self.max_items if max_items is None else max_items

        inserted_count = 0
        duplicate_count = 0
        error_count = 0
        processed = 0

        async with make_client() as client:
            try:
                html = await fetch_text(client, self.base_url)
            except Exception as e:
                logger.exception("SETEC main page fetch failed: %s", e)
                return {
                    "institution": self.institution,
                    "processed": 0,
                    "new": 0,
                    "duplicates": 0,
                    "errors": 1,
                }

            soup = BeautifulSoup(html, "html.parser")
            year_links = self._get_year_links(soup)
            logger.info("SETEC found %s year sub-pages", len(year_links))

            for year_url in year_links:
                if item_limit is not None and processed >= item_limit:
                    break
                try:
                    year_html = await fetch_text(client, year_url)
                except Exception as e:
                    error_count += 1
                    logger.warning("SETEC year page failed %s: %s", year_url, e)
                    continue

                year_soup = BeautifulSoup(year_html, "html.parser")
                for block in self._extract_edital_blocks(year_soup):
                    if item_limit is not None and processed >= item_limit:
                        break
                    edital = self._pick_edital(block)
                    if not edital:
                        continue
                    processed += 1
                    try:
                        result = db.add_opportunity_with_result(
                            institution=self.institution,
                            title=edital["title"],
                            link=edital["link"],
                            description=edital["title"],
                            deadline="",
                        )
                        if result == "inserted":
                            inserted_count += 1
                        else:
                            duplicate_count += 1
                    except Exception as e:
                        error_count += 1
                        logger.exception("Error parsing SETEC item: %s", e)

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
    parser = SetecParser()
    result = asyncio.run(parser.parse(db))
    db.export_to_spreadsheet(str(PROJECT_ROOT / "editais.csv"), str(PROJECT_ROOT / "editais.xlsx"))
    logger.info("Done: %s", result)
