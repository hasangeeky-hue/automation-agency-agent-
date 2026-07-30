"""
content_engine_aeo.py
============================================================================
E14 — AEO / GEO: are you IN the answer, or is a competitor?

The engine already measured AI visibility for competitors. It never measured
it for Anthropos. This closes that.

Engines probed:
    claude      LIVE via the engine's own ANTHROPIC_API_KEY
    google_ai   LIVE via Serper (answerBox / AI Overview / PAA on real SERPs)
    openai      key-gated (OPENAI_API_KEY) — reported as "not connected", never faked
    perplexity  key-gated (PERPLEXITY_API_KEY) — same

Also here: llms.txt generation, and the quotable-block audit (does each H2
actually ANSWER, which is what gets you quoted).

Run offline self-check:  python content_engine_aeo.py
============================================================================
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger("aeo")

SETTING_KEY = "aeo_visibility"

# Buyer-intent prompts: what a real prospect asks an AI before they buy.
BASE_PROMPTS = [
    "who are the best AI automation agencies for small businesses",
    "how do law firms automate client intake",
    "best n8n automation consultants",
    "how much does business process automation cost for a small company",
    "AI automation agency for medical practices",
    "how do I automate lead follow-up for my agency",
    "best automation partner for Shopify stores",
    "AI automation for tax consultants",
    "who can build an n8n workflow for my business",
    "automation agency Germany small business",
]

SEGMENT_PROMPTS = {
    "regulated-professionals": "how do law firms automate intake and conflict checks",
    "medical-professionals": "how do clinics reduce no-shows automatically",
    "ecommerce-retail": "how do Shopify stores automate abandoned cart recovery",
    "service-professionals": "how do service businesses stop missing calls on the job",
    "freelancers-agencies": "how do freelancers automate proposal follow-up",
    "creators-coaches": "how do coaches turn an audience into clients automatically",
    "b2b-providers": "how do B2B firms improve speed-to-lead",
    "business-launch": "how do I automate a new business from day one",
}


def default_prompts(extra=None) -> list:
    out = list(BASE_PROMPTS) + list(SEGMENT_PROMPTS.values())
    for p in (extra or []):
        if p and p not in out:
            out.append(p)
    return out


# ---------------------------------------------------------------- mention math
def find_mentions(text: str, brand: str, domain: str, rivals=None) -> dict:
    """Who got named in this answer — us, and which rivals."""
    low = (text or "").lower()
    brand_l = (brand or "").lower().strip()
    dom_l = (domain or "").lower().replace("www.", "").split("/")[0]
    root = dom_l.split(".")[0] if dom_l else ""
    mentioned = bool(
        (brand_l and brand_l in low) or (dom_l and dom_l in low)
        or (root and len(root) > 4 and root in low))
    pos = 0
    if mentioned:
        for needle in (brand_l, dom_l, root):
            if needle and needle in low:
                pos = low.index(needle)
                break
    rivals_found = []
    for r in rivals or []:
        rl = str(r).lower().replace("www.", "")
        rroot = rl.split(".")[0]
        if rl in low or (len(rroot) > 4 and rroot in low):
            rivals_found.append(r)
    return {"mentioned": mentioned, "position_char": pos,
            "rivals_mentioned": rivals_found,
            "answer_chars": len(text or "")}


# ---------------------------------------------------------------- engines
def _claude_answer(prompt: str, store=None) -> str:
    """Ask Claude the buyer's question with NO context — exactly as a prospect
    would. Cheap model; the answer text is all we need."""
    try:
        import content_engine_providers as P
        spec = {"model": P.CHEAP_MODEL, "max_tokens": 500,
                "system": [{"type": "text",
                            "text": "Answer the user's question the way you normally would. "
                                    "Name specific companies where that is genuinely useful."}],
                "messages": [{"role": "user", "content": prompt}]}
        res = P.call_provider(P.CHEAP_MODEL, spec)
        data = getattr(res, "data", None)
        if isinstance(data, dict):
            return data.get("text") or data.get("answer") or str(data)
        return str(data or "")
    except Exception as e:
        log.warning("claude probe failed: %s", e)
        return ""


def _google_ai(prompt: str, domain: str) -> dict:
    """Google's own answer surfaces: answerBox / AI Overview / People Also Ask."""
    try:
        import content_engine_connectors as C
        s = C.Serper()
        if not s.available():
            return {"connected": False}
        r = s.rank(prompt, domain, num=10)
        return {"connected": True,
                "owns_snippet": r.get("owns_snippet", False),
                "organic_position": r.get("position", 0),
                "features": r.get("features", []),
                "paa": r.get("paa", [])}
    except Exception as e:
        log.warning("google_ai probe failed: %s", e)
        return {"connected": False}


