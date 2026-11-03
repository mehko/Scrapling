"""Command-line interface. stdout: JSON only; stderr: logs."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional, Sequence

import orjson

from .models import ScraperError
from .scraper import scrape
from .urls import build_search_url, resolve_category

MAX_PAGES = 20


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="leboncoin_scraper", description="Scrape public Leboncoin search results.")
    p.add_argument("--query", "-q", required=True)
    p.add_argument("--category", "-c")
    p.add_argument("--pages", "-p", type=int, default=1)
    p.add_argument("--delay", type=float, default=3.0)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--headful", action="store_true", help="Accepted for compatibility; ignored (HTTP-only fetcher).")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--output")
    a = p.parse_args(argv)
    if not a.query.strip():
        p.error("--query must not be empty")
    if not 1 <= a.pages <= MAX_PAGES:
        p.error(f"--pages must be between 1 and {MAX_PAGES}")
    if a.delay < 0:
        p.error("--delay must not be negative")
    if a.timeout <= 0:
        p.error("--timeout must be positive")
    try:
        resolve_category(a.category)
    except ValueError as exc:
        p.error(str(exc))
    return a


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, stream=sys.stderr, force=True,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("leboncoin_scraper")
    if args.headful:
        log.warning("--headful has no effect: only the HTTP fetcher is used")
    if args.dry_run:
        for n in range(1, args.pages + 1):
            log.info("would fetch %s", build_search_url(args.query, args.category, n))
        sys.stdout.write("[]\n")
        return 0
    try:
        listings = scrape(args.query, args.category, args.pages, args.delay, args.timeout)
    except ScraperError as exc:
        log.error("%s: %s", type(exc).__name__, exc)
        return exc.exit_code
    except KeyboardInterrupt:
        log.error("Interrupted")
        return 130
    data = orjson.dumps([x.to_dict() for x in listings], option=orjson.OPT_INDENT_2).decode()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(data + "\n")
    sys.stdout.write(data + "\n")
    if not listings:
        log.info("Search completed with zero results")
    return 0


if __name__ == "__main__":
    sys.exit(main())
