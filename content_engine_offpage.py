"""
content_engine_offpage.py
============================================================================
E11 + E12 — OFF-PAGE. The half of SEO the dashboard had nothing for.

E11 BACKLINK INTELLIGENCE (DataForSEO, key-gated)
    referring domains, new/lost links, anchor mix, rival link gap, toxic flags

E12 LINK ACQUISITION (Serper + the outreach engine that already exists)
    prospect -> qualify -> personalised pitch -> YOUR approval -> send -> verify

Honest limits, stated in code because they matter:
  * Without DataForSEO there is NO way to see your own backlink profile —
    Google's Links report has no API. Prospecting still works without it.
  * Pitches are NEVER auto-sent. Mass link-begging burns a domain, and this
    domain was just warmed up. `send_ok` from the model plus a human click.
  * Nothing here buys links or offers exchanges — that is link spam.

Run offline self-check:  python content_engine_offpage.py
============================================================================
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

log = logging.getLogger("offpage")

PROSPECT_KEY = "link_prospects"
PROFILE_KEY = "backlink_profile"

# Query templates that find pages which LINK OUT by design.
PROSPECT_QUERIES = {
    "resource_page": ['{kw} "useful resources"', '{kw} "helpful links"',
                      '{kw} inurl:resources'],
    "guest_post": ['{kw} "write for us"', '{kw} "guest post" guidelines',
                   '{kw} "contribute to"'],
    "listicle": ['best {kw} tools', 'top {kw} companies', '{kw} alternatives'],
    "broken_link": ['{kw} inurl:links', '{kw} "recommended reading"'],
}

# Never pitch these — platforms, competitors' own sites, or junk.
_SKIP_DOMAINS = {"facebook.com", "twitter.com", "x.com", "linkedin.com", "reddit.com",
                 "youtube.com", "instagram.com", "pinterest.com", "medium.com",
                 "quora.com", "wikipedia.org", "amazon.com", "google.com",
                 "yelp.com", "tiktok.com", "github.com"}


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _skip(url: str, own_domain: str = "") -> bool:
    d = _domain(url)
    if not d:
        return True
    if own_domain and own_domain.replace("www.", "") in d:
        return True
    return any(d == s or d.endswith("." + s) for s in _SKIP_DOMAINS)


# ======================================================================
#  E11 — BACKLINK INTELLIGENCE
# ======================================================================
def profile(domain: str, store=None, *, limit: int = 100) -> dict:
    """Your own backlink profile. Empty (with a reason) when DataForSEO is off —
    never a fabricated number."""
    from datetime import datetime, timezone
    try:
        import content_engine_connectors as C
        dfs = C.DataForSEO()
    except Exception as e:
        return {"connected": False, "reason": f"connector unavailable: {e}"}
    if not dfs.available():
        return {"connected": False,
                "reason": "DataForSEO not connected — set DATAFORSEO_LOGIN + "
                          "DATAFORSEO_PASSWORD. Google exposes no backlink API, "
                          "so this is the only source."}
    summary = dfs.backlink_summary(domain) or {}
    domains = dfs.referring_domains(domain, limit) or []
    links = dfs.backlinks(domain, limit) or []
    anchors = {}
    for l in links:
        a = (l.get("anchor") or "").strip().lower() or "(empty)"
        anchors[a] = anchors.get(a, 0) + 1
    out = {"connected": True,
           "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "domain": domain, **summary,
           "referring_list": domains[:50],
           "links": links[:50],
           "anchors": sorted(anchors.items(), key=lambda kv: -kv[1])[:25],
           "lost": [l for l in links if l.get("lost")][:25],
           "dofollow_pct": round(100 * sum(1 for l in links if l.get("dofollow"))
                                 / max(len(links), 1), 1),
           "toxic": [l for l in links
                     if (l.get("rank", 100) or 0) < 10 and not l.get("lost")][:25],
           "score": min(100, int((summary.get("referring_domains", 0) or 0) * 2))}
    if store is not None:
        try:
            store.set_setting(PROFILE_KEY, out)
        except Exception as e:
            log.warning("profile save failed: %s", e)
    return out


def link_gap(our_profile: dict, rival_profiles: list) -> list:
    """Domains that link to rivals but not to you — the single most actionable
    off-page list there is, because they already link to someone like you."""
    ours = {d.get("domain") for d in (our_profile or {}).get("referring_list", [])}
    gap = {}
    for rp in rival_profiles or []:
        rival = rp.get("domain", "")
        for d in rp.get("referring_list", []):
            dom = d.get("domain")
            if not dom or dom in ours:
                continue
            g = gap.setdefault(dom, {"domain": dom, "rank": d.get("rank", 0),
                                     "links_to": [], "backlinks": d.get("backlinks", 0)})
            if rival not in g["links_to"]:
                g["links_to"].append(rival)
    out = list(gap.values())
    for g in out:
        g["rivals_linked"] = len(g["links_to"])
    return sorted(out, key=lambda g: (-g["rivals_linked"], -g["rank"]))


# ======================================================================
#  E12 — PROSPECTING
# ======================================================================
def find_prospects(keywords: list, *, kinds=("resource_page", "guest_post"),
                   own_domain="", per_query: int = 8, limit: int = 60) -> list:
    """Serper-powered prospecting. One credit per query; dedupes by domain."""
    try:
        import content_engine_connectors as C
        s = C.Serper()
    except Exception as e:
        log.warning("serper unavailable: %s", e)
        return []
    if not s.available():
        return []
    seen, out = set(), []
    for kw in keywords or []:
        for kind in kinds:
            for tpl in PROSPECT_QUERIES.get(kind, []):
                if len(out) >= limit:
                    return out
                for r in s.search(tpl.format(kw=kw), num=per_query) or []:
                    url = r.get("link", "")
                    d = _domain(url)
                    if not d or d in seen or _skip(url, own_domain):
                        continue
                    seen.add(d)
                    out.append({"domain": d, "url": url,
                                "title": r.get("title", ""),
                                "evidence": (r.get("snippet", "") or "")[:400],
                                "opportunity": kind, "keyword": kw,
                                "status": "found"})
    return out


def unlinked_mentions(brand: str, domain: str, *, limit: int = 20) -> list:
    """Pages that already NAME you but don't link. The warmest link ask there
    is — they already wrote about you."""
    try:
        import content_engine_connectors as C
        import content_engine_crawler as CR
        s = C.Serper()
    except Exception as e:
        log.warning("unlinked_mentions unavailable: %s", e)
        return []
    if not s.available():
        return []
    root = domain.replace("www.", "")
    results = s.search(f'"{brand}" -site:{root}', num=limit) or []
    out = []
    for r in results:
        url = r.get("link", "")
        if _skip(url, domain):
            continue
        _, status, html, _, _, _ = CR._fetch(url)
        if status != 200 or not html:
            continue
        if root in html.lower():
            continue                      # already links to us
        out.append({"domain": _domain(url), "url": url, "title": r.get("title", ""),
                    "evidence": (r.get("snippet", "") or "")[:400],
                    "opportunity": "unlinked_mention", "keyword": brand,
                    "status": "found"})
    return out


def qualify(prospects: list, *, min_title_len: int = 10) -> list:
    """Cheap deterministic filter before we spend a token on a pitch."""
    out = []
    for p in prospects or []:
        score = 0
        if p.get("evidence"):
            score += 40
        if len(p.get("title", "")) >= min_title_len:
            score += 20
        if p.get("opportunity") == "unlinked_mention":
            score += 40
        elif p.get("opportunity") == "resource_page":
            score += 25
        elif p.get("opportunity") == "broken_link":
            score += 20
        else:
            score += 10
        p = dict(p, fit_score=min(100, score))
        if p["fit_score"] >= 40:
            out.append(p)
    return sorted(out, key=lambda x: -x["fit_score"])


def pitch(prospect: dict, *, asset_url="", asset_title="", asset_value="",
          sender_name="", store=None) -> dict:
    """Write ONE pitch. Returns the draft — it is NOT sent here."""
    payload = {"prospect": prospect, "asset_url": asset_url,
               "asset_title": asset_title, "asset_value": asset_value,
               "sender_name": sender_name}
    try:
        import content_engine_orchestrator as orch
        job = {"job_id": f"pitch_{prospect.get('domain','x')}", "type": "link_pitch",
               "status": "pitching", "payload": payload, "cost_so_far_usd": 0.0}
        data, cost = orch.run_llm_skill(job, "link_pitch", store)
    except Exception as e:
        log.warning("pitch failed for %s: %s", prospect.get("domain"), e)
        return {**prospect, "status": "pitch_failed", "error": str(e)}
    if not (data or {}).get("send_ok", False):
        return {**prospect, "status": "rejected",
                "reason": (data or {}).get("angle", "model judged this a poor fit"),
                "cost": cost}
    return {**prospect, "status": "awaiting_approval",
            "subject": data.get("subject", ""), "body": data.get("body", ""),
            "angle": data.get("angle", ""), "cost": cost}


def run_prospecting(store, *, keywords, brand, domain, asset_url="", asset_title="",
                    asset_value="", sender_name="", limit: int = 15,
                    include_mentions: bool = True) -> dict:
    """Find -> qualify -> pitch -> park in the approval queue. Sends nothing."""
    from datetime import datetime, timezone
    found = find_prospects(keywords, own_domain=domain, limit=limit * 3)
    if include_mentions:
        found += unlinked_mentions(brand, domain, limit=10)
    good = qualify(found)[:limit]
    existing = load_prospects(store)
    known = {p.get("domain") for p in existing}
    drafts = []
    for p in good:
        if p["domain"] in known:
            continue
        drafts.append(pitch(p, asset_url=asset_url, asset_title=asset_title,
                            asset_value=asset_value, sender_name=sender_name,
                            store=store))
    allp = existing + drafts
    save_prospects(store, allp)
    return {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "found": len(found), "qualified": len(good), "new_drafts": len(drafts),
            "total_pipeline": len(allp), "stats": pipeline_stats(allp)}


# ---------------------------------------------------------------- store
def load_prospects(store) -> list:
    try:
        return store.get_setting(PROSPECT_KEY, []) or []
    except Exception:
        return []


def save_prospects(store, prospects: list) -> None:
    try:
        store.set_setting(PROSPECT_KEY, (prospects or [])[:400])
    except Exception as e:
        log.warning("prospect save failed: %s", e)


def pipeline_stats(prospects: list) -> dict:
    by_status, by_kind = {}, {}
    for p in prospects or []:
        by_status[p.get("status", "found")] = by_status.get(p.get("status", "found"), 0) + 1
        by_kind[p.get("opportunity", "?")] = by_kind.get(p.get("opportunity", "?"), 0) + 1
    placed = by_status.get("placed", 0)
    contacted = by_status.get("sent", 0) + by_status.get("replied", 0) + placed
    return {"total": len(prospects or []), "by_status": by_status, "by_kind": by_kind,
            "awaiting_approval": by_status.get("awaiting_approval", 0),
            "contacted": contacted, "replied": by_status.get("replied", 0) + placed,
            "placed": placed,
            "win_rate": round(100 * placed / max(contacted, 1), 1)}


def verify_placements(prospects: list, domain: str) -> list:
    """Did the link actually appear? Crawl each contacted page and check."""
    try:
        import content_engine_crawler as CR
    except Exception:
        return prospects
    root = domain.replace("www.", "")
    for p in prospects or []:
        if p.get("status") not in ("sent", "replied"):
            continue
        _, status, html, _, _, _ = CR._fetch(p.get("url", ""))
        if status == 200 and root in (html or "").lower():
            p["status"] = "placed"
    return prospects


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    assert _domain("https://www.Example.com/a/b") == "example.com"
    assert _skip("https://facebook.com/x"), "platforms must be skipped"
    assert _skip("https://m.facebook.com/x"), "subdomains of platforms too"
    assert _skip("https://linkedin.com/in/x"), "platforms must be skipped"
    assert _skip("https://anthropos-automation.com/x", "anthropos-automation.com"), "never pitch ourselves"
    assert not _skip("https://legaltechblog.de/resources", "anthropos-automation.com")

    raw = [
        {"domain": "a.com", "url": "https://a.com/resources", "title": "Automation Resources",
         "evidence": "A list of useful automation resources", "opportunity": "resource_page"},
        {"domain": "b.com", "url": "https://b.com/x", "title": "", "evidence": "",
         "opportunity": "listicle"},
        {"domain": "c.com", "url": "https://c.com/post", "title": "We use Anthropos",
         "evidence": "mentions you", "opportunity": "unlinked_mention"},
    ]
    q = qualify(raw)
    assert [p["domain"] for p in q] == ["c.com", "a.com"], [p["domain"] for p in q]
    assert q[0]["fit_score"] == 100, q[0]

    ours = {"referring_list": [{"domain": "known.com", "rank": 30}]}
    rivals = [{"domain": "pricefy.io", "referring_list": [
                  {"domain": "known.com", "rank": 30},
                  {"domain": "newlink.com", "rank": 55, "backlinks": 3}]},
              {"domain": "rival2.com", "referring_list": [
                  {"domain": "newlink.com", "rank": 55, "backlinks": 2}]}]
    gap = link_gap(ours, rivals)
    assert len(gap) == 1 and gap[0]["domain"] == "newlink.com", gap
    assert gap[0]["rivals_linked"] == 2, gap[0]

    class S:
        def __init__(self): self.d = {}
        def get_setting(self, k, default=None): return self.d.get(k, default)
        def set_setting(self, k, v): self.d[k] = v

    st = S()
    save_prospects(st, [{"domain": "a.com", "status": "sent", "opportunity": "resource_page"},
                        {"domain": "b.com", "status": "placed", "opportunity": "guest_post"},
                        {"domain": "c.com", "status": "awaiting_approval",
                         "opportunity": "unlinked_mention"}])
    ps = pipeline_stats(load_prospects(st))
    assert ps["awaiting_approval"] == 1 and ps["placed"] == 1, ps
    assert ps["contacted"] == 2 and ps["win_rate"] == 50.0, ps

    off = profile("anthropos-automation.com")
    assert off["connected"] is False and "DataForSEO" in off["reason"], off
    print("offpage self-check OK — prospect filter, qualify, link gap, pipeline, honest degrade")