def probe(prompt: str, *, brand: str, domain: str, rivals=None, store=None) -> dict:
    answer = _claude_answer(prompt, store)
    m = find_mentions(answer, brand, domain, rivals)
    g = _google_ai(prompt, domain)
    return {"prompt": prompt,
            "claude": {"connected": bool(answer), **m,
                       "excerpt": (answer or "")[:280]},
            "google_ai": g,
            "openai": {"connected": False, "reason": "OPENAI_API_KEY not set"},
            "perplexity": {"connected": False, "reason": "PERPLEXITY_API_KEY not set"}}


def run_probes(store=None, *, brand="Anthropos", domain="anthropos-automation.com",
               prompts=None, rivals=None, limit: int = 30) -> dict:
    from datetime import datetime, timezone
    prompts = (prompts or default_prompts())[:limit]
    results = [probe(p, brand=brand, domain=domain, rivals=rivals, store=store)
               for p in prompts]
    out = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "brand": brand, "domain": domain,
           "results": results, **summarize(results, rivals)}
    if store is not None:
        try:
            store.set_setting(SETTING_KEY, out)
        except Exception as e:
            log.warning("aeo save failed: %s", e)
    return out


def summarize(results: list, rivals=None) -> dict:
    n = len(results or [])
    if not n:
        return {"score": 0, "mention_rate": 0, "engines": {}, "gaps": [],
                "share_of_voice": {}}
    claude_hits = sum(1 for r in results if r["claude"].get("mentioned"))
    snippet_hits = sum(1 for r in results if r["google_ai"].get("owns_snippet"))
    ranked = sum(1 for r in results if (r["google_ai"].get("organic_position") or 0) > 0)
    sov = {}
    for r in results:
        for riv in r["claude"].get("rivals_mentioned", []):
            sov[riv] = sov.get(riv, 0) + 1
    sov["_you"] = claude_hits
    gaps = [{"prompt": r["prompt"],
             "rivals": r["claude"].get("rivals_mentioned", [])}
            for r in results
            if not r["claude"].get("mentioned") and r["claude"].get("rivals_mentioned")]
    score = int(round(100 * (claude_hits * 0.6 + snippet_hits * 0.25 + ranked * 0.15) / n))
    return {"score": min(100, score),
            "mention_rate": round(100 * claude_hits / n, 1),
            "prompts_tested": n,
            "engines": {"claude": {"connected": any(r["claude"].get("connected") for r in results),
                                   "mentions": claude_hits},
                        "google_ai": {"connected": any(r["google_ai"].get("connected") for r in results),
                                      "snippets": snippet_hits, "ranked": ranked},
                        "openai": {"connected": False},
                        "perplexity": {"connected": False}},
            "share_of_voice": dict(sorted(sov.items(), key=lambda kv: -kv[1])),
            "gaps": gaps[:15]}


# ---------------------------------------------------------------- on-site AEO
def quotable_audit(crawl: dict) -> dict:
    """AI engines quote a heading that ASKS and a paragraph that ANSWERS.
    A page of vague headings never gets quoted, however good the prose is."""
    pages = [r for r in (crawl or {}).get("urls", []) if r.get("status") == 200]
    rows = []
    for r in pages:
        h2 = r.get("h2") or []
        questions = [h for h in h2 if h.strip().endswith("?")]
        rows.append({"url": r["url"], "h2_count": len(h2),
                     "question_headings": len(questions),
                     "quotable": len(questions) >= 2,
                     "has_faq_schema": "FAQPage" in (r.get("schema_types") or [])})
    quotable = sum(1 for x in rows if x["quotable"])
    faq = sum(1 for x in rows if x["has_faq_schema"])
    return {"pages": len(rows), "quotable": quotable,
            "quotable_pct": round(100 * quotable / max(len(rows), 1), 1),
            "faq_schema": faq,
            "faq_pct": round(100 * faq / max(len(rows), 1), 1),
            "weakest": [x for x in rows if not x["quotable"]][:20],
            "rows": rows}


def llms_txt(crawl: dict, *, site_name="Anthropos Automation", description="",
             max_links: int = 60) -> str:
    """Generate /llms.txt — the emerging convention telling AI crawlers what
    your site is and which pages matter. Costs nothing, takes one upload."""
    pages = [r for r in (crawl or {}).get("urls", [])
             if r.get("status") == 200 and r.get("title")]
    services = [p for p in pages if "/services/" in p["url"] or "/business-launch" in p["url"]]
    guides = [p for p in pages if "/guide" in p["url"]]
    blogs = [p for p in pages if "/blog" in p["url"]]
    other = [p for p in pages if p not in services + guides + blogs]

    def block(title, items, cap):
        if not items:
            return ""
        lines = [f"\n## {title}\n"]
        for p in items[:cap]:
            desc = (p.get("meta_desc") or "").strip().replace("\n", " ")
            lines.append(f"- [{p['title'][:90]}]({p['url']})"
                         + (f": {desc[:120]}" if desc else ""))
        return "\n".join(lines) + "\n"

    head = f"# {site_name}\n\n> {description or 'AI and n8n business automation.'}\n"
    return (head + block("Services", services, 12) + block("Guides", guides, max_links // 2)
            + block("Articles", blogs, max_links // 3) + block("Other", other, 10))


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    m = find_mentions(
        "For law firms I'd look at Anthropos Automation, Zapier partners, or pricefy.io.",
        "Anthropos", "anthropos-automation.com", rivals=["pricefy.io", "acme.com"])
    assert m["mentioned"] and m["rivals_mentioned"] == ["pricefy.io"], m

    m2 = find_mentions("Try Zapier or Make.", "Anthropos", "anthropos-automation.com",
                       rivals=["zapier.com"])
    assert not m2["mentioned"] and m2["rivals_mentioned"] == ["zapier.com"], m2

    fake = [
        {"prompt": "a", "claude": {"connected": True, "mentioned": True, "rivals_mentioned": []},
         "google_ai": {"connected": True, "owns_snippet": True, "organic_position": 2}},
        {"prompt": "b", "claude": {"connected": True, "mentioned": False,
                                   "rivals_mentioned": ["pricefy.io"]},
         "google_ai": {"connected": True, "owns_snippet": False, "organic_position": 0}},
    ]
    s = summarize(fake)
    assert s["mention_rate"] == 50.0, s
    assert s["gaps"] and s["gaps"][0]["prompt"] == "b", s["gaps"]
    assert s["share_of_voice"]["_you"] == 1 and s["share_of_voice"]["pricefy.io"] == 1, s
    assert s["engines"]["openai"]["connected"] is False, "never claim an engine we can't reach"
    assert 0 < s["score"] <= 100, s["score"]

    crawl = {"urls": [
        {"url": "https://x.com/guide-a", "status": 200, "title": "Guide A",
         "meta_desc": "How firms automate intake.",
         "h2": ["What is the problem?", "How does it work?"], "schema_types": ["FAQPage"]},
        {"url": "https://x.com/services/medical", "status": 200, "title": "Medical",
         "meta_desc": "", "h2": ["Overview", "Details"], "schema_types": []},
    ]}
    qa = quotable_audit(crawl)
    assert qa["quotable"] == 1 and qa["faq_schema"] == 1, qa
    assert qa["weakest"][0]["url"].endswith("/services/medical"), qa["weakest"]

    txt = llms_txt(crawl, site_name="Anthropos", description="AI + n8n automation.")
    assert "# Anthropos" in txt and "## Services" in txt and "## Guides" in txt, txt
    assert "https://x.com/guide-a" in txt, txt
    assert len(default_prompts()) >= 18, len(default_prompts())
    print("aeo self-check OK — mentions, share of voice, quotable audit, llms.txt")
