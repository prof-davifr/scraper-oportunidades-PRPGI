# TODO — scraper-oportunidades-PRPGI

Coletor de editais de fomento à pesquisa (CAPES, CNPq, FINEP, FAPESB, SETEC) —
banco SQLite persistido no repositório, exports CSV/XLSX/HTML e publicação
diária no GitHub Pages.

_Última atualização: 31/08/2026 (sessão: revisão do backlog depois de 26 dias de crawl automático)_

---

## Estado atual (31/08/2026)

- **475 registros** no `oportunidades.db` de `origin/main` (eram 434 em 04/08).
- Crawl de 31/08 (run `33422299637`, 3m58s): `processed=375 new=0 duplicates=375
  errors=0`, `db_total=475` — todas as cinco fontes responderam sem erro.
- **140/475 com data de lançamento**; **43/475 com prazo de inscrição**.

| Instituição | Registros | Com data | Com prazo |
|---|---|---|---|
| CAPES | 346 | 67 | 0 |
| SETEC | 56 | 0 | 0 |
| FINEP | 38 | 38 | 25 |
| FAPESB | 20 | 20 | 7 |
| CNPq | 15 | 15 | 11 |

- Último commit de **código**: 05/08/2026 (`856531d`). De 06/08 para cá o
  repositório só recebeu commits automáticos de crawl (25 commits).
- ⚠️ **A cópia local está 27 commits atrás de `origin/main`** — o robô do
  `crawl.yml` comita banco e exports direto no remoto. Dar `git pull` antes de
  mexer em qualquer coisa, senão os exports locais (05/08) atropelam os do robô.
- 46 testes passando (`python -m pytest`); `ruff check .` e `ruff format --check .` limpos.

## Backlog

- [ ] **CAPES — 279/346 registros sem data de lançamento** (só há data quando o nome do arquivo SEI traz `DDMMYYYY_`).
      É a maior lacuna da página, que ordena e filtra por recência. Explorar a
      leitura do texto do PDF — o gov.br serve HTML para o `httpx`, então precisa
      de outra estratégia de download. (Era 398/654 em 04/08; o denominador caiu
      com a limpeza de resultados de seleção.)
- [ ] **Editais vencidos nunca saem da página** — os 475 registros estão com `status = 'Aberta'` e só 43 têm prazo.
      Definir a regra de encerramento (prazo vencido → mudança de `status` ou
      filtro no export) antes de divulgar mais o link para a comunidade.
- [ ] **SETEC — 0/56 registros com data**, embora a extração por metadados de PDF tenha chegado a 29/53 em 03/08.
      Verificar se `crawler/pdf_utils.py` ainda roda no crawl diário ou se os
      links dos PDFs morreram (404 no gov.br).
- [ ] **FINEP lista 9 chamadas de 2015–2024** como "aberta" na API (a mais antiga é de 13/10/2015).
      O corte "só de 2025 em diante" foi limpeza manual em 03/08, nunca virou
      regra do pipeline — implementar o filtro na ingestão.
- [ ] **CI parado desde 05/08/2026** — o `ci.yml` só dispara em push, e o push do bot não re-dispara workflows.
      Lint, testes e build do exe Windows não rodam há 26 dias. Avaliar um
      `schedule` no `ci.yml` ou chamar `ruff`/`pytest` dentro do `crawl.yml`.
- [ ] **Actions em Node 20 depreciado** — `checkout@v4`, `setup-python@v5`, `upload-artifact@v4` e `deploy-pages@v4`.
      Já rodam forçados em Node 24, com aviso em toda execução. Atualizar as versões.
- [ ] **MCTI** — reavaliar a re-inclusão se voltar a publicar listagem pública de editais (hoje: 302 → `require_login`).

## Concluído (ago/2026)

- [x] **Crawl diário + Pages consolidado** — 32 de 33 execuções verdes desde
      05/08, a última em **31/08/2026** (run `33422299637`, 3m58s). A única falha
      (06/08, run `31103764101`) foi timeout do `deploy-pages`; o crawl em si
      passou. Página no ar: `https://prof-davifr.github.io/scraper-oportunidades-PRPGI/`.
