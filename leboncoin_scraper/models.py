"""Data models and exceptions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass
class Listing:
    id: Optional[str]
    title: Optional[str]
    price: Optional[float]
    currency: Optional[str]
    location: Optional[str]
    published_at: Optional[str]
    url: Optional[str]
    category: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ScraperError(Exception):
    """Base class; ``exit_code`` is used by the CLI."""

    exit_code = 1


class BlockedError(ScraperError):
    """Access refused (403/429, anti-bot challenge). Never retried or bypassed."""

    exit_code = 3


class FetchError(ScraperError):
    """Network failure or persistent 5xx."""

    exit_code = 4


class ExtractionError(ScraperError):
    """Page looks like a results page but no listing could be extracted."""

    exit_code = 5
