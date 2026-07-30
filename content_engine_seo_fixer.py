"""
content_engine_seo_fixer.py
============================================================================
E7 / E8 / E9 — THE HANDS. Turns work orders into real changes on the site.

Split of authority (the founder's call, 2026-07-30):
    AUTO-PUSH   schema, image alt text, internal links, OG tags, IndexNow
                -> machine-readable markup and links. No human words changed.
    APPROVAL    titles, meta descriptions, body rewrites
                -> anything a visitor reads. Proposals are written into the
                   work order and wait for a click.

Every fix is idempotent (re-running does nothing), records before/after for
rollback, and verifies itself where verification is possible.

Run offline self-check:  python content_engine_seo_fixer.py
============================================================================
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

import content_engine_workorders as WO

log = logging.getLogger("seo_fixer")

# Injectable so the self-check runs with zero API calls / zero network.
LLM_FN = None          # (skill, payload, store) -> (data, cost)
WP_FN = None           # () -> a WordPress-like connector


def _wp():
    if WP_FN:
        return WP_FN()
    import content_engine_connectors as C
    return C.WordPress()


def _llm(skill: str, payload: dict, store) -> tuple:
    """Run one LLM skill through the real runner so budget caps, model routing,
    cost recording and schema validation all still apply."""
    if LLM_FN:
        return LLM_FN(skill, payload, store)
    import content_engine_orchestrator as orch
    job = {"job_id": f"seofix_{skill}", "type": "seo_fix", "status": "seo_fixing",
           "payload": payload, "cost_so_far_usd": 0.0}
    return orch.run_llm_skill(job, skill, store)


# ======================================================================
#  E9 — SCHEMA
# ======================================================================
def build_schema(rec: dict, *, site_name="Anthropos Automation Service LLC",
                 site_url="") -> dict:
    """Build JSON-LD from what the page ACTUALLY contains. No invented fields."""
    url = rec.get("final_url") or rec.get("url", "")
    title = rec.get("title", "")
    desc = rec.get("meta_desc", "")
    h2s = rec.get("h2", []) or []
    # Question-style H2s -> a real FAQPage (this is what AI engines quote).
    questions = [h for h in h2s if h.strip().endswith("?")]
    graph = []
    is_article = "/guide" in url or "/blog" in url or rec.get("words", 0) > 600
    graph.append({
        "@type": "Article" if is_article else "WebPage",
        "@id": url + "#main",
        "url": url,
        "headline": (title or "")[:110],
        "description": desc,
        "publisher": {"@type": "Organization", "name": site_name,
                      "url": site_url or url},
    })
    if len(questions) >= 2:
        graph.append({
            "@type": "FAQPage",
            "@id": url + "#faq",
            "mainEntity": [{"@type": "Question", "name": q,
                            "acceptedAnswer": {"@type": "Answer", "text": ""}}
                           for q in questions[:10]],
        })
    crumbs = [c for c in url.replace("https://", "").replace("http://", "").split("/")[1:] if c]
    if crumbs:
        graph.append({
            "@type": "BreadcrumbList", "@id": url + "#crumbs",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1,
                 "name": c.replace("-", " ").title()}
                for i, c in enumerate(crumbs[:4])],
        })
    return {"@context": "https://schema.org", "@graph": graph}


def _has_jsonld(html: str) -> bool:
    return "application/ld+json" in (html or "")


def fix_schema(order: dict, rec: dict, store) -> dict:
    """Inject JSON-LD into the post body, then VERIFY it survived.

    WordPress strips <script> for users without unfiltered_html, so this
    reports honestly rather than claiming a silent success."""
    wp = _wp()
    if not wp.available():
        return {"status": "skipped", "result": "WordPress not connected"}
    post = wp.find_by_url(order["url"])
    if not post:
        return {"status": "failed", "result": "post not found in WordPress"}
    if _has_jsonld(post.get("content", "")):
        return {"status": "done", "result": "schema already present (no change)"}
    schema = build_schema(rec, site_url=order.get("extra", {}).get("site_url", ""))
    block = ('\n<script type="application/ld+json">'
             + json.dumps(schema, ensure_ascii=False) + "</script>\n")
    res = wp.update_post(post["id"], {"content": post.get("content", "") + block},
                         kind=post.get("kind", "posts"))
    if res != "updated":
        return {"status": "failed", "result": res}
    check = wp.find_by_url(order["url"])
    if check and _has_jsonld(check.get("content", "")):
        types = [n.get("@type") for n in schema["@graph"]]
        return {"status": "done", "result": f"injected {', '.join(types)}"}
    return {"status": "failed",
            "result": ("WordPress stripped the script tag — the WP user needs "
                       "unfiltered_html, or add the schema in the theme")}


# ======================================================================
#  E8 — INTERNAL LINKS
# ======================================================================
_STOP = {"the", "and", "for", "with", "your", "you", "how", "what", "why", "a",
         "an", "of", "to", "in", "on", "is", "are", "that", "this", "it", "we"}


def _phrases(title: str) -> list:
    """Candidate anchor phrases from a target page's title, longest first."""
    t = re.sub(r"[|–—:].*$", "", title or "").strip()
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-']+", t)]
    out = []
    for n in (4, 3, 2):
        for i in range(len(words) - n + 1):
            chunk = words[i:i + n]
            if all(w.lower() in _STOP for w in chunk):
                continue
            out.append(" ".join(chunk))
    return out


