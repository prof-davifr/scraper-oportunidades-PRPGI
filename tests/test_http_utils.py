"""Testes para crawler/http_utils.py (fetch com retry e detecção de CAPTCHA)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from crawler.http_utils import fetch_text, is_blocked, make_client


def test_is_blocked_detects_captcha():
    assert is_blocked("This question is for testing whether you are a human visitor")
    assert is_blocked("Acesso Temporariamente Interrompido")
    assert is_blocked("What code is in the image? submit")
    assert not is_blocked("Editais abertos para submissão de propostas")


@pytest.mark.asyncio
async def test_fetch_text_ok():
    client = AsyncMock()
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.text = "<html>Editais</html>"
    client.get = AsyncMock(return_value=resp)

    text = await fetch_text(client, "https://exemplo.gov.br", attempts=2, base_delay=0.01)
    assert text == "<html>Editais</html>"
    client.get.assert_awaited_once_with("https://exemplo.gov.br")


@pytest.mark.asyncio
async def test_fetch_text_retries_on_captcha():
    client = AsyncMock()

    blocked = MagicMock()
    blocked.raise_for_status = MagicMock()
    blocked.text = "This question is for testing whether you are a human visitor"

    ok = MagicMock()
    ok.raise_for_status = MagicMock()
    ok.text = "<html>OK</html>"

    client.get = AsyncMock(side_effect=[blocked, ok])

    text = await fetch_text(client, "https://exemplo.gov.br", attempts=3, base_delay=0.01)
    assert text == "<html>OK</html>"
    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_fetch_text_raises_after_attempts():
    client = AsyncMock()
    resp = MagicMock()
    resp.raise_for_status = MagicMock(side_effect=httpx.ConnectError("timeout"))
    client.get = AsyncMock(return_value=resp)

    with pytest.raises(RuntimeError, match="after 2 attempts"):
        await fetch_text(client, "https://exemplo.gov.br", attempts=2, base_delay=0.01)


def test_make_client_headers():
    client = make_client()
    assert client.headers["User-Agent"].startswith("Mozilla/5.0")
    assert "pt-BR" in client.headers["Accept-Language"]
    # httpx permite fechar clientes sem loop (aclose usa o loop atual se houver)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(client.aclose())
        else:
            loop.run_until_complete(client.aclose())
    except RuntimeError:
        pass
