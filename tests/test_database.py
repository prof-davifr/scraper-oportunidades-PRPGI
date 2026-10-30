import sqlite3
import tempfile
from pathlib import Path

import pytest

from crawler.database import OpportunityDatabase


class TestOpportunityDatabase:
    @pytest.fixture
    def tmp_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            db = OpportunityDatabase(db_path)
            yield db

    def test_init_creates_table(self, tmp_db):
        with sqlite3.connect(tmp_db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='opportunities'")
            assert cursor.fetchone() is not None

    def test_add_opportunity_with_result_inserts(self, tmp_db):
        result = tmp_db.add_opportunity_with_result(
            institution="FINEP",
            title="Test Edital",
            link="https://example.com/edital-1",
            description="A test opportunity",
            deadline="31/12/2026",
        )
        assert result == "inserted"

    def test_add_opportunity_with_result_duplicates(self, tmp_db):
        tmp_db.add_opportunity_with_result(
            institution="FINEP",
            title="Test Edital",
            link="https://example.com/edital-1",
            description="A test opportunity",
            deadline="31/12/2026",
        )
        result = tmp_db.add_opportunity_with_result(
            institution="FINEP",
            title="Test Edital",
            link="https://example.com/edital-1",
            description="Duplicate attempt",
            deadline="01/01/2027",
        )
        assert result == "duplicate"

    def test_add_opportunity_returns_bool(self, tmp_db):
        assert (
            tmp_db.add_opportunity(
                institution="CNPq",
                title="Another Edital",
                link="https://example.com/edital-2",
            )
            is True
        )
        assert (
            tmp_db.add_opportunity(
                institution="CNPq",
                title="Another Edital",
                link="https://example.com/edital-2",
            )
            is False
        )

    def test_get_total_count(self, tmp_db):
        assert tmp_db.get_total_count() == 0
        tmp_db.add_opportunity_with_result(institution="FINEP", title="E1", link="https://example.com/e1")
        tmp_db.add_opportunity_with_result(institution="CNPq", title="E2", link="https://example.com/e2")
        assert tmp_db.get_total_count() == 2

    def test_get_count_by_institution(self, tmp_db):
        tmp_db.add_opportunity_with_result(institution="FINEP", title="E1", link="https://example.com/e1")
        tmp_db.add_opportunity_with_result(institution="CNPq", title="E2", link="https://example.com/e2")
        tmp_db.add_opportunity_with_result(institution="FINEP", title="E3", link="https://example.com/e3")
        assert tmp_db.get_count_by_institution("FINEP") == 2
        assert tmp_db.get_count_by_institution("CNPq") == 1
        assert tmp_db.get_count_by_institution("NONEXISTENT") == 0

    def test_get_totals_by_institution(self, tmp_db):
        tmp_db.add_opportunity_with_result(institution="FINEP", title="E1", link="https://example.com/e1")
        tmp_db.add_opportunity_with_result(institution="FINEP", title="E2", link="https://example.com/e2")
        tmp_db.add_opportunity_with_result(institution="CNPq", title="E3", link="https://example.com/e3")
        totals = tmp_db.get_totals_by_institution()
        assert totals["FINEP"] == 2
        assert totals["CNPq"] == 1

    def test_export_to_spreadsheet(self, tmp_db):
        import os

        tmpdir = Path(tempfile.mkdtemp())
        csv_path = str(tmpdir / "test.csv")
        xlsx_path = str(tmpdir / "test.xlsx")

        tmp_db.add_opportunity_with_result(
            institution="FINEP",
            title="Test Edital",
            link="https://example.com/edital-1",
            deadline="31/12/2026",
        )
        csv_out, xlsx_out = tmp_db.export_to_spreadsheet(csv_path, xlsx_path)

        assert os.path.exists(csv_out)
        assert os.path.exists(xlsx_out)

        with open(csv_out, encoding="utf-8-sig") as f:
            content = f.read()
            assert "Test Edital" in content

    def test_uid_is_deterministic(self, tmp_db):
        uid1 = tmp_db._generate_uid("Same Title", "https://example.com/link")
        uid2 = tmp_db._generate_uid("Same Title", "https://example.com/link")
        assert uid1 == uid2

    def test_uid_differs_for_different_inputs(self, tmp_db):
        uid1 = tmp_db._generate_uid("Title A", "https://example.com/link1")
        uid2 = tmp_db._generate_uid("Title B", "https://example.com/link1")
        uid3 = tmp_db._generate_uid("Title A", "https://example.com/link2")
        assert uid1 != uid2
        assert uid1 != uid3

    def test_delete_published_before_keeps_recent_and_undated(self, tmp_db):
        tmp_db.add_opportunity_with_result("FINEP", "Antiga", "https://example.com/a", pub_date="2015-10-13")
        tmp_db.add_opportunity_with_result("FINEP", "Recente", "https://example.com/b", pub_date="2025-01-02")
        tmp_db.add_opportunity_with_result("FINEP", "Sem data", "https://example.com/c")
        tmp_db.add_opportunity_with_result("CAPES", "Outra fonte", "https://example.com/d", pub_date="2020-01-01")

        removed = tmp_db.delete_published_before("FINEP", "2025-01-01")

        assert removed == 1
        with sqlite3.connect(tmp_db.db_path) as conn:
            titles = {t for (t,) in conn.execute("SELECT title FROM opportunities")}
        assert titles == {"Recente", "Sem data", "Outra fonte"}

    def test_page_url_fills_on_duplicate(self, tmp_db):
        pdf = "https://example.com/edital.pdf"
        tmp_db.add_opportunity_with_result("CAPES", "Edital nº 1/2026", pdf)
        tmp_db.add_opportunity_with_result("CAPES", "Edital nº 1/2026", pdf, page_url="https://example.com/programa")
        tmp_db.add_opportunity_with_result("CAPES", "Edital nº 1/2026", pdf, page_url="https://example.com/outra")

        rows = tmp_db._fetch_all_rows()
        assert [r["page_url"] for r in rows] == ["https://example.com/programa"]

    def test_init_adds_page_url_to_old_db(self, tmp_path):
        db_path = tmp_path / "old.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "CREATE TABLE opportunities (id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT UNIQUE, "
                "institution TEXT, title TEXT, description TEXT, link TEXT, publication_date TEXT, "
                "deadline TEXT, status TEXT, captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )

        db = OpportunityDatabase(str(db_path))
        db.add_opportunity_with_result(
            "SETEC", "Edital 1", "https://example.com/1.pdf", page_url="https://example.com/2026"
        )

        assert db._fetch_all_rows()[0]["page_url"] == "https://example.com/2026"

    def test_export_html_columns_and_page_icon(self, tmp_db, tmp_path):
        tmp_db.add_opportunity_with_result(
            "CAPES",
            "Edital nº 5/2026 - Programa X",
            "https://example.com/edital5.pdf",
            description="Descrição longa do edital",
            pub_date="2026-01-10",
            page_url="https://example.com/programa-x",
        )
        tmp_db.add_opportunity_with_result(
            "CAPES",
            "Resultado final do Edital nº 5/2026 - Programa X",
            "https://example.com/resultado5.pdf",
            pub_date="2026-03-10",
        )
        tmp_db.add_opportunity_with_result("CNPq", "Chamada nº 9/2026", "https://example.com/chamada-9")

        html = Path(tmp_db.export_to_html(str(tmp_path / "editais.html"))).read_text(encoding="utf-8")

        assert ">Descrição<" not in html
        assert "Descrição longa do edital" not in html
        assert "relacionado(s)" not in html
        assert '<summary title="Documentos relacionados">1</summary>' in html
        assert html.count('class="page-link" href="https://example.com/programa-x"') == 1
        # o link do CNPq já é a página: sem ícone
        assert html.count('class="page-link"') == 1
