"""Live IndiaMART search: a query -> the real product cards indiamart.com shows for it.

The desktop search (dir.indiamart.com/search.mp) renders its results from an internal API that refuses
outside IPs ("Source IP not allowed"). The mobile site (m.indiamart.com/isearch.php?s=...) is server-rendered
and embeds the same result list as JSON (`let mcatCardsData1 = [...]`), so we fetch that page with a phone
user agent and parse the JSON. Nothing is invented: every card is a real listing with its real supplier.

Results are cached for a few minutes per query so a demo search never waits twice.
"""
from __future__ import annotations

import html
import json
import re
import time

import httpx

SEARCH_URL = "https://m.indiamart.com/isearch.php"
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/129.0 Mobile Safari/537.36")
CACHE_TTL = 600  # seconds
_cache: dict[str, tuple[float, dict]] = {}

_BLOB = re.compile(r"mcatCardsData\d*\s*=\s*")


def _https(u: str | None) -> str | None:
    return u.replace("http://", "https://", 1) if u else None


def _parse_records(page: str) -> list[dict]:
    """All objects inside the `mcatCardsData*` arrays of the page, in page order."""
    dec = json.JSONDecoder()
    out: list[dict] = []
    for m in _BLOB.finditer(page):
        start = page.find("[", m.end())
        if start < 0 or start - m.end() > 5:
            continue
        try:
            arr, _ = dec.raw_decode(page[start:])
        except json.JSONDecodeError:
            continue
        for x in arr:
            if not isinstance(x, dict):
                continue
            raw = x.get("rawData") if isinstance(x.get("rawData"), dict) else {}
            rec = {**x, **raw}  # the card wraps the full record under rawData; card-level keys fill any gaps
            rec.setdefault("companyname", x.get("companyName"))
            rec.setdefault("memberSinceDisplay", x.get("member_since"))
            rec.setdefault("price_f", x.get("standardPrice"))
            rec.setdefault("large_image", x.get("imgUrl"))
            if rec.get("companyname") and (rec.get("title") or rec.get("original_title")):
                out.append(rec)
    return out


def _clean(r: dict) -> dict:
    price_f = html.unescape(r.get("price_f") or "")  # "₹ 190/Piece"
    unit = price_f.split("/", 1)[1].strip() if "/" in price_f else (r.get("moq_type") or "")
    price = (r.get("itemprice") or "").strip()
    specs = [s.replace("==", ": ") for s in (r.get("isq") or [])[:3]]
    return {
        "title": r.get("title") or r.get("original_title") or "",
        "price": price or None,
        "price_unit": unit or None,
        "price_text": (f"₹ {price}/{unit}" if price and unit else f"₹ {price}" if price else "Ask Price"),
        "moq": (f"{r['moq']} {r.get('moq_type') or ''}".strip() if r.get("moq") else None),
        "company": r.get("companyname"),
        "city": r.get("city"),
        "state": r.get("state"),
        "member_since": r.get("memberSinceDisplay"),
        "gst_verified": r.get("gstVerifiedFlag") == "1",
        "rating": r.get("supplier_rating"),
        "rating_count": r.get("rating_count"),
        "image": _https(r.get("large_image") or r.get("image")),
        "url": r.get("title_url") or r.get("desktop_title_url"),
        "supplier_url": (r.get("desktop_catalog_url") or r.get("catalog_url") or "").split("?")[0] or None,  # drop the tracking tags
        "display_id": r.get("displayid"),
        "seller_glid": r.get("glusrid"),
        "category": (r.get("mcatname") or [None])[0],
        "specs": specs,
    }


def search_indiamart(query: str, limit: int = 12) -> dict:
    q = " ".join(query.split())
    key = q.lower()
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1] | {"cached": True}
    t0 = time.perf_counter()
    r = httpx.get(SEARCH_URL, params={"s": q}, follow_redirects=True, timeout=15,
                  headers={"User-Agent": MOBILE_UA, "Accept-Language": "en-IN,en;q=0.9"})
    r.raise_for_status()
    items = [_clean(x) for x in _parse_records(r.text)]
    seen: set[str] = set()
    uniq = []
    for it in items:
        k = it["display_id"] or it["title"]
        if it["title"] and k not in seen:
            seen.add(k)
            uniq.append(it)
    result = {"query": q, "items": uniq[:limit], "total_parsed": len(items), "source": "m.indiamart.com",
              "search_url": f"https://dir.indiamart.com/search.mp?ss={q.replace(' ', '+')}",
              "fetched_in": round(time.perf_counter() - t0, 2), "cached": False}
    _cache[key] = (time.time(), result)
    return result


if __name__ == "__main__":
    import sys
    res = search_indiamart(" ".join(sys.argv[1:]) or "pen drive")
    print(json.dumps({k: v for k, v in res.items() if k != "items"}, indent=1))
    for it in res["items"]:
        print(f"- {it['title']} · {it['price_text']} · {it['company']}, {it['city']} · ⭐{it['rating']} ({it['rating_count']})")
