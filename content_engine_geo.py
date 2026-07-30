"""
content_engine_geo.py
============================================================================
E21 + E22 — GEO in the GEOGRAPHIC sense: the five target markets.

(The generative sense of GEO — ChatGPT/Perplexity citations — lives in
content_engine_aeo.py. The dashboard shows both, on separate tabs, because
they are genuinely different problems.)

E21 MULTI-MARKET AUDIT   hreflang validation, language coverage per market,
                         per-market query cross-cut, service-area page gaps.
                         The crawler ALREADY captures hreflang — nothing read
                         it until now. Costs nothing.
E22 LOCAL PACK GRID      where you rank in the map pack per market, plus NAP
                         consistency. Serper Maps is already connected.

Run offline self-check:  python content_engine_geo.py
============================================================================
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger("geo")

GRID_KEY = "geo_local_grid"
AUDIT_KEY = "geo_market_audit"

# The founder's five markets (see the ICP memory), with the language a page
# must be in to compete there and the Serper country code.
MARKETS = [
    {"name": "United States", "gl": "us", "hl": "en", "lang": "en", "hreflang": "en-US"},
    {"name": "United Kingdom", "gl": "gb", "hl": "en", "lang": "en", "hreflang": "en-GB"},
    {"name": "Germany", "gl": "de", "hl": "de", "lang": "de", "hreflang": "de-DE"},
    {"name": "Switzerland", "gl": "ch", "hl": "de", "lang": "de", "hreflang": "de-CH"},
    {"name": "Canada", "gl": "ca", "hl": "en", "lang": "en", "hreflang": "en-CA"},
]

GSC_COUNTRY = {"usa": "United States", "gbr": "United Kingdom", "deu": "Germany",
               "che": "Switzerland", "can": "Canada"}

# Rough German-language detector: no dependency, good enough to tell whether a
# page could compete in DE/CH at all.
_DE_MARKERS = (" der ", " die ", " das ", " und ", " für ", " mit ", " nicht ",
               " ist ", " werden ", " Unternehmen", " Ihre ", " wir ")


def detect_language(rec: dict) -> str:
    """Declared lang attribute wins; otherwise sniff the visible text."""
    lang = (rec.get("lang") or "").strip().lower()
    if lang:
        return lang.split("-")[0]
    text = " ".join([rec.get("title", ""), rec.get("meta_desc", "")]
                    + (rec.get("h2") or []))
    hits = sum(1 for m in _DE_MARKERS if m.lower() in f" {text.lower()} ")
    return "de" if hits >= 2 else "en"


# ======================================================================
#  E21 — HREFLANG + MARKET COVERAGE
# ======================================================================
def hreflang_audit(crawl: dict) -> dict:
    """Validate the hreflang the crawler already collected.

    Real rules checked: a page that declares alternates must include a
    self-reference, must not declare the same hreflang twice, and every code
    must be well formed.
    """
    pages = [r for r in (crawl or {}).get("urls", []) if r.get("status") == 200]
    with_tags, issues, codes = [], [], {}
    code_re = re.compile(r"^([a-z]{2})(-[A-Z]{2})?$|^x-default$")
    for r in pages:
        tags = r.get("hreflang") or []
        if not tags:
            continue
        with_tags.append(r["url"])
        seen, self_ref = set(), False
        for code, href in tags:
            code = (code or "").strip()
            codes[code] = codes.get(code, 0) + 1
            if not code_re.match(code):
                issues.append({"url": r["url"], "issue": f"malformed hreflang '{code}'"})
            if code in seen:
                issues.append({"url": r["url"], "issue": f"duplicate hreflang '{code}'"})
            seen.add(code)
            if (href or "").rstrip("/") == r["url"].rstrip("/"):
                self_ref = True
        if not self_ref:
            issues.append({"url": r["url"],
                           "issue": "no self-referencing hreflang (Google ignores the set)"})
    return {"pages": len(pages), "pages_with_hreflang": len(with_tags),
            "coverage_pct": round(100 * len(with_tags) / max(len(pages), 1), 1),
            "codes": sorted(codes.items(), key=lambda kv: -kv[1]),
            "issues": issues[:40], "issue_count": len(issues),
            "declared_markets": sorted(codes),
            "missing_markets": [m["hreflang"] for m in MARKETS
                                if m["hreflang"] not in codes]}


def language_coverage(crawl: dict) -> dict:
    """How many pages could actually compete in each market's language."""
    pages = [r for r in (crawl or {}).get("urls", []) if r.get("status") == 200]
    langs = {}
    for r in pages:
        langs[detect_language(r)] = langs.get(detect_language(r), 0) + 1
    rows = []
    for m in MARKETS:
        n = langs.get(m["lang"], 0)
        rows.append({"market": m["name"], "language": m["lang"], "pages": n,
                     "covered": n > 0,
                     "share_pct": round(100 * n / max(len(pages), 1), 1)})
    return {"pages": len(pages), "languages": sorted(langs.items(), key=lambda kv: -kv[1]),
            "markets": rows,
            "uncovered": [r["market"] for r in rows if not r["covered"]]}


