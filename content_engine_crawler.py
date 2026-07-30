"""
content_engine_crawler.py
============================================================================
E1 — THE SITE CRAWLER.  The engine's own eyes on its own website.

Until this module existed the system could report what Google *already knew*
(GSC/GA4) but had never once looked at its own 225 URLs. Every on-page and
technical card in the dashboard is fed from here.

Zero API cost. Pure stdlib + (optionally) requests. Seeds from the XML sitemap,
falls back to a breadth-first crawl from the homepage.

Per URL it records:
    status, redirect chain, depth, title, meta description, H1..H6 tree,
    word count, canonical, robots meta, JSON-LD @type list, images + missing
    alt, internal/outbound links with anchor text, byte size, fetch ms.

Then link_graph() turns those records into the architecture view: inbound link
counts, orphan pages, click depth, anchor-text distribution.

Run offline self-check:  python content_engine_crawler.py
============================================================================
"""

from __future__ import annotations

import json
import logging
import re
import time
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse

log = logging.getLogger("crawler")

_UA = "Anthropos-SEO-Crawler/1.0 (+https://anthropos-automation.com)"
_TIMEOUT = 20
_SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".zip",
             ".mp4", ".mp3", ".css", ".js", ".ico", ".woff", ".woff2", ".xml")


# ---------------------------------------------------------------- fetching
def _requests():
    try:
        import requests
        return requests
    except Exception:
        return None


def _fetch(url: str):
    """-> (final_url, status, html, bytes, ms, redirect_chain). Never raises."""
    t0 = time.time()
    rq = _requests()
    if rq is not None:
        try:
            r = rq.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT,
                       allow_redirects=True)
            chain = [h.status_code for h in r.history]
            body = r.text if "text/html" in r.headers.get("Content-Type", "") else ""
            return (r.url, r.status_code, body, len(r.content or b""),
                    int((time.time() - t0) * 1000), chain)
        except Exception as e:
            log.debug("fetch failed %s: %s", url, e)
            return (url, 0, "", 0, int((time.time() - t0) * 1000), [])
    # stdlib fallback
    try:
        from urllib.request import Request, urlopen
        req = Request(url, headers={"User-Agent": _UA})
        with urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read()
            ct = resp.headers.get("Content-Type", "")
            html = raw.decode("utf-8", "replace") if "text/html" in ct else ""
            return (resp.geturl(), resp.status, html, len(raw),
                    int((time.time() - t0) * 1000), [])
    except Exception as e:
        log.debug("fetch failed %s: %s", url, e)
        return (url, 0, "", 0, int((time.time() - t0) * 1000), [])


def normalize(url: str) -> str:
    """Strip fragments and the trailing slash (root included) so the same page
    is never counted twice — sites link to both '/x/' and '/x' constantly."""
    try:
        p = urlparse(url)
        path = (p.path or "").rstrip("/")
        return urlunparse((p.scheme, p.netloc.lower(), path, "", p.query, ""))
    except Exception:
        return url


def _same_host(a: str, b: str) -> bool:
    try:
        return urlparse(a).netloc.lower().replace("www.", "") == \
               urlparse(b).netloc.lower().replace("www.", "")
    except Exception:
        return False


def _skippable(url: str) -> bool:
    low = url.lower()
    if any(low.endswith(e) for e in _SKIP_EXT):
        return True
    return any(x in low for x in ("/wp-json", "/wp-admin", "/feed", "wp-content/uploads",
                                  "?replytocom", "/comment-page-"))


