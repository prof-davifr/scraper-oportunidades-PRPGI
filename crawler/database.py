import hashlib
import re
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
            # Registro já existe (dedup por uid): preenche datas vazias,
            # mantendo as informações já capturadas.
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        UPDATE opportunities
                        SET publication_date = COALESCE(NULLIF(publication_date, ''), ?),
                            deadline = COALESCE(NULLIF(deadline, ''), ?)
                        WHERE uid = ?
                        """,
                        (pub_date, deadline, uid),
                    )
                    conn.commit()
            except sqlite3.Error:
                pass
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

    def _format_date(self, value) -> str:
        """Converte data ISO (YYYY-MM-DD) para DD/MM/YYYY para exibição.
        Aceita também timestamps ISO completos (YYYY-MM-DDTHH:MM:SS...)."""
        if not value:
            return ""
        s = str(value).strip()
        if not s:
            return ""
        # Já está em DD/MM/YYYY
        if re.match(r"^\d{2}/\d{2}/\d{4}$", s):
            return s
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
        if m:
            return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
        return s

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
                    publication_date as "Data de Lançamento",
                    deadline as Prazo,
                    link as Link,
                    description as Descrição
                FROM opportunities
                ORDER BY
                    CASE WHEN publication_date IS NULL OR publication_date = '' THEN 1 ELSE 0 END,
                    publication_date DESC,
                    institution ASC, title ASC, link ASC, id ASC
                """,
                conn,
            )
            # Data de lançamento em ISO (YYYY-MM-DD) -> DD/MM/YYYY para exibição
            if "Data de Lançamento" in df.columns:
                df["Data de Lançamento"] = df["Data de Lançamento"].apply(
                    lambda v: self._format_date(v)
                )

        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        df.to_excel(xlsx_path, index=False)
        return csv_path, xlsx_path

    def export_to_html(self, html_path: str = "editais.html") -> str:
        """Export all opportunities to a standalone HTML page."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT institution, title, publication_date, deadline, link, description
                FROM opportunities
                ORDER BY
                    CASE WHEN publication_date IS NULL OR publication_date = '' THEN 1 ELSE 0 END,
                    publication_date DESC,
                    institution ASC, title ASC, link ASC, id ASC
            """)
            rows = cursor.fetchall()

        totals = self.get_totals_by_institution()
        total_count = sum(totals.values())

        rows_html = ""
        for inst, title, pub_date, deadline, link, desc in rows:
            safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            safe_desc = (desc or "")[:300].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            safe_deadline = self._format_date(deadline) or "—"
            safe_pub = self._format_date(pub_date) or "—"
            # destaque para lançamentos recentes (últimos 60 dias)
            recent = ""
            if pub_date:
                try:
                    import datetime as _dt
                    pub_dt = _dt.date.fromisoformat(str(pub_date)[:10])
                    if (_dt.date.today() - pub_dt).days <= 60:
                        recent = ' class="recent"'
                except ValueError:
                    pass
            rows_html += f"""<tr{recent}>
                <td class="inst">{inst}</td>
                <td class="title"><a href="{link}" target="_blank" rel="noopener">{safe_title}</a></td>
                <td class="pub">{safe_pub}</td>
                <td class="deadline">{safe_deadline}</td>
                <td class="desc">{safe_desc}</td>
            </tr>
"""

        inst_badges = "".join(
            f'<button class="badge badge-{k.lower()}" data-inst="{k}" onclick="filterByInst(\'{k}\')">{k} ({v})</button>'
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
  .badge {{ display: inline-block; padding: .35em .75em; border-radius: 20px; font-size: .8rem; font-weight: 600; background: #e0e0e0; color: #333; border: 2px solid transparent; cursor: pointer; }}
  .badge:hover {{ border-color: #165c33; }}
  .badge.active {{ background: #165c33; color: #fff; border-color: #165c33; }}
  .badge-total {{ background: #165c33; color: #fff; }}
  .badge-total.active {{ background: #0e3d21; }}
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
  .pub {{ white-space: nowrap; color: #333; font-variant-numeric: tabular-nums; }}
  .deadline {{ white-space: nowrap; color: #666; }}
  .desc {{ color: #555; max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  tr.recent {{ background: #eef7ef; }}
  tr.recent td.pub::after {{ content: " • novo"; color: #00853f; font-weight: 600; font-size: .72rem; }}
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
    <span class="badge badge-total" data-inst="" onclick="filterByInst('')">Total: {total_count}</span>
    {inst_badges}
  </div>
  <div class="filter-bar">
    <input type="text" id="filterTitle" placeholder="Buscar por título..." oninput="filterTable()">
    <select id="filterInst" onchange="filterTable()">
      <option value="">Todas as instituições</option>
      {''.join(f'<option value="{k}">{k}</option>' for k in sorted(totals))}
    </select>
    <select id="filterRecent" onchange="filterTable()">
      <option value="">Todas as datas</option>
      <option value="30">Últimos 30 dias</option>
      <option value="60">Últimos 60 dias</option>
      <option value="90">Últimos 90 dias</option>
    </select>
  </div>
  <div class="table-wrap">
    <table id="oppTable">
      <thead>
        <tr>
          <th onclick="sortTable(0)">Instituição</th>
          <th onclick="sortTable(1)">Título</th>
          <th onclick="sortTable(2)">Lançamento</th>
          <th onclick="sortTable(3)">Prazo</th>
          <th onclick="sortTable(4)">Descrição</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>
<script>
function filterByInst(inst) {{
  document.getElementById('filterInst').value = inst;
  document.querySelectorAll('.stats .badge').forEach(b => {{
    b.classList.toggle('active', (b.getAttribute('data-inst') || '') === inst);
  }});
  filterTable();
}}
function filterTable() {{
  const q = document.getElementById('filterTitle').value.toLowerCase();
  const inst = document.getElementById('filterInst').value;
  const days = parseInt(document.getElementById('filterRecent').value || '0', 10);
  const now = Date.now();
  const dayMs = 24*60*60*1000;
  document.querySelectorAll('#oppTable tbody tr').forEach(r => {{
    const title = r.children[1].textContent.toLowerCase();
    const rowInst = r.children[0].textContent;
    const pubRaw = r.children[2].textContent.trim();
    let pubMs = NaN;
    const m = pubRaw.match(/(\\d{{2}})\\/(\\d{{2}})\\/(\\d{{4}})/);
    if (m) pubMs = new Date(+m[3], +m[2]-1, +m[1]).getTime();
    const matchTitle = !q || title.includes(q);
    const matchInst = !inst || rowInst === inst;
    const matchRecent = !days || (pubMs && (now - pubMs) <= days*dayMs);
    r.style.display = matchTitle && matchInst && matchRecent ? '' : 'none';
  }});
}}
let sortDir = [1,1,1,1,1];
function sortTable(col) {{
  const tbody = document.querySelector('#oppTable tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  sortDir[col] *= -1;
  const dir = sortDir[col];
  rows.sort((a, b) => {{
    const va = a.children[col].textContent.trim().toLowerCase();
    const vb = b.children[col].textContent.trim().toLowerCase();
    // colunas de data: comparar por timestamp quando parseável
    const da = va.match(/(\\d{{2}})\\/(\\d{{2}})\\/(\\d{{4}})/);
    const db = vb.match(/(\\d{{2}})\\/(\\d{{2}})\\/(\\d{{4}})/);
    if (da && db) {{
      const ta = new Date(+da[3], +da[2]-1, +da[1]).getTime();
      const tb = new Date(+db[3], +db[2]-1, +db[1]).getTime();
      return (ta - tb) * dir;
    }}
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
