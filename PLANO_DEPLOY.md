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
- [ ] `PLANO_DEPLOY.md` salvo (este arquivo)
- [ ] **Mover o projeto** do monorepo `PRPGI/` para `~/projetos/repos-independentes/` preservando histórico (`git subtree split`)
- [ ] Criar repo público `scraper-oportunidades-PRPGI` no GitHub e push
- [ ] Habilitar GitHub Pages (source = GitHub Actions) via API
- [ ] `crawler/main.py`: flag `--force-export` (exporta mesmo com `new=0`, essencial com banco persistido)
- [ ] `.gitignore`: remover `oportunidades.db` / `editais.*` do ignore (banco e exports passam a ser versionados)
- [ ] Limpar resíduos `crawler/oportunidades.db` e `crawler/editais.*` (base antiga de março, 14 registros)
- [ ] `.github/workflows/crawl.yml`: agendamento + commit-back + Pages
- [ ] `ci.yml`: corrigir job `test` (remove `playwright install chromium` — playwright não é mais dependência)
- [ ] README.md: seção "Acesso público" com URL do Pages
- [ ] AGENTS.md: documentar pipeline de deploy e estado do CI
- [ ] TODO.md: registrar a sessão de deploy
- [ ] Testes: `pytest` + crawl completo local com `--force-export`
- [ ] Monorepo `PRPGI/`: remover pasta, atualizar `AGENTS.md` e commit
- [ ] Push dos dois repos (scraper + monorepo) e verificação final (Pages no ar, workflow ok)

## Riscos / mitigações

| Risco | Mitigação |
|---|---|
| gov.br/finep bloqueiam IP do runner (datacenter Azure) | retry automático já existe; `workflow_dispatch` p/ rodada manual; aceitar resultado parcial (fontes saudáveis: CAPES, CNPq, FINEP, FAPESB) |
| Export pulado com banco persistido (`new=0`) | flag `--force-export` implementado neste plano |
| Pages exige repo público no plano free | repo será público (decisão do usuário) |
| Push do bot não re-dispara workflows | comportamento padrão do `GITHUB_TOKEN` — sem loop infinito |
| DB grande no git | ~700 KB hoje, deltas comprimidos; crescimento lento (registros novos/dia) |
