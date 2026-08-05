"""Consolidação de editais.

Agrupa os documentos que pertencem a um mesmo edital (o edital em si +
atualizações: alteração, retificação, prorrogação, resultado, listas de
inscritos etc.) em uma única entrada, e deduplica documentos iguais listados
em páginas diferentes (caso comum no portal da CAPES).

A identificação é feita por: instituição + tipo do documento ("edital",
"edital conjunto", "chamada", ...) + número/ano (ex.: 05/2024). Títulos sem
número detectável são agrupados apenas por título normalizado.
"""

import re
import unicodedata
from collections import Counter
from typing import Any

# ---------------------------------------------------------------------------
# Normalização de título
# ---------------------------------------------------------------------------

# Sufixos de tamanho/formato típicos dos portais: ", formato, pdf, 62kb",
# "- pdf, 91kb", ", formato - pdf, 143kb", ", pdf 748kb", ", formato, pdf, 8,5kb".
_SIZE_RE = re.compile(
    r"[,;\-–—]?\s*(?:formato\s*[,;\-–—]?\s*)?(?:pdf|docx?|planilha|xlsx?|odt|zip)?"
    r"(?:[,;\-–—]?\s*[\d.,]+\s*(?:kb|mb|gb)\s*(?:df)?)?\s*$",
    re.I,
)


