"""Generates SYNTHETIC fixtures (shape follows public write-ups; not captured from the live site)."""
import json, pathlib
d = pathlib.Path(__file__).parent
def page(ads):
    data = {"props": {"pageProps": {"searchData": {"ads": ads}}}}
    return f'<html><body><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></body></html>'
ad = lambda i, **k: {"list_id": i, "subject": f"Nikon D{i}", "price": [50 + i], "url": f"https://www.leboncoin.fr/ad/photo_audio_video/{i}",
                     "location": {"city": "Paris"}, "first_publication_date": "2026-11-01 10:00:00", "category_name": "Photo", **k}
(d/"page1.html").write_text(page([ad(1), ad(2), ad(1), {"list_id": 3, "subject": "  Sans   prix ", "url": "/ad/photo_audio_video/3"}]))
(d/"page2.html").write_text(page([ad(2), ad(4)]))
(d/"page_empty.html").write_text(page([]))
(d/"cards.html").write_text('<html><body><a href="/ad/informatique/77?x=1" title="Mac"><p>1 299 €</p></a></body></html>')
(d/"challenge.html").write_text("<html><body>Please enable JS and disable any ad blocker</body></html>")
