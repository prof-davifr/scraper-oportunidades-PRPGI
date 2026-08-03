# TODO — scraper-oportunidades-PRPGI

Scraper de editais de fomento à pesquisa (CAPES, CNPq, FINEP, FAPESB, SETEC, CONFAP, EMBRAPII, BNDES, MCTI).

_Última atualização: 03/08/2026 (sessão: dados de lançamento + CNPq no novo site)_

## Estado atual

- Crawl completo: **03/08/2026** — **1253 registros** no `oportunidades.db`
- Distribuição no banco:
  - CAPES 654 · SETEC 495 · FINEP 36 · EMBRAPII 29 · FAPESB 18 · CONFAP 8 · CNPq 10 · BNDES 3
  - **MCTI: 0** (parser corrigido, aguardando site liberar do CAPTCHA)
- **302 registros com data de lançamento** (CNPq 10/10, FINEP 36/36, CAPES 256/654)
- Todos os 29 testes passam (`python -m pytest`).

## Foco: FAPESB, CNPq, FINEP, CAPES, SETEC-MEC

| Instituição | Registros | Estado | Última captura |
|---|---|---|---|
| CAPES | 654 | ✅ consistente; 256 com data de lançamento | 03/08 |
| SETEC | 495 | ⏳ **a refazer** (ver pendências) | 03/08 |
| FINEP | 36 | ✅ consistente; 36/36 com data | 03/08 |
| FAPESB | 18 | ✅ consistente (sem datas — site não publica) | 03/08 |
| CNPq | 10 | ✅ **migrado para o novo site** (gov.br) — 10/10 com data | 03/08 |

## Sessão 03/08 (tarde) — dados de lançamento + CNPq novo

- **Objetivo do usuário**: página com oportunidades recentes de financiamento p/ IFBA, com **data de lançamento** na planilha.
- **Export**: coluna "Data de Lançamento" adicionada ao CSV/XLSX; HTML com coluna Lançamento, destaque de recentes (≤60 dias) e filtro 30/60/90 dias; ordenação por recência.
- **CNPq migrou do Liferay para o portal gov.br**: `https://www.gov.br/cnpq/pt-br/chamadas/abertas-para-submissao`. Parser reescrito: 10 chamadas abertas com "Publicado em" (data) e "Inscrições" (prazo). Removida duplicata antiga (PROAFRICA via memoria2).
- **FINEP**: data de publicação extraída da API (`dataDePublicacao`) — 36/36 preenchidos.
- **CAPES**: site não expõe datas no HTML; extração via data no nome do arquivo SEI (`DDMMYYYY_...`) — 256/654. PDFs não são baixáveis direto (gov.br serve HTML).
- **FAPESB/SETEC**: não publicam datas de lançamento (campos vazios na listagem e na página do edital).
- **`add_opportunity_with_result`**: em caso de duplicata, preenche datas vazias do registro existente (UPDATE via COALESCE).
- Teste do CNPq atualizado (mock por seletor).

### SETEC — reparo em 03/08

- Site MEC aplica **CAPTCHA intermitente** ("human visitor") — `_goto_with_retry` reescrito com 6 tentativas, espera crescente (8–48s) e detecção de bloqueio.
- Estrutura da página mudou: links de ano agora em `.../secretaria-de-educacao-profissional/editais/2026` (antes `/centrais-de-conteudo/editais/2026`) — seletor atualizado.
- PDFs agora são links diretos `a[href*=".pdf"]` (antes `a[href*="/editais/pdf/"]`) — seletor atualizado.
- Título contextual quando o link é vago ("Edital", "(documento Nº ...)") — usa texto do item pai.
- Filtro de anexos (anexo/modelo/termo de autorização) — não são editais.
- Resultado: 344 itens / 301 novos capturados (2026 → anterior-a-2021).
- Obs.: 151 registros antigos (16/06) são de outra seção (SESU/UNESCO, ex. TR_21_2026_SV_914Brz1102) — mantidos como complemento; títulos são nomes de arquivo.

## Sessões anteriores (03/08)

- Ambiente restaurado (playwright/pandas/numpy corrompidos); `main.py` com bootstrap de `sys.path`.
- CAPES/CNPq/BNDES/MCTI reparados; 150 registros-lixo do MCTI removidos.

## Pendências

- [ ] **SETEC — REFAZER** (URL: `gov.br/mec/pt-br/.../secretaria-de-educacao-profissional/editais`): os 495 registros atuais têm títulos inconsistentes (nomes de arquivo, anexos) e sem datas. Reavaliar escopo: focar em 2025-2026, melhorar títulos, buscar datas (páginas de ano têm "Atualizado em").
- [ ] **MCTI**: CAPTCHA intermitente — parser corrigido aguardando o site liberar para validar.
- [ ] **CAPES**: 398/654 sem data (nome de arquivo sem DDMMYYYY). Explorar extração do texto do PDF via navegador (gov.br serve HTML para httpx).
- [ ] **FAPESB**: não publica datas — avaliar se o campo "LANÇAMENTO:" é preenchido em algum edital.
- [ ] **Ruff/CI**: 116 erros de lint pré-existentes — decidir limpeza ou ajuste do CI.
- [ ] `pyproject.toml` dependencies desatualizadas (faltam httpx/bs4; entry point `main` inexistente).

## Sessão de 03/08/2026 — o que foi feito

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

## Pendências

- [ ] **SETEC**: `gov.br/mec` bloqueado por CAPTCHA anti-bot ("human visitor" + 429/403). Parser retorna 0. Reavaliar quando o bloqueio cair.
- [ ] **MCTI**: site com CAPTCHA intermitente (rate-limit por IP). Parser corrigido e aguardando o site voltar para validar captura real.
- [ ] **Ruff/CI**: codebase tem 116 erros de lint pré-existentes (`ruff check .` falha). Decidir se vale limpar ou ajustar config do CI.
- [ ] `pyproject.toml` dependencies desatualizadas (não incluem httpx/bs4; `main` não existe como entry point — verificar `[project.scripts]`).

## Log de execuções

| Data | Fonte(s) | Resultado |
|---|---|---|
| 16/06/2026 | todas | 647 registros; CNPq/BNDES/CAPES zerados; MCTI só ruído |
| 03/08/2026 | todas | 1050 → 900 após limpeza MCTI; CAPES 365, CNPq 1, BNDES 3; SETEC/MCTI bloqueados por CAPTCHA |

## Fonte de referência

- Guia de fontes: `fontes.md`
- Fontes registradas em `crawler/config.py` (ordem: CAPES, CNPq, FINEP, FAPESB, SETEC, CONFAP, EMBRAPII, BNDES, MCTI)