def normalize_title(title: str) -> str:
    """Minúsculas, sem acentos, espaços colapsados e sem sufixo de tamanho."""
    s = unicodedata.normalize("NFKD", title)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    prev = None
    while prev != s:
        prev = s
        s = _SIZE_RE.sub("", s)
    s = re.sub(r"[,;\-–—\s]+$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---------------------------------------------------------------------------
# Referência do edital: (tipo, número, ano)
# ---------------------------------------------------------------------------

_KIND_SPECS: list[tuple[str, str]] = [
    ("edital_conjunto", r"edital\s+conjunto"),
    ("edital", r"edital"),
    ("chamada_publica", r"chamada\s+p[úu]blica"),
    ("chamamento_publico", r"chamamento\s+p[úu]blico"),
    ("chamada", r"chamada"),
    ("chamamento", r"chamamento"),
    ("carta_convite", r"carta\s+convite"),
    ("aviso", r"aviso"),
]
_KIND_RE = re.compile("|".join(f"(?P<{k}>{p})" for k, p in _KIND_SPECS), re.I)
_NUM_EXPLICIT_RE = re.compile(r"n[º°oª]?\.?\s*(\d{1,4})\s*/\s*(\d{4})", re.I)
_NUM_BARE_RE = re.compile(r"\s*(\d{1,4})\s*/\s*(\d{4})")


def _kind_before(norm: str, end: int) -> str:
    """Palavra-chave de tipo mais próxima (última) antes da posição `end`.

    Ex.: em "Chamada nº 25 do Edital nº 14/2022" o número é do EDITAL, não da
    chamada — o tipo correto é o último antes do número.
    """
    kms = list(_KIND_RE.finditer(norm[:end]))
    return kms[-1].lastgroup if kms else "edital"


def _bare_number_after_kind(norm: str, kmatch) -> re.Match | None:
    window = norm[kmatch.end() : kmatch.end() + 12]
    m = _NUM_BARE_RE.match(window)
    if m and m.start() <= 3:
        return m
    return None


def extract_ref(title: str) -> tuple[str, str, str] | None:
    """Retorna (tipo, número, ano) quando o título tem número de edital.

    Aceita "Edital nº 05/2024", "Edital 27/2024", "EDITAL 009/2026",
    "Chamada Pública 01/2016", "Nº 24/2026" etc. Retorna None caso contrário.
    """
    norm = normalize_title(title)

    # 1) número explícito com "nº" (pode aparecer após o nome do programa)
    m = _NUM_EXPLICIT_RE.search(norm)
    if m:
        kind = _kind_before(norm, m.start())
        return (kind, m.group(1).lstrip("0") or "0", m.group(2))

    # 2) número "cru" logo após uma palavra-chave ("Edital 1/2026",
    #    "Chamada nª 20 do Edital 14/2022"): procura em todas as ocorrências
    #    de palavra-chave e usa a primeira que tiver número na sequência.
    for km in _KIND_RE.finditer(norm):
        m = _bare_number_after_kind(norm, km)
        if m:
            return (km.lastgroup, m.group(1).lstrip("0") or "0", m.group(2))

    return None


def extract_subject(title: str) -> str:
    """Texto após o número do edital (normalizado), vazio quando inexistente."""
    norm = normalize_title(title)
    m = _NUM_EXPLICIT_RE.search(norm)
    if m:
        return norm[m.end() :].strip(" -–—,;").strip()
    for km in _KIND_RE.finditer(norm):
        m = _bare_number_after_kind(norm, km)
        if m:
            return norm[km.end() + m.end() :].strip(" -–—,;").strip()
    return norm


# ---------------------------------------------------------------------------
# Classificação: documento principal (edital) vs. documento relacionado
# ---------------------------------------------------------------------------

_RELATED_PREFIXES = (
    "alteração",
    "alteracao",
    "retificação",
    "retificacao",
    "prorrogação",
    "prorrogacao",
    "suspensão",
    "suspensao",
    "reabertura",
    "resultado",
    "homologa",
    "lista de inscritos",
    "lista de inscrições",
    "lista das inscrições",
    "lista das inscricoes",
    "relação",
    "relacao",
    "republicação",
    "republicacao",
    "anexo",
    "comunicado",
    "aditivo",
    "errata",
    "esclarecimento",
    "cronograma",
    "orientações",
    "orientacoes",
    "adesão",
    "adesao",
    "termo",
    "formulário",
    "formulario",
    "modelo",
    "declaração",
    "declaracao",
)

# Marcadores que podem aparecer no assunto (após o número) indicando documento
# relacionado: "… – RESULTADO FINAL", "… - Retificado", "… - Lista de inscritos".
_SUBJECT_RELATED_STARTS = (
    "resultado",
    "lista",
    "relação",
    "relacao",
    "retificad",
    "alterad",
    "homologa",
    "anexo",
    "aviso de",
)


def is_related_doc(title: str) -> bool:
    """True quando o título indica um documento que não é o edital em si
    (alteração, resultado, lista de inscritos, anexo, retificação etc.)."""
    norm = normalize_title(title)
    if norm.startswith(_RELATED_PREFIXES):
        return True
    ref = extract_ref(title)
    if ref:
        subj = extract_subject(title)
        return subj.startswith(_SUBJECT_RELATED_STARTS)
    return False


# ---------------------------------------------------------------------------
# Agrupamento
# ---------------------------------------------------------------------------

# Palavras que marcam assunto "variante" (retificado, resultado etc.): quando o
# assunto de um documento é só isso, ele não forma grupo próprio — herda o
# assunto dominante do edital.
_VARIANT_WORDS = (
    "retificad",
    "alterad",
    "prorrogad",
    "suspens",
    "reabertur",
    "resultado",
    "homologa",
    "republicad",
    "comunicad",
    "anexo",
    "adesao",
    "adesão",
    "termo",
    "lista",
    "relacao",
    "relação",
    "cronograma",
    "errata",
    "esclarecimento",
    "aviso",
    "orienta",
    "formulario",
    "formulário",
    "modelo",
    "declar",
)


def _is_variant_marker(subject: str) -> bool:
    s = subject.lower()
    if len(s) <= 12:
        return True
    return any(w in s for w in _VARIANT_WORDS)


def _jaccard(a: str, b: str) -> float:
    wa = set(re.findall(r"[a-z0-9]+", a))
    wb = set(re.findall(r"[a-z0-9]+", b))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _primary_key(u: dict[str, Any]) -> tuple:
    pub = u.get("publication_date") or ""
    return (
        u["_related"],  # edital principal antes de documentos relacionados
        0 if pub else 1,  # com data de publicação primeiro
        pub,  # a mais antiga (a original) primeiro
        -len(u["_subject"]),  # título com assunto mais descritivo primeiro
        u.get("id") or 0,
    )


def _date_ordinal(value: str) -> tuple[int, int, int]:
    """Converte ISO (YYYY-MM-DD) ou DD/MM/YYYY em tupla ordenável."""
    s = (value or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        return (int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return (0, 0, 0)


def consolidate_editais(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agrupa registros de um mesmo edital.

    Args:
        rows: lista de dicts com as chaves institution, title, link,
            publication_date, deadline, description e opcionalmente id.

    Returns:
        Lista de grupos consolidados:
            {
                "institution", "title", "link", "publication_date", "deadline",
                "description", "docs_count", "latest_date",
                "related": [{"title", "link", "publication_date"}, ...]
            }
    """
    # 1) deduplica títulos idênticos (mesmo documento listado em várias páginas)
    units: list[dict[str, Any]] = []
    seen = set()
    for r in sorted(rows, key=lambda r: r.get("id") or 0):
        norm = normalize_title(r.get("title", ""))
        key = (r.get("institution", ""), norm)
        if key in seen:
            continue
        seen.add(key)
        unit = dict(r)
        unit["_norm"] = norm
        unit["_ref"] = extract_ref(r.get("title", ""))
        unit["_subject"] = extract_subject(r.get("title", "")) or ""
        unit["_related"] = is_related_doc(r.get("title", ""))
        units.append(unit)

    # 2) agrupa por referência (instituição, tipo, número, ano)
    by_ref: dict[tuple, list[dict]] = {}
    for u in units:
        if u["_ref"]:
            by_ref.setdefault((u["institution"],) + u["_ref"], []).append(u)

    final_groups: list[list[dict]] = []
    for _, grp in by_ref.items():
        subs_all = [u["_subject"] for u in grp if u["_subject"]]
        subs_core = [s for s in subs_all if not _is_variant_marker(s)]
        pool = subs_core or subs_all
        canon = Counter(pool).most_common(1)[0][0] if pool else ""

        if not canon:
            final_groups.append(grp)
            continue

        # separa colisões reais de número (dois editais distintos com nº igual):
        # assunto muito diferente do dominante e "substantivo" forma grupo próprio.
        subgroups: dict[str, list[dict]] = {}
        for u in grp:
            s = u["_subject"]
            if not s or _is_variant_marker(s) or _jaccard(s, canon) >= 0.3:
                subgroups.setdefault(canon, []).append(u)
            else:
                subgroups.setdefault(s, []).append(u)
        final_groups.extend(subgroups.values())

    # grupos sem número detectável: ficam sozinhos (título já deduplicado)
    for u in units:
        if not u["_ref"]:
            final_groups.append([u])

    # 3) escolhe o documento principal e monta a saída
    consolidated = []
    for grp in final_groups:
        primary = min(grp, key=_primary_key)
        related = [u for u in grp if u is not primary]
        related.sort(
            key=lambda u: (
                _date_ordinal(u.get("publication_date") or ""),
                u.get("id") or 0,
            )
        )
        sort_date = max(
            (u.get("publication_date") or "" for u in grp),
            key=_date_ordinal,
        )
        consolidated.append(
            {
                "institution": primary["institution"],
                "title": primary["title"],
                "link": primary["link"],
                "publication_date": primary.get("publication_date") or "",
                "deadline": primary.get("deadline") or "",
                "description": primary.get("description") or "",
                "docs_count": len(grp),
                "latest_date": sort_date,
                "related": [
                    {
                        "title": u["title"],
                        "link": u["link"],
                        "publication_date": u.get("publication_date") or "",
                    }
                    for u in related
                ],
            }
        )

    # 4) ordena: mais recentes primeiro; sem data por último
    consolidated.sort(
        key=lambda g: (
            0 if g["latest_date"] else 1,
            tuple(-x for x in _date_ordinal(g["latest_date"])),
            g["institution"],
            g["title"].lower(),
        )
    )
    return consolidated