def market_performance(gsc_countries: list, gsc_queries: list = None) -> dict:
    """Search Console country rows -> per-market performance for OUR five."""
    by_market = {}
    for row in gsc_countries or []:
        key = str(row.get("key", "")).lower()
        name = GSC_COUNTRY.get(key)
        if not name:
            continue
        by_market[name] = {
            "market": name,
            "impressions": int(row.get("impressions", 0) or 0),
            "clicks": int(row.get("clicks", 0) or 0),
            "position": round(float(row.get("position", 0) or 0), 1),
            "ctr": round(float(row.get("ctr", 0) or 0), 2)}
    rows = [by_market.get(m["name"], {"market": m["name"], "impressions": 0,
                                      "clicks": 0, "position": 0, "ctr": 0})
            for m in MARKETS]
    total = sum(r["impressions"] for r in rows)
    for r in rows:
        r["share_pct"] = round(100 * r["impressions"] / total, 1) if total else 0.0
    return {"markets": rows, "total_impressions": total,
            "total_clicks": sum(r["clicks"] for r in rows),
            "active": [r["market"] for r in rows if r["impressions"] > 0],
            "silent": [r["market"] for r in rows if r["impressions"] == 0]}


def service_area_gaps(crawl: dict) -> dict:
    """One page per market, in that market's language, is how you compete
    locally without an office there. Which are missing?"""
    pages = [r for r in (crawl or {}).get("urls", []) if r.get("status") == 200]
    found = {}
    for m in MARKETS:
        needle = m["name"].lower()
        short = needle.split()[-1]
        hit = next((r["url"] for r in pages
                    if needle in (r.get("title", "") or "").lower()
                    or needle in r["url"].lower()
                    or (len(short) > 4 and short in r["url"].lower())), "")
        found[m["name"]] = hit
    return {"markets": [{"market": k, "url": v, "has_page": bool(v)}
                        for k, v in found.items()],
            "covered": sum(1 for v in found.values() if v),
            "missing": [k for k, v in found.items() if not v]}


def local_schema_audit(crawl: dict) -> dict:
    pages = [r for r in (crawl or {}).get("urls", []) if r.get("status") == 200]
    local = sum(1 for r in pages if "LocalBusiness" in (r.get("schema_types") or []))
    org = sum(1 for r in pages if "Organization" in (r.get("schema_types") or []))
    return {"pages": len(pages), "localbusiness": local, "organization": org,
            "has_local": local > 0,
            "coverage_pct": round(100 * local / max(len(pages), 1), 1)}


# ======================================================================
#  E22 — LOCAL PACK GRID
# ======================================================================
def local_grid(queries: list, domain: str, *, markets=None, limit: int = 5) -> list:
    """Where you rank per market for each query. Serper, ~1 credit per cell."""
    try:
        import content_engine_connectors as C
        s = C.Serper()
    except Exception as e:
        log.warning("serper unavailable: %s", e)
        return []
    if not s.available():
        return []
    markets = markets or MARKETS
    rows = []
    for q in (queries or [])[:limit]:
        for m in markets:
            r = s.rank(q, domain, gl=m["gl"]) or {}
            rows.append({"market": m["name"], "gl": m["gl"], "query": q,
                         "position": r.get("position", 0),
                         "found": bool(r.get("position")),
                         "features": r.get("features", []),
                         "top3": r.get("top3", [])})
    return rows


def local_competitors(vertical: str, city: str, limit: int = 10) -> list:
    try:
        import content_engine_connectors as C
        s = C.Serper()
        if not s.available():
            return []
        return s.maps(f"{vertical} in {city}", num=limit) or []
    except Exception as e:
        log.warning("maps scan failed: %s", e)
        return []


def nap_consistency(crawl: dict, *, name="", phone="", address="") -> dict:
    """Is the business name / phone / address stated the same way everywhere?"""
    pages = [r for r in (crawl or {}).get("urls", []) if r.get("status") == 200]
    hits = {"name": 0, "phone": 0, "address": 0}
    for r in pages:
        blob = " ".join([r.get("title", ""), r.get("meta_desc", "")]).lower()
        if name and name.lower() in blob:
            hits["name"] += 1
        if phone and re.sub(r"\D", "", phone)[-6:] in re.sub(r"\D", "", blob):
            hits["phone"] += 1
        if address and address.lower()[:18] in blob:
            hits["address"] += 1
    declared = sum(1 for v in (name, phone, address) if v)
    return {"pages": len(pages), "hits": hits, "declared": declared,
            "consistent": declared > 0 and all(
                hits[k] > 0 for k, v in (("name", name), ("phone", phone),
                                         ("address", address)) if v),
            "note": ("Your registered address is a Wyoming registered-agent "
                     "address, so citation building matters less than for a "
                     "physical local business — but it must still be identical "
                     "everywhere it appears.")}


