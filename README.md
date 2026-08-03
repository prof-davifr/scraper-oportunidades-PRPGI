# scraper-oportunidades-PRPGI

Coletor de editais de fomento à pesquisa brasileiros — **CAPES, CNPq, FINEP, FAPESB, SETEC e MCTI** — que gera planilha Excel, CSV e página HTML.

## 👤 Para usuários finais (Windows, sem instalar nada)

1. Baixe o executável **`GeradorEditais.exe`** (disponível em *Actions* do repositório → artifact do job `build-windows`).
2. Dê **duplo clique** no arquivo.
3. Escolha a pasta onde quer a planilha (opcional — padrão: a mesma pasta do programa).
4. Clique em **"Gerar Editais"** e aguarde o progresso.
5. Abra o arquivo **`editais.xlsx`** no Excel.

O programa baixa sozinho os dados das 6 fontes e salva ao lado dele:
`editais.xlsx` (planilha), `editais.csv`, `editais.html` e `oportunidades.db`.

> Requer internet. A primeira geração pode levar alguns minutos (sites governamentais são lentos).

## 🛠️ Para desenvolvedores

### Requisitos

- Python 3.11+
- Sem navegador: os parsers usam apenas `httpx` + `BeautifulSoup`

```bash
pip install -r requirements.txt
```

### Execução

```bash
python crawler/main.py                     # todas as fontes
python crawler/main.py --parser capes      # só CAPES
python crawler/main.py --max-items 100     # limite por fonte
python crawler/main.py --output-dir ~/editais   # gera em outra pasta
python crawler/main.py --no-consolidate    # sem agrupar documentos do mesmo edital
```

### Testes

```bash
python -m pytest
```

## 📦 Distribuição (gerar o executável)

O **exe Windows** é gerado automaticamente pelo GitHub Actions (job `build-windows`)
a cada push na `main` — o arquivo fica em *Actions → GeradorEditais-windows*.

Para gerar localmente:

```bash
pip install pyinstaller
pyinstaller scraper_exe.spec --noconfirm   # gera dist/GeradorEditais(.exe)
```

## Saídas

- `oportunidades.db` — banco SQLite (dedup por SHA256 de título+link)
- `editais.csv` — CSV com BOM (`utf-8-sig`). Colunas: Instituição, Título, Data de Lançamento, Prazo, Link, Documentos, Documentos Relacionados — ordenado por recência
- `editais.xlsx` — planilha Excel (mesmas colunas)
- `editais.html` — página HTML standalone (ordena, filtra, destaca lançamentos recentes)

A exportação **consolida** documentos do mesmo edital (edital + retificações + resultados) em uma linha. Use `--no-consolidate` para a lista crua.

## Data de lançamento

- **CNPq**: "Publicado em" da página de chamadas abertas.
- **FINEP**: `dataDePublicacao` da API REST.
- **FAPESB**: `date` da API do WordPress + prazo best-effort da página/PDF.
- **CAPES**: data no nome do arquivo PDF (padrão SEI `DDMMYYYY_...`).
- **SETEC**: metadados de criação do PDF (`pypdf`) — aproximação.
- **MCTI**: quando disponível no texto.

Registros existentes têm datas vazias preenchidas automaticamente nas execuções seguintes.

## Como funciona

- `crawler/main.py` — orquestra parsers e exportação (CLI)
- `crawler/gui.py` — interface gráfica (tkinter) usada no executável
- `crawler/database.py` — camada SQLite + exportação CSV/XLSX/HTML
- `crawler/consolidate.py` — agrupa documentos do mesmo edital
- `crawler/http_utils.py` — GET com retry/backoff e detecção de CAPTCHA do gov.br
- `crawler/parsers/` — um módulo por fonte (todos via `httpx`, sem navegador):
  - **capes.py** — páginas de programas + PDFs diretos
  - **cnpq.py** — chamadas abertas (gov.br): título, "Publicado em", "Inscrições"
  - **finep.py** — API REST, filtra chamadas abertas
  - **fapesb.py** — API do WordPress (categoria "Edital")
  - **setec.py** — blocos de edital (título + anexos) por ano; `_clean_title` limpa ruído
  - **mcti.py** — links de editais do conteúdo principal/submenu

## Adicionar uma fonte

1. Criar `crawler/parsers/<nome>.py` com classe expondo `institution` (str) e `parse(db)` (async).
2. Adicionar ao `SOURCES` em `crawler/config.py`.
3. Inserir via `db.add_opportunity_with_result(institution, title, link, description, pub_date, deadline)`.

## Problemas conhecidos

- Sites governamentais (`gov.br`, `finep.gov.br`) são lentos e aplicam **CAPTCHA intermitente**. Os parsers detectam o bloqueio e tentam novamente com espera crescente (retry automático).
- `gov.br/mec` (SETEC) pode bloquear por alguns minutos após muitos acessos — basta rodar de novo mais tarde.
- A primeira geração pode demorar (CAPES visita dezenas de páginas de programa).
