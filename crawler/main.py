import asyncio
import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawler.config import Settings
from crawler.database import OpportunityDatabase

logger = logging.getLogger(__name__)


def _normalize_result(result: Any, institution: str) -> Dict[str, int | str]:
    if isinstance(result, int):
        return {
            "institution": institution,
            "processed": result,
            "new": result,
            "duplicates": 0,
            "errors": 0,
        }
    if isinstance(result, dict):
        return {
            "institution": str(result.get("institution", institution)),
            "processed": int(result.get("processed", 0)),
            "new": int(result.get("new", 0)),
            "duplicates": int(result.get("duplicates", 0)),
            "errors": int(result.get("errors", 0)),
        }
    raise ValueError(f"Unsupported parser result type: {type(result)!r}")


def _build_parsers(
    settings: Settings, selected_parser: str, max_items: Optional[int]
) -> list:
    if selected_parser == "all":
        return [
            settings.build_parser(name, max_items)
            for name in settings.source_names()
        ]
    return [settings.build_parser(selected_parser, max_items)]


async def run_crawler(
    selected_parser: str = "all",
    max_items: Optional[int] = None,
    settings: Optional[Settings] = None,
    no_consolidate: bool = False,
) -> None:
    if settings is None:
        settings = Settings()

    logger.info("Starting crawler...")

    db = OpportunityDatabase(settings.db_path)
    parsers = _build_parsers(settings, selected_parser, max_items)

    run_results: list[Dict[str, int | str]] = []
    for parser in parsers:
        logger.info("Running parser for %s...", parser.institution)
        try:
            raw_result = await parser.parse(db, max_items=max_items)
            result = _normalize_result(raw_result, parser.institution)
            run_results.append(result)

            logger.info(
                "%s: processed=%s, new=%s, duplicates=%s, errors=%s",
                result["institution"],
                result["processed"],
                result["new"],
                result["duplicates"],
                result["errors"],
            )

            if int(result["processed"]) == 0:
                logger.warning(
                    "%s returned zero records (site instability may be affecting the crawl).",
                    result["institution"],
                )
        except Exception as e:
            logger.exception("Error running parser for %s: %s", parser.institution, e)
            run_results.append(
                {
                    "institution": getattr(parser, "institution", "unknown"),
                    "processed": 0,
                    "new": 0,
                    "duplicates": 0,
                    "errors": 1,
                }
            )

    total_new = sum(int(result["new"]) for result in run_results)
    total_duplicates = sum(int(result["duplicates"]) for result in run_results)
    total_errors = sum(int(result["errors"]) for result in run_results)
    total_processed = sum(int(result["processed"]) for result in run_results)

    should_export = total_new > 0 or not Path(settings.xlsx_path).exists()
    if should_export:
        logger.info("Exporting to spreadsheet...")
        exported_csv, exported_xlsx = db.export_to_spreadsheet(
            settings.csv_path, settings.xlsx_path, consolidate=not no_consolidate
        )
        logger.info("Spreadsheets updated: %s, %s", exported_csv, exported_xlsx)

        logger.info("Exporting to HTML...")
        exported_html = db.export_to_html(settings.html_path, consolidate=not no_consolidate)
        logger.info("HTML updated: %s", exported_html)
    else:
        logger.info("No new opportunities found; keeping existing exports.")

    logger.info("Run summary:")
    for result in run_results:
        logger.info(
            "- %s | processed=%s new=%s duplicates=%s errors=%s",
            result["institution"],
            result["processed"],
            result["new"],
            result["duplicates"],
            result["errors"],
        )

    logger.info(
        "Total | processed=%s new=%s duplicates=%s errors=%s db_total=%s",
        total_processed,
        total_new,
        total_duplicates,
        total_errors,
        db.get_total_count(),
    )
    logger.info("Crawler finished.")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    settings = Settings()
    parser = argparse.ArgumentParser(
        description="Scrape open editais from multiple Brazilian funding agencies."
    )
    parser.add_argument(
        "--parser",
        choices=["all"] + settings.source_names(),
        default="all",
        help="Parser to run (default: all).",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Optional maximum number of page items to process per parser.",
    )
    parser.add_argument(
        "--no-consolidate",
        action="store_true",
        help="Export sem consolidação (uma linha por documento, incluindo duplicatas e atualizações).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Diretório onde os arquivos de saída (db/csv/xlsx/html) serão gravados. Padrão: raiz do projeto.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=settings.db_path,
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "--csv-path",
        type=str,
        default=settings.csv_path,
        help="Path for CSV output.",
    )
    parser.add_argument(
        "--xlsx-path",
        type=str,
        default=settings.xlsx_path,
        help="Path for Excel output.",
    )
    parser.add_argument(
        "--html-path",
        type=str,
        default=settings.html_path,
        help="Path for HTML output.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=settings.log_level,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> None:
    """Entry point da CLI (usado pelo comando instalado `scraper-oportunidades`)."""
    args = parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    if args.output_dir:
        out = Path(args.output_dir).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        db_path = str(out / "oportunidades.db")
        csv_path = str(out / "editais.csv")
        xlsx_path = str(out / "editais.xlsx")
        html_path = str(out / "editais.html")
    else:
        db_path = args.db_path
        csv_path = args.csv_path
        xlsx_path = args.xlsx_path
        html_path = args.html_path

    settings = Settings(
        db_path=db_path,
        csv_path=csv_path,
        xlsx_path=xlsx_path,
        html_path=html_path,
        log_level=args.log_level,
    )
    asyncio.run(
        run_crawler(
            selected_parser=args.parser,
            max_items=args.max_items,
            settings=settings,
            no_consolidate=args.no_consolidate,
        )
    )


if __name__ == "__main__":
    main()