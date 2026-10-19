from datetime import date

import pandas as pd
import pytest

from crawler.database import deadline_status

TODAY = date(2026, 10, 18)


@pytest.mark.parametrize(
    ("deadline", "expected"),
    [
        ("17/10/2026", "Encerrada"),
        ("18/10/2026", "Aberta"),
        ("14/01/2027", "Aberta"),
        ("2026-04-09", "Encerrada"),
        ("2026-12-01T18:00:00Z", "Aberta"),
        ("", "Sem prazo"),
        (None, "Sem prazo"),
        ("a definir", "Sem prazo"),
        ("31/02/2026", "Sem prazo"),
    ],
)
def test_deadline_status(deadline, expected):
    assert deadline_status(deadline, TODAY) == expected


def _seed(db):
    db.add_opportunity_with_result("FINEP", "Chamada vencida", "https://example.com/a", deadline="09/04/2026")
    db.add_opportunity_with_result("FINEP", "Chamada aberta", "https://example.com/b", deadline="14/01/2027")
    db.add_opportunity_with_result("CAPES", "Edital sem prazo", "https://example.com/c")


@pytest.mark.parametrize("consolidate", [True, False])
def test_spreadsheet_has_status_column(tmp_db, tmp_path, consolidate):
    _seed(tmp_db)
    csv_out, _ = tmp_db.export_to_spreadsheet(
        str(tmp_path / "e.csv"), str(tmp_path / "e.xlsx"), consolidate=consolidate, today=TODAY
    )
    df = pd.read_csv(csv_out, encoding="utf-8-sig")
    cols = list(df.columns)
    assert cols.index("Situação") == cols.index("Prazo") + 1
    status = dict(zip(df["Título"], df["Situação"], strict=True))
    assert status == {
        "Chamada vencida": "Encerrada",
        "Chamada aberta": "Aberta",
        "Edital sem prazo": "Sem prazo",
    }


@pytest.mark.parametrize("consolidate", [True, False])
def test_html_marks_expired_rows(tmp_db, tmp_path, consolidate):
    _seed(tmp_db)
    html_path = tmp_db.export_to_html(str(tmp_path / "e.html"), consolidate=consolidate, today=TODAY)
    html = (tmp_path / "e.html").read_text(encoding="utf-8")
    assert html_path == str(tmp_path / "e.html")
    assert html.count('data-status="encerrado"') == 1
    assert html.count('data-status="aberto"') == 2
    assert 'class="expired" data-status="encerrado"' in html
    assert "Incluir prazos encerrados (1)" in html
    assert '<option value="abertos" selected>' in html
