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
    would.

    Uses the RAW Anthropic client, not call_provider: call_provider forces
    structured JSON output for skill calls, and this needs plain prose. Same
    pattern as providers.web_research(). (The first version called
    P.CHEAP_MODEL — which lives in the orchestrator, not providers — so every
    probe silently returned "" and the board honestly reported zero mentions
    for a probe that never ran.)
    """
    import os
    try:
        import content_engine_providers as P
        model = os.getenv("CHEAP_MODEL", "claude-haiku-4-5")
        client = P._get_anthropic()
        resp = client.messages.create(
            model=model, max_tokens=600,
            messages=[{"role": "user", "content": prompt}])
        text = "\n".join(b.text for b in resp.content
                         if getattr(b, "type", "") == "text" and getattr(b, "text", ""))
        try:                                   # cost accounting, best-effort
            u = resp.usage
            cost, _ = P._compute_cost(model, {
                "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0})
            import content_engine_connectors as C
            C._record_cost(cost, "aeo_probe")
            C.record_api_spend("anthropic", cost)
        except Exception:
            pass
        return text.strip()
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


def _openai_answer(prompt: str) -> str:
    """E15 — ChatGPT, key-gated. Never faked: no key means 'not connected'."""
    try:
        import content_engine_connectors as C
        key = C._env("OPENAI_API_KEY")
        if not (key and C._requests()):
            return ""
        j = C._post_json("https://api.openai.com/v1/chat/completions",
                         {"model": C._env("OPENAI_AEO_MODEL", "gpt-4o-mini"),
                          "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 500},
                         headers={"Authorization": f"Bearer {key}",
                                  "Content-Type": "application/json"})
        C.record_api_spend("openai", 0.0004)
        return ((j or {}).get("choices") or [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        log.warning("openai probe failed: %s", e)
        return ""


def _perplexity_answer(prompt: str) -> str:
    """E15 — Perplexity, key-gated. It cites sources, so this is the richest
    engine for citation attribution."""
    try:
        import content_engine_connectors as C
        key = C._env("PERPLEXITY_API_KEY")
        if not (key and C._requests()):
            return ""
        j = C._post_json("https://api.perplexity.ai/chat/completions",
                         {"model": C._env("PERPLEXITY_MODEL", "sonar"),
                          "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 500},
                         headers={"Authorization": f"Bearer {key}",
                                  "Content-Type": "application/json"})
        C.record_api_spend("perplexity", 0.001)
        txt = ((j or {}).get("choices") or [{}])[0].get("message", {}).get("content", "")
        # Perplexity returns its sources separately — fold them in so the
        # citation extractor sees them.
        for c in (j or {}).get("citations", []) or []:
            txt += f"\n{c}"
        return txt
    except Exception as e:
        log.warning("perplexity probe failed: %s", e)
        return ""


def _gemini_answer(prompt: str) -> str:
    """E15 — Gemini, key-gated. Google offers a free tier for this."""
    try:
        import content_engine_connectors as C
        key = C._env("GEMINI_API_KEY")
        if not (key and C._requests()):
            return ""
        model = C._env("GEMINI_MODEL", "gemini-2.0-flash")
        j = C._post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
            {"contents": [{"parts": [{"text": prompt}]}]},
            headers={"Content-Type": "application/json"})
        parts = (((j or {}).get("candidates") or [{}])[0]
                 .get("content", {}).get("parts") or [{}])
        return parts[0].get("text", "")
    except Exception as e:
        log.warning("gemini probe failed: %s", e)
        return ""


# Resolved by NAME at call time, not captured as function objects — otherwise
# a test (or a hot-patch) that replaces one of these is silently ignored.
_ENGINES = [("claude", "_claude_answer", "ANTHROPIC_API_KEY"),
            ("openai", "_openai_answer", "OPENAI_API_KEY"),
            ("perplexity", "_perplexity_answer", "PERPLEXITY_API_KEY"),
            ("gemini", "_gemini_answer", "GEMINI_API_KEY")]


def probe(prompt: str, *, brand: str, domain: str, rivals=None, store=None) -> dict:
    """One buyer question, asked of every connected AI engine."""
    out = {"prompt": prompt, "google_ai": _google_ai(prompt, domain)}
    for name, fname, keyname in _ENGINES:
        fn = globals().get(fname)
        try:
            answer = fn(prompt, store) if name == "claude" else fn(prompt)
        except Exception as e:
            log.warning("%s probe failed: %s", name, e)
            answer = ""
        if not answer:
            out[name] = {"connected": False, "mentioned": False,
                         "rivals_mentioned": [], "citations": [],
                         "reason": f"{keyname} not set or call failed"}
            continue
        m = find_mentions(answer, brand, domain, rivals)
        out[name] = {"connected": True, **m,
                     "citations": extract_citations(answer, domain),
                     "quality": answer_quality(answer, brand,
                                               m.get("position_char") if m["mentioned"] else None),
                     "excerpt": answer[:280]}
    return out


def run_probes(store=None, *, brand="Anthropos", domain="anthropos-automation.com",
               prompts=None, rivals=None, limit: int = 30) -> dict:
    from datetime import datetime, timezone
    prompts = (prompts or get_prompts(store))[:limit]
    results = [probe(p, brand=brand, domain=domain, rivals=rivals, store=store)
               for p in prompts]
    out = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "brand": brand, "domain": domain,
           "results": results, **summarize(results, rivals)}
    out["citations"] = citation_summary(results)
    if store is not None:
        try:
            store.set_setting(SETTING_KEY, out)
        except Exception as e:
            log.warning("aeo save failed: %s", e)
        record_history(store, out)
    return out


ENGINE_NAMES = ("claude", "openai", "perplexity", "gemini")


def summarize(results: list, rivals=None) -> dict:
    """Aggregate across EVERY connected engine — not just Claude."""
    n = len(results or [])
    if not n:
        return {"score": 0, "mention_rate": 0, "engines": {}, "gaps": [],
                "share_of_voice": {}, "prompts_tested": 0, "placement": {}}
    engines, any_hits = {}, 0
    for eng in ENGINE_NAMES:
        connected = any((r.get(eng) or {}).get("connected") for r in results)
        hits = sum(1 for r in results if (r.get(eng) or {}).get("mentioned"))
        engines[eng] = {"connected": connected, "mentions": hits,
                        "rate": round(100 * hits / n, 1) if connected else 0,
                        "reason": ("" if connected else
                                   next((( r.get(eng) or {}).get("reason", "")
                                         for r in results if (r.get(eng) or {}).get("reason")), ""))}
    snippet_hits = sum(1 for r in results if (r.get("google_ai") or {}).get("owns_snippet"))
    ranked = sum(1 for r in results if ((r.get("google_ai") or {}).get("organic_position") or 0) > 0)
    engines["google_ai"] = {"connected": any((r.get("google_ai") or {}).get("connected")
                                             for r in results),
                            "snippets": snippet_hits, "ranked": ranked}
    # A prompt counts as WON if any connected engine named us.
    won = [r for r in results
           if any((r.get(e) or {}).get("mentioned") for e in ENGINE_NAMES)]
    any_hits = len(won)
    sov, placement = {}, {"first": 0, "middle": 0, "buried": 0}
    recommended = 0
    for r in results:
        for e in ENGINE_NAMES:
            blk = r.get(e) or {}
            for riv in blk.get("rivals_mentioned", []) or []:
                sov[riv] = sov.get(riv, 0) + 1
            q = blk.get("quality") or {}
            if q.get("placement") in placement:
                placement[q["placement"]] += 1
            if q.get("recommended"):
                recommended += 1
    sov["_you"] = any_hits
    gaps = [{"prompt": r["prompt"],
             "rivals": sorted({riv for e in ENGINE_NAMES
                               for riv in ((r.get(e) or {}).get("rivals_mentioned") or [])})}
            for r in results
            if not any((r.get(e) or {}).get("mentioned") for e in ENGINE_NAMES)
            and any((r.get(e) or {}).get("rivals_mentioned") for e in ENGINE_NAMES)]
    live_engines = max(sum(1 for e in ENGINE_NAMES if engines[e]["connected"]), 1)
    score = int(round(100 * (any_hits * 0.6 + snippet_hits * 0.25 + ranked * 0.15) / n))
    return {"score": min(100, score),
            "mention_rate": round(100 * any_hits / n, 1),
            "prompts_tested": n, "prompts_won": any_hits,
            "prompts_lost": n - any_hits,
            "engines_live": live_engines, "engines": engines,
            "placement": placement, "recommended": recommended,
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


# ===========================================================================
# E16 — AI CRAWLER ACCESS.  The hard blocker nobody checks.
# If robots.txt disallows GPTBot / ClaudeBot / PerplexityBot, you can NEVER be
# cited by that engine however good the content is. Costs nothing to check.
# ===========================================================================
AI_BOTS = {
    "GPTBot": "ChatGPT / OpenAI training",
    "OAI-SearchBot": "ChatGPT Search",
    "ChatGPT-User": "ChatGPT live browsing",
    "ClaudeBot": "Claude / Anthropic",
    "PerplexityBot": "Perplexity",
    "Google-Extended": "Google Gemini + AI Overviews",
    "Applebot-Extended": "Apple Intelligence",
    "CCBot": "Common Crawl (feeds many models)",
}


def _parse_robots(text: str) -> dict:
    """robots.txt -> {user_agent_lower: {"allow":[...], "disallow":[...]}}"""
    groups, current = {}, []
    for raw in (text or "").splitlines():
        line = raw.split("#")[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field, value = field.strip().lower(), value.strip()
        if field == "user-agent":
            ua = value.lower()
            groups.setdefault(ua, {"allow": [], "disallow": []})
            current = [ua]
        elif field in ("allow", "disallow") and current:
            for ua in current:
                groups.setdefault(ua, {"allow": [], "disallow": []})[field].append(value)
    return groups


def _bot_blocked(groups: dict, bot: str):
    """-> (blocked, why). A bot-specific rule beats the '*' catch-all."""
    rules = groups.get(bot.lower())
    scope = "its own robots.txt rule"
    if rules is None:
        rules = groups.get("*")
        scope = "the '*' catch-all rule"
    if rules is None:
        return False, "no robots.txt rule — crawling is allowed by default"
    if any(d == "/" for d in rules["disallow"]):
        return True, f"{scope} blocks the whole site (Disallow: /)"
    blocked = [d for d in rules["disallow"] if d]
    if blocked:
        return False, f"{scope} allows the site (blocks only {', '.join(blocked[:3])})"
    return False, f"{scope} allows crawling"


def crawler_access(site_url: str) -> dict:
    """Per AI engine: may it read your site at all?"""
    from urllib.parse import urljoin
    try:
        import content_engine_crawler as CR
        _, status, text, _, _, _ = CR._fetch(
            urljoin(site_url.rstrip("/") + "/", "robots.txt"))
    except Exception as e:
        return {"checked": False, "reason": f"could not fetch robots.txt: {e}",
                "bots": [], "blocked_count": 0, "allowed_count": 0}
    if status != 200:
        return {"checked": True, "robots_found": False, "status": status,
                "bots": [{"bot": b, "vendor": v, "blocked": False,
                          "why": "no robots.txt on the site — everything is allowed"}
                         for b, v in AI_BOTS.items()],
                "blocked_count": 0, "allowed_count": len(AI_BOTS)}
    groups = _parse_robots(text)
    bots = []
    for bot, vendor in AI_BOTS.items():
        blocked, why = _bot_blocked(groups, bot)
        bots.append({"bot": bot, "vendor": vendor, "blocked": blocked, "why": why})
    return {"checked": True, "robots_found": True, "status": status, "bots": bots,
            "blocked_count": sum(1 for b in bots if b["blocked"]),
            "allowed_count": sum(1 for b in bots if not b["blocked"]),
            "has_sitemap": "sitemap:" in (text or "").lower()}


# ===========================================================================
# E17 — CITATION ATTRIBUTION.  Which PAGE did the AI actually cite?
# ===========================================================================
_URL_RE = re.compile(r"https?://[^\s\)\]\"'>]+")


def extract_citations(text: str, domain: str) -> list:
    root = (domain or "").lower().replace("www.", "").split("/")[0]
    out = []
    for u in _URL_RE.findall(text or ""):
        clean = u.rstrip(".,);:")
        if root and root in clean.lower() and clean not in out:
            out.append(clean)
    return out


def citation_summary(results: list) -> dict:
    pages, by_engine = {}, {}
    for r in results or []:
        for eng in ("claude", "openai", "perplexity", "gemini"):
            cites = ((r.get(eng) or {}).get("citations")) or []
            if cites:
                by_engine[eng] = by_engine.get(eng, 0) + len(cites)
            for c in cites:
                pages[c] = pages.get(c, 0) + 1
    return {"total": sum(pages.values()), "unique_pages": len(pages),
            "by_engine": by_engine,
            "top_pages": sorted(pages.items(), key=lambda kv: -kv[1])[:15]}


# ===========================================================================
# E18 — ENTITY / KNOWLEDGE GRAPH.  sameAs is a primary citation signal.
# ===========================================================================
ENTITY_HOSTS = ["wikidata.org", "wikipedia.org", "linkedin.com", "crunchbase.com",
                "github.com", "x.com", "twitter.com", "facebook.com",
                "instagram.com", "youtube.com"]
KEY_ENTITIES = ["wikidata.org", "wikipedia.org", "linkedin.com", "crunchbase.com"]


def entity_audit(crawl: dict) -> dict:
    pages = [r for r in (crawl or {}).get("urls", []) if r.get("status") == 200]
    types = {}
    for r in pages:
        for t in r.get("schema_types") or []:
            types[t] = types.get(t, 0) + 1
    outbound = set()
    for r in pages:
        for l in r.get("outbound_links") or []:
            for host in ENTITY_HOSTS:
                if host in l.lower():
                    outbound.add(host)
    org = types.get("Organization", 0) + types.get("LocalBusiness", 0)
    person = types.get("Person", 0)
    return {"schema_types": sorted(types.items(), key=lambda kv: -kv[1]),
            "organization_pages": org, "person_pages": person,
            "entity_links": sorted(outbound),
            "missing_entities": [h for h in KEY_ENTITIES if h not in outbound],
            "score": min(100, org * 8 + person * 8 + len(outbound) * 9),
            "pages": len(pages)}


# ===========================================================================
# E19 — ANSWER QUALITY.  Named first, or buried in paragraph six?
# ===========================================================================
def answer_quality(answer: str, brand: str, mention_pos: int) -> dict:
    text = (answer or "")
    if not text or mention_pos is None:
        return {"placement": "absent", "share_pct": 0.0, "recommended": False}
    frac = mention_pos / max(len(text), 1)
    placement = ("first" if frac <= 0.2 else
                 "middle" if frac <= 0.6 else "buried")
    window = text[max(0, mention_pos - 160): mention_pos + 240].lower()
    recommended = any(w in window for w in
                      ("recommend", "best", "top choice", "strong option",
                       "worth considering", "good fit", "specialis"))
    dismissed = any(w in window for w in
                    ("however", "although", "less known", "limited", "unclear"))
    return {"placement": placement, "share_pct": round(100 * (1 - frac), 1),
            "recommended": recommended and not dismissed,
            "qualified": dismissed}


# ===========================================================================
# E20 — PROMPT LIBRARY + HISTORY.  Editable prompts, and a real trend.
# ===========================================================================
PROMPT_KEY = "aeo_prompts"
HISTORY_KEY = "aeo_history"
MAX_HISTORY = 60


def get_prompts(store=None) -> list:
    if store is not None:
        try:
            saved = store.get_setting(PROMPT_KEY, None)
            if saved:
                return list(saved)
        except Exception:
            pass
    return default_prompts()


def set_prompts(store, prompts: list) -> int:
    clean = [p.strip() for p in (prompts or []) if p and p.strip()][:80]
    try:
        store.set_setting(PROMPT_KEY, clean)
    except Exception as e:
        log.warning("prompt save failed: %s", e)
    return len(clean)


def record_history(store, snapshot: dict) -> list:
    """One row per run, so the boards show a TREND instead of a snapshot that
    silently overwrites the previous one."""
    try:
        hist = list(store.get_setting(HISTORY_KEY, []) or [])
    except Exception:
        hist = []
    hist.append({"at": snapshot.get("at", ""), "score": snapshot.get("score", 0),
                 "mention_rate": snapshot.get("mention_rate", 0),
                 "prompts": snapshot.get("prompts_tested", 0),
                 "citations": (snapshot.get("citations") or {}).get("total", 0)})
    hist = hist[-MAX_HISTORY:]
    try:
        store.set_setting(HISTORY_KEY, hist)
    except Exception as e:
        log.warning("history save failed: %s", e)
    return hist


def get_history(store) -> list:
    try:
        return list(store.get_setting(HISTORY_KEY, []) or [])
    except Exception:
        return []


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
        {"prompt": "a",
         "claude": {"connected": True, "mentioned": True, "rivals_mentioned": [],
                    "citations": ["https://anthropos-automation.com/guide-a"],
                    "quality": {"placement": "first", "recommended": True}},
         "openai": {"connected": False, "mentioned": False, "rivals_mentioned": [],
                    "reason": "OPENAI_API_KEY not set"},
         "google_ai": {"connected": True, "owns_snippet": True, "organic_position": 2}},
        {"prompt": "b",
         "claude": {"connected": True, "mentioned": False,
                    "rivals_mentioned": ["pricefy.io"], "citations": [],
                    "quality": {"placement": "absent"}},
         "openai": {"connected": False, "mentioned": False, "rivals_mentioned": [],
                    "reason": "OPENAI_API_KEY not set"},
         "google_ai": {"connected": True, "owns_snippet": False, "organic_position": 0}},
    ]
    s = summarize(fake)
    assert s["mention_rate"] == 50.0, s
    assert s["prompts_won"] == 1 and s["prompts_lost"] == 1, s
    assert s["gaps"] and s["gaps"][0]["prompt"] == "b", s["gaps"]
    assert s["share_of_voice"]["_you"] == 1 and s["share_of_voice"]["pricefy.io"] == 1, s
    assert s["engines"]["openai"]["connected"] is False, "never claim an engine we can't reach"
    assert s["engines"]["openai"]["reason"], "an unreachable engine must say WHY"
    assert s["engines"]["claude"]["rate"] == 50.0, s["engines"]["claude"]
    assert s["placement"]["first"] == 1 and s["recommended"] == 1, s
    assert s["engines_live"] == 1, s["engines_live"]
    assert 0 < s["score"] <= 100, s["score"]

    # ---- REGRESSION: every cross-module symbol the probe uses must EXIST ----
    # A probe that silently returns "" reads as "no AI mentions you" — an
    # honest-looking zero produced by a broken call. P.CHEAP_MODEL did not
    # exist (it lives in the orchestrator) and 18 probes failed in production
    # while the board reported 0% mention rate. Never again: assert the names.
    import content_engine_providers as _P
    import content_engine_orchestrator as _O
    for _sym in ("_get_anthropic", "_compute_cost"):
        assert hasattr(_P, _sym), f"providers.{_sym} is gone — _claude_answer would fail"
    assert not hasattr(_P, "CHEAP_MODEL"), \
        "CHEAP_MODEL lives in the orchestrator; do not reach for it on providers"
    assert hasattr(_O, "CHEAP_MODEL"), "orchestrator.CHEAP_MODEL is the real one"
    import content_engine_connectors as _C
    for _sym in ("_record_cost", "record_api_spend", "_env", "_post_json", "_requests"):
        assert hasattr(_C, _sym), f"connectors.{_sym} is gone — the probes would fail"

    # A failing engine must degrade to not-connected, never to a false zero.
    _orig = globals()["_claude_answer"]
    globals()["_claude_answer"] = lambda p, s=None: ""
    try:
        r = probe("q", brand="Anthropos", domain="x.com")
        assert r["claude"]["connected"] is False, r["claude"]
        assert "not set or call failed" in r["claude"]["reason"], r["claude"]
    finally:
        globals()["_claude_answer"] = _orig

    # ---- E17 citations ----
    assert extract_citations("See https://anthropos-automation.com/guide-a. Also https://x.com/y",
                             "anthropos-automation.com") == \
        ["https://anthropos-automation.com/guide-a"]
    cs = citation_summary(fake)
    assert cs["total"] == 1 and cs["unique_pages"] == 1, cs
    assert cs["top_pages"][0][0].endswith("/guide-a"), cs

    # ---- E16 AI crawler access (the potential hard blocker) ----
    robots = ("User-agent: GPTBot\nDisallow: /\n\n"
              "User-agent: *\nDisallow: /wp-admin/\nSitemap: https://x.com/s.xml\n")
    g = _parse_robots(robots)
    blocked, why = _bot_blocked(g, "GPTBot")
    assert blocked and "whole site" in why, (blocked, why)
    ok, why2 = _bot_blocked(g, "ClaudeBot")
    assert not ok and "catch-all" in why2, (ok, why2)
    assert not _bot_blocked({}, "PerplexityBot")[0], "no robots.txt = allowed"
    assert _bot_blocked({"*": {"allow": [], "disallow": ["/"]}}, "CCBot")[0], "site-wide block"

    # ---- E18 entities ----
    ea = entity_audit({"urls": [
        {"url": "https://x.com/a", "status": 200, "schema_types": ["Organization"],
         "outbound_links": ["https://linkedin.com/company/x", "https://random.com"]},
        {"url": "https://x.com/b", "status": 200, "schema_types": ["Article"],
         "outbound_links": []}]})
    assert ea["organization_pages"] == 1 and "linkedin.com" in ea["entity_links"], ea
    assert "wikidata.org" in ea["missing_entities"], ea["missing_entities"]
    assert ea["score"] > 0

    # ---- E19 answer quality ----
    txt = "Anthropos Automation is a strong option here. " + "x" * 400
    q = answer_quality(txt, "Anthropos", 0)
    assert q["placement"] == "first" and q["recommended"], q
    q2 = answer_quality("x" * 400 + " Anthropos", "Anthropos", 400)
    assert q2["placement"] == "buried", q2

    # ---- E20 prompt library + history ----
    class _S:
        def __init__(self): self.d = {}
        def get_setting(self, k, dflt=None): return self.d.get(k, dflt)
        def set_setting(self, k, v): self.d[k] = v
    st = _S()
    assert len(get_prompts(st)) >= 18, "falls back to the built-in buyer questions"
    assert set_prompts(st, ["  my own question  ", "", "another"]) == 2
    assert get_prompts(st) == ["my own question", "another"], get_prompts(st)
    record_history(st, {"at": "2026-07-30T10:00:00", "score": 0, "mention_rate": 0.0,
                        "prompts_tested": 18, "citations": {"total": 0}})
    record_history(st, {"at": "2026-07-31T10:00:00", "score": 12, "mention_rate": 11.0,
                        "prompts_tested": 18, "citations": {"total": 3}})
    h = get_history(st)
    assert len(h) == 2 and h[-1]["score"] == 12 and h[-1]["citations"] == 3, h

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
