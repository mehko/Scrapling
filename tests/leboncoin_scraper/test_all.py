import pathlib
import pytest
from scrapling.parser import Selector
from leboncoin_scraper import cli, extractors as ex, scraper
from leboncoin_scraper.models import BlockedError, ExtractionError, FetchError
from leboncoin_scraper.urls import build_search_url, resolve_category, with_page

FX = pathlib.Path(__file__).parent / "fixtures"
sel = lambda n: Selector((FX / n).read_text(), url="https://www.leboncoin.fr/recherche")


class FakePage:
    def __init__(self, name=None, status=200, body=None):
        html = body if body is not None else (FX / name).read_text()
        self.status, self.body, self._sel = status, html.encode(), Selector(html)
    def css(self, *a, **k): return self._sel.css(*a, **k)


class FakeSession:
    def __init__(self, items): self.items, self.calls = list(items), []
    def get(self, url):
        self.calls.append(url); it = self.items.pop(0)
        if isinstance(it, Exception): raise it
        return it


# urls
def test_url_encoding_and_params():
    u = build_search_url("nikon d'été", "Informatique", 2)
    assert u == "https://www.leboncoin.fr/recherche?text=nikon+d%27%C3%A9t%C3%A9&category=15&page=2"
    assert "page" not in build_search_url("x")
    assert with_page(u, 3).endswith("&page=3") and "category=15" in with_page(u, 3)
    assert "page" not in with_page(u, 1)

def test_categories():
    assert resolve_category("42") == "42" and resolve_category(None) is None
    with pytest.raises(ValueError): resolve_category("inconnue")
    with pytest.raises(ValueError): build_search_url("  ")
    with pytest.raises(ValueError): build_search_url("a", page=0)


# extractors
@pytest.mark.parametrize("v,exp", [(1299, 1299.0), ([80], 80.0), ("1 299 €", 1299.0), ("1.299,50 €", 1299.5),
                                   ("12,5", 12.5), ("gratuit", None), (None, None), ([], None)])
def test_price(v, exp): assert ex.normalize_price(v) == exp

def test_url():
    assert ex.normalize_url("/ad/a/1?x=2#f") == "https://www.leboncoin.fr/ad/a/1"
    assert ex.normalize_url(None) is None

def test_json_extraction_and_missing_fields():
    ls = ex.extract_listings(sel("page1.html"), "photo")
    assert len(ls) == 4
    full, bare = ls[0], ls[3]
    assert (full.id, full.title, full.price, full.currency, full.location) == ("1", "Nikon D1", 51.0, "EUR", "Paris")
    assert bare.title == "Sans prix" and bare.price is None and bare.currency is None and bare.location is None
    assert bare.url == "https://www.leboncoin.fr/ad/photo_audio_video/3" and bare.category == "photo"

def test_html_fallback():
    (l,) = ex.extract_listings(sel("cards.html"))
    assert (l.id, l.price, l.url, l.title) == ("77", 1299.0, "https://www.leboncoin.fr/ad/informatique/77", "Mac")

def test_dedupe():
    seen = set()
    assert len(ex.dedupe(ex.extract_listings(sel("page1.html")), seen)) == 3
    assert len(ex.dedupe(ex.extract_listings(sel("page1.html")), seen)) == 0

def test_challenge_detection():
    assert ex.is_challenge(403, "") and ex.is_challenge(429, "")
    assert ex.is_challenge(200, (FX / "challenge.html").read_text())
    assert not ex.is_challenge(200, (FX / "page1.html").read_text())


# pagination / errors
def run(items, pages=3, **kw):
    s = FakeSession(items)
    return scraper.scrape("nikon", None, pages, 0, 5, session=s, sleep=lambda _: None, **kw), s

def test_pagination_dedupes_across_pages():
    res, s = run([FakePage("page1.html"), FakePage("page2.html"), FakePage("page_empty.html")])
    assert [r.id for r in res] == ["1", "2", "3", "4"] and len(s.calls) == 3

def test_stops_on_empty_page_and_limit():
    res, s = run([FakePage("page_empty.html")])
    assert res == [] and len(s.calls) == 1
    res, s = run([FakePage("page1.html"), FakePage("page2.html")], pages=1)
    assert len(s.calls) == 1 and len(res) == 3

def test_stops_when_no_new_results():
    res, s = run([FakePage("page1.html"), FakePage("page1.html")])
    assert len(s.calls) == 2 and len(res) == 3

def test_blocked_and_challenge_200():
    with pytest.raises(BlockedError): run([FakePage("challenge.html", status=403)])
    with pytest.raises(BlockedError): run([FakePage("challenge.html", status=200)])

def test_transient_retry_then_success_and_giveup():
    res, s = run([FakePage("page1.html", status=503), OSError("dns"), FakePage("page_empty.html")], pages=1)
    assert res == [] and len(s.calls) == 3
    with pytest.raises(FetchError): run([FakePage("page1.html", status=500)] * 3)
    with pytest.raises(FetchError): run([FakePage("page1.html", status=404)])

def test_unparseable_markup_is_error_not_empty():
    with pytest.raises(ExtractionError):
        run([FakePage(body='<script id="__NEXT_DATA__" type="application/json">{"props":{}}</script><a href="/ad/x/zz">y</a>')])


# cli
def test_cli_validation(capsys):
    for argv in (["-q", " "], ["-q", "a", "-p", "0"], ["-q", "a", "-p", "999"], ["-q", "a", "--delay", "-1"], ["-q", "a", "-c", "zz"]):
        with pytest.raises(SystemExit) as e: cli.parse_args(argv)
        assert e.value.code == 2

def test_cli_dry_run_stdout_is_pure_json(capsys):
    assert cli.main(["-q", "a b", "-p", "2", "--dry-run"]) == 0
    out = capsys.readouterr()
    assert out.out.strip() == "[]" and "page=2" in out.err

def test_cli_output_and_exit_codes(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "scrape", lambda *a, **k: ex.extract_listings(sel("page1.html")))
    f = tmp_path / "o.json"
    assert cli.main(["-q", "a", "--output", str(f)]) == 0
    import json; assert json.loads(capsys.readouterr().out) == json.loads(f.read_text()) and len(json.loads(f.read_text())) == 4
    def boom(*a, **k): raise BlockedError("x")
    monkeypatch.setattr(cli, "scrape", boom)
    assert cli.main(["-q", "a"]) == 3 and capsys.readouterr().out == ""
