"""Pagination loop on top of Scrapling's ``FetcherSession`` (plain HTTP, no stealth)."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

from .extractors import dedupe, extract_listings, is_challenge, looks_unparseable
from .models import BlockedError, ExtractionError, FetchError, Listing
from .urls import build_search_url

log = logging.getLogger(__name__)
TRANSIENT = {500, 502, 503, 504}


def make_session(timeout: int) -> Any:
    from scrapling.fetchers import FetcherSession

    # retries=1: network-level retries are handled by fetch_page, with backoff.
    return FetcherSession(timeout=timeout, retries=1)


def fetch_page(session: Any, url: str, retries: int = 2, backoff: float = 2.0,
               sleep: Callable[[float], None] = time.sleep) -> Any:
    """GET with limited retries on 5xx/network errors. 403/429 raise BlockedError immediately."""
    last: Optional[str] = None
    for attempt in range(retries + 1):
        try:
            page = session.get(url)
        except Exception as exc:  # curl_cffi / network errors
            last = f"{type(exc).__name__}: {exc}"
        else:
            body = page.body.decode("utf-8", "replace") if isinstance(page.body, bytes) else str(page.body)
            if is_challenge(page.status, body):
                raise BlockedError(
                    f"Access refused (HTTP {page.status}) on {url}: anti-bot challenge. "
                    "Collection stopped; no bypass is attempted."
                )
            if page.status in TRANSIENT:
                last = f"HTTP {page.status}"
            elif page.status >= 400:
                raise FetchError(f"HTTP {page.status} on {url}")
            else:
                return page
        if attempt < retries:
            delay = backoff * (2 ** attempt)
            log.warning("Transient failure (%s), retry %d/%d in %.1fs", last, attempt + 1, retries, delay)
            sleep(delay)
    raise FetchError(f"Giving up on {url}: {last}")


def scrape(query: str, category: Optional[str], pages: int, delay: float, timeout: int,
           session: Any = None, sleep: Callable[[float], None] = time.sleep) -> list[Listing]:
    """Scrape up to ``pages`` result pages; stops on empty/no-new page or block."""
    ctx = make_session(timeout) if session is None else None
    seen: set[str] = set()
    results: list[Listing] = []
    try:
        if ctx is not None:
            session = ctx.__enter__()  # FetcherSession returns the client used for .get()
        for n in range(1, pages + 1):
            url = build_search_url(query, category, n)
            log.info("Page %d/%d: %s", n, pages, url)
            page = fetch_page(session, url, sleep=sleep)
            listings = extract_listings(page, category)
            if not listings:
                if looks_unparseable(page):
                    raise ExtractionError(f"Page {n} has ad markup but no listing could be parsed")
                log.info("Page %d has no results: end of pagination", n)
                break
            fresh = dedupe(listings, seen)
            log.info("Page %d: %d listings, %d new", n, len(listings), len(fresh))
            if not fresh:
                break
            results.extend(fresh)
            if n < pages and delay > 0:
                sleep(delay)
    finally:
        if ctx is not None:
            ctx.__exit__(None, None, None)
    return results
