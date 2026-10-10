"""Real www.indiamart.com home page feed: "Trending on IndiaMART" tiles and "Explore by Industry" rows.

The home page is server-rendered, so a plain GET (gzip) gives the names and images. Cached for an hour.
Used by the emulated website on /demo so the home looks like the real site and shows varied categories,
not only the user's own (often near-identical) search keywords.
"""
from __future__ import annotations

import html
import re
import time

import httpx

HOME_URL = "https://www.indiamart.com/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/129.0 Safari/537.36")
CACHE_TTL = 3600
_cache: dict[str, tuple[float, dict]] = {}

_IMG = re.compile(r"<img\b[^>]*>", re.I)
_ATTR = re.compile(r'\b(src|data-src|alt)\s*=\s*"([^"]*)"', re.I)
_H3 = re.compile(r"<h3[^>]*>\s*(.*?)\s*</h3>", re.I | re.S)


def _imgs(seg: str) -> list[dict]:
    out = []
    for tag in _IMG.findall(seg):
        a = {k.lower(): v for k, v in _ATTR.findall(tag)}
        name = html.unescape(a.get("alt", "")).strip()
        src = a.get("data-src") or a.get("src") or ""
        if 3 <= len(name) <= 40 and "imimg.com" in src:
            out.append({"name": name, "image": src.replace("http://", "https://", 1)})
    return out


def _parse(page: str) -> dict:
    t = page.find("Trending on IndiaMART")
    e = page.find("Explore by Industry")
    trending = _imgs(page[t:e] if t >= 0 and e > t else page[t:t + 40000]) if t >= 0 else []
    industries: list[dict] = []
    if e >= 0:
        seg = page[e:]
        heads = list(_H3.finditer(seg))
        for i, m in enumerate(heads[:12]):
            name = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
            block = seg[m.end(): heads[i + 1].start() if i + 1 < len(heads) else m.end() + 30000]
            prods = _imgs(block)[:6]
            if prods and "Videos" not in name and len(prods) >= 4:
                industries.append({"industry": name, "products": prods})
    seen: set[str] = set()
    trending = [x for x in trending if not (x["name"].lower() in seen or seen.add(x["name"].lower()))]
    return {"trending": trending[:18], "industries": industries[:8]}


def home_feed() -> dict:
    hit = _cache.get("home")
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1] | {"cached": True}
    t0 = time.perf_counter()
    r = httpx.get(HOME_URL, headers={"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9"}, timeout=15, follow_redirects=True)
    r.raise_for_status()
    data = _parse(r.text) | {"source": "www.indiamart.com", "fetched_in": round(time.perf_counter() - t0, 2), "cached": False}
    _cache["home"] = (time.time(), data)
    return data


if __name__ == "__main__":
    import json
    d = home_feed()
    print(json.dumps({k: v for k, v in d.items() if k not in ("trending", "industries")}))
    print("trending:", [x["name"] for x in d["trending"]])
    for ind in d["industries"]:
        print(f"- {ind['industry']}: {[p['name'] for p in ind['products']]}")
