"""Search URL construction and category resolution."""

from __future__ import annotations

from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

BASE_URL = "https://www.leboncoin.fr"
SEARCH_PATH = "/recherche"

# Category name -> numeric id used by the ``category=`` query parameter.
# NOT verified live (the site was unreachable from the dev environment, see
# README). Numeric ids are always accepted, so users can pass any id they
# confirmed in their own browser. Extend this table only with confirmed ids.
CATEGORIES: dict[str, str] = {
    "informatique": "15",
    "voitures": "2",
    "ventes immobilieres": "9",
    "locations": "10",
}


def _fold(value: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).strip().lower()


def resolve_category(category: Optional[str]) -> Optional[str]:
    """Return the numeric category id, or raise ``ValueError`` if unknown."""
    if category is None:
        return None
    value = category.strip()
    if value.isdigit():
        return value
    key = _fold(value)
    if key in CATEGORIES:
        return CATEGORIES[key]
    known = ", ".join(sorted(CATEGORIES))
    raise ValueError(f"Unknown category {category!r}. Known names: {known}; or pass a numeric category id.")


def build_search_url(query: str, category: Optional[str] = None, page: int = 1) -> str:
    """Build a Leboncoin search URL (``text``, ``category``, ``page`` parameters)."""
    if not query or not query.strip():
        raise ValueError("query must not be empty")
    if page < 1:
        raise ValueError("page must be >= 1")
    params = [("text", query.strip())]
    category_id = resolve_category(category)
    if category_id:
        params.append(("category", category_id))
    if page > 1:
        params.append(("page", str(page)))
    return f"{BASE_URL}{SEARCH_PATH}?{urlencode(params)}"


def with_page(url: str, page: int) -> str:
    """Return ``url`` with only its ``page`` parameter changed (others preserved)."""
    parts = urlsplit(url)
    params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "page"]
    if page > 1:
        params.append(("page", str(page)))
    return urlunsplit(parts._replace(query=urlencode(params)))
