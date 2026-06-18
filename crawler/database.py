import hashlib
import sqlite3
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

import pandas as pd

AddResult = Literal["inserted", "duplicate"]


class OpportunityDatabase:
    """Persistence layer for scraped funding opportunities."""

    def __init__(self, db_path: str = "oportunidades.db") -> None:
        """Initialize database connection target and schema.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = str(Path(db_path))
        self._init_db()

    def _init_db(self) -> None:
        """Create required tables if they do not exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE,
                    institution TEXT,
                    title TEXT,
                    description TEXT,
                    link TEXT,
                    publication_date TEXT,
                    deadline TEXT,
                    status TEXT,
                    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def _generate_uid(self, title: str, link: str) -> str:
        """Generate deterministic unique key from title+link."""
        return hashlib.sha256(f"{title}{link}".encode("utf-8")).hexdigest()

    def add_opportunity_with_result(
        self,
        institution: str,
        title: str,
        link: str,
        description: str = "",
        pub_date: str = "",
        deadline: str = "",
        status: str = "Aberta",
    ) -> AddResult:
        """Insert an opportunity and return insertion status.

        Returns:
            "inserted" when a new record is added.
            "duplicate" when a record with same uid already exists.
        """
        uid = self._generate_uid(title, link)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO opportunities (uid, institution, title, link, description, publication_date, deadline, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (uid, institution, title, link, description, pub_date, deadline, status),
                )
                conn.commit()
            return "inserted"
        except sqlite3.IntegrityError:
            return "duplicate"

    def add_opportunity(
        self,
        institution: str,
        title: str,
        link: str,
        description: str = "",
        pub_date: str = "",
        deadline: str = "",
        status: str = "Aberta",
    ) -> bool:
        """Backward-compatible insert API.

        Returns:
            True when inserted, False when duplicate.
        """
        result = self.add_opportunity_with_result(
            institution=institution,
            title=title,
            link=link,
            description=description,
            pub_date=pub_date,
            deadline=deadline,
            status=status,
        )
        return result == "inserted"

    def export_to_spreadsheet(
        self, csv_path: str = "editais.csv", xlsx_path: str = "editais.xlsx"
    ) -> Tuple[str, str]:
        """Export all opportunities to CSV and Excel.

        CSV is written as UTF-8 with BOM for Excel compatibility.
        Export ordering is deterministic (institution/title/link/id).
        """
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                """
                SELECT
                    institution as Instituição,
                    title as Título,
                    deadline as Prazo,
                    link as Link,
                    description as Descrição
                FROM opportunities
                ORDER BY institution ASC, title ASC, link ASC, id ASC
                """,
                conn,
            )

        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        df.to_excel(xlsx_path, index=False)
        return csv_path, xlsx_path

    def export_to_html(self, html_path: str = "editais.html") -> str:
        """Export all opportunities to a standalone HTML page."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT institution, title, deadline, link, description
                FROM opportunities
                ORDER BY institution ASC, title ASC, link ASC, id ASC
            """)
            rows = cursor.fetchall()

        totals = self.get_totals_by_institution()
        total_count = sum(totals.values())

        rows_html = ""
        for inst, title, deadline, link, desc in rows:
            safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            safe_desc = (desc or "")[:300].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            safe_deadline = deadline or "—"
            rows_html += f"""<tr>
                <td class="inst">{inst}</td>
                <td class="title"><a href="{link}" target="_blank" rel="noopener">{safe_title}</a></td>
                <td class="deadline">{safe_deadline}</td>
                <td class="desc">{safe_desc}</td>
            </tr>
"""

        inst_badges = "".join(
            f'<span class="badge badge-{k.lower()}">{k} ({v})</span>'
            for k, v in sorted(totals.items())
        )

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Editais — PRPGI</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: #f5f5f5; color: #222; line-height: 1.5; padding: 1rem;
  }}
  .container {{ max-width: 1280px; margin: 0 auto; }}
  header {{ background: linear-gradient(135deg, #165c33, #00853f); color: #fff; padding: 1.5rem 2rem; border-radius: 10px; margin-bottom: 1.5rem; }}
  header h1 {{ font-size: 1.5rem; font-weight: 700; margin-bottom: .25rem; }}
  header p {{ opacity: .85; font-size: .9rem; }}
  .stats {{ display: flex; flex-wrap: wrap; gap: .5rem; margin-bottom: 1.25rem; }}
  .badge {{ display: inline-block; padding: .35em .75em; border-radius: 20px; font-size: .8rem; font-weight: 600; background: #e0e0e0; color: #333; }}
  .badge-total {{ background: #165c33; color: #fff; }}
  .filter-bar {{ margin-bottom: 1rem; display: flex; gap: .5rem; flex-wrap: wrap; }}
  .filter-bar input, .filter-bar select {{
    padding: .5rem .75rem; border: 1px solid #ccc; border-radius: 6px; font-size: .9rem;
    background: #fff; flex: 1; min-width: 180px;
  }}
  .table-wrap {{ overflow-x: auto; background: #fff; border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  table {{ width: 100%; border-collapse: collapse; font-size: .875rem; }}
  th {{ background: #f0f0f0; text-align: left; padding: .75rem .5rem; font-weight: 600; white-space: nowrap; cursor: pointer; user-select: none; position: relative; }}
  th:hover {{ background: #e4e4e4; }}
  th::after {{ content: " \\25B4\\25BE"; font-size: .6rem; opacity: .3; }}
  th.sort-asc::after {{ opacity: 1; content: " \\25B4"; }}
  th.sort-desc::after {{ opacity: 1; content: " \\25BE"; }}
  td {{ padding: .6rem .5rem; border-top: 1px solid #eee; vertical-align: top; }}
  tr:hover td {{ background: #fafafa; }}
  .inst {{ font-weight: 600; white-space: nowrap; color: #165c33; }}
  .title a {{ color: #1a73e8; text-decoration: none; }}
  .title a:hover {{ text-decoration: underline; }}
  .deadline {{ white-space: nowrap; color: #666; }}
  .desc {{ color: #555; max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .empty {{ text-align: center; padding: 3rem 1rem; color: #888; }}
  @media (max-width: 640px) {{
    header {{ padding: 1rem; }}
    .desc {{ max-width: 140px; }}
    td, th {{ padding: .4rem .3rem; font-size: .8rem; }}
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Editais de Pesquisa e Inovação</h1>
    <p>Oportunidades coletadas automaticamente — PRPGI / IFBA</p>
  </header>
  <div class="stats">
    <span class="badge badge-total">Total: {total_count}</span>
    {inst_badges}
  </div>
  <div class="filter-bar">
    <input type="text" id="filterTitle" placeholder="Buscar por título..." oninput="filterTable()">
    <select id="filterInst" onchange="filterTable()">
      <option value="">Todas as instituições</option>
      {''.join(f'<option value="{k}">{k}</option>' for k in sorted(totals))}
    </select>
  </div>
  <div class="table-wrap">
    <table id="oppTable">
      <thead>
        <tr>
          <th onclick="sortTable(0)">Instituição</th>
          <th onclick="sortTable(1)">Título</th>
          <th onclick="sortTable(2)">Prazo</th>
          <th onclick="sortTable(3)">Descrição</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>
<script>
function filterTable() {{
  const q = document.getElementById('filterTitle').value.toLowerCase();
  const inst = document.getElementById('filterInst').value;
  document.querySelectorAll('#oppTable tbody tr').forEach(r => {{
    const title = r.children[1].textContent.toLowerCase();
    const rowInst = r.children[0].textContent;
    const matchTitle = !q || title.includes(q);
    const matchInst = !inst || rowInst === inst;
    r.style.display = matchTitle && matchInst ? '' : 'none';
  }});
}}
let sortDir = [1,1,1,1];
function sortTable(col) {{
  const tbody = document.querySelector('#oppTable tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  sortDir[col] *= -1;
  const dir = sortDir[col];
  rows.sort((a, b) => {{
    const va = a.children[col].textContent.trim().toLowerCase();
    const vb = b.children[col].textContent.trim().toLowerCase();
    return va.localeCompare(vb, 'pt-BR') * dir;
  }});
  rows.forEach(r => tbody.appendChild(r));
  document.querySelectorAll('#oppTable th').forEach((th, i) => {{
    th.classList.remove('sort-asc', 'sort-desc');
    if (i === col) th.classList.add(dir > 0 ? 'sort-asc' : 'sort-desc');
  }});
}}
</script>
</body>
</html>"""

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        return html_path

    def get_latest_opportunities(self, limit: int = 10) -> List[Tuple[str, str, str, str]]:
        """Return latest opportunities by capture time."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT title, institution, link, deadline
                FROM opportunities
                ORDER BY captured_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return cursor.fetchall()

    def get_total_count(self) -> int:
        """Return total number of records in database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM opportunities")
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    def get_count_by_institution(self, institution: str) -> int:
        """Return total number of records for a given institution."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM opportunities WHERE institution = ?", (institution,)
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    def get_totals_by_institution(self) -> Dict[str, int]:
        """Return counts grouped by institution."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT institution, COUNT(*) FROM opportunities GROUP BY institution"
            )
            rows = cursor.fetchall()
            return {str(institution): int(total) for institution, total in rows if institution}
