import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _make_page_locator(items: list) -> MagicMock:
    loc = MagicMock()
    loc.all = AsyncMock(return_value=items)
    return loc


def _make_item_locator(**kwargs) -> MagicMock:
    loc = MagicMock()
    for attr, value in kwargs.items():
        setattr(loc, attr, AsyncMock(return_value=value))
    return loc


# ---- FinepParser tests ----
class TestFinepParser:
    @pytest.mark.asyncio
    async def test_parse_returns_expected_keys(self):
        from crawler.parsers.finep import FinepParser

        parser = FinepParser(max_items=5)
        mock_db = MagicMock()
        mock_db.add_opportunity_with_result.return_value = "inserted"

        fake_response = {
            "items": [
                {
                    "titulo": "Chamada Teste 1",
                    "situacao": {"key": "aberta"},
                    "id": 123,
                    "descricaoRawText": "Descricao da chamada",
                    "prazoProposto": "2026-12-31T18:00:00Z",
                },
                {
                    "titulo": "Chamada Teste 2",
                    "situacao": {"key": "aberta"},
                    "id": 456,
                    "descricaoRawText": "Outra descricao",
                    "prazoProposto": "2026-11-30T18:00:00Z",
                },
                {
                    "titulo": "Chamada Fechada",
                    "situacao": {"key": "fechada"},
                    "id": 789,
                    "descricaoRawText": "Nao deve aparecer",
                },
            ]
        }

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=fake_response)
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await parser.parse(mock_db)

        assert result["institution"] == "FINEP"
        assert result["new"] == 2
        assert result["processed"] == 2
        assert result["errors"] == 0
        # links no formato atual: /e/chamada-publica/{siteId}/{id}
        calls = [c for c in mock_db.add_opportunity_with_result.call_args_list]
        links = [c.kwargs["link"] for c in calls]
        assert links == [
            "https://www.finep.gov.br/e/chamada-publica/222684/123",
            "https://www.finep.gov.br/e/chamada-publica/222684/456",
        ]
        assert "institution" in result
        assert "processed" in result
        assert "new" in result
        assert "duplicates" in result
        assert "errors" in result