- [x] **Ruff limpo** — `ruff check .` responde "All checks passed!". Os 116 erros
      de lint pré-existentes foram resolvidos em `b1323f4` (04/08: `line-length
      120` + ignores para tipografia PT-BR). O item estava duplicado neste
      arquivo, em duas seções "Pendências" — unificado aqui.
- [x] **`pyproject.toml` em dia** — `dependencies` já traz `httpx` e
      `beautifulsoup4` (além de pandas, openpyxl e pypdf), e os dois entry points
      existem de fato: `crawler.main:main` (`crawler/main.py:200`) e
      `crawler.gui:main` (`crawler/gui.py:171`).
- [x] **SETEC voltou a coletar** — no crawl de 31/08 processou 53 itens com
      `errors=0`, e o banco tem 56 registros (eram 53 em 04/08). O CAPTCHA do
      `gov.br/mec` não está mais bloqueando as rodadas agendadas.
- [x] **FAPESB** — datas de lançamento resolvidas pela API REST do WordPress
      (campo `date`): 20/20.
- [x] **MCTI removido** (04/08) — página de editais atrás de login gov.br.
- [x] **Sobre em pop-up + identidade visual** (05/08) — símbolo IFBA no topo do
      HTML e subtítulo "Assessoria de Ciência de Dados - NPP - PRPGI / IFBA".

---

## Histórico de sessões

### Sessão 04/08 — repositório público + crawl diário + GitHub Pages

- **Decisão do usuário**: disponibilizar para a PRPGI/IFBA — repo público, banco persistido, atualização automática diária, HTML público via Pages.
- **Plano salvo em `PLANO_DEPLOY.md`** (arquitetura, tarefas, riscos).
- **Projeto movido** do monorepo `PRPGI/` para `~/projetos/repos-independentes/scraper-oportunidades-PRPGI` com histórico preservado (`git subtree split` — 10 commits). Repo: `github.com/prof-davifr/scraper-oportunidades-PRPGI` (público).
- **`crawler/main.py`**: flag `--force-export` — regenera CSV/XLSX/HTML mesmo com `new=0` (essencial com banco persistido).
- **`.gitignore`**: `oportunidades.db` e `editais.*` **deixaram de ser ignorados** — banco e exports agora são versionados (persistência). Resíduos `crawler/oportunidades.db` (base de março, 14 regs) removidos.
- **`.github/workflows/crawl.yml`** (novo): cron `0 11 * * *` (08h BRT) + push na main + `workflow_dispatch` → crawl com `--force-export` → commit-back → deploy GitHub Pages (`_site/` com `editais.html → index.html`).
- **`ci.yml`**: corrigido job `test` (removido `playwright install chromium` — playwright não é mais dependência e quebrava o job).
- **Banco inicial versionado**: 434 registros (04/08).
- Página pública: `https://prof-davifr.github.io/scraper-oportunidades-PRPGI/`.

### Sessão 04/08 — remoção do MCTI

- **Decisão do usuário**: MCTI fora do escopo — a página de editais (`gov.br/mcti/pt-br/acesso-a-informacao/editais`) passou a responder **302 → `require_login`** (autenticação gov.br) e o link de referência (`acompanhe-o-mcti/editais-concursos-e-chamadas-publicas`) é **404**. Não há listagem pública de editais do MCTI (só notícias).
- Removidos: entrada do `SOURCES` (`crawler/config.py`), arquivo `crawler/parsers/mcti.py`, testes do parser (46 passando), menções em `README.md`, `fontes.md`, `AGENTS.md`, `pyproject.toml` e `crawler/gui.py`. Banco: 0 registros MCTI (nada a apagar).
- **Se o MCTI voltar a publicar listagem pública de editais, reavaliar re-inclusão.**

### Sessão 03/08 (tarde) — remoção da BNDES

