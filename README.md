# scraper-oportunidades-PRPGI

Web scraper para editais de fomento à pesquisa brasileiros. Coleta de **CAPES, CNPq, FINEP, FAPESB, SETEC, CONFAP, EMBRAPII, BNDES, MCTI**, armazena em SQLite e exporta para CSV/Excel/HTML.

## Pré-requisitos

```bash
pip install -r requirements.txt
playwright install chromium
```

## Execução

**Crawl completo** (todas as fontes) — rodar da raiz do projeto:

```bash
python crawler/main.py
```

**Parser específico:**

```bash
python crawler/parsers/capes.py
python crawler/parsers/cnpq.py
```

Filtros opcionais:

```bash
python crawler/main.py --parser capes|cnpq|finep|fapesb|setec|confap|embrapii|bndes|mcti|all --max-items N
```

## Saídas

- `oportunidades.db` — banco SQLite (raiz do projeto)
- `editais.csv` — CSV com BOM (`utf-8-sig`) para compatibilidade com Excel
- `editais.xlsx` — planilha Excel
- `editais.html` — página HTML standalone (responsiva, ordenável e filtrável)

As planilhas são regeneradas apenas quando há novos registros.

## Como funciona

- `crawler/main.py` — orquestra parsers e exportação
- `crawler/database.py` — camada SQLite com deduplicação SHA256 em (título, link)
- `crawler/parsers/` — um módulo por fonte:
  - **capes.py** — httpx + BeautifulSoup (sem Playwright). Busca a página de editais, extrai links de programas (`acoes-e-programas`) e PDFs diretos de editais.
  - **cnpq.py** — Playwright em `memoria2.cnpq.br` (`ol.list-chamadas`); link de detalhe construído a partir do `idDivulgacao`.
  - **finep.py** — httpx REST API (`/o/c/chamadapublicas`), filtra `situacao.key == "aberta"`.
  - **fapesb.py, setec.py, mcti.py** — Playwright (portal gov.br e fapesb.ba.gov.br).
  - **confap.py** — Playwright em `news.confap.org.br/tag/editais/` (WordPress).
  - **embrapii.py** — Playwright em `/transparencia/` (WordPress), links `a[href*="chamadas-publicas"]`.
  - **bndes.py** — Playwright na home (`bndes.gov.br`); captura cards de destaque de editais/chamadas/seleções (a página antiga de chamadas públicas retorna 404).

Parsers usam retry com backoff exponencial e isolam falhas por item.

## Adicionar um novo parser

1. Criar `crawler/parsers/<nome>.py` com classe expondo:
   - `institution` (str)
   - `parse(db)` (async, retorna stats ou contagem)
2. Adicionar ao `SOURCES` em `crawler/config.py` (o config auto-registra).
3. Inserir registros via `db.add_opportunity_with_result(institution, title, link, description, pub_date, deadline)`.

## Problemas conhecidos

- **SETEC/MEC**: o site `gov.br/mec` está atrás de CAPTCHA anti-bot ("This question is for testing whether you are a human visitor"). O parser retorna 0 registros enquanto durar o bloqueio.
- Sites governamentais (`memoria2.cnpq.br`, `finep.gov.br`, `gov.br`) são lentos e podem retornar 5xx. Parsers tratam com graça e retornam 0.
- Playwright exige binários do Chromium (`playwright install chromium`).

## Testes

```bash
python -m pytest
```