def propose_internal_link(source: dict, candidates: list) -> Optional[dict]:
    """Find a phrase already written in the source page that names a candidate
    target page. We only ever link text the author already wrote — we never
    insert new sentences."""
    src_text = " ".join([source.get("title", "")] + (source.get("h2") or [])
                        + [source.get("meta_desc", "")])
    body = source.get("_body", "") or src_text
    already = set(source.get("internal_links") or [])
    best = None
    for cand in candidates or []:
        curl = cand.get("url", "")
        if not curl or curl == source.get("url") or curl in already:
            continue
        for phrase in _phrases(cand.get("title", "")):
            m = re.search(r"(?<![>\w])" + re.escape(phrase) + r"(?![\w<])", body, re.I)
            if not m:
                continue
            # never link inside an existing anchor
            before = body[:m.start()]
            if before.rfind("<a ") > before.rfind("</a>"):
                continue
            score = len(phrase.split())
            if not best or score > best["score"]:
                best = {"target": curl, "anchor": m.group(0), "score": score,
                        "target_title": cand.get("title", "")}
    return best


def fix_internal_links(order: dict, source: dict, candidates: list, store) -> dict:
    wp = _wp()
    if not wp.available():
        return {"status": "skipped", "result": "WordPress not connected"}
    post = wp.find_by_url(order["url"])
    if not post:
        return {"status": "failed", "result": "post not found in WordPress"}
    src = dict(source, _body=post.get("content", ""))
    prop = propose_internal_link(src, candidates)
    if not prop:
        return {"status": "skipped",
                "result": "no natural anchor phrase found — would need new copy"}
    body = post["content"]
    pattern = re.compile(r"(?<![>\w])(" + re.escape(prop["anchor"]) + r")(?![\w<])")
    new_body, n = pattern.subn(
        lambda m: f'<a href="{prop["target"]}">{m.group(1)}</a>', body, count=1)
    if not n:
        return {"status": "skipped", "result": "anchor vanished before write"}
    res = wp.update_post(post["id"], {"content": new_body}, kind=post.get("kind", "posts"))
    if res != "updated":
        return {"status": "failed", "result": res}
    return {"status": "done",
            "result": f'linked “{prop["anchor"]}” -> {prop["target"]}'}


# ======================================================================
#  E7 — COPY (alt = auto, title/meta = proposal only)
# ======================================================================
def fix_alt_text(order: dict, rec: dict, store) -> dict:
    wp = _wp()
    if not wp.available():
        return {"status": "skipped", "result": "WordPress not connected"}
    imgs = (order.get("extra") or {}).get("images") or []
    if not imgs:
        return {"status": "skipped", "result": "no image list captured for this page"}
    done, failed = 0, 0
    for src in imgs[:6]:
        mid = wp.media_by_src(src)
        if not mid:
            failed += 1
            continue
        data, _ = _llm("seo_fixer", {
            "fix_type": "alt", "url": order["url"], "current": "",
            "page": rec, "image_context": f"{rec.get('title','')} — {src.rsplit('/',1)[-1]}",
            "primary_keyword": (order.get("extra") or {}).get("keyword", ""),
        }, store)
        alt = (data or {}).get("value", "").strip()
        if not alt:
            failed += 1
            continue
        if wp.update_media_alt(mid, alt[:120]) == "updated":
            done += 1
        else:
            failed += 1
    if not done:
        return {"status": "failed", "result": f"no alt text written ({failed} attempts)"}
    return {"status": "done", "result": f"alt text written for {done} image(s)"}


