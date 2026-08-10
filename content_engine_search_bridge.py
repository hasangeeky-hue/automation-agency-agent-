# -*- coding: utf-8 -*-
"""Feed the Search OS screens from the data this engine already has.

The Search OS screens read one vocabulary (search_totals, tracked_keywords,
domain_profile, prompts). content_engine_seo_ops.build_ctx() produces a
different one (insights, ranks, offpage, aeo). Both were written correctly
and neither knew about the other, so Search Console and GA4 have been
connected the whole time and the new screens showed "not connected".

This module is the ONE place that translates. It is deliberately the only
one: two hand-written mappings that must agree is the bug that has cost
this project five outages.

WHAT IT WILL NOT DO
-------------------
It will not upgrade a number by moving it. Two temptations were refused
here, and both are commented at the site:

  * GSC impressions are NOT search volume. Impressions count how often
    YOU appeared; volume counts how often people searched. Putting
    impressions in a Volume column would make every keyword look
    proportional to your current ranking, which is exactly backwards.
  * Average position is impression-weighted, never a mean of the
    per-query averages, which would let one query with four impressions
    move the headline as much as one with forty thousand.

Where the source genuinely has nothing, this returns nothing, and the
screen's empty state does its job.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

GSC = "Google Search Console"
GA4 = "GA4"


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return list(x) if isinstance(x, (list, tuple)) else []


def _f(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Search Console
# ---------------------------------------------------------------------------
def _gsc(ctx) -> dict:
    return _d(_d(_d(ctx).get("insights")).get("gsc"))


def _ga4(ctx) -> dict:
    return _d(_d(_d(ctx).get("insights")).get("ga4"))


def _gsc_totals(ctx) -> dict:
    """Clicks, impressions and position from the daily rows.

    Summed first and divided once, per the ratio rule. Position is
    weighted by impressions: a query seen four times must not move the
    headline as much as one seen forty thousand times, and a plain mean
    of the per-row averages would let it.
    """
    daily = _l(_gsc(ctx).get("daily"))
    if not daily:
        return {}
    clicks = sum(_f(r.get("clicks"), 0) or 0 for r in daily)
    imps = sum(_f(r.get("impressions"), 0) or 0 for r in daily)
    wsum = sum((_f(r.get("position"), 0) or 0) * (_f(r.get("impressions"), 0) or 0)
               for r in daily)
    return {
        "clicks": int(clicks),
        "impressions": int(imps),
        # None, not 0.0: no impressions means there was no rate, not a
        # rate of nought.
        "ctr": round(clicks / imps * 100, 2) if imps else None,
        "position": round(wsum / imps, 1) if imps else None,
        "days": len(daily),
    }


def _ga4_totals(ctx) -> dict:
    t = _d(_ga4(ctx).get("totals"))
    if not t:
        return {}
    return {"sessions": _f(t.get("sessions")),
            "users": _f(t.get("totalUsers")),
            "new_users": _f(t.get("newUsers")),
            "engagement_rate": _f(t.get("engagementRate"))}


#: GA4's default channel group names that mean "someone found us in a
#: search engine without us paying". Deliberately explicit. Matching a
#: bare "organic" would swallow Organic Social, Organic Video and
#: Organic Shopping, which are three other things entirely and would
#: inflate the one number this whole section is about.
ORGANIC_CHANNELS = ("organic search",)


def _organic(ctx) -> dict:
    """Organic sessions, and an account of the lookup either way.

    A bare None here is the worst possible answer, because it reads
    exactly like "GA4 is not connected" when the truth may be "GA4
    answered and organic search was not in what it returned". The two
    call for completely different actions, so this reports which.
    """
    rows = _l(_ga4(ctx).get("channels"))
    if not rows:
        return {"sessions": None, "seen": [],
                "why": "GA4 returned no channel breakdown for this window"}
    seen = []
    for row in rows:
        d = _d(row)
        name = str(d.get("sessionDefaultChannelGroup") or "").strip()
        seen.append(name)
        if name.lower() in ORGANIC_CHANNELS:
            return {"sessions": _f(d.get("sessions")), "seen": seen,
                    "why": "GA4 channel '" + name + "'"}
    return {
        "sessions": None,
        "seen": seen,
        "why": ("GA4 answered with " + str(len(seen)) + " channel(s) and "
                "Organic Search was not among them: "
                + (", ".join(x for x in seen if x) or "unnamed")
                + ". That is not the same as GA4 being disconnected, and "
                "it usually means no organic session was recorded in this "
                "window."),
    }


def _organic_sessions(ctx) -> Optional[float]:
    return _organic(ctx).get("sessions")


# ---------------------------------------------------------------------------
# the screens' vocabulary
# ---------------------------------------------------------------------------
def search_totals(ctx) -> Optional[dict]:
    g, a = _gsc_totals(ctx), _ga4_totals(ctx)
    if not g and not a:
        return None
    out = dict(g)
    org = _organic(ctx)
    out["sessions"] = org.get("sessions")
    out["sessions_note"] = org.get("why")
    out["channels_seen"] = org.get("seen")
    # Conversions and revenue are NOT pulled by ga4_full(), so they stay
    # absent. Showing 0 here would read as "search earned nothing",
    # which is a different and much worse claim than "not measured".
    out["conversions"] = None
    out["revenue"] = None
    # the same daily rows the totals were summed from, so the screen
    # can draw clicks per day without a second source of truth
    out["daily"] = [{"date": str(r.get("date") or r.get("keys") or ""),
                     "clicks": _f(r.get("clicks"))}
                    for r in _l(_gsc(ctx).get("daily"))]
    return out


def funnel_stages(ctx) -> Optional[dict]:
    g = _gsc_totals(ctx)
    sess = _organic_sessions(ctx)
    if not g and sess is None:
        return None
    return {"impressions": g.get("impressions"),
            "clicks": g.get("clicks"),
            "organic_sessions": sess,
            # engaged_sessions, conversions and revenue are left out
            # rather than estimated. The funnel screen prints which
            # stages are missing and says it refused to invent them.
            }


def page_conversions(ctx) -> Optional[list]:
    """GSC pages joined to GA4 sessions, keyed on path.

    Conversions are absent from the GA4 pull, so every row says so
    rather than showing a zero that would rank a page last unfairly.
    """
    pages = _l(_gsc(ctx).get("pages"))
    if not pages:
        return None
    sess = {}
    for r in _l(_ga4(ctx).get("pages")):
        p = str(_d(r).get("pagePath") or "")
        if p:
            sess[p] = _f(_d(r).get("sessions"))
    out = []
    for r in pages:
        url = str(_d(r).get("key") or "")
        path = url
        for cut in ("https://", "http://"):
            if path.startswith(cut):
                path = "/" + path[len(cut):].split("/", 1)[-1] \
                    if "/" in path[len(cut):] else "/"
        out.append({"url": url, "clicks": _f(_d(r).get("clicks"), 0),
                    "impressions": _f(_d(r).get("impressions"), 0),
                    "sessions": sess.get(path),
                    "conversions": None})
    return out


def organic_keywords(ctx) -> Optional[list]:
    """Queries this site actually ranks for, from Search Console.

    volume is left None ON PURPOSE. GSC does not report search volume;
    it reports impressions, which is how often YOU appeared. Putting
    impressions under Volume would make every keyword look proportional
    to your current ranking, which is precisely backwards, and the whole
    board would then be reasoning from a number that means something
    else.
    """
    qs = _l(_gsc(ctx).get("queries"))
    if not qs:
        return None
    return [{"keyword": _d(r).get("key"),
             "position": _f(_d(r).get("position")),
             "volume": None,
             "impressions": _f(_d(r).get("impressions")),
             "clicks": _f(_d(r).get("clicks")),
             "url": None,
             "intent": None} for r in qs]


def keyword_research(ctx) -> Optional[list]:
    """The same queries, in the explorer, with the caveat stated."""
    qs = _l(_gsc(ctx).get("queries"))
    if not qs:
        return None
    out = []
    for r in qs:
        d = _d(r)
        imps = int(_f(d.get("impressions"), 0) or 0)
        clicks = int(_f(d.get("clicks"), 0) or 0)
        out.append({
            "keyword": d.get("key"),
            "volume": None,          # see organic_keywords for why
            "difficulty": None,      # no provider connected to model it
            "intent": None,
            "cpc": None,
            "serp_note": (f"{imps:,} impression(s) and {clicks:,} click(s) "
                          f"in Search Console. These are YOUR impressions, "
                          f"not market search volume."),
        })
    return out


def tracked_keywords(ctx) -> Optional[list]:
    """The rank tracker's own rows, which ARE measured positions."""
    rows = _l(_d(ctx).get("ranks"))
    if not rows:
        return None
    out = []
    for r in rows:
        d = _d(r)
        out.append({"keyword": d.get("query") or d.get("keyword"),
                    "position": _f(d.get("position") or d.get("pos")),
                    "delta": _f(d.get("delta")),
                    "best": _f(d.get("best")),
                    "device": d.get("device"),
                    "location": d.get("location") or d.get("country")})
    return out


