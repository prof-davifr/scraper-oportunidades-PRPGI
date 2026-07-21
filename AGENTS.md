# AGENTS.md

## Project

Web scraper for Brazilian research funding opportunities ("editais"). Collects from CAPES, CNPq, FINEP, FAPESB, SETEC, CONFAP, EMBRAPII, BNDES, MCTI — stores in SQLite, exports to CSV/Excel.

## Quick start

```bash
pip install -r requirements.txt
playwright install chromium
python crawler/main.py
```

No lockfile exists; dependencies are tracked in `requirements.txt`.

## How to run

- **Full crawl** (all sources): `python crawler/main.py`
- **Single parser**: `python crawler/parsers/capes.py` (or `cnpq.py`, `finep.py`, `fapesb.py`, `setec.py`, etc.)
- **Optional filters**: `python crawler/main.py --parser capes|cnpq|finep|fapesb|setec|all --max-items N`

## Key details

- **DB**: SQLite at `oportunidades.db` (root). Deduplicates via SHA256 hash of title+link.
- **Output**: `editais.csv`, `editais.xlsx`, and `editais.html` written to project root. CSV uses `utf-8-sig` (BOM) for Excel compatibility.
- **Parser mechanics**: CNPq/FAPESB/SETEC/MCTI/BNDES use Playwright headless Chromium with retry/backoff. CAPES uses httpx + BeautifulSoup (no Playwright — fetches program pages to extract edital PDF links). FINEP uses httpx REST API (`/o/c/chamadapublicas`). EMBRAPII scrapes `a[href*="chamadas-publicas"]` from `/transparencia/` (WordPress). CONFAP scrapes `a.d-flex.flex-wrap...` from `/tag/editais/` (WordPress news site). All isolate per-item failures.
- **Standalone parser execution**: Parser `__main__` blocks resolve project root robustly and write outputs to root-level files.
- **Files at root vs `crawler/`**: Duplicate `editais.xlsx`, `editais.csv`, and `oportunidades.db` exist at both levels. Root-level files are the canonical outputs; `crawler/` copies come from standalone parser runs.

## Gotchas

- **Playwright browser**: Must run `playwright install chromium` after pip install. Without it, parsers fail immediately.
- **Government sites are unreliable**: CNPq (`memoria2.cnpq.br`), FINEP (`finep.gov.br`), CAPES/SETEC/MCTI (`gov.br`), FAPESB (`fapesb.ba.gov.br`) are slow and may return 5xx errors. Parsers handle this gracefully but return 0 results.
  - FINEP bypasses gov.br instability by using its REST API directly (`/o/c/chamadapublicas`).
  - SETEC/MCTI/BNDES may return 0 records when their Liferay portals are down or blocked.
  - CAPES page lists 20 active programs; each program page is scraped via httpx for edital PDF links. ~290 editais found across all programs. The "Editais Abertos" section shows program links, not individual editais.
- **FINEP API**: Uses `httpx` (not Playwright) to call `https://www.finep.gov.br/o/c/chamadapublicas` with `?sort=dataDePublicacao:desc&pageSize=250`. Filters for `situacao.key == "aberta"`. Returns structured JSON with title, deadline, description.
- **EMBRAPII**: Scrapes `/transparencia/`, looks for `a[href*="chamadas-publicas"]`, filters out "Ver documentos" links. The old `/editais-e-chamadas/` URL was 404.
- **CONFAP**: Domain moved to `news.confap.org.br`. Scrapes `/tag/editais/`, looks for article links with class `d-flex.flex-wrap.p-3.p-md-4.text-white`, extracts title from `<h2>` and date from `<small>`.
- **HTML export**: `editais.html` is generated with no external dependencies (responsive, sortable, filterable).
- **No tests, no CI, no linting, no git**: This is a raw script project, not a production repo. Don't expect to find any of these.
- **Dependency manifest**: Runtime dependencies are listed in `requirements.txt`.

## Adding a new parser

1. Create `crawler/parsers/<name>.py` with a class that has `institution` (str) and `parse(db)` (async, returns new count or structured stats) attributes.
2. Add it to the `SOURCES` list in `crawler/config.py` (not `main.py` — config auto-registers sources).
3. Use `db.add_opportunity_with_result(institution, title, link, description, pub_date, deadline)` to insert records.

Current priority order (config.py `SOURCES`): CAPES, CNPq, FINEP, FAPESB, SETEC, CONFAP, EMBRAPII, BNDES, MCTI.

## TODO.md

Este projeto mantém um `TODO.md` na raiz com o planejamento e acompanhamento das tarefas.
O agente é responsável por criar e manter este arquivo atualizado.

O arquivo `TODO.md` da raiz de `/home/davi/projetos/` consolida automaticamente os TODOs de todos os subprojetos.
Execute `python3 /home/davi/projetos/_gen_sumula.py` para regenerar a súmula consolidada após alterações neste TODO.md.

