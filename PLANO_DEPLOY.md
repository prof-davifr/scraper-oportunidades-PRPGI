# Plano — Repositório público + crawl diário + GitHub Pages

**Data:** 04/08/2026
**Objetivo:** disponibilizar o scraper para a PRPGI/IFBA com atualização automática diária e página HTML pública, 100% gratuito (GitHub).

## Decisões (confirmadas com o usuário)

1. **Repositório público** `github.com/prof-davifr/scraper-oportunidades-PRPGI` — Pages grátis; dados de editais são públicos.
2. **Banco SQLite persiste** no repo (comitado a cada rodada) — preserva histórico e dedup (434 registros acumulados).
3. **Crawl diário via GitHub Actions** (cron 11:00 UTC = 08:00 BRT) + rodada manual (`workflow_dispatch`) + rodada a cada push na `main`.
4. **HTML público via GitHub Pages** — `https://prof-davifr.github.io/scraper-oportunidades-PRPGI/`.

## Arquitetura

```
cron (11:00 UTC) ─┐
push na main ─────┼─► GitHub Actions (ubuntu) ─► python crawler/main.py --force-export
workflow_dispatch ┘        │
                           ├─► git commit + push: oportunidades.db, editais.csv/xlsx/html (histórico persiste)
                           └─► upload-pages-artifact ─► deploy-pages ─► github.io/scraper-oportunidades-PRPGI
```

## Tarefas

- [x] Remoção do MCTI (sessão anterior — commitado no monorepo)
- [x] `PLANO_DEPLOY.md` salvo (este arquivo)
- [x] **Mover o projeto** do monorepo `PRPGI/` para `~/projetos/repos-independentes/` preservando histórico (`git subtree split` — 10 commits)
- [x] Criar repo público `scraper-oportunidades-PRPGI` no GitHub e push
- [x] Habilitar GitHub Pages (source = GitHub Actions) via API
- [x] `crawler/main.py`: flag `--force-export` (exporta mesmo com `new=0`, essencial com banco persistido)
- [x] `.gitignore`: remover `oportunidades.db` / `editais.*` do ignore (banco e exports passam a ser versionados)
- [x] Limpar resíduos `crawler/oportunidades.db` e `crawler/editais.*` (base antiga de março, 14 registros)
- [x] `.github/workflows/crawl.yml`: agendamento + commit-back + Pages
- [x] `ci.yml`: corrigir job `test` (remove `playwright install chromium` — playwright não é mais dependência; usa `python -m pytest`)
- [x] **CI verde**: ruff limpo (line-length 120, ignores PT-BR/typing moderno, formato unificado) — lint, test e build-windows passando
- [x] `http_utils.py`: mais resiliência para IP de datacenter (5 tentativas, timeout 60s)
- [x] README.md: seção "Acesso público" com URL do Pages
- [x] AGENTS.md: documentar pipeline de deploy e estado do CI
- [x] TODO.md: registrar a sessão de deploy
- [x] Testes: `pytest` (46) + crawls reais validados no GitHub Actions (2 rodadas ok)
- [x] Monorepo `PRPGI/`: remover pasta, atualizar `AGENTS.md` e commit
- [x] Push dos dois repos (scraper + monorepo) e verificação final (Pages no ar, workflow ok)

## Riscos / mitigações

| Risco | Mitigação |
|---|---|
| gov.br/finep bloqueiam IP do runner (datacenter Azure) | retry automático (5 tentativas, timeout 60s); `workflow_dispatch` p/ rodada manual; **banco persistido garante que o site nunca perde dados** (rodada parcial mantém último estado); IP do runner rotaciona entre rodadas |
| Export pulado com banco persistido (`new=0`) | flag `--force-export` implementado neste plano |
| Pages exige repo público no plano free | repo será público (decisão do usuário) |
| Push do bot não re-dispara workflows | comportamento padrão do `GITHUB_TOKEN` — sem loop infinito |
| DB grande no git | ~700 KB hoje, deltas comprimidos; crescimento lento (registros novos/dia) |

## Resultado (04/08)

- Repo público: `github.com/prof-davifr/scraper-oportunidades-PRPGI`
- Pages no ar: `https://prof-davifr.github.io/scraper-oportunidades-PRPGI/` (HTTP 200; index + editais.xlsx + editais.csv)
- CI verde: lint, test, build-windows ✓
- 2 crawls de validação no Actions: rodada 1 completa (todas as fontes), rodada 2 parcial (4/5 com ConnectTimeout do gov.br — retry/backoff atualizados para mitigar)
- Commit-back automático funcionando (chore: crawl 2026-08-05)
- Banco persistido no repo (696 KB, 434 registros)
