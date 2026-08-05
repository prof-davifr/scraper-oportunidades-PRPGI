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
