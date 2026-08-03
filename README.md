# scraper-oportunidades-PRPGI

Web scraper para editais de fomento à pesquisa brasileiros. Coleta de **CAPES, CNPq, FINEP, FAPESB, SETEC, CONFAP, BNDES, MCTI**, armazena em SQLite e exporta para CSV/Excel/HTML.

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
python crawler/main.py --parser capes|cnpq|finep|fapesb|setec|confap|bndes|mcti|all --max-items N
```

## Saídas

- `oportunidades.db` — banco SQLite (raiz do projeto)
- `editais.csv` — CSV com BOM (`utf-8-sig`) para compatibilidade com Excel. Colunas: Instituição, Título, **Data de Lançamento**, Prazo, Link, Descrição — ordenado por recência.
- `editais.xlsx` — planilha Excel (mesmas colunas)
- `editais.html` — página HTML standalone (responsiva, ordenável e filtrável, com destaque para lançamentos recentes e filtro de últimos 30/60/90 dias)

As planilhas são regeneradas apenas quando há novos registros.

## Data de lançamento

Os parsers preenchem `publication_date` (ISO `YYYY-MM-DD` no banco, exibida como DD/MM/AAAA):

- **CNPq**: campo "Publicado em" da página de chamadas abertas (gov.br).
- **FINEP**: campo `dataDePublicacao` da API REST.
- **CAPES**: data embutida no nome do arquivo PDF (padrão SEI `DDMMYYYY_...`) — aproximação; a página não expõe a data.
- **FAPESB/SETEC**: não publicam datas de lançamento — campo vazio.

Registros já existentes têm datas vazias preenchidas automaticamente em execuções seguintes (UPDATE no dedup).

## Como funciona

- `crawler/main.py` — orquestra parsers e exportação
- `crawler/database.py` — camada SQLite com deduplicação SHA256 em (título, link)
- `crawler/parsers/` — um módulo por fonte:
  - **capes.py** — httpx + BeautifulSoup (sem Playwright). Busca a página de editais, extrai links de programas (`acoes-e-programas`) e PDFs diretos de editais.
  - **cnpq.py** — Playwright no novo site do CNPq (`gov.br/cnpq/pt-br/chamadas/abertas-para-submissao`); extrai título, "Publicado em" (data de lançamento) e "Inscrições" (prazo).
  - **finep.py** — httpx REST API (`/o/c/chamadapublicas`), filtra `situacao.key == "aberta"`.
  - **fapesb.py, setec.py, mcti.py** — Playwright (portal gov.br e fapesb.ba.gov.br).
  - **confap.py** — Playwright em `news.confap.org.br/tag/editais/` (WordPress).
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
