from __future__ import annotations

import importlib
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class Source:
    """Registry entry for a parser source."""
    name: str
    module: str
    class_name: str
    url: str
    description: str = ""


@dataclass
class Settings:
    """Application settings and sources registry."""

    # Paths
    db_path: str = str(PROJECT_ROOT / "oportunidades.db")
    csv_path: str = str(PROJECT_ROOT / "editais.csv")
    xlsx_path: str = str(PROJECT_ROOT / "editais.xlsx")
    html_path: str = str(PROJECT_ROOT / "editais.html")
    log_file: str | None = None

    # Retry / network
    retry_attempts: int = 3
    retry_base_delay: float = 1.0
    page_timeout: int = 30000
    navigation_wait: str = "domcontentloaded"

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s %(levelname)s %(name)s - %(message)s"

    # Parser defaults
    default_max_items: int | None = None

    # Sources registry — each entry maps a CLI name to a parser class location
    SOURCES: list[Source] = field(default_factory=lambda: [
        Source(
            name="capes",
            module="crawler.parsers.capes",
            class_name="CapesParser",
            url="https://www.gov.br/capes/pt-br/acesso-a-informacao/acoes-a-programas/bolsas/editais",
            description="Coordenação de Aperfeiçoamento de Pessoal de Nível Superior (CAPES)",
        ),
        Source(
            name="cnpq",
            module="crawler.parsers.cnpq",
            class_name="CnpqParser",
            url="http://memoria2.cnpq.br/web/guest/chamadas-publicas",
            description="Conselho Nacional de Desenvolvimento Científico e Tecnológico (CNPq)",
        ),
        Source(
            name="finep",
            module="crawler.parsers.finep",
            class_name="FinepParser",
            url="http://www.finep.gov.br/chamadas-publicas/chamadaspublicas?situacao=aberta",
            description="Fundação de Amparo à Pesquisa do Estado de Minas Gerais (FINEP)",
        ),
        Source(
            name="fapesb",
            module="crawler.parsers.fapesb",
            class_name="FapesbParser",
            url="https://www.fapesb.ba.gov.br/category/edital/",
            description="Fundação de Amparo à Pesquisa do Estado da Bahia (FAPESB)",
        ),
        Source(
            name="setec",
            module="crawler.parsers.setec",
            class_name="SetecParser",
            url="https://www.gov.br/mec/pt-br/acesso-a-informacao/institucional/estrutura-organizacional/orgaos-especificos-singulares/secretaria-de-educacao-profissional/editais",
            description="Secretaria de Educação Profissional e Tecnológica (SETEC/MEC)",
        ),
        Source(
            name="confap",
            module="crawler.parsers.confap",
            class_name="ConfapParser",
            url="https://confap.org.br/news/category/chamadas/",
            description="Conselho Nacional das Fundações Estaduais de Amparo à Pesquisa (CONFAP)",
        ),
        Source(
            name="embrapii",
            module="crawler.parsers.embrapii",
            class_name="EmbrapiiParser",
            url="https://embrapii.org.br/editais-e-chamadas/",
            description="Embrapii — Empresa Brasileira de Pesquisa e Inovação Industrial",
        ),
        Source(
            name="bndes",
            module="crawler.parsers.bndes",
            class_name="BndesParser",
            url="https://www.bndes.gov.br/wps/portal/site/home/onde-atuamos/inovacao/chamadas-publicas",
            description="Banco Nacional de Desenvolvimento Econômico e Social (BNDES)",
        ),
        Source(
            name="mcti",
            module="crawler.parsers.mcti",
            class_name="MctiParser",
            url="https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/editais-concursos-e-chamadas-publicas",
            description="Ministério da Ciência, Tecnologia e Inovação (MCTI)",
        ),
    ])

    def source_names(self) -> list[str]:
        """Return list of registered source names."""
        return [s.name for s in self.SOURCES]

    def get_source(self, name: str) -> Source:
        """Look up a source by name."""
        for s in self.SOURCES:
            if s.name == name:
                return s
        raise KeyError(f"Unknown source: {name!r}. Available: {self.source_names()}")

    def load_parser_class(self, source: Source) -> type:
        """Dynamically import and return the parser class for a Source."""
        mod: ModuleType = importlib.import_module(source.module)
        cls = getattr(mod, source.class_name)
        return cls

    def build_parser(self, name: str, max_items: int | None = None) -> Any:
        """Instantiate a parser by source name, passing max_items."""
        source = self.get_source(name)
        cls = self.load_parser_class(source)
        return cls(max_items=max_items)