def tracking_meta(ctx) -> Optional[dict]:
    # Returns None, not {"pulled_at": None}, when nothing has been
    # pulled. A dict with an empty field inside still counts as a value
    # to enrich(), so it would set the key on a store that holds nothing
    # and the screen would print "last pull: not recorded" over a
    # tracker that has never existed.
    rows = _l(_d(ctx).get("ranks"))
    if not rows:
        return None
    at = ""
    for r in rows:
        a = str(_d(r).get("at") or "")
        if a > at:
            at = a
    return {"pulled_at": at[:16]} if at else None


def domain_profile(ctx) -> Optional[dict]:
    """Our own domain, from the backlink provider and Search Console."""
    off = _d(_d(ctx).get("offpage"))
    g = _gsc_totals(ctx)
    if not off.get("connected") and not g:
        return None
    qs = _l(_gsc(ctx).get("queries"))
    top3 = sum(1 for r in qs if (_f(_d(r).get("position")) or 99) <= 3)
    top10 = sum(1 for r in qs if (_f(_d(r).get("position")) or 99) <= 10)
    return {
        "domain": _d(ctx).get("site") or off.get("target") or "this site",
        "authority": off.get("rank") or off.get("domain_rank"),
        "keywords": len(qs) or None,
        # NOT a provider traffic estimate: these are measured clicks.
        # The screen labels its traffic figure an estimate, so this is
        # passed as clicks and the estimate slot stays empty.
        "traffic": None,
        "clicks": g.get("clicks"),
        "referring_domains": off.get("referring_domains"),
        "top3": top3 or None,
        "top10": top10 or None,
        "source": GSC + (" + backlink provider" if off.get("connected")
                         else ""),
    }