- **Decisão do usuário**: BNDES fora do escopo.
- Removidos: entrada do `SOURCES` (`crawler/config.py`), arquivo `crawler/parsers/bndes.py`, testes do parser (42 passando), 3 registros do banco e menções em `README.md`, `fontes.md`, `AGENTS.md`.
- Exports regenerados: 550 registros.

### Sessão 03/08 (tarde) — remoção da CONFAP

- **Decisão do usuário**: CONFAP não publica editais, só notícias — fora do escopo.
- Removidos: entrada do `SOURCES` (`crawler/config.py`), arquivo `crawler/parsers/confap.py`, testes do parser (44 passando), 8 registros do banco e menções em `README.md`, `fontes.md`, `AGENTS.md`.
- Exports regenerados: 553 registros.

### Sessão 03/08 (tarde) — exclusão de registros anteriores a 2025

- **Decisão do usuário**: manter apenas editais de 2025 em diante.
- **328 registros excluídos** (CAPES 275, SETEC 44, FINEP 9): critério = ano extraído da data de publicação ou, na ausência, do título ("nº X/YYYY"), do nome do arquivo (SEI `DDMMYYYY_...`, `..._2024_...`) ou do caminho da URL (`editais/2026`, `edital-2023`). 0 registros ficaram sem classificação.
- Total: 550 → **224 registros** (2026 = 153, 2025 = 71).
- Exports regenerados.

### Sessão 03/08 (tarde) — datas para SETEC e FAPESB

- **Objetivo**: FAPESB e SETEC não publicavam datas de lançamento (campos vazios).
- **FAPESB reescrita** (`crawler/parsers/fapesb.py`): migrada do Playwright para a **API REST do WordPress** (`wp-json/wp/v2/posts?categories=1`, categoria "Edital") — título, link e **data de publicação** (`date`) estáveis, sem navegador. Prazo de inscrição best-effort: o widget "⏰ Início/Encerramento" é template fixo do site (mesmas datas em todas as páginas — NÃO usado); prazos reais extraídos do corpo da página ("encerra-se em", "Após as 17h do dia") ou do cronograma no PDF do edital ("Encerramento do prazo..."). Filtro de ano ≥ 2025 descarta datas velhas do rodapé (2022/2024).
- **SETEC** (`crawler/parsers/setec.py`): data de publicação via **metadados de criação do PDF** do edital (novo `crawler/pdf_utils.py` com pypdf + fallback regex), downloads concorrentes (semáforo 5).
- **Resultado**: FAPESB **20/20 com data** (7/20 com prazo); SETEC **29/53 com data** (restante = PDFs com link morto 404 no gov.br). Registros FAPESB antigos em CAIXA ALTA sem data removidos (sósias com data).
- Testes: parser FAPESB reescrito (httpx mock); 43 passando.

### Sessão 03/08 (tarde) — fix links FINEP

- **Problema**: links das chamadas FINEP apontavam para o padrão antigo `finep.gov.br/oportunidades#!/chamada-publica/{id}`; o site atual usa `finep.gov.br/e/chamada-publica/{siteId}/{id}`.
- **Parser** (`crawler/parsers/finep.py`): extrai o `siteId` do Liferay a partir da home (regex do template `href="/e/chamada-publica/{siteId}/${item.id}"`), com fallback `222684` (valor atual). Teste do link adicionado (17 testes de parser passando).
- **Banco**: 36 links FINEP migrados para o novo formato (uid recalculado para manter o dedup); exports regenerados. Links validados (HTTP 200).

### Sessão 03/08 (tarde) — remoção da EMBRAPII

- **Decisão do usuário**: EMBRAPII fora do escopo do scraper.
- Removidos: entrada do `SOURCES` (`crawler/config.py`), arquivo `crawler/parsers/embrapii.py`, testes do parser (46 passando), 29 registros do banco e menções em `README.md`, `fontes.md`, `AGENTS.md`.
- Exports regenerados: 561 registros → **231 grupos** (consolidados).