# ---- CnpqParser tests ----
class TestCnpqParser:
    @pytest.mark.asyncio
    async def test_parse_returns_expected_keys(self):
        from crawler.parsers.cnpq import CnpqParser

        parser = CnpqParser(max_items=5)
        mock_db = MagicMock()
        mock_db.add_opportunity_with_result.return_value = "inserted"

        html = """<div id="content">
          <div class="item">
            <h2 class="headline"><a href="https://www.gov.br/cnpq/pt-br/chamadas/todas-as-chamadas/chamada-no-24-2026/chamada-publica-cnpq-N-24-2026">Chamada CNPq nº 24/2026 - Teste</a></h2>
            <div class="documentByLine"><span class="documentPublished"><span>Publicado em</span><span class="value">03/08/2026 10h55</span></span></div>
            <p>Inscrições: 03/08/2026 a 18/09/2026</p>
          </div>
          <div class="item">
            <h2 class="headline"><a href="https://www.gov.br/cnpq/pt-br/chamadas/todas-as-chamadas/chamada-no-25-2026/chamada-publica-cnpq-N-25-2026">Chamada CNPq/MCTI nº 25/2026 - Endometriose</a></h2>
            <div class="documentByLine"><span class="documentPublished"><span>Publicado em</span><span class="value">10/07/2026 14h37</span></span></div>
            <p>INSCRIÇÕES: 10/07/2026 a 15/09/2026</p>
          </div>
        </div>"""

        with patch("crawler.parsers.cnpq.make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock()
            mock_make.return_value.__exit__ = AsyncMock(return_value=False)
            with patch(
                "crawler.parsers.cnpq.fetch_text",
                new=AsyncMock(return_value=html),
            ):
                result = await parser.parse(mock_db)

        assert result["institution"] == "CNPq"
        assert result["processed"] == 2
        assert result["new"] == 2
        assert result["duplicates"] == 0
        assert result["errors"] == 0


# ---- CapesParser tests ----
class TestCapesParser:
    @pytest.mark.asyncio
    async def test_parse_returns_expected_keys(self):
        from crawler.parsers.capes import CapesParser

        parser = CapesParser(max_items=5)
        mock_db = MagicMock()
        mock_db.add_opportunity_with_result.return_value = "inserted"

        main_html = """
        <div class="tile-content">
            <a href="https://www.gov.br/capes/pt-br/acoes-e-programas/programa-teste">Programa Teste</a>
        </div>
        <div class="tile-content">
            <a href="https://www.gov.br/capes/pt-br/assuntos/resultados-2026">Resultados 2026</a>
        </div>
        """
        prog_html = """
        <div id="content-core">
            <a href="https://www.gov.br/capes/pt-br/centrais-de-conteudo/editais/Edital_123_EDITAL_1_2026.pdf">
                Edital nº 01/2026 - Programa Teste, formato, pdf, 200kb
            </a>
            <a href="https://www.gov.br/capes/pt-br/centrais-de-conteudo/editais/Edital_456_Anexo_I.pdf">
                Anexo I - não deve aparecer
            </a>
            <a href="https://www.gov.br/capes/pt-br/centrais-de-conteudo/editais/Edital_789_EDITAL_2_2026.pdf">
                Edital nº 02/2026 - Outro Programa, formato, pdf, 150kb
            </a>
        </div>
        """

        def mock_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "acoes-e-programas" in url:
                resp.text = prog_html
            else:
                resp.text = main_html
            return resp

        with patch("crawler.parsers.capes.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(side_effect=mock_get)
            mock_client_cls.return_value = mock_client

            result = await parser.parse(mock_db)

        assert result["institution"] == "CAPES"
        assert result["processed"] == 2
        assert result["new"] == 2
        assert "institution" in result
        assert "processed" in result
        assert "new" in result
        assert "duplicates" in result
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_parse_handles_main_page_error(self):
        from crawler.parsers.capes import CapesParser

        parser = CapesParser()
        mock_db = MagicMock()

        with patch("crawler.parsers.capes.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock(status_code=404))
            )
            mock_client_cls.return_value = mock_client

            result = await parser.parse(mock_db)

        assert result["institution"] == "CAPES"
        assert result["new"] == 0


# ---- FapesbParser tests ----
class TestFapesbParser:
    @pytest.mark.asyncio
    async def test_parse_returns_expected_keys(self):
        from crawler.parsers.fapesb import FapesbParser

        parser = FapesbParser(max_items=5)
        mock_db = MagicMock()
        mock_db.add_opportunity_with_result.return_value = "inserted"

        fake_posts = [
            {
                "title": {"rendered": "EDITAL TESTE 01/2026 - "},
                "link": "https://www.fapesb.ba.gov.br/edital-teste-01-2026/",
                "date": "2026-07-20T16:52:26",
                "content": {"rendered": "<p>Descricao do edital</p>"},
            },
            {
                "title": {"rendered": "CHAMADA TESTE 2026"},
                "link": "https://www.fapesb.ba.gov.br/chamada-teste/",
                "date": "2026-07-15T10:00:00",
                "content": {"rendered": ""},
            },
        ]

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=fake_posts)
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await parser.parse(mock_db)

        assert result["institution"] == "FAPESB"
        assert result["processed"] == 2
        assert result["errors"] == 0
        # título sem o "-" residual e data de publicação da API
        calls = [c for c in mock_db.add_opportunity_with_result.call_args_list]
        assert calls[0].kwargs["title"] == "EDITAL TESTE 01/2026"
        assert calls[0].kwargs["pub_date"] == "2026-07-20"
        assert calls[1].kwargs["pub_date"] == "2026-07-15"

    @pytest.mark.asyncio
    async def test_parse_handles_api_error(self):
        from crawler.parsers.fapesb import FapesbParser

        parser = FapesbParser()
        mock_db = MagicMock()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(side_effect=RuntimeError("boom"))

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await parser.parse(mock_db)

        assert result["institution"] == "FAPESB"
        assert result["errors"] == 1
        assert result["processed"] == 0


# ---- SetecParser tests ----
class TestSetecParser:
    @pytest.mark.asyncio
    async def test_parse_returns_expected_keys(self):
        from crawler.parsers.setec import SetecParser

        parser = SetecParser(max_items=5)
        mock_db = MagicMock()
        mock_db.add_opportunity_with_result.return_value = "inserted"

        html = """<html><body><div id="content">
          <a href="https://www.gov.br/mec/pt-br/acesso-a-informacao/institucional/estrutura-organizacional/orgaos-especificos-singulares/secretaria-de-educacao-profissional/editais/2026">2026</a>
          <a href="https://www.gov.br/mec/pt-br/acesso-a-informacao/institucional/estrutura-organizacional/orgaos-especificos-singulares/secretaria-de-educacao-profissional/editais/2025">2025</a>
        </div></body></html>"""
        year_html = """<html><body><div id="content"><div id="parent-fieldname-text">
          <p><a href="https://www.gov.br/mec/pt-br/.../editais/2026/sei_7012727_edital_5.pdf">Edital nº 5 /2026</a> - Seleção de propostas de projetos de extensão</p>
          <ul>
            <li>Anexo I - <a href="https://www.gov.br/mec/pt-br/.../sei_7012732_documento.pdf">Termo de autorização</a></li>
            <li><a href="https://www.gov.br/mec/pt-br/.../SEI_7062666_Retificacao_.pdf">Retificação de edital</a></li>
          </ul>
          <p><a href="https://www.gov.br/mec/pt-br/.../editais/2026/SEI_6991254_chamada.pdf">Chamada (documento Nº 6991254)</a> para seleção de unidades da Rede Federal</p>
        </div></div></body></html>"""

        with patch("crawler.parsers.setec.make_client") as mock_make:
            mock_make.return_value.__aenter__ = AsyncMock()
            mock_make.return_value.__exit__ = AsyncMock(return_value=False)
            with patch(
                "crawler.parsers.setec.fetch_text",
                new=AsyncMock(side_effect=[html, year_html]),
            ):
                result = await parser.parse(mock_db)

        assert result["institution"] == "SETEC"
        assert result["processed"] == 2
        assert result["new"] == 2


# ---- Config / Settings tests ----
class TestConfig:
    def test_settings_defaults(self):
        from crawler.config import Settings

        s = Settings()
        assert "finep" in s.source_names()
        assert "cnpq" in s.source_names()
        assert "capes" in s.source_names()
        assert "fapesb" in s.source_names()
        assert "setec" in s.source_names()
        assert len(s.source_names()) == 5

    def test_get_source_find(self):
        from crawler.config import Settings

        s = Settings()
        src = s.get_source("finep")
        assert src.name == "finep"
        assert src.module == "crawler.parsers.finep"
        assert src.class_name == "FinepParser"

    def test_get_source_missing_raises(self):
        from crawler.config import Settings

        s = Settings()
        with pytest.raises(KeyError, match="Unknown source"):
            s.get_source("nonexistent")

    def test_build_parser_creates_instance(self):
        from crawler.config import Settings

        s = Settings()
        parser = s.build_parser("finep", max_items=10)
        assert parser.institution == "FINEP"
        assert parser.max_items == 10

    def test_load_parser_class_returns_correct_class(self):
        from crawler.config import Settings

        s = Settings()
        source = s.get_source("cnpq")
        cls = s.load_parser_class(source)
        assert cls.__name__ == "CnpqParser"
