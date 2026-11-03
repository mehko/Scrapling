# leboncoin_scraper

CLI scraping public Leboncoin search results with Scrapling (`FetcherSession`, plain HTTP; Scrapling 0.4.7).

## Install
    pip install -e ".[fetchers]" pytest      # from the repo root

## Run
    python -m leboncoin_scraper -q "iphone 15" -p 2 --delay 3 --debug
    python -m leboncoin_scraper -q "macbook pro" -c informatique -o out.json
    python -m leboncoin_scraper -q "nikon" --dry-run      # prints URLs (stderr), no request

stdout = JSON array only; stderr = logs. Exit codes: 0 ok (zero results is still 0, logged),
2 bad arguments, 3 access blocked (403/429/challenge), 4 network/5xx, 5 page present but unparseable, 130 interrupted.

## Design
- Strategy A (`FetcherSession`): enough if results are in the returned HTML. No browser (`--headful` is accepted but ignored).
- Extraction order: embedded `script#__NEXT_DATA__` JSON (`props.pageProps.searchData.ads`), then `a[href*="/ad/"]` HTML cards. No generated CSS classes are used.
- Retries with exponential backoff on 5xx/network errors only. A 403/429 or anti-bot page (even with HTTP 200) stops the run with exit 3.
  **No captcha solving, challenge bypass or identity rotation is implemented, by design.**
- Pagination stops on: page limit, empty page, no new listings, block/error. Dedup by id, else normalized URL.

## Categories
`--category` takes a numeric id or a name from `urls.CATEGORIES` (accent/case-insensitive). The names listed there are **not verified live**; unknown names fail with an explicit error. Add only ids you confirmed in your browser.

## Tests
    python -m pytest tests/leboncoin_scraper -o addopts=""

## Validation status (honest)
- 24 offline tests pass. Fixtures in `tests/leboncoin_scraper/fixtures/` are **synthetic** (shape taken from public write-ups), not captured from the live site.
- Live test: a single plain request to leboncoin.fr from the dev environment returned **HTTP 403** ("Please enable JS and disable any ad blocker", a DataDome-style block). The scraper correctly stopped with exit 3. **Extraction against real pages has therefore never been verified**: field paths in `__NEXT_DATA__` and category ids may need adjusting on a network/browser the site accepts.