### Sessão 03/08 (tarde) — consolidação de editais

- **Objetivo**: um edital aparecia várias vezes na lista (duplicatas do mesmo PDF em páginas de programa + atualizações: alteração, retificação, prorrogação, lista de inscritos).
- **Novo módulo `crawler/consolidate.py`**: identifica o edital por instituição + tipo (edital, edital conjunto, chamada...) + número/ano, extrai o assunto e agrupa:
  - deduplica títulos idênticos (mesmo doc em várias páginas);
  - agrupa documentos relacionados sob o edital núcleo (o principal é o próprio edital, preferindo o com data mais antiga);
  - separa colisões reais de número (ex.: "Edital nº 5/2026" PURDUE vs "Edital Conjunto nº 5/2026" OBEDUC);
  - títulos sem número ficam sozinhos.
- **Exports** (raiz): `editais.csv/xlsx` agora com colunas Instituição, Título, Data de Lançamento, Prazo, Link, **Documentos** (contagem) e **Documentos Relacionados** (título | link ; ...). `editais.html` ganhou coluna **Documentos** com seletor expansível (`<details>`) listando os relacionados. Contagem dos badges reflete grupos, não registros.
- **Flag** `--no-consolidate` em `main.py` para exportar a lista completa.
- **Banco**: 590 registros → **231 grupos** (59 com >1 documento) no momento da geração.
- **Testes**: `tests/test_consolidate.py` (+19); 48 passando.
- Obs.: crawl SETEC rodando em paralelo (outra sessão) alterou o banco durante a sessão — exports regenerados refletem o estado no momento da geração.

### Sessão 03/08 (tarde) — limpeza de resultados CAPES

- **Objetivo**: remover do CAPES os documentos que são apenas **resultados** de seleção (não são editais/oportunidades).
- **Parser** (`crawler/parsers/capes.py`): `_ANNEX_KEYWORDS` ganhou `resultado` e `homologa` — filtra títulos como "Resultado final do Edital nº ...", "Resultado preliminar", "Retificação do Resultado", "Edital nº X - Resultado da Renovação de Projetos", "Lista de inscrições homologadas" etc.
- **Banco**: 221 registros CAPES removidos (215 com "resultado" + 6 "Lista de inscrições homologadas") — CAPES 654 → 433; total 1253 → 1032.
- Exports regenerados (`editais.csv`, `editais.xlsx`, `editais.html`).

### Sessão 03/08 (tarde) — dados de lançamento + CNPq novo

- **Objetivo do usuário**: página com oportunidades recentes de financiamento p/ IFBA, com **data de lançamento** na planilha.
- **Export**: coluna "Data de Lançamento" adicionada ao CSV/XLSX; HTML com coluna Lançamento, destaque de recentes (≤60 dias) e filtro 30/60/90 dias; ordenação por recência.
- **CNPq migrou do Liferay para o portal gov.br**: `https://www.gov.br/cnpq/pt-br/chamadas/abertas-para-submissao`. Parser reescrito: 10 chamadas abertas com "Publicado em" (data) e "Inscrições" (prazo). Removida duplicata antiga (PROAFRICA via memoria2).
- **FINEP**: data de publicação extraída da API (`dataDePublicacao`) — 36/36 preenchidos.
- **CAPES**: site não expõe datas no HTML; extração via data no nome do arquivo SEI (`DDMMYYYY_...`) — 256/654. PDFs não são baixáveis direto (gov.br serve HTML).
- **FAPESB/SETEC**: não publicam datas de lançamento (campos vazios na listagem e na página do edital).
- **`add_opportunity_with_result`**: em caso de duplicata, preenche datas vazias do registro existente (UPDATE via COALESCE).
- Teste do CNPq atualizado (mock por seletor).

#### SETEC — reparo em 03/08

