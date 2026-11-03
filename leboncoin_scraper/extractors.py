"""Listing extraction from a search-results page.

Priority: (1) embedded JSON in ``script#__NEXT_DATA__`` (props.pageProps.searchData.ads),
(2) HTML fallback on ``a[href*="/ad/"]`` cards. CSS classes are never relied upon.
The JSON layout follows public write-ups and could NOT be re-checked live from the
dev environment (blocked), so every field access is defensive.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable, Optional
from urllib.parse import urljoin, urlsplit

import orjson

from .models import Listing

log = logging.getLogger(__name__)
BASE = "https://www.leboncoin.fr"
_AD_HREF = re.compile(r"/ad/[^/]+/(\d+)")
_CHALLENGE_MARKERS = ("captcha-delivery.com", "datadome", "enable js and disable any ad blocker")


def normalize_price(value: Any) -> Optional[float]:
    """Convert ``1299``, ``[1299]``, ``"1 299 €"``, ``"1.299,50 €"`` to float; else None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (list, tuple)):
        return normalize_price(value[0]) if value else None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^\d,.]", "", str(value).replace("\xa0", " "))
    if not text:
        return None
    if "," in text:  # French format: '.' thousands, ',' decimals
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "")
    try:
        return float(text)
    except ValueError:
        return None


def normalize_url(href: Optional[str]) -> Optional[str]:
    """Absolute URL without query/fragment; None if empty."""
    if not href:
        return None
    parts = urlsplit(urljoin(BASE, href.strip()))
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def is_challenge(status: int, body: str) -> bool:
    """True for 403/429 or any page carrying anti-bot challenge markers."""
    if status in (403, 429):
        return True
    low = body[:20000].lower()
    return any(m in low for m in _CHALLENGE_MARKERS)


def _clean(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text or None


def parse_listing(ad: dict[str, Any], requested_category: Optional[str] = None) -> Optional[Listing]:
    """Parse one JSON ad; returns None when neither id nor url is available."""
    if not isinstance(ad, dict):
        return None
    ad_id = ad.get("list_id") or ad.get("id")
    url = normalize_url(ad.get("url"))
    if ad_id is None and url:
        m = _AD_HREF.search(url)
        ad_id = m.group(1) if m else None
    if ad_id is None and url is None:
        return None
    loc = ad.get("location") if isinstance(ad.get("location"), dict) else {}
    price = normalize_price(ad.get("price"))
    if price is None and ad.get("price_cents") is not None:
        cents = normalize_price(ad.get("price_cents"))
        price = cents / 100 if cents is not None else None
    return Listing(
        id=str(ad_id) if ad_id is not None else None,
        title=_clean(ad.get("subject")),
        price=price,
        currency="EUR" if price is not None else None,
        location=_clean(loc.get("city_label") or loc.get("city")),
        published_at=_clean(ad.get("first_publication_date") or ad.get("index_date")),
        url=url,
        category=_clean(ad.get("category_name")) or requested_category,
    )


def _from_next_data(page: Any, requested_category: Optional[str]) -> Optional[list[Listing]]:
    raw = page.css("script#__NEXT_DATA__::text").get()
    if not raw:
        return None
    try:
        data = orjson.loads(str(raw))
        search = data["props"]["pageProps"]["searchData"]
    except (orjson.JSONDecodeError, KeyError, TypeError):
        log.warning("__NEXT_DATA__ present but searchData missing; falling back to HTML")
        return None
    ads = list(search.get("ads") or [])
    return [lst for lst in (parse_listing(a, requested_category) for a in ads) if lst]


def _from_html(page: Any, requested_category: Optional[str]) -> list[Listing]:
    out: list[Listing] = []
    for a in page.css('a[href*="/ad/"]'):
        href = a.attrib.get("href", "")
        m = _AD_HREF.search(href)
        if not m:
            continue
        title = _clean(a.attrib.get("title") or a.attrib.get("aria-label"))
        texts = [t for t in (_clean(x) for x in a.css("::text").getall()) if t]
        price = next((normalize_price(t) for t in texts if "€" in t), None)
        title = title or (texts[0] if texts else None)
        out.append(
            Listing(m.group(1), title, price, "EUR" if price is not None else None, None, None,
                    normalize_url(href), requested_category)
        )
    return out


def extract_listings(page: Any, requested_category: Optional[str] = None) -> list[Listing]:
    """Extract listings, preferring embedded JSON over HTML. May return an empty list."""
    listings = _from_next_data(page, requested_category)
    if listings is None:
        listings = _from_html(page, requested_category)
    return listings


def looks_unparseable(page: Any) -> bool:
    """True when an empty extraction is suspicious: ad links in the HTML, or embedded JSON lacking searchData."""
    if page.css('a[href*="/ad/"]'):
        return True
    raw = page.css("script#__NEXT_DATA__::text").get()
    if not raw:
        return False
    try:
        orjson.loads(str(raw))["props"]["pageProps"]["searchData"]
    except (orjson.JSONDecodeError, KeyError, TypeError):
        return True
    return False


def dedupe(listings: Iterable[Listing], seen: set[str]) -> list[Listing]:
    """Drop listings whose id (else normalized URL) is in ``seen``; updates ``seen``."""
    fresh = []
    for lst in listings:
        key = lst.id or lst.url
        if key is None or key in seen:
            continue
        seen.add(key)
        fresh.append(lst)
    return fresh
