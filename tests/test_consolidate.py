from crawler.consolidate import (
    consolidate_editais,
    extract_ref,
    is_related_doc,
    normalize_title,
)


def _row(title, inst="CAPES", link="https://example.com/x", pub="", id=1):
    return {
        "id": id,
        "institution": inst,
        "title": title,
        "description": "",
        "link": link,
        "publication_date": pub,
        "deadline": "",
    }


class TestNormalizeTitle:
    def test_strips_size_suffix(self):
        assert normalize_title("Edital nº 05/2024 - Programa X, formato, pdf, 62kb") == (
            "edital no 05/2024 - programa x"
        )

    def test_strips_pdf_suffix(self):
        assert normalize_title("Edital nº 05/2024 - Programa X - pdf, 91kb") == ("edital no 05/2024 - programa x")

    def test_strips_accents_and_case(self):
        assert normalize_title("Alteração do Edital nº 07/2026 - CAPES/Cofecub") == (
            "alteracao do edital no 07/2026 - capes/cofecub"
        )


class TestExtractRef:
    def test_explicit_numero(self):
        assert extract_ref("Edital nº 05/2024 - Programa CAPES/CLIMAT-AMSUD") == (
            "edital",
            "5",
            "2024",
        )

    def test_bare_number_after_kind(self):
        assert extract_ref("EDITAL 009/2026 – APOIO A ORGANIZAÇÃO DE EVENTOS") == (
            "edital",
            "9",
            "2026",
        )

    def test_edital_conjunto(self):
        assert extract_ref("Edital Conjunto nº 5/2026 - Programa OBEDUC-EI") == (
            "edital_conjunto",
            "5",
            "2026",
        )

    def test_last_kind_wins(self):
        # "Chamada nº 25" é a chamada; o número do edital é o 14/2022
        assert extract_ref("Lista de Inscritos - Chamada nº 25 do Edital nº 14/2022") == (
            "edital",
            "14",
            "2022",
        )

    def test_bare_number_after_second_kind(self):
        assert extract_ref("Chamada nª 20 do Edital 14/2022") == (
            "edital",
            "14",
            "2022",
        )

    def test_chamada_publica(self):
        assert extract_ref("Chamada Pública 01/2016 – RESULTADO FINAL") == (
            "chamada_publica",
            "1",
            "2016",
        )

    def test_no_number_returns_none(self):
        assert extract_ref("SEBRAE lança chamada 2026-2027 para apoiar projetos de inovação") is None
        assert extract_ref("Edital de Cinema 2026") is None


class TestIsRelatedDoc:
    def test_prefix_related(self):
        assert is_related_doc("Alteração do Edital nº 07/2026 - CAPES/Cofecub")
        assert is_related_doc("Resultado final do Edital nº 05/2024 - CAPES/CLIMAT-AMSUD")

    def test_subject_related(self):
        assert is_related_doc("Chamada Pública 01/2016 – RESULTADO FINAL")
        assert is_related_doc("Edital nº 44/2012 - Retificado")

    def test_core_not_related(self):
        assert not is_related_doc("Edital nº 05/2024 - Programa CAPES/CLIMAT-AMSUD")


class TestConsolidate:
    def test_duplicate_titles_deduplicated(self):
        rows = [
            _row(
                "Edital nº 07/2026 - CAPES/Cofecub, formato, pdf, 545kb",
                link="https://a",
                id=1,
            ),
            _row(
                "Edital nº 07/2026 - CAPES/Cofecub, formato, pdf, 545kb",
                link="https://b",
                id=2,
            ),
        ]
        groups = consolidate_editais(rows)
        assert len(groups) == 1
        assert groups[0]["docs_count"] == 1

    def test_related_docs_grouped_under_core(self):
        rows = [
            _row(
                "Alteração do Edital nº 07/2026 - CAPES/Cofecub, formato, pdf, 48kb",
                pub="2026-04-01",
                id=2,
            ),
            _row(
                "Edital nº 07/2026 - CAPES/Cofecub, formato, pdf, 545kb",
                pub="2026-02-10",
                id=1,
            ),
            _row(
                "Lista de inscritos no Edital n° 7/2026 - Programa CAPES/COFECUB, formato, pdf, 90kb",
                pub="2026-05-01",
                id=3,
            ),
        ]
        groups = consolidate_editais(rows)
        assert len(groups) == 1
        g = groups[0]
        assert g["docs_count"] == 3
        assert g["title"].startswith("Edital nº 07/2026")  # o principal é o edital núcleo
        assert len(g["related"]) == 2

    def test_number_collision_split_by_subject(self):
        rows = [
            _row(
                "Edital nº 5/2026 - Programa CAPES - PURDUE de Projetos conjuntos, formato, pdf, 257kb",
                id=1,
            ),
            _row(
                "Edital Conjunto nº 5/2026 - Programa OBEDUC-EI - Observatório da Educação Especial, formato, pdf, 80kb",
                id=2,
            ),
        ]
        groups = consolidate_editais(rows)
        assert len(groups) == 2  # edital ≠ edital conjunto

    def test_no_number_stays_separate(self):
        rows = [
            _row(
                "SEBRAE lança chamada 2026-2027 para apoiar projetos de inovação",
                inst="SEBRAE",
                id=1,
            ),
            _row("Chamada de Acesso a Crédito para Inovação", inst="FINEP", id=2),
        ]
        groups = consolidate_editais(rows)
        assert len(groups) == 2

    def test_different_institutions_never_merge(self):
        rows = [
            _row("Edital nº 05/2024 - Programa X", inst="CAPES", id=1),
            _row("Edital nº 05/2024 - Programa X", inst="FAPESB", id=2),
        ]
        groups = consolidate_editais(rows)
        assert len(groups) == 2

    def test_empty_subject_inherits_group(self):
        rows = [
            _row("Edital n° 14/2022 - formato, pdf, 380kb", pub="2022-01-01", id=1),
            _row(
                "Lista de Inscritos no Edital nº 14/2022 do Programa CAPES/Humboldt",
                pub="2022-03-01",
                id=2,
            ),
            _row(
                "Alteração do Edital n° 14/2022 - formato, pdf, 49kb",
                pub="2022-02-01",
                id=3,
            ),
        ]
        groups = consolidate_editais(rows)
        assert len(groups) == 1
        assert groups[0]["docs_count"] == 3
        assert groups[0]["title"].startswith("Edital n° 14/2022")