- Site MEC aplica **CAPTCHA intermitente** ("human visitor") — `_goto_with_retry` reescrito com 6 tentativas, espera crescente (8–48s) e detecção de bloqueio.
- Estrutura da página mudou: links de ano agora em `.../secretaria-de-educacao-profissional/editais/2026` (antes `/centrais-de-conteudo/editais/2026`) — seletor atualizado.
- PDFs agora são links diretos `a[href*=".pdf"]` (antes `a[href*="/editais/pdf/"]`) — seletor atualizado.
- Título contextual quando o link é vago ("Edital", "(documento Nº ...)") — usa texto do item pai.
- Filtro de anexos (anexo/modelo/termo de autorização) — não são editais.
- Resultado: 344 itens / 301 novos capturados (2026 → anterior-a-2021).
- Obs.: 151 registros antigos (16/06) são de outra seção (SESU/UNESCO, ex. TR_21_2026_SV_914Brz1102) — mantidos como complemento; títulos são nomes de arquivo.

### Sessões anteriores (03/08)

- Ambiente restaurado (playwright/pandas/numpy corrompidos); `main.py` com bootstrap de `sys.path`.
- CAPES/CNPq/BNDES/MCTI reparados; 150 registros-lixo do MCTI removidos.

### Distribuição — exe Windows (03/08, noite)

- **Objetivo**: outras pessoas (nível técnico zero) rodarem e gerarem suas tabelas — exe Windows com duplo clique.
- **Playwright ELIMINADO**: todas as fontes funcionam com httpx puro. Parsers reescritos: cnpq, mcti, setec → httpx+BS4 (fapesb/capes/finep já eram). Exe sem browser (~30 MB, sem `playwright install`).
- **`crawler/http_utils.py`** (novo): `fetch_text` com retry/backoff + detecção de CAPTCHA ("human visitor").
- **`crawler/gui.py`** (novo): interface tkinter — botão "Gerar Editais", escolha de pasta, log de progresso; grava ao lado do exe.
- **`scraper_exe.spec`** (novo): PyInstaller onefile, windowed, `collect_submodules('crawler')`.
- **CI `build-windows`**: gera `GeradorEditais.exe` como artifact a cada push na main.
- **CLI**: `main()` (entry point funcional), `--output-dir`; scripts `scraper-oportunidades` e `gerador-editais-gui`.
- **pyproject**: deps corretas (httpx, bs4, pandas, openpyxl, pypdf; sem playwright).
- Testes: +5 (http_utils); parsers atualizados p/ httpx. 47 passando.

### SETEC — reparo em 04/08

- [x] **SETEC — parser refeito** (URL: `gov.br/mec/pt-br/.../secretaria-de-educacao-profissional/editais`):
  - Parser reescrito: extrai **blocos de edital** (título `<p>` + lista de anexos `<ul>`) em vez de cada PDF como registro. 495 registros → **53 editais** com títulos completos e link do PDF principal.
  - `_clean_title`: remove sufixos de navegação ("Acesse o edital", "accessibility-anchor"), anexos/resultados concatenados e duplicação de número — preservando títulos legítimos (ex.: "art. 13, Anexo I, do Decreto").
  - Link principal: usa o link do PDF no título, senão o link "Edital"/"Chamada" da lista de anexos; ignora links de retificação/anexo/modelo.
  - CAPTCHA intermitente do gov.br/MEC contornado com retry + detecção (6 tentativas, espera crescente).
  - Obs.: SETEC não publica datas de lançamento — campo vazio.
- [x] **MCTI**: ~~CAPTCHA intermitente~~ — na verdade a página passou a exigir **login gov.br** (302 → `require_login`); parser **removido** do sistema em 04/08/2026 (ver sessão acima).
- [x] **FAPESB**: datas de lançamento resolvidas via API REST do WordPress (campo `date`).

### Sessão de 03/08/2026 — o que foi feito