def health(ctx) -> Optional[dict]:
    s = _d(_d(ctx).get("scores"))
    return s or None


def opportunities(ctx) -> Optional[list]:
    """Striking-distance queries the audit already found."""
    rows = _l(_d(_d(ctx).get("audit")).get("striking"))
    if not rows:
        return None
    out = []
    for r in rows:
        d = _d(r)
        out.append({"title": d.get("query") or d.get("title"),
                    "url": d.get("page") or d.get("url"),
                    "position": _f(d.get("position")),
                    "impressions": _f(d.get("impressions")),
                    "clicks": _f(d.get("clicks")),
                    "why": d.get("why") or
                    "in striking distance according to the last audit",
                    "source": GSC})
    return out


def content_rows(ctx) -> Optional[list]:
    urls = _l(_d(_d(ctx).get("crawl")).get("urls"))
    return urls or None


def questions(ctx) -> Optional[list]:
    """AEO questions the answer engine has already assessed."""
    aeo = _d(_d(ctx).get("aeo"))
    rows = _l(aeo.get("questions")) or _l(aeo.get("rows"))
    if not rows:
        return None
    out = []
    for r in rows:
        d = _d(r)
        out.append({"question": d.get("question") or d.get("q"),
                    "demand": _f(d.get("demand")),
                    "page": d.get("page") or d.get("url"),
                    "answer_words": d.get("answer_words"),
                    "position": _f(d.get("position"))})
    return out


