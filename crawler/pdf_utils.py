"""Utilitários de PDF: extração de metadados (data de criação)."""

import re


def pdf_creation_date(data: bytes) -> str:
    """Data de criação do PDF (ISO YYYY-MM-DD) via metadados.

    Usada como aproximação da data de publicação do edital quando o portal
    não expõe a data (gov.br/SETEC, FAPESB). pypdf primeiro; fallback por
    regex nos bytes brutos do /CreationDate.
    """
    try:
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
        cd = getattr(reader.metadata, "creation_date", None)
        if cd:
            m = re.match(r"(\d{4}-\d{2}-\d{2})", str(cd))
            if m:
                return m.group(1)
    except Exception:
        pass
    m = re.search(rb"/CreationDate\s*\(D:(\d{4})(\d{2})(\d{2})", data)
    if m:
        return (
            f"{m.group(1).decode()}-{m.group(2).decode()}-{m.group(3).decode()}"
        )
    return ""
