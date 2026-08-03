"""Utilitários HTTP compartilhados pelos parsers (httpx puro, sem navegador).

O portal gov.br aplica CAPTCHA/anti-bot intermitente ("human visitor").
`fetch_text` detecta o bloqueio e tenta novamente com backoff exponencial.
"""

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Marcadores de página de bloqueio/anti-bot
_BLOCK_MARKERS = (
    "human visitor",
    "what code is in the image",
    "acesso temporariamente interrompido",
    "captcha",
)


def is_blocked(text: str) -> bool:
    """True quando a resposta parece página de bloqueio (CAPTCHA/anti-bot)."""
    low = (text or "").lower()
    return any(m in low for m in _BLOCK_MARKERS)


async def fetch_text(
    client: httpx.AsyncClient,
    url: str,
    attempts: int = 4,
    base_delay: float = 3.0,
) -> str:
    """GET com retry/backoff e detecção de bloqueio.

    Lança RuntimeError após `attempts` tentativas.
    """
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = await client.get(url)
            r.raise_for_status()
            if is_blocked(r.text):
                raise RuntimeError("CAPTCHA/anti-bot detected")
            return r.text
        except Exception as exc:
            last_exc = exc
            if attempt < attempts:
                sleep_time = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "HTTP %s failed (attempt %s/%s): %s. Aguardando %.1fs",
                    url[:70],
                    attempt,
                    attempts,
                    exc,
                    sleep_time,
                )
                await asyncio.sleep(sleep_time)
    raise RuntimeError(f"HTTP failed after {attempts} attempts: {url[:70]}") from last_exc


def make_client(timeout: float = 45.0) -> httpx.AsyncClient:
    """AsyncClient com headers padrão (navegador)."""
    return httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        timeout=timeout,
        follow_redirects=True,
    )
