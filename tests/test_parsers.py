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

        with patch("crawler.parsers.cnpq.async_playwright") as mock_pw:
            mock_page = AsyncMock()
            mock_browser = AsyncMock()
            mock_pw.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page

            mock_item = MagicMock()
            title_loc = _make_item_locator(
                count=1,
                inner_text="Chamada CNPq nº 24/2026 - Teste",
                get_attribute=(
                    "https://www.gov.br/cnpq/pt-br/chamadas/todas-as-chamadas/"
                    "chamada-no-24-2026/chamada-publica-cnpq-N-24-2026"
                ),
            )
            pub_loc = _make_item_locator(count=1, inner_text="03/08/2026 10h55")

            def _loc_side_effect(sel):
                if sel == "h2.headline a":
                    return title_loc
                return pub_loc

            mock_item.locator = MagicMock(side_effect=_loc_side_effect)
            mock_item.inner_text = AsyncMock(
                return_value="Inscrições: 03/08/2026 a 18/09/2026"
            )

            mock_page.locator = MagicMock(return_value=_make_page_locator(
                [mock_item, mock_item]
            ))

            result = await parser.parse(mock_db)

        assert result["institution"] == "CNPq"
        assert result["processed"] == 2
        assert "new" in result
        assert "duplicates" in result
        assert "errors" in result


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
            mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock(status_code=404)
            ))
            mock_client_cls.return_value = mock_client

            result = await parser.parse(mock_db)

        assert result["institution"] == "CAPES"
        assert result["new"] == 0


# ---- ConfapParser tests ----
class TestConfapParser:
    @pytest.mark.asyncio
    async def test_parse_returns_expected_keys(self):
        from crawler.parsers.confap import ConfapParser

        parser = ConfapParser(max_items=5)
        mock_db = MagicMock()
        mock_db.add_opportunity_with_result.return_value = "inserted"

        with patch("crawler.parsers.confap.async_playwright") as mock_pw:
            mock_page = AsyncMock()
            mock_browser = AsyncMock()
            mock_pw.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page

            mock_link = MagicMock()
            mock_link.text_content = AsyncMock(
                return_value="FAPEMA abre edital para inovacao"
            )
            mock_link.get_attribute = AsyncMock(
                return_value="https://news.confap.org.br/fapema-edital-2026/"
            )

            mock_h2 = MagicMock()
            mock_h2.count = AsyncMock(return_value=1)
            mock_h2.text_content = AsyncMock(
                return_value="FAPEMA abre edital para inovacao"
            )
            mock_link.locator = MagicMock(return_value=mock_h2)

            mock_small = MagicMock()
            mock_small.count = AsyncMock(return_value=1)
            mock_small.text_content = AsyncMock(return_value="Em 12/06/2026")
            mock_h2.locator = MagicMock(return_value=mock_small)

            mock_page.locator = MagicMock(
                return_value=_make_page_locator([mock_link])
            )

            result = await parser.parse(mock_db)

        assert result["institution"] == "CONFAP"
        assert result["processed"] == 1

    @pytest.mark.asyncio
    async def test_goto_with_retry_raises_after_max_attempts(self):
        from crawler.parsers.confap import ConfapParser

        parser = ConfapParser()

        with patch("crawler.parsers.confap.async_playwright") as mock_pw:
            mock_page = AsyncMock()
            mock_browser = AsyncMock()
            mock_pw.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            mock_page.goto = AsyncMock(side_effect=RuntimeError("Connection refused"))

            with pytest.raises(RuntimeError, match="CONFAP navigation failed after 3 attempts"):
                await parser._goto_with_retry(mock_page)


# ---- BndesParser tests ----
class TestBndesParser:
    @pytest.mark.asyncio
    async def test_parse_returns_expected_keys(self):
        from crawler.parsers.bndes import BndesParser

        parser = BndesParser(max_items=5)
        mock_db = MagicMock()
        mock_db.add_opportunity_with_result.return_value = "inserted"

        with patch("crawler.parsers.bndes.async_playwright") as mock_pw:
            mock_page = AsyncMock()
            mock_page.url = "https://www.bndes.gov.br/wps/portal/site/home"
            mock_browser = AsyncMock()
            mock_pw.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page

            mock_card = MagicMock()
            h2_loc = _make_item_locator(count=1, inner_text="Edital de Cinema 2026")
            mock_card.locator = MagicMock(return_value=h2_loc)
            mock_card.get_attribute = AsyncMock(
                return_value=(
                    "?1dmy&urile=wcm:path:/bndes_institucional/home/transparencia/"
                    "patrocinios/selecao-publica-patrocinio-cultural-01-2026"
                )
            )
            mock_card.inner_text = AsyncMock(
                return_value="Edital de Cinema 2026 Inscrições até 13/08/2026"
            )

            mock_page.locator = MagicMock(
                return_value=_make_page_locator([mock_card])
            )

            result = await parser.parse(mock_db)

        assert result["institution"] == "BNDES"
        assert result["processed"] == 1
        assert result["new"] == 1