# ======================================================================
#  ONE CALL
# ======================================================================
def run_market_audit(store, crawl: dict, gsc: dict) -> dict:
    """E21 — everything free, from data already collected."""
    from datetime import datetime, timezone
    out = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "hreflang": hreflang_audit(crawl),
           "language": language_coverage(crawl),
           "performance": market_performance((gsc or {}).get("countries") or [],
                                             (gsc or {}).get("queries") or []),
           "service_areas": service_area_gaps(crawl),
           "schema": local_schema_audit(crawl)}
    covered = len(MARKETS) - len(out["language"]["uncovered"])
    out["score"] = int(round(100 * (
        0.4 * covered / len(MARKETS)
        + 0.3 * min(1.0, out["hreflang"]["coverage_pct"] / 100)
        + 0.3 * out["service_areas"]["covered"] / len(MARKETS))))
    if store is not None:
        try:
            store.set_setting(AUDIT_KEY, out)
        except Exception as e:
            log.warning("geo audit save failed: %s", e)
    return out


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    crawl = {"urls": [
        {"url": "https://x.com/en/a", "status": 200, "lang": "en",
         "title": "Automation for law firms", "meta_desc": "", "h2": [],
         "schema_types": ["Organization"], "outbound_links": [],
         "hreflang": [("en-US", "https://x.com/en/a"), ("de-DE", "https://x.com/de/a")]},
        {"url": "https://x.com/de/a", "status": 200, "lang": "de",
         "title": "Automatisierung für Kanzleien", "meta_desc": "", "h2": [],
         "schema_types": [], "outbound_links": [],
         "hreflang": [("en-US", "https://x.com/en/a"), ("de-DE", "https://x.com/de/a")]},
        {"url": "https://x.com/orphan", "status": 200, "lang": "", "title": "Germany services",
         "meta_desc": "", "h2": [], "schema_types": [], "outbound_links": [], "hreflang": []},
        {"url": "https://x.com/bad", "status": 200, "lang": "en", "title": "Bad",
         "meta_desc": "", "h2": [], "schema_types": [], "outbound_links": [],
         "hreflang": [("english", "https://x.com/other"), ("en-US", "https://x.com/other")]},
    ]}
    h = hreflang_audit(crawl)
    assert h["pages_with_hreflang"] == 3, h
    codes = dict(h["codes"])
    assert codes["en-US"] == 3 and codes["de-DE"] == 2, h["codes"]
    problems = " ".join(i["issue"] for i in h["issues"])
    assert "malformed hreflang 'english'" in problems, h["issues"]
    assert "no self-referencing hreflang" in problems, h["issues"]
    assert "de-CH" in h["missing_markets"] and "en-GB" in h["missing_markets"], h

    lc = language_coverage(crawl)
    assert dict((r["market"], r["pages"]) for r in lc["markets"])["Germany"] == 1, lc
    assert "Germany" not in lc["uncovered"], lc["uncovered"]
    assert detect_language({"lang": "de-DE"}) == "de"
    assert detect_language({"lang": "", "title": "Wir automatisieren Ihre Kanzlei",
                            "meta_desc": "Die Lösung für Unternehmen und mit Erfolg",
                            "h2": []}) == "de"

    mp = market_performance([{"key": "usa", "impressions": 300, "clicks": 2, "position": 42},
                             {"key": "deu", "impressions": 100, "clicks": 0, "position": 60},
                             {"key": "fra", "impressions": 999, "clicks": 9}])
    assert mp["total_impressions"] == 400, mp          # France is not a target market
    assert mp["active"] == ["United States", "Germany"], mp["active"]
    assert "Switzerland" in mp["silent"] and "Canada" in mp["silent"], mp["silent"]
    us = next(r for r in mp["markets"] if r["market"] == "United States")
    assert us["share_pct"] == 75.0, us

    sa = service_area_gaps(crawl)
    assert sa["covered"] == 1 and "Germany" not in sa["missing"], sa
    assert "Switzerland" in sa["missing"], sa["missing"]

    ls = local_schema_audit(crawl)
    assert ls["localbusiness"] == 0 and ls["organization"] == 1, ls

    nap = nap_consistency(crawl, name="Anthropos", phone="", address="")
    assert nap["declared"] == 1 and nap["hits"]["name"] == 0, nap

    class _S:
        def __init__(self): self.d = {}
        def get_setting(self, k, d=None): return self.d.get(k, d)
        def set_setting(self, k, v): self.d[k] = v
    st = _S()
    audit = run_market_audit(st, crawl, {"countries": [{"key": "usa", "impressions": 300,
                                                        "clicks": 2, "position": 42}]})
    assert 0 <= audit["score"] <= 100, audit["score"]
    assert st.d[AUDIT_KEY]["hreflang"]["issue_count"] >= 2
    assert local_grid(["x"], "x.com") == [], "no Serper key -> empty, never invented"
    print("geo self-check OK — hreflang validation, language coverage, market "
          "performance, service areas, NAP, honest degrade")