- [x] **Ambiente restaurado**: `playwright`, `pandas`, `numpy` estavam corrompidos no site-packages (só `dist-info`, sem os arquivos). Reinstalados do zero + `playwright install chromium`.
- [x] **`crawler/main.py`**: faltava bootstrap de `sys.path` — `python crawler/main.py` falhava com `ModuleNotFoundError`.
- [x] **CAPES**: site mudou (sem `.tile-content`). `_get_program_urls` agora seleciona `a[href*="acoes-e-programas"]` direto + scrape de PDFs diretos da página principal. 0 → 365 itens.
- [x] **CNPq**: seletor `a.btn[alt="Chamada"]` não existe mais. Reescrito para `ol.list-chamadas li`, link construído via `idDivulgacao` (URL descodificada do link de share). Só 1 chamada aberta hoje (PROAFRICA).
- [x] **BNDES**: página antiga de chamadas públicas retorna 404 (site reestruturado). Parser captura cards de destaque da home (`a[href*="urile"]` + `figcaption h2`). 0 → 3 itens.
- [x] **MCTI**: parser capturava apenas ruído de menu/rodapé (todos os 150 registros eram lixo — nunca pegou um edital real). Reescrito para `main a[href]` + `ul.submenu.navTree a[href]` com filtro por `edital|chamada|editais|in.gov.br`. 150 registros-lixo removidos do banco.
- [x] Testes atualizados (BNDES e MCTI) para as novas interfaces.
- [x] `crawler/config.py`: URLs informativas corrigidas (CAPES, CONFAP, BNDES) + descrição FINEP.
- [x] `requirements.txt`: adicionados `httpx`, `beautifulsoup4`, `pytest`, `pytest-asyncio`.
- [x] Exports regenerados (`editais.csv`, `editais.xlsx`, `editais.html`).
- [x] README.md atualizado (citava apenas FINEP + CNPq).

## Log de execuções

| Data | Fonte(s) | Resultado |
|---|---|---|
| 16/06/2026 | todas | 647 registros; CNPq/BNDES/CAPES zerados; MCTI só ruído |
| 03/08/2026 | todas | 1050 → 900 após limpeza MCTI; CAPES 365, CNPq 1, BNDES 3; SETEC/MCTI bloqueados por CAPTCHA |
| 03/08/2026 | CAPES | 221 resultados de seleção removidos (CAPES 654 → 433; total 1253 → 1032) |
| 03/08/2026 | exports | Consolidação: 590 registros → 231 grupos (59 multi-documento) |
| 03/08/2026 | FINEP | 36 links migrados para /e/chamada-publica/{siteId}/{id} (antes oportunidades#!/...) |
| 03/08/2026 | CONFAP | Removida do sistema (só notícias, sem editais) — 8 registros apagados |
| 03/08/2026 | BNDES | Removida do sistema — 3 registros apagados |
| 03/08/2026 | SETEC/FAPESB | Datas de publicação: FAPESB 20/20 (REST WP), SETEC 29/53 (metadados PDF); prazos FAPESB 7/20 |
| 03/08/2026 | banco | Excluídos 328 registros < 2025 (550 → 224; 2026=153, 2025=71) |
| 04/08/2026 | todas | Crawl completo ao vivo: processed=360, new=2 (CNPq), erros=1 (CAPES); banco 432 → **434** |
| 04/08/2026 | MCTI | **Removido do sistema** — página de editais atrás de login gov.br (302 → require_login); 0 registros no banco |
| 05/08/2026 | deploy | Repo público + Pages no ar; Sobre em pop-up e identidade IFBA/NPP no HTML |
| 06/08 a 31/08/2026 | todas (Actions) | Crawl diário automático: 33 execuções, 32 verdes (1 timeout de deploy em 06/08); banco 434 → **475** |
| 31/08/2026 | todas | processed=375, new=0, duplicates=375, erros=0; db_total=**475** (CAPES 346, SETEC 56, FINEP 38, FAPESB 20, CNPq 15) |

## Fonte de referência

- Guia de fontes: `fontes.md`
- Fontes registradas em `crawler/config.py` (ordem: CAPES, CNPq, FINEP, FAPESB, SETEC)