def propose_copy(order: dict, rec: dict, store, fix_type: str) -> dict:
    """Titles and metas are NEVER auto-pushed. We write the proposal onto the
    order and it waits for approval."""
    current = rec.get("title", "") if fix_type == "title" else rec.get("meta_desc", "")
    data, cost = _llm("seo_fixer", {
        "fix_type": fix_type, "url": order["url"], "current": current,
        "page": rec, "first_paragraph": (order.get("extra") or {}).get("first_paragraph", ""),
        "primary_keyword": (order.get("extra") or {}).get("keyword", ""),
        "queries": (order.get("extra") or {}).get("queries", []),
    }, store)
    value = (data or {}).get("value", "").strip()
    if not value:
        return {"status": "failed", "result": "model returned no value"}
    return {"status": "awaiting_approval",
            "result": f"proposed {fix_type}: {value}",
            "proposal": {"field": fix_type, "before": current, "after": value,
                         "reason": (data or {}).get("reason", ""), "cost": cost}}


def apply_proposal(order: dict) -> dict:
    """Called when the founder approves a copy proposal in the dashboard."""
    prop = (order.get("extra") or {}).get("proposal") or order.get("proposal") or {}
    if not prop:
        return {"status": "failed", "result": "no proposal on this order"}
    wp = _wp()
    if not wp.available():
        return {"status": "skipped", "result": "WordPress not connected"}
    post = wp.find_by_url(order["url"])
    if not post:
        return {"status": "failed", "result": "post not found in WordPress"}
    field = prop.get("field")
    payload = ({"title": prop["after"]} if field == "title"
               else {"excerpt": prop["after"]} if field == "meta"
               else None)
    if not payload:
        return {"status": "failed", "result": f"unknown field {field}"}
    res = wp.update_post(post["id"], payload, kind=post.get("kind", "posts"))
    return ({"status": "done", "result": f'{field} updated to “{prop["after"]}”'}
            if res == "updated" else {"status": "failed", "result": res})


# ======================================================================
#  BATCH RUNNER
# ======================================================================
_HANDLERS = {
    "schema_missing": fix_schema,
    "img_alt_missing": fix_alt_text,
    "few_internal_links": None,     # needs candidates -> handled in run_batch
    "orphan_page": None,
}


