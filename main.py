"""ATS Job Automator — CLI entry point.

Usage:
    python main.py scrape                     # All scrapers (6 APIs + Google Dorks)
    python main.py scrape --lever             # Only Lever
    python main.py scrape --greenhouse        # Only Greenhouse
    python main.py scrape --ashby             # Only Ashby
    python main.py scrape --smartrecruiters   # Only SmartRecruiters
    python main.py scrape --recruitee         # Only Recruitee
    python main.py scrape --workable          # Only Workable
    python main.py scrape --dorks             # Only Google Dorks (Playwright)
    python main.py list                       # Show all offers
    python main.py list --status PENDING      # Filter by status
    python main.py stats                      # Summary statistics
    python main.py export --format csv        # Export to CSV
    python main.py export --format json       # Export to JSON
"""

import argparse
import asyncio
import logging
import sys

from rich.console import Console
from rich.table import Table

from config import APP_ENV, LOG_LEVEL
from database import (
    get_all_offers,
    get_offers_summary,
    init_db,
    insert_offer,
)
from parser import classify_job
from src.scraper import ALL_SCRAPERS

console = Console()


# ─── Logging setup ───────────────────────────────────────────────────────────

def _setup_logging() -> None:
    """Configure structured logging with level from config."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


logger = logging.getLogger(__name__)


# ─── Scrape command ──────────────────────────────────────────────────────────

async def _run_api_scrapers(platforms: list[str]) -> int:
    """Run the specified API scrapers and persist results.

    Args:
        platforms: List of platform names to scrape.

    Returns:
        Total number of new offers inserted.
    """
    total_inserted = 0
    total_found = 0

    for platform_name in platforms:
        scraper_cls = ALL_SCRAPERS.get(platform_name)
        if not scraper_cls:
            console.print(f"[red]Unknown platform: {platform_name}[/red]")
            continue

        scraper = scraper_cls()
        try:
            jobs = await scraper.scrape_all()
            total_found += len(jobs)

            for job in jobs:
                classification = classify_job(job["title"], job["url"])
                work_modality = classification.work_modality
                if classification.geo_scope != "UNKNOWN":
                    work_modality = f"{work_modality}_{classification.geo_scope}"

                try:
                    insert_offer(
                        company_name=job["company"],
                        job_title=job["title"],
                        url=job["url"],
                        ats_type=job.get("ats_type", platform_name),
                        location=job.get("location"),
                        work_modality=work_modality,
                        status="PENDING",
                    )
                    total_inserted += 1
                except Exception:
                    pass  # Duplicate or invalid — already logged by database module

        except Exception:
            logger.exception("Error running %s scraper", platform_name)

    return total_inserted


async def _run_google_dorks() -> int:
    """Run the Google Dorks scraper (Playwright).

    Returns:
        Total number of new offers inserted.
    """
    from scraper import run_scraper
    result = await run_scraper()
    return result.get("total_inserted", 0)


def cmd_scrape(args: argparse.Namespace) -> None:
    """Handle the 'scrape' subcommand."""
    init_db()

    # Determine which platforms to scrape
    platforms_to_run: list[str] = []
    run_dorks = False

    platform_flags = {
        "lever": args.lever,
        "greenhouse": args.greenhouse,
        "ashby": args.ashby,
        "smartrecruiters": args.smartrecruiters,
        "recruitee": args.recruitee,
        "workable": args.workable,
    }

    any_flag = any(platform_flags.values()) or args.dorks

    if not any_flag:
        # No flags = run everything
        platforms_to_run = list(ALL_SCRAPERS.keys())
        run_dorks = True
    else:
        platforms_to_run = [name for name, flag in platform_flags.items() if flag]
        run_dorks = args.dorks

    console.print()
    console.rule("[bold cyan]ATS Job Automator — Scraping[/bold cyan]")
    console.print()

    total_inserted = 0

    # Run API scrapers
    if platforms_to_run:
        console.print(
            f"[bold]Scraping {len(platforms_to_run)} API platforms:[/bold] "
            f"{', '.join(platforms_to_run)}"
        )
        api_inserted = asyncio.run(_run_api_scrapers(platforms_to_run))
        total_inserted += api_inserted
        console.print(f"[green]API scrapers: {api_inserted} new offers inserted[/green]")

    # Run Google Dorks
    if run_dorks:
        console.print("[bold]Running Google Dorks (Playwright)...[/bold]")
        dork_inserted = asyncio.run(_run_google_dorks())
        total_inserted += dork_inserted
        console.print(f"[green]Google Dorks: {dork_inserted} new offers inserted[/green]")

    console.print()
    console.rule(f"[bold green]Total: {total_inserted} new offers[/bold green]")
    console.print()


# ─── List command ────────────────────────────────────────────────────────────

def cmd_list(args: argparse.Namespace) -> None:
    """Handle the 'list' subcommand."""
    offers = get_all_offers(status=args.status)

    if not offers:
        console.print("[yellow]No offers found.[/yellow]")
        return

    table = Table(
        title=f"Job Offers ({len(offers)} results)",
        show_lines=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="dim", width=5, justify="right")
    table.add_column("Company", style="bold", max_width=20)
    table.add_column("Title", max_width=35)
    table.add_column("ATS", width=15)
    table.add_column("Location", max_width=20)
    table.add_column("Modality", width=15)
    table.add_column("Status", width=10, justify="center")
    table.add_column("Date", width=12)

    status_colors = {
        "PENDING": "yellow",
        "APPLIED": "green",
        "FAILED": "red",
        "SKIPPED": "dim",
    }

    for offer in offers:
        status = offer.get("status", "")
        color = status_colors.get(status, "white")
        created = offer.get("created_at", "")[:10]

        table.add_row(
            str(offer.get("id", "")),
            offer.get("company_name", ""),
            offer.get("job_title", ""),
            offer.get("ats_type", ""),
            offer.get("location", "") or "-",
            offer.get("work_modality", "") or "-",
            f"[{color}]{status}[/{color}]",
            created,
        )

    console.print()
    console.print(table)
    console.print()


# ─── Stats command ───────────────────────────────────────────────────────────

def cmd_stats(args: argparse.Namespace) -> None:
    """Handle the 'stats' subcommand."""
    summary = get_offers_summary()
    total = sum(summary.values())

    console.print()
    console.rule("[bold cyan]Offers Summary[/bold cyan]")
    console.print()

    table = Table(header_style="bold cyan")
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")

    status_colors = {
        "PENDING": "yellow",
        "APPLIED": "green",
        "FAILED": "red",
        "SKIPPED": "dim",
    }

    for status, count in sorted(summary.items()):
        color = status_colors.get(status, "white")
        pct = f"{(count / total * 100):.1f}%" if total > 0 else "0.0%"
        table.add_row(f"[{color}]{status}[/{color}]", str(count), pct)

    table.add_row("[bold]TOTAL[/bold]", f"[bold]{total}[/bold]", "[bold]100%[/bold]")

    console.print(table)
    console.print()


# ─── Export command ──────────────────────────────────────────────────────────

def cmd_export(args: argparse.Namespace) -> None:
    """Handle the 'export' subcommand."""
    from exporter import export_csv, export_json

    fmt = args.format.lower()
    status_filter = args.status

    if fmt == "csv":
        filepath = export_csv(status_filter=status_filter)
    elif fmt == "json":
        filepath = export_json(status_filter=status_filter)
    else:
        console.print(f"[red]Unknown format: {fmt}. Use 'csv' or 'json'.[/red]")
        return

    console.print(f"[green]Exported to: {filepath}[/green]")


# ─── Argument Parser ─────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="ATS Job Automator — Multi-portal job scraper with DevSecOps architecture.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scrape
    scrape_parser = subparsers.add_parser("scrape", help="Scrape job offers from ATS portals")
    scrape_parser.add_argument("--lever", action="store_true", help="Scrape Lever only")
    scrape_parser.add_argument("--greenhouse", action="store_true", help="Scrape Greenhouse only")
    scrape_parser.add_argument("--ashby", action="store_true", help="Scrape Ashby only")
    scrape_parser.add_argument("--smartrecruiters", action="store_true", help="Scrape SmartRecruiters only")
    scrape_parser.add_argument("--recruitee", action="store_true", help="Scrape Recruitee only")
    scrape_parser.add_argument("--workable", action="store_true", help="Scrape Workable only")
    scrape_parser.add_argument("--dorks", action="store_true", help="Run Google Dorks (Playwright)")
    scrape_parser.set_defaults(func=cmd_scrape)

    # list
    list_parser = subparsers.add_parser("list", help="List job offers")
    list_parser.add_argument("--status", type=str, default=None, help="Filter by status (PENDING, APPLIED, FAILED, SKIPPED)")
    list_parser.set_defaults(func=cmd_list)

    # stats
    stats_parser = subparsers.add_parser("stats", help="Show summary statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # export
    export_parser = subparsers.add_parser("export", help="Export offers to CSV or JSON")
    export_parser.add_argument("--format", type=str, required=True, choices=["csv", "json"], help="Export format")
    export_parser.add_argument("--status", type=str, default=None, help="Filter by status")
    export_parser.set_defaults(func=cmd_export)

    return parser


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    """CLI entry point."""
    _setup_logging()
    logger.info("ATS Job Automator [env=%s, log_level=%s]", APP_ENV, LOG_LEVEL)

    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