#: The engines content_engine_aeo.probe() actually asks. Read from that
#: module at import so this list cannot drift from the one that runs.
def _engines():
    try:
        import content_engine_aeo as AEO
        return tuple(n for n, _fn, _key in AEO._ENGINES)
    except Exception:                                 # noqa: BLE001
        return ("claude", "openai", "perplexity", "gemini")


def prompts(ctx) -> Optional[list]:
    """One row per prompt, one run per AI engine that actually answered.

    Reads aeo["results"], which is where probe() puts the real answers.
    The previous version read aeo_history, whose rows are DAILY
    SUMMARIES ({at, score, mention_rate, ...}) with no prompt text and no
    provider, so the board rendered seven aggregates as though they were
    seven observations.

    An engine that did not answer is left OUT of the runs rather than
    recorded as an absence. It was not asked, and NOT RUN and ABSENT are
    different findings: one is our failure to look, the other is the
    answer.
    """
    aeo = _d(_d(ctx).get("aeo"))
    results = _l(aeo.get("results"))
    if not results:
        # No fallback to aeo_history. It cannot answer this question, and
        # a screen fed summaries would look populated while showing
        # nothing anyone can act on.
        return None
    at = str(aeo.get("at") or "")[:16]
    engines = _engines()
    out = []
    for r in results:
        d = _d(r)
        runs, not_run, rivals = [], [], []
        for eng in engines:
            e = _d(d.get(eng))
            if not e:
                not_run.append(eng)
                continue
            if not e.get("connected"):
                not_run.append(eng + " (" + str(e.get("reason") or
                                                "did not answer") + ")")
                continue
            cites = _l(e.get("citations"))
            runs.append({
                "at": at,
                "provider": eng,
                # CITED means the answer linked us. MENTIONED means it
                # named us without a link. probe() records those
                # separately and the GEO board keeps them apart.
                "cited": bool(cites),
                "mentioned": bool(e.get("mentioned")),
                "answer": e.get("excerpt"),
                "citations": cites,
            })
            for x in _l(e.get("rivals_mentioned")):
                if x not in rivals:
                    rivals.append(x)
        row = {"prompt": d.get("prompt"),
               "provider": ", ".join(x["provider"] for x in runs) or None,
               "runs": runs,
               "competitors": rivals,
               "competitor": ", ".join(str(x) for x in rivals) or None}
        if not_run:
            row["not_run"] = not_run
        out.append(row)
    return out


def citation_gaps(ctx) -> Optional[list]:
    """Sources the AI engines cited, from the probe's own citation roll-up.

    This is not the full competitor gap the screen can show: it needs
    observed citations for a rival on the SAME prompts, and probe()
    records rival MENTIONS but not rival citations. So our side is filled
    from real data and the competitor column stays honestly empty rather
    than being invented, and the screen prints both.
    """
    cites = _d(_d(_d(ctx).get("aeo")).get("citations"))
    top = _l(cites.get("top_pages"))
    if not top:
        return None
    out = []
    for row in top:
        pair = list(row) if isinstance(row, (list, tuple)) else []
        if len(pair) != 2:
            continue
        src, n = pair
        out.append({"source": src, "our_citations": n,
                    "competitor_citations": None,
                    "topic": None,
                    "relevance": None,
                    "strategy": None})
    return out