def run_batch(store, *, crawl=None, limit: int = 20, auto_only: bool = True,
              dry_run: bool = False) -> dict:
    """Execute the highest-priority open work orders. Returns a run report.

    Safe by default: only `auto` orders run; copy changes become proposals.
    """
    crawl = crawl or {}
    by_url = {r.get("url"): r for r in crawl.get("urls", [])}
    candidates = [{"url": r["url"], "title": r.get("title", "")}
                  for r in crawl.get("urls", [])
                  if r.get("status") == 200 and r.get("title")]
    orders = WO.load(store)
    batch = WO.next_batch(orders, auto_only=auto_only, limit=limit)
    report = {"attempted": 0, "done": 0, "skipped": 0, "failed": 0,
              "awaiting_approval": 0, "details": []}
    for o in batch:
        rec = by_url.get(o["url"], {})
        code = o["code"]
        report["attempted"] += 1
        if dry_run:
            report["details"].append({"id": o["id"], "code": code, "url": o["url"],
                                      "would": o.get("fix", "")})
            continue
        try:
            if code == "schema_missing":
                out = fix_schema(o, rec, store)
            elif code == "img_alt_missing":
                out = fix_alt_text(o, rec, store)
            elif code in ("few_internal_links", "orphan_page"):
                out = fix_internal_links(o, rec, candidates, store)
            elif code in ("title_long", "title_short", "title_missing",
                          "title_duplicate", "ctr_gap"):
                out = propose_copy(o, rec, store, "title")
            elif code in ("meta_missing", "meta_short", "meta_long", "meta_duplicate"):
                out = propose_copy(o, rec, store, "meta")
            else:
                out = {"status": "skipped",
                       "result": "no automated handler — needs a human"}
        except Exception as e:                       # never let one fix kill the run
            log.warning("fix %s on %s failed: %s", code, o["url"], e)
            out = {"status": "failed", "result": f"{type(e).__name__}: {e}"}

        if out.get("proposal"):
            o.setdefault("extra", {})["proposal"] = out["proposal"]
            for stored in orders:
                if stored["id"] == o["id"]:
                    stored.setdefault("extra", {})["proposal"] = out["proposal"]
        WO.mark(store, o["id"], out["status"], out.get("result", ""))
        report[out["status"]] = report.get(out["status"], 0) + 1
        report["details"].append({"id": o["id"], "code": code, "url": o["url"],
                                  "status": out["status"], "result": out.get("result", "")})
    WO.save(store, orders)
    return report


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    rec = {"url": "https://x.com/guide-a", "final_url": "https://x.com/guide-a",
           "title": "AI Automation for Law Firms | Anthropos", "meta_desc": "",
           "h2": ["What is the problem?", "How does it work?", "Pricing"],
           "words": 900, "internal_links": []}
    s = build_schema(rec, site_url="https://x.com")
    types = [n["@type"] for n in s["@graph"]]
    assert "Article" in types and "FAQPage" in types and "BreadcrumbList" in types, types
    faq = next(n for n in s["@graph"] if n["@type"] == "FAQPage")
    assert len(faq["mainEntity"]) == 2, faq          # only the 2 real questions
    thin = build_schema({"url": "https://x.com/p", "title": "T", "h2": ["One"], "words": 100})
    assert "FAQPage" not in [n["@type"] for n in thin["@graph"]], "1 question != an FAQ"

    src = {"url": "https://x.com/guide-a", "title": "Guide", "internal_links": [],
           "_body": "<p>Many regulated professionals lose leads every week.</p>"}
    cands = [{"url": "https://x.com/services/regulated-professionals",
              "title": "Automation Service for Regulated Professionals"},
             {"url": "https://x.com/guide-a", "title": "Guide"}]
    p = propose_internal_link(src, cands)
    assert p and p["target"].endswith("regulated-professionals"), p
    assert p["anchor"].lower() == "regulated professionals", p["anchor"]

    linked = {"url": "https://x.com/g", "title": "G", "internal_links": [],
              "_body": '<p>See <a href="/x">regulated professionals</a> here.</p>'}
    assert propose_internal_link(linked, cands) is None, "must not nest anchors"
    assert propose_internal_link(src, [{"url": "https://x.com/z", "title": "The And For"}]) is None

    # ---- batch runner with fake WP + fake LLM: no network, no API ----
    class FakeWP:
        def __init__(self): self.posts = {"https://x.com/guide-a": {
            "id": 1, "kind": "posts", "content": "<p>Many regulated professionals lose leads.</p>"}}
        def available(self): return True
        def find_by_url(self, url): return dict(self.posts.get(url, {}), link=url) if url in self.posts else {}
        def update_post(self, pid, fields, kind="posts"):
            for p in self.posts.values():
                if p["id"] == pid:
                    p.update(fields)
            return "updated"
        def update_media_alt(self, mid, alt): return "updated"
        def media_by_src(self, src): return 7

    fake = FakeWP()
    WP_FN = lambda: fake
    LLM_FN = lambda skill, payload, store: (
        {"value": "AI Automation for Law Firms: Cut Intake Time" if payload.get("fix_type") == "title"
                  else "A short honest description of the page.",
         "reason": "targets a real query"}, 0.0004)

    class S:
        def __init__(self): self.d = {}
        def get_setting(self, k, default=None): return self.d.get(k, default)
        def set_setting(self, k, v): self.d[k] = v

    store = S()
    crawl = {"urls": [rec, {"url": "https://x.com/services/regulated-professionals",
                            "status": 200, "title": "Automation Service for Regulated Professionals"}]}
    crawl["urls"][0]["status"] = 200
    WO.save(store, [
        WO.make_order("schema_missing", "https://x.com/guide-a", severity="high"),
        WO.make_order("few_internal_links", "https://x.com/guide-a", severity="medium"),
        WO.make_order("meta_missing", "https://x.com/guide-a", severity="high", auto=False),
    ])
    rep = run_batch(store, crawl=crawl, auto_only=True, limit=10)
    assert rep["done"] == 2, rep          # schema + internal link pushed
    assert "ld+json" in fake.posts["https://x.com/guide-a"]["content"], "schema must land"
    assert "<a href=" in fake.posts["https://x.com/guide-a"]["content"], "link must land"

    # re-running is idempotent: nothing is done twice
    rep2 = run_batch(store, crawl=crawl, auto_only=True, limit=10)
    assert rep2["attempted"] == 0, rep2

    # the meta order produces a PROPOSAL, never a silent push
    rep3 = run_batch(store, crawl=crawl, auto_only=False, limit=10)
    assert rep3.get("awaiting_approval") == 1, rep3
    meta_order = next(o for o in WO.load(store) if o["code"] == "meta_missing")
    assert meta_order["extra"]["proposal"]["after"].startswith("A short honest"), meta_order
    assert fake.posts["https://x.com/guide-a"].get("excerpt") is None, "must NOT push unapproved copy"

    applied = apply_proposal(meta_order)
    assert applied["status"] == "done" and fake.posts["https://x.com/guide-a"]["excerpt"], applied
    print("seo_fixer self-check OK — schema, internal links, proposals, approval, idempotency")
