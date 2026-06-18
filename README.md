# scraper-oportunidades-PRPGI

Web scraper for Brazilian research funding opportunities ("editais"). Collects from FINEP and CNPq, stores in SQLite, exports to CSV/Excel.

## Prerequisites

```bash
pip install -r requirements.txt
playwright install chromium
```

## Running

**Full crawl** (FINEP + CNPq) — run from the project root:

```bash
python crawler/main.py
```

**Single parser:**

```bash
python crawler/parsers/finep.py
python crawler/parsers/cnpq.py
```

Optional parser selection/limits from the main runner:

```bash
python crawler/main.py --parser finep
python crawler/main.py --parser cnpq --max-items 30
```

## Output

- `oportunidades.db` — SQLite database (root level)
- `editais.csv` — CSV with BOM (`utf-8-sig`) for Excel compatibility
- `editais.xlsx` — Excel workbook

Spreadsheets are only regenerated when new opportunities are found.

## How it works

- `crawler/main.py` — orchestrates parsers and export
- `crawler/database.py` — SQLite layer with SHA256 dedup on (title, link), deterministic export ordering, and count helpers
- `crawler/parsers/finep.py` — scrapes `finep.gov.br` (`.item` selector)
- `crawler/parsers/cnpq.py` — scrapes `memoria2.cnpq.br` (`li` elements, Liferay portal)

Parsers use navigation retry with exponential backoff and keep per-item failure isolation, so one bad item does not abort the full crawl.

## Adding a new parser

1. Create `crawler/parsers/<name>.py` with a class exposing:
   - `institution` (str)
   - `parse(db)` (async, returns parser stats or new record count)
2. Add it to the `parsers` list in `crawler/main.py`.
3. Insert records via `db.add_opportunity(institution, title, link, description, pub_date, deadline)`.

## Known issues

- Government sites (`finep.gov.br`, `memoria2.cnpq.br`) are slow and may return 5xx errors. Parsers handle this gracefully and return 0 results.
- Playwright browser binaries are required (`playwright install chromium`) after dependency installation.