# ---- MctiParser tests ----
class TestMctiParser:
    @pytest.mark.asyncio
    async def test_parse_returns_expected_keys(self):
        from crawler.parsers.mcti import MctiParser

        parser = MctiParser(max_items=5)
        mock_db = MagicMock()
        mock_db.add_opportunity_with_result.return_value = "inserted"

        with patch("crawler.parsers.mcti.async_playwright") as mock_pw:
            mock_page = AsyncMock()
            mock_browser = AsyncMock()
            mock_browser.new_context = AsyncMock()
            mock_context = AsyncMock()
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_browser.new_context.return_value = mock_context
            mock_pw.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser

            mock_item = MagicMock()
            mock_item.inner_text = AsyncMock(
                return_value="EDITAL DE CHAMAMENTO PÚBLICO Nº 66/2024/SEI-MCTI"
            )
            mock_item.get_attribute = AsyncMock(
                return_value=(
                    "https://www.gov.br/mcti/pt-br/acesso-a-informacao/"
                    "editais/edital-no-66-2024-sei-mcti"
                )
            )

            mock_page.locator = MagicMock(return_value=_make_page_locator([mock_item]))

            result = await parser.parse(mock_db)

        assert result["institution"] == "MCTI"
        assert result["processed"] == 1


# ---- FapesbParser tests ----
class TestFapesbParser:
    @pytest.mark.asyncio
    async def test_parse_returns_expected_keys(self):
        from crawler.parsers.fapesb import FapesbParser

        parser = FapesbParser(max_items=5)
        mock_db = MagicMock()
        mock_db.add_opportunity_with_result.return_value = "inserted"

        with patch("crawler.parsers.fapesb.async_playwright") as mock_pw:
            mock_page = AsyncMock()
            mock_browser = AsyncMock()
            mock_pw.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page

            mock_item = MagicMock()
            mock_item.locator = MagicMock(return_value=_make_item_locator(
                count=1,
                inner_text="Test Edital FAPESB - ",
                get_attribute="https://example.com/edital",
            ))
            mock_item.inner_text = AsyncMock(
                return_value="Edital FAPESB description 15/07/2026"
            )

            mock_page.locator = MagicMock(return_value=_make_page_locator([mock_item]))

            result = await parser.parse(mock_db)

        assert result["institution"] == "FAPESB"
        assert result["processed"] == 1

    @pytest.mark.asyncio
    async def test_goto_with_retry_raises_after_max_attempts(self):
        from crawler.parsers.fapesb import FapesbParser

        parser = FapesbParser()

        with patch("crawler.parsers.fapesb.async_playwright") as mock_pw:
            mock_page = AsyncMock()
            mock_browser = AsyncMock()
            mock_pw.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            mock_page.goto = AsyncMock(side_effect=RuntimeError("Connection refused"))

            with pytest.raises(RuntimeError, match="FAPESB navigation failed after 3 attempts"):
                await parser._goto_with_retry(mock_page)


# ---- SetecParser tests ----
class TestSetecParser:
    @pytest.mark.asyncio
    async def test_parse_returns_expected_keys(self):
        from crawler.parsers.setec import SetecParser

        parser = SetecParser(max_items=5)
        mock_db = MagicMock()
        mock_db.add_opportunity_with_result.return_value = "inserted"

        with patch("crawler.parsers.setec.async_playwright") as mock_pw:
            mock_page = AsyncMock()
            mock_page.locator.return_value.all = AsyncMock(return_value=[])
            mock_page.close = AsyncMock()

            mock_browser = MagicMock()
            mock_browser.new_context = AsyncMock()
            mock_context = AsyncMock()
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_browser.new_context.return_value = mock_context
            mock_browser.close = AsyncMock()

            mock_pw_instance = MagicMock()
            mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw.return_value.__aenter__.return_value = mock_pw_instance

            with patch.object(parser, "_get_year_links", AsyncMock(return_value=[])):
                result = await parser.parse(mock_db)

        assert result["institution"] == "SETEC"
        assert "processed" in result

    @pytest.mark.asyncio
    async def test_goto_with_retry_raises_after_max_attempts(self):
        from crawler.parsers.setec import SetecParser

        parser = SetecParser()

        mock_page = AsyncMock()
        mock_page.goto.side_effect = RuntimeError("Connection refused")

        with pytest.raises(RuntimeError, match="SETEC navigation failed after 3 attempts"):
            await parser._goto_with_retry(
                mock_page, "https://example.com", attempts=3, base_delay=0.01
            )


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
        assert "confap" in s.source_names()
        assert "bndes" in s.source_names()
        assert "mcti" in s.source_names()
        assert len(s.source_names()) == 8

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
