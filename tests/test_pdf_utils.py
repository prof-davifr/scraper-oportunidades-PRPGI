from unittest.mock import AsyncMock, MagicMock

import pytest

from crawler.pdf_utils import (
    backfill_pdf_dates,
    fetch_pdf_creation_date,
    pdf_creation_date,
    pdf_download_candidates,
)

FAKE_PDF = b"%PDF-1.4\n1 0 obj << /CreationDate (D:20260409120000-03'00') >> endobj\n%%EOF"
CAPES_LINK = (
    "https://www.gov.br/capes/pt-br/centrais-de-conteudo/editais/Edital_2800035_SEI_2799041_Edital_9__de_2026.pdf"
)


def _response(status: int, content: bytes) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.content = content
    return r


def test_pdf_creation_date_regex_fallback():
    assert pdf_creation_date(FAKE_PDF) == "2026-04-09"
    assert pdf_creation_date(b"<!doctype html>") == ""


def test_download_candidates_govbr_uses_plone_download_first():
    assert pdf_download_candidates(CAPES_LINK) == [CAPES_LINK + "/@@download/file", CAPES_LINK]


def test_download_candidates_keeps_other_links():
    display = "https://www.gov.br/capes/pt-br/centrais-de-conteudo/editais/edital_2844920.pdf/@@display-file/file"
    assert pdf_download_candidates(display) == [display]
    assert pdf_download_candidates("https://example.com/edital.pdf") == ["https://example.com/edital.pdf"]
    assert pdf_download_candidates("") == []


@pytest.mark.asyncio
async def test_fetch_pdf_creation_date_falls_back_when_first_url_is_html():
    client = MagicMock()
    client.get = AsyncMock(side_effect=[_response(404, b'{"error"}'), _response(200, FAKE_PDF)])
    assert await fetch_pdf_creation_date(client, CAPES_LINK) == "2026-04-09"
    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_fetch_pdf_creation_date_rejects_html_and_future_dates():
    client = MagicMock()
    client.get = AsyncMock(return_value=_response(200, b"<!doctype html><html></html>"))
    assert await fetch_pdf_creation_date(client, CAPES_LINK) == ""

    future = b"%PDF-1.4 /CreationDate (D:20990101000000)"
    client.get = AsyncMock(return_value=_response(200, future))
    assert await fetch_pdf_creation_date(client, "https://example.com/x.pdf") == ""


@pytest.mark.asyncio
async def test_backfill_fills_only_undated_records(tmp_db):
    tmp_db.add_opportunity_with_result("CAPES", "Edital sem data", CAPES_LINK)
    tmp_db.add_opportunity_with_result("CAPES", "Edital com data", "https://example.com/b.pdf", pub_date="2025-03-01")
    tmp_db.add_opportunity_with_result("CAPES", "Link morto", "https://example.com/morto.pdf")
    tmp_db.add_opportunity_with_result("SETEC", "Outra fonte", "https://example.com/s.pdf")

    async def fake_get(url):
        if url.startswith(CAPES_LINK):
            return _response(200, FAKE_PDF)
        return _response(404, b"")

    client = MagicMock()
    client.get = AsyncMock(side_effect=fake_get)

    filled = await backfill_pdf_dates(client, tmp_db, "CAPES")

    assert filled == 1
    dates = {r["title"]: r["publication_date"] for r in tmp_db._fetch_all_rows()}
    assert dates == {
        "Edital sem data": "2026-04-09",
        "Edital com data": "2025-03-01",
        "Link morto": "",
        "Outra fonte": "",
    }


@pytest.mark.asyncio
async def test_backfill_respects_limit(tmp_db):
    for i in range(5):
        tmp_db.add_opportunity_with_result("SETEC", f"Edital {i}", f"https://example.com/{i}.pdf")
    client = MagicMock()
    client.get = AsyncMock(return_value=_response(200, FAKE_PDF))

    assert await backfill_pdf_dates(client, tmp_db, "SETEC", limit=2) == 2
    assert client.get.await_count == 2
