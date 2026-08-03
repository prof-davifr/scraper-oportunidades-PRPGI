# AGENTS.md

## Project

Web scraper for Brazilian research funding opportunities ("editais"). Collects from CAPES, CNPq, FINEP, FAPESB, SETEC, MCTI — stores in SQLite, exports to CSV/Excel/HTML, and can be built as a Windows executable (GUI).

## Quick start

```bash
pip install -r requirements.txt
python crawler/main.py
```

No lockfile exists; dependencies are tracked in `requirements.txt`.

## How to run

- **Full crawl** (all sources): `python crawler/main.py`
- **Single parser**: `python crawler/parsers/capes.py` (or `cnpq.py`, `finep.py`, `fapesb.py`, `setec.py`, `mcti.py`)
- **Optional filters**: `python crawler/main.py --parser capes|cnpq|finep|fapesb|setec|mcti|all --max-items N`
- **Output dir**: `python crawler/main.py --output-dir ~/editais` (db/csv/xlsx/html nesse diretório)
- **GUI (executável)**: `python crawler/gui.py` (tkinter)

## Key details

- **DB**: SQLite at `oportunidades.db` (root). Deduplicates via SHA256 hash of title+link. `add_opportunity_with_result` preenche datas vazias de registros duplicados (UPDATE via COALESCE).
- **Output**: `editais.csv`, `editais.xlsx`, and `editais.html` written to project root (or `--output-dir`). CSV uses `utf-8-sig` (BOM). **Exportação consolida** documentos do mesmo edital em uma linha (colunas `Documentos`/`Documentos Relacionados`); `--no-consolidate` para lista crua.
- **Parser mechanics — TODOS via httpx + BeautifulSoup, SEM navegador/Playwright**:
  - CAPES: program pages + direct PDF links (extracts date from SEI filename `DDMMYYYY_...`).
  - CNPq: gov.br chamadas abertas (`#content div.item`) — title, "Publicado em" (date), "Inscrições" (deadline).
  - FINEP: REST API `/o/c/chamadapublicas`, filters `situacao.key == "aberta"`; `dataDePublicacao` → date.
  - FAPESB: WordPress REST API (`wp-json/wp/v2/posts`, category "Edital"); deadlines best-effort from page prose/PDF cronograma (pypdf). The "⏰ Início/Encerramento" widget is a fixed template — do NOT use it.
  - SETEC: gov.br/MEC editais pages by year; extracts edital blocks (`<p>` title + `<ul>` annexes), one record per edital with real title; `_clean_title` removes nav/anexo noise. CAPTCHA retry via `crawler/http_utils.py`.
  - MCTI: editais links from main content + nav submenu.
- **HTTP**: `crawler/http_utils.py` — `fetch_text` with retry/backoff and CAPTCHA detection ("human visitor", "Acesso Temporariamente Interrompido"). Use it in new parsers.
- **Consolidation**: `crawler/consolidate.py` groups documents of the same edital (number/type/year) in exports.
- **Standalone parser execution**: Parser `__main__` blocks resolve project root robustly and write outputs to root-level files.
- **GUI**: `crawler/gui.py` — tkinter window ("Gerar Editais"), writes outputs next to the executable (PyInstaller frozen) or cwd.

## Windows executable (distribution)

- Build via PyInstaller: `pyinstaller scraper_exe.spec --noconfirm` → `dist/GeradorEditais(.exe)`
- GitHub Actions job `build-windows` builds and uploads the exe as artifact on every push to `main`.
- The GUI targets users with zero technical skills (double-click → planilha gerada).
- No Playwright/browser needed → small exe (~30 MB) and no `playwright install` step.

## Gotchas

- **Government sites are unreliable / CAPTCHA intermitente**: `gov.br` and `finep.gov.br` are slow, may return 5xx, and occasionally serve a CAPTCHA page ("human visitor"). `fetch_text` retries; parsers return 0 results gracefully when all attempts are blocked.
- **SETEC (`gov.br/mec`)**: after several accesses it may block for minutes — rerun later.
- **MCTI**: sometimes behind CAPTCHA; the parser returns 0 until it clears.
- **No tests, no CI, no linting**: legacy statement — actually there IS pytest (47 tests) and CI (lint+test+build-windows). Ruff check has pre-existing failures; CI runs `ruff check .` (may fail — decide whether to clean or adjust).
- **Dependency manifest**: runtime deps in `requirements.txt` (httpx, beautifulsoup4, pandas, openpyxl, pypdf) and `pyproject.toml`.

## Adding a new parser

1. Create `crawler/parsers/<name>.py` with a class that has `institution` (str) and `parse(db)` (async, returns new count or structured stats) attributes.
2. Add it to the `SOURCES` list in `crawler/config.py` (not `main.py` — config auto-registers sources).
3. Use `db.add_opportunity_with_result(institution, title, link, description, pub_date, deadline)` to insert records.
4. Fetch pages with `crawler/http_utils.fetch_text` (retry + CAPTCHA detection).
