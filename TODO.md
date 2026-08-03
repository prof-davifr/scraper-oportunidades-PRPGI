# TODO — scraper-oportunidades-PRPGI

Scraper de editais de fomento à pesquisa (CAPES, CNPq, FINEP, FAPESB, SETEC, CONFAP, EMBRAPII, BNDES, MCTI).

_Última atualização: 03/08/2026_

## Estado atual

- Crawl completo: **03/08/2026** — **900 registros** no `oportunidades.db` (após limpeza de 150 registros-lixo do MCTI)
- Distribuição no banco:
  - CAPES 654 · SETEC 151 · FINEP 36 · EMBRAPII 29 · FAPESB 18 · CONFAP 8 · BNDES 3 · CNPq 1
  - **MCTI: 0** (todos os 150 registros antigos eram ruído de menu/rodapé; parser corrigido, mas site está com CAPTCHA)
- Todos os 29 testes passam (`python -m pytest`).

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
