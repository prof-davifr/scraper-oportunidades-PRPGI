"""Utilitários de PDF: extração de metadados (data de criação)."""

import asyncio
import logging
import re
from datetime import date

logger = logging.getLogger(__name__)


def pdf_creation_date(data: bytes) -> str:
    """Data de criação do PDF (ISO YYYY-MM-DD) via metadados.

    Usada como aproximação da data de publicação do edital quando o portal
    não expõe a data (gov.br/SETEC, FAPESB). pypdf primeiro; fallback por
    regex nos bytes brutos do /CreationDate.
    """
    try:
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
        cd = getattr(reader.metadata, "creation_date", None)
        if cd:
            m = re.match(r"(\d{4}-\d{2}-\d{2})", str(cd))
            if m:
                return m.group(1)
    except Exception:  # noqa: S110 — metadados ausentes/corrompidos; cai no fallback regex abaixo
        pass
    m = re.search(rb"/CreationDate\s*\(D:(\d{4})(\d{2})(\d{2})", data)
    if m:
        return f"{m.group(1).decode()}-{m.group(2).decode()}-{m.group(3).decode()}"
    return ""


# gov.br (Plone) responde com a página HTML de visualização quando se pede o
# endereço "cru" do PDF; o arquivo em si sai pelo sufixo /@@download/file.
_PLONE_DOWNLOAD_SUFFIX = "/@@download/file"
# Teto de downloads de PDF por fonte em cada rodada, para o crawl diário não
# crescer sem limite enquanto houver registros sem data.
MAX_PDF_LOOKUPS = 120
_PDF_CONCURRENCY = 5


def pdf_download_candidates(link: str) -> list[str]:
    """Endereços a tentar para baixar o PDF de um link (no gov.br, /@@download/file primeiro)."""
    link = (link or "").strip()
    if not link:
        return []
    if "gov.br/" in link and "@@" not in link and re.search(r"\.pdf/?$", link, re.IGNORECASE):
        return [link.rstrip("/") + _PLONE_DOWNLOAD_SUFFIX, link]
    return [link]


def _plausible(iso: str, today: date | None = None) -> bool:
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return False
    return date(2000, 1, 1) <= d <= (today or date.today())


async def fetch_pdf_creation_date(client, link: str) -> str:
    """Baixa o PDF do link e devolve a data de criação (ISO), ou "" quando não dá."""
    for url in pdf_download_candidates(link):
        try:
            r = await client.get(url)
        except Exception as exc:
            logger.debug("PDF %s falhou: %s", url[:80], exc)
            continue
        if r.status_code != 200 or not r.content.startswith(b"%PDF"):
            continue
        iso = pdf_creation_date(r.content)
        if iso and _plausible(iso):
            return iso
    return ""


async def backfill_pdf_dates(client, db, institution: str, limit: int = MAX_PDF_LOOKUPS) -> int:
    """Preenche a data de publicação dos registros sem data com a data de criação do PDF.

    Aproximação: o portal não expõe a data, mas o PDF gerado pelo SEI traz a
    data de criação nos metadados. Devolve quantos registros ganharam data.
    """
    rows = list(db.get_undated(institution, limit))
    if not rows:
        return 0
    sem = asyncio.Semaphore(_PDF_CONCURRENCY)

    async def one(row_id: int, link: str) -> int:
        async with sem:
            iso = await fetch_pdf_creation_date(client, link)
        if iso and db.set_publication_date_if_empty(row_id, iso):
            return 1
        return 0

    filled = sum(await asyncio.gather(*(one(row_id, link) for row_id, link in rows)))
    logger.info("%s: %s/%s registros sem data receberam a data do PDF", institution, filled, len(rows))
    return filled