def local(ctx) -> Optional[dict]:
    c = _d(ctx)
    nap = _d(c.get("nap"))
    grid = _l(c.get("local_grid"))
    geo = _d(c.get("geo"))
    loc = _d(c.get("local"))
    profiles, markets = [], []
    if nap or loc:
        profiles.append({"name": nap.get("name") or loc.get("name"),
                         "location": nap.get("address") or loc.get("address"),
                         "reviews": loc.get("reviews"),
                         "rating": loc.get("rating"),
                         "state": ("consistent" if nap.get("consistent")
                                   else nap.get("state"))})
    for m in _l(geo.get("markets")) or grid:
        d = _d(m)
        markets.append({"market": d.get("market") or d.get("location"),
                        "keywords": d.get("keywords"),
                        "avg_position": _f(d.get("avg_position")
                                           or d.get("position")),
                        "language": d.get("language")})
    if not profiles and not markets:
        return None
    return {"profiles": [p for p in profiles if p.get("name")],
            "markets": markets}


def competitors(ctx) -> Optional[list]:
    ci = _d(_d(ctx).get("competitor_intel"))
    names = _l(ci.get("competitors")) or _l(ci.get("domains"))
    return [str(x) for x in names] or None


def cms(ctx) -> str:
    """Which CMS adapter applies. Unknown stays 'manual', which is a
    supported mode rather than a broken one."""
    c = _d(ctx)
    for key in ("cms", "platform"):
        v = str(c.get(key) or "").lower()
        if v in ("wordpress", "webflow", "shopify"):
            return v
    return "manual"


def source_state(ctx) -> list:
    """What is connected, for the freshness bar and the report caveat."""
    ins = _d(_d(ctx).get("insights"))
    at = str(ins.get("at") or "")[:16]
    out = []
    if _gsc(ctx):
        out.append({"name": GSC, "state": "FRESH" if at else "UNKNOWN",
                    "at": at})
    if _ga4(ctx):
        out.append({"name": GA4, "state": "FRESH" if at else "UNKNOWN",
                    "at": at})
    off = _d(_d(ctx).get("offpage"))
    if off:
        out.append({"name": "Backlink provider",
                    "state": "FRESH" if off.get("connected") else "ERROR",
                    "at": off.get("at"),
                    "reason": off.get("reason")})
    return out


#: The whole mapping, in one place. Adding a screen means adding a line
#: HERE, not writing a second translation somewhere else.
MAPPING = {
    "search_totals": search_totals,
    "funnel_stages": funnel_stages,
    "page_conversions": page_conversions,
    "organic_keywords": organic_keywords,
    "keyword_research": keyword_research,
    "tracked_keywords": tracked_keywords,
    "tracking_meta": tracking_meta,
    "domain_profile": domain_profile,
    "health": health,
    "opportunities": opportunities,
    "content_rows": content_rows,
    "questions": questions,
    "prompts": prompts,
    "citation_gaps": citation_gaps,
    "local": local,
    "competitors": competitors,
    "cms": cms,
    "sources": source_state,
}


def enrich(ctx) -> dict:
    """Add the Search OS keys to a build_ctx() dict, without clobbering.

    A key the caller already set is LEFT ALONE. Tests pass their own
    fixtures in, and a bridge that overwrote them would make every test
    pass against live data instead of the case it was written for.

    A mapper that raises loses its own key and nothing else. One bad
    field in a Google payload must not blank the section.
    """
    out = dict(_d(ctx))
    for key, fn in MAPPING.items():
        if out.get(key) not in (None, {}, []):
            continue
        try:
            val = fn(out)
        except Exception:                             # noqa: BLE001
            val = None
        if val not in (None, {}, []):
            out[key] = val
    return out