# ---------------------------------------------------------------- parsing
class _PageParser(HTMLParser):
    """Pulls every on-page SEO signal out of one HTML document."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base = base_url
        self.title = ""
        self.meta_desc = ""
        self.canonical = ""
        self.robots = ""
        self.og = {}
        self.headings = {f"h{i}": [] for i in range(1, 7)}
        self.links = []          # (href, anchor, rel)
        self.images = []         # (src, alt)
        self.jsonld = []
        self.words = 0
        self.lang = ""
        self.hreflang = []
        self._t = None           # current tag capturing text
        self._buf = []
        self._anchor = []
        self._href = None
        self._rel = ""
        self._in_body = False
        self._skip_depth = 0

    # -- tags
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
                self._t = "jsonld"
                self._buf = []
                return
            self._skip_depth += 1
            return
        if tag == "body":
            self._in_body = True
        elif tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "title":
            self._t = "title"
            self._buf = []
        elif tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            content = a.get("content", "")
            if name == "description":
                self.meta_desc = content.strip()
            elif name == "robots":
                self.robots = content.strip().lower()
            elif name.startswith("og:"):
                self.og[name] = content
        elif tag == "link":
            rel = (a.get("rel") or "").lower()
            if isinstance(rel, list):
                rel = " ".join(rel)
            if "canonical" in rel:
                self.canonical = urljoin(self.base, a.get("href", ""))
            elif "alternate" in rel and a.get("hreflang"):
                self.hreflang.append((a.get("hreflang"), a.get("href", "")))
        elif tag in self.headings:
            self._t = tag
            self._buf = []
        elif tag == "a":
            href = a.get("href")
            if href:
                self._href = urljoin(self.base, href)
                rel = a.get("rel") or ""
                self._rel = " ".join(rel) if isinstance(rel, list) else rel
                self._anchor = []
        elif tag == "img":
            self.images.append((urljoin(self.base, a.get("src", "")), a.get("alt")))

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            if self._t == "jsonld":
                self._collect_jsonld("".join(self._buf))
                self._t, self._buf = None, []
            elif self._skip_depth:
                self._skip_depth -= 1
            return
        if tag == "title" and self._t == "title":
            self.title = "".join(self._buf).strip()
            self._t, self._buf = None, []
        elif tag in self.headings and self._t == tag:
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if text:
                self.headings[tag].append(text)
            self._t, self._buf = None, []
        elif tag == "a" and self._href:
            anchor = re.sub(r"\s+", " ", "".join(self._anchor)).strip()
            self.links.append((self._href, anchor, self._rel))
            self._href, self._anchor, self._rel = None, [], ""

    def handle_data(self, data):
        if self._t:
            self._buf.append(data)
        if self._href is not None:
            self._anchor.append(data)
        if self._in_body and not self._skip_depth and self._t != "jsonld":
            self.words += len(data.split())

    def _collect_jsonld(self, raw):
        try:
            obj = json.loads(raw)
        except Exception:
            return
        for node in (obj if isinstance(obj, list) else [obj]):
            if not isinstance(node, dict):
                continue
            graph = node.get("@graph")
            for n in (graph if isinstance(graph, list) else [node]):
                if isinstance(n, dict) and n.get("@type"):
                    t = n["@type"]
                    self.jsonld.extend(t if isinstance(t, list) else [t])


def parse_page(html: str, url: str) -> dict:
    """HTML -> the on-page signal record (no network)."""
    p = _PageParser(url)
    try:
        p.feed(html)
    except Exception as e:
        log.debug("parse error %s: %s", url, e)
    h = p.headings
    order_ok, prev = True, 0
    for tag in re.findall(r"<(h[1-6])[\s>]", html, re.I):
        lvl = int(tag[1])
        if prev and lvl > prev + 1:
            order_ok = False
        prev = lvl
    return {
        "title": p.title, "title_len": len(p.title),
        "meta_desc": p.meta_desc, "meta_len": len(p.meta_desc),
        "canonical": normalize(p.canonical) if p.canonical else "",
        "robots": p.robots, "lang": p.lang, "hreflang": p.hreflang,
        "h1": h["h1"], "h2": h["h2"], "h3": h["h3"],
        "h_counts": {k: len(v) for k, v in h.items()},
        "heading_order_ok": order_ok,
        "words": p.words,
        "schema_types": sorted(set(p.jsonld)),
        "images": len(p.images),
        "images_no_alt": sum(1 for _, alt in p.images if not (alt or "").strip()),
        "og_ok": bool(p.og.get("og:title") and p.og.get("og:description")),
        "_links": p.links,
    }


# ---------------------------------------------------------------- sitemap
def sitemap_urls(base: str, max_urls: int = 500) -> list:
    """Read wp-sitemap.xml (or sitemap.xml / sitemap_index.xml), following one
    level of sitemap-index nesting. Returns normalized page URLs."""
    found, seen = [], set()
    candidates = [urljoin(base, "/wp-sitemap.xml"), urljoin(base, "/sitemap.xml"),
                  urljoin(base, "/sitemap_index.xml")]
    queue = list(candidates)
    depth = 0
    while queue and len(found) < max_urls and depth < 40:
        sm = queue.pop(0)
        depth += 1
        _, status, body, _, _, _ = _fetch(sm)
        if status != 200 or not body:
            # some servers return xml without text/html; retry raw
            try:
                from urllib.request import Request, urlopen
                with urlopen(Request(sm, headers={"User-Agent": _UA}), timeout=_TIMEOUT) as r:
                    body = r.read().decode("utf-8", "replace")
            except Exception:
                continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body, re.I)
        is_index = "<sitemapindex" in body.lower()
        for loc in locs:
            if is_index or loc.lower().endswith(".xml"):
                if loc not in seen:
                    seen.add(loc)
                    queue.append(loc)
            else:
                n = normalize(loc)
                if n not in seen and not _skippable(n):
                    seen.add(n)
                    found.append(n)
        if found and not is_index and sm in candidates:
            break
    return found[:max_urls]


# ---------------------------------------------------------------- crawl
def crawl_site(base_url: str, max_urls: int = 300, delay: float = 0.2,
               use_sitemap: bool = True) -> dict:
    """Crawl the site and return {base, at, count, urls:[record...]}.

    Sitemap-seeded (so we see pages nothing links to) plus BFS from the
    homepage (so we learn real click depth and catch pages the sitemap omits).
    """
    from datetime import datetime, timezone
    base = base_url.rstrip("/")
    home = normalize(base + "/")
    seeds = sitemap_urls(base, max_urls) if use_sitemap else []
    depth_of = {home: 0}
    for u in seeds:
        depth_of.setdefault(u, 99)          # 99 = not yet reached by a link
    queue = [home] + [u for u in seeds if u != home]
    seen, records = set(), []

    while queue and len(records) < max_urls:
        url = queue.pop(0)
        if url in seen or _skippable(url):
            continue
        seen.add(url)
        final, status, html, size, ms, chain = _fetch(url)
        final_n = normalize(final)
        rec = {"url": url, "final_url": final_n, "status": status,
               "redirected": final_n != url, "redirect_hops": len(chain),
               "bytes": size, "ms": ms, "depth": depth_of.get(url, 99),
               "internal_links": [], "outbound_links": [], "anchors": []}
        if status == 200 and html:
            rec.update(parse_page(html, final))
            links = rec.pop("_links", [])
            for href, anchor, rel in links:
                n = normalize(href)
                if not n.startswith("http"):
                    continue
                if _same_host(n, base):
                    if _skippable(n):
                        continue
                    rec["internal_links"].append(n)
                    rec["anchors"].append((n, anchor[:120]))
                    d = rec["depth"] + 1 if rec["depth"] < 99 else 99
                    if n not in depth_of or d < depth_of[n]:
                        depth_of[n] = d
                    if n not in seen and n not in queue and len(seen) + len(queue) < max_urls * 2:
                        queue.append(n)
                else:
                    rec["outbound_links"].append(n)
            rec["internal_links"] = sorted(set(rec["internal_links"]))
            rec["outbound_links"] = sorted(set(rec["outbound_links"]))
        records.append(rec)
        if delay:
            time.sleep(delay)

    for r in records:                      # final depth after full discovery
        r["depth"] = depth_of.get(r["url"], 99)
    return {"base": base, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "count": len(records), "urls": records}


# ---------------------------------------------------------------- graph
def link_graph(crawl: dict) -> dict:
    """Internal-link architecture: inbound counts, orphans, depth spread,
    anchor-text distribution, broken internal links."""
    urls = crawl.get("urls") or []
    known = {r["url"] for r in urls} | {r.get("final_url") for r in urls if r.get("final_url")}
    ok = {r["url"] for r in urls if r.get("status") == 200}
    inbound = {r["url"]: 0 for r in urls}
    anchors, broken, pairs = {}, [], 0
    for r in urls:
        for tgt in r.get("internal_links", []):
            pairs += 1
            if tgt in inbound:
                inbound[tgt] += 1
            elif tgt not in known:
                broken.append({"from": r["url"], "to": tgt})
        for tgt, text in r.get("anchors", []):
            t = (text or "").strip().lower()
            if t:
                anchors[t] = anchors.get(t, 0) + 1
    home = normalize(crawl.get("base", "") + "/")
    orphans = [u for u, n in inbound.items() if n == 0 and u != home and u in ok]
    depths = {}
    for r in urls:
        d = r.get("depth", 99)
        key = "unreachable" if d >= 99 else str(min(d, 5))
        depths[key] = depths.get(key, 0) + 1
    top_linked = sorted(inbound.items(), key=lambda kv: -kv[1])[:15]
    return {"inbound": inbound, "orphans": orphans, "orphan_count": len(orphans),
            "broken_internal": broken[:100], "broken_count": len(broken),
            "total_internal_links": pairs, "depth_spread": depths,
            "top_linked": top_linked,
            "anchors": sorted(anchors.items(), key=lambda kv: -kv[1])[:40],
            "avg_inbound": round(sum(inbound.values()) / max(len(inbound), 1), 1)}


def money_page_support(crawl: dict, graph: dict, money_patterns=None) -> dict:
    """How much internal link equity reaches the pages that make money
    (/services/*, /business-launch/). A guide that links nowhere is decoration."""
    money_patterns = money_patterns or ["/services/", "/business-launch"]
    inbound = graph.get("inbound", {})
    money = [u for u in inbound if any(p in u for p in money_patterns)]
    supported = {u: inbound.get(u, 0) for u in money}
    articles = [r for r in crawl.get("urls", [])
                if r.get("status") == 200 and not any(p in r["url"] for p in money_patterns)]
    linking = sum(1 for r in articles
                  if any(any(p in l for p in money_patterns) for l in r.get("internal_links", [])))
    return {"money_pages": len(money), "supported": supported,
            "articles": len(articles), "articles_linking_to_money": linking,
            "coverage_pct": round(100 * linking / max(len(articles), 1), 1),
            "weakest": sorted(supported.items(), key=lambda kv: kv[1])[:10]}


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    html = """<!doctype html><html lang="en"><head>
      <title>AI Automation for Law Firms | Anthropos</title>
      <meta name="description" content="How law firms automate intake and follow-up.">
      <link rel="canonical" href="https://x.com/guide-a">
      <script type="application/ld+json">{"@type":"FAQPage","name":"x"}</script>
    </head><body>
      <h1>AI Automation for Law Firms</h1>
      <h2>What is the problem?</h2><p>Firms lose leads because replies are slow today.</p>
      <h4>Skipped level</h4>
      <a href="/services/regulated-professionals/">regulated professionals</a>
      <a href="https://external.com/x">external</a>
      <img src="/a.png" alt="diagram"><img src="/b.png">
    </body></html>"""
    rec = parse_page(html, "https://x.com/guide-a")
    assert rec["title_len"] == len("AI Automation for Law Firms | Anthropos"), rec["title_len"]
    assert rec["meta_desc"].startswith("How law firms"), rec
    assert rec["h1"] == ["AI Automation for Law Firms"], rec["h1"]
    assert rec["schema_types"] == ["FAQPage"], rec["schema_types"]
    assert rec["images"] == 2 and rec["images_no_alt"] == 1, rec
    assert rec["heading_order_ok"] is False, "h2 -> h4 must flag"
    assert rec["words"] > 5, rec["words"]
    assert len(rec["_links"]) == 2, rec["_links"]

    assert normalize("https://X.com/a/?b=1#frag") == "https://x.com/a?b=1"
    assert _skippable("https://x.com/a.png") and not _skippable("https://x.com/a")

    fake = {"base": "https://x.com", "urls": [
        {"url": "https://x.com", "status": 200, "depth": 0,
         "internal_links": ["https://x.com/guide-a"], "anchors": [("https://x.com/guide-a", "Guide A")]},
        {"url": "https://x.com/guide-a", "status": 200, "depth": 1,
         "internal_links": ["https://x.com/services/regulated-professionals"], "anchors": []},
        {"url": "https://x.com/services/regulated-professionals", "status": 200, "depth": 2,
         "internal_links": [], "anchors": []},
        {"url": "https://x.com/orphan", "status": 200, "depth": 99,
         "internal_links": [], "anchors": []}]}
    g = link_graph(fake)
    assert g["orphans"] == ["https://x.com/orphan"], g["orphans"]
    assert g["total_internal_links"] == 2, g
    m = money_page_support(fake, g)
    assert m["money_pages"] == 1 and m["articles_linking_to_money"] == 1, m
    print("crawler self-check OK — parse, normalize, graph, money-page support")
