"""
content_engine_media_creative.py
============================================================================
PHASE 2: THE CREATIVE ENGINE AND THE AUDIENCE ENGINE.

CREATIVE IS NOT AN UPLOAD
  A creative here is a structured object with the attributes that actually
  decide performance: concept, angle, hook, persona, format, CTA and funnel
  stage. That is the whole point. "Creative A has ROAS 3.2" tells you
  nothing you can act on. "UGC with a pain-point hook aimed at practice
  managers is beating product-only by 2.4x" tells you what to make next,
  and only an attributed creative can produce that sentence.

VERSIONS ARE IMMUTABLE
  Publishing appends. A version that has spent money must stay readable
  for ever, because the record of what you tested is the only thing that
  makes the next test worth running. Overwriting it destroys the evidence
  and leaves a number nobody can explain.

AUDIENCES ARE PROVIDER-NEUTRAL, AND THE GAPS ARE NAMED
  One canonical definition, and a capability mapper that translates it per
  platform. Where a platform cannot express part of a definition, the
  mapper SAYS SO and drops that part explicitly. Silently ignoring a
  targeting clause is how a campaign reaches an audience nobody chose.

WINNERS ARE NOT DECLARED FROM THIN AIR
  The matrix refuses to name a winning attribute below a minimum sample,
  in the same words the A/B verdict uses in the email OS. Confidence from
  forty impressions is the most expensive kind of wrong.

NOTHING HERE SPENDS MONEY OR CALLS A PLATFORM.
============================================================================
"""

from __future__ import annotations

import logging

import content_engine_os_core as CORE
from content_engine_os_core import _D, _L, now, rid

log = logging.getLogger("content_engine.media_creative")

# ---------------------------------------------------------------------------
# THE VOCABULARY
# ---------------------------------------------------------------------------
CREATIVE_TYPES = ("IMAGE", "VIDEO", "CAROUSEL", "TEXT", "UGC")

FUNNEL_STAGES = ("COLD", "WARM", "HOT", "RETENTION")

AUDIENCE_TYPES = ("CUSTOM", "PROSPECTING", "REMARKETING", "LOOKALIKE",
                  "CUSTOMER", "SUPPRESSION")

#: The dimensions a creative is measured ALONG, not just as a whole. This
#: is the list the learning loop reasons over.
ATTRIBUTES = ("concept", "angle", "hook", "persona", "type", "cta",
              "funnel_stage")

#: What a targeting definition may contain. A key not on this list is
#: refused at save time rather than silently ignored at launch.
TARGET_FIELDS = {
    "countries": "Countries", "cities": "Cities", "radius_km": "Radius",
    "age_min": "Minimum age", "age_max": "Maximum age", "genders": "Genders",
    "languages": "Languages", "interests": "Interests",
    "behaviours": "Behaviours", "job_titles": "Job titles",
    "industries": "Industries", "company_size": "Company size",
    "keywords": "Search keywords", "customer_list": "Customer list",
    "website_visitors": "Website visitors", "lookalike_of": "Lookalike of",
    "lookalike_percent": "Lookalike percent", "exclude": "Exclusions",
}

#: WHAT EACH PLATFORM CAN ACTUALLY TARGET. A field absent here is a field
#: that platform cannot express, and the mapper reports it as dropped.
#: Deliberately conservative: claiming a capability that does not exist is
#: worse than under-promising, because the campaign launches either way.
TARGET_SUPPORT = {
    "meta": {"countries", "cities", "radius_km", "age_min", "age_max",
             "genders", "languages", "interests", "behaviours",
             "customer_list", "website_visitors", "lookalike_of",
             "lookalike_percent", "exclude"},
    "google": {"countries", "cities", "radius_km", "age_min", "age_max",
               "genders", "languages", "interests", "keywords",
               "customer_list", "website_visitors", "exclude"},
    "tiktok": {"countries", "age_min", "age_max", "genders", "languages",
               "interests", "behaviours", "customer_list",
               "website_visitors", "lookalike_of", "exclude"},
    "linkedin": {"countries", "cities", "languages", "job_titles",
                 "industries", "company_size", "interests", "customer_list",
                 "website_visitors", "exclude"},
}

#: Below this, an attribute has not earned a verdict. Stated once so the
#: matrix and the recommendation cannot disagree about what "enough" means.
MIN_IMPRESSIONS = 1000
MIN_CONVERSIONS = 10


# ---------------------------------------------------------------------------
# THE CREATIVE LIBRARY
# ---------------------------------------------------------------------------
def save_creative(r, *, creative_id="", name="", type="IMAGE", asset_url="",
                  thumbnail_url="", duration=None, aspect_ratio="",
                  hook="", headline="", primary_text="", description="",
                  cta="", landing_page_url="", concept="", angle="",
                  persona="", funnel_stage="COLD", publish=False) -> dict:
    """Save a draft, or publish a version.

    A PUBLISHED VERSION IS NEVER OVERWRITTEN. Publishing appends, exactly
    as the email OS does with templates, because a creative that has spent
    money must stay readable after you change it."""
    nm = str(name or "").strip()
    if not nm:
        return {"ok": False, "message": "a creative needs a name"}
    if type not in CREATIVE_TYPES:
        return {"ok": False,
                "message": f"{type!r} is not a format. They are: "
                           + ", ".join(CREATIVE_TYPES)}
    if funnel_stage not in FUNNEL_STAGES:
        return {"ok": False,
                "message": f"{funnel_stage!r} is not a funnel stage. They "
                           f"are: " + ", ".join(FUNNEL_STAGES)}
    cid = creative_id or rid("crea", r.ws, nm.lower())
    cur = r.one("creatives", cid) or {"id": cid, "version": 0}
    body = {"name": nm, "type": type, "asset_url": asset_url,
            "thumbnail_url": thumbnail_url, "duration": duration,
            "aspect_ratio": aspect_ratio, "hook": hook, "headline": headline,
            "primary_text": primary_text, "description": description,
            "cta": cta, "landing_page_url": landing_page_url,
            "concept": concept, "angle": angle, "persona": persona,
            "funnel_stage": funnel_stage}
    cur.update(body)
    if publish:
        v = int(cur.get("version") or 0) + 1
        cur["version"] = v
        cur["published_at"] = now()
        r.put("creative_versions", {
            "id": rid("creav", r.ws, cid, v), "creative_id": cid,
            "version": v, "published_at": now(), **body})
    rec = r.put("creatives", cur)
    thin = [a for a in ATTRIBUTES if not str(rec.get(a) or "").strip()]
    return {"ok": True, "id": rec["id"], "version": rec.get("version", 0),
            "unattributed": thin,
            "message": (f"{nm!r} published as version {rec.get('version')}"
                        if publish else f"{nm!r} saved as a draft")
                       + (f". Without {', '.join(thin)} this creative can "
                          f"be measured but not learned from."
                          if thin else "")}


def creative_rows(r) -> list:
    vers = {}
    for v in r.all("creative_versions"):
        vers[v.get("creative_id")] = vers.get(v.get("creative_id"), 0) + 1
    return [{"id": c.get("id"), "name": c.get("name"), "type": c.get("type"),
             "concept": c.get("concept", ""), "angle": c.get("angle", ""),
             "hook": c.get("hook", ""), "persona": c.get("persona", ""),
             "cta": c.get("cta", ""), "funnel_stage": c.get("funnel_stage"),
             "version": c.get("version", 0),
             "versions": vers.get(c.get("id"), 0),
             "updated_at": c.get("updated_at", "")}
            for c in r.all("creatives")]


def from_agent(doc) -> dict:
    """Accept a creative agent's structured output, keeping only what the
    model understands. A concept the agent invents a field for is dropped
    with a note rather than written as an attribute nothing can measure."""
    doc = _D(doc)
    kept = {k: doc.get(k) for k in
            ("name", "type", "hook", "headline", "primary_text",
             "description", "cta", "concept", "angle", "persona",
             "funnel_stage", "landing_page_url") if doc.get(k)}
    refused = [k for k in doc if k not in kept and k not in ("confidence",)]
    return {"creative": kept, "refused": refused,
            "confidence": doc.get("confidence")}


# ---------------------------------------------------------------------------
# CREATIVE INTELLIGENCE. Performance BY ATTRIBUTE, not just by creative.
# ---------------------------------------------------------------------------
def _metrics_by_creative(r) -> dict:
    """Spend and outcome per creative, from ad_metrics joined through ads."""
    ads = {a.get("id"): a for a in r.all("ads")}
    out = {}
    for m in r.all("ad_metrics"):
        ad = ads.get(m.get("ad_id")) or {}
        cid = ad.get("creative_id") or m.get("creative_id")
        if not cid:
            continue
        b = out.setdefault(cid, {"impressions": 0, "clicks": 0, "spend": 0.0,
                                 "conversions": 0, "conversion_value": 0.0})
        for k in b:
            try:
                b[k] += float(m.get(k) or 0)
            except Exception:
                pass
    return out


def _derive(b) -> dict:
    imp = b.get("impressions") or 0
    clicks = b.get("clicks") or 0
    spend = b.get("spend") or 0.0
    conv = b.get("conversions") or 0
    val = b.get("conversion_value") or 0.0
    return {**b,
            "ctr": round(clicks / imp * 100, 2) if imp else None,
            "cpc": round(spend / clicks, 2) if clicks else None,
            "cpm": round(spend / imp * 1000, 2) if imp else None,
            "cvr": round(conv / clicks * 100, 2) if clicks else None,
            "cpa": round(spend / conv, 2) if conv else None,
            "roas": round(val / spend, 2) if spend else None}


def creative_performance(r) -> list:
    """Every creative with its numbers and its attributes, so the matrix
    can be built from one pass."""
    by = _metrics_by_creative(r)
    out = []
    for c in r.all("creatives"):
        b = by.get(c.get("id"), {"impressions": 0, "clicks": 0, "spend": 0.0,
                                 "conversions": 0, "conversion_value": 0.0})
        out.append({"id": c.get("id"), "name": c.get("name"),
                    **{a: c.get(a) for a in ATTRIBUTES}, **_derive(b)})
    return sorted(out, key=lambda x: -(x.get("spend") or 0))


def matrix(r, dimension="angle", metric="roas") -> dict:
    """Performance grouped by ONE attribute.

    This is the sentence the optimisation loop needs: not which creative
    won, but which ANGLE won, so the next ten can be made deliberately
    rather than hopefully."""
    if dimension not in ATTRIBUTES:
        return {"ok": False,
                "message": f"{dimension!r} is not an attribute. They are: "
                           + ", ".join(ATTRIBUTES)}
    rows = creative_performance(r)
    groups = {}
    for x in rows:
        key = str(x.get(dimension) or "").strip() or "(not recorded)"
        g = groups.setdefault(key, {"value": key, "creatives": 0,
                                    "impressions": 0, "clicks": 0,
                                    "spend": 0.0, "conversions": 0,
                                    "conversion_value": 0.0})
        g["creatives"] += 1
        for k in ("impressions", "clicks", "spend", "conversions",
                  "conversion_value"):
            g[k] += x.get(k) or 0
    out = []
    for g in groups.values():
        d = _derive(g)
        d["enough"] = (g["impressions"] >= MIN_IMPRESSIONS
                       and g["conversions"] >= MIN_CONVERSIONS)
        out.append(d)
    out.sort(key=lambda x: -((x.get(metric) or 0)))
    return {"ok": True, "dimension": dimension, "metric": metric,
            "rows": out, "verdict": verdict(out, dimension, metric)}


def verdict(rows, dimension, metric="roas") -> dict:
    """Which value of this attribute wins, and whether that means anything.

    REFUSES below the sample floor, in the same words the email OS uses,
    because an attribute crowned on four hundred impressions sends the
    next ten creatives in the wrong direction and costs real money."""
    ready = [r_ for r_ in _L(rows) if r_.get("enough")]
    if len(ready) < 2:
        return {"state": "early", "leader": "",
                "message": (f"not enough spend behind any {dimension} yet. "
                            f"An attribute needs {MIN_IMPRESSIONS:,} "
                            f"impressions and {MIN_CONVERSIONS} conversions "
                            f"before it has earned a verdict; below that the "
                            f"ranking is noise and acting on it sends the "
                            f"next ten creatives the wrong way.")}
    best, worst = ready[0], ready[-1]
    b, w = best.get(metric) or 0, worst.get(metric) or 0
    if not w or b / max(w, 0.01) < 1.3:
        return {"state": "tied", "leader": "",
                "message": f"no {dimension} is clearly ahead: {best['value']!r} "
                           f"and {worst['value']!r} are within 30 percent of "
                           f"each other on {metric}."}
    return {"state": "winner", "leader": best["value"],
            "message": f"{best['value']!r} is beating {worst['value']!r} by "
                       f"{b / max(w, 0.01):.1f}x on {metric}, over "
                       f"{int(best['impressions']):,} impressions. Make the "
                       f"next batch around it."}


def learn(r) -> dict:
    """Every attribute at once: what is winning, and what to make next.

    This is the output the creative agent is given as its brief, so what
    it produces next is grounded in what has already been paid for."""
    findings, briefs = [], []
    for dim in ATTRIBUTES:
        m = matrix(r, dim)
        if not m.get("ok"):
            continue
        v = m["verdict"]
        findings.append({"attribute": dim, **v})
        if v["state"] == "winner":
            briefs.append(f"{dim}: {v['leader']}")
    return {"findings": findings, "brief": briefs,
            "message": (("Make the next batch with " + ", ".join(briefs))
                        if briefs else
                        "Nothing has earned a verdict yet. Keep the current "
                        "creatives running until an attribute clears "
                        f"{MIN_IMPRESSIONS:,} impressions.")}


def fatigue(r, creative_id) -> dict:
    """How tired one creative is, from what was actually measured.

    Every input is named with its own number, because a score with no
    evidence is a number nobody can argue with and therefore nobody can
    act on."""
    rows = [x for x in creative_performance(r) if x["id"] == creative_id]
    if not rows:
        return {"ok": False, "message": "no such creative"}
    x = rows[0]
    c = r.one("creatives", creative_id) or {}
    age = CORE.days_ago(c.get("published_at") or c.get("created_at")) or 0
    series = sorted([m for m in r.all("ad_metrics")
                     if m.get("creative_id") == creative_id],
                    key=lambda m: str(m.get("day")))
    signals, score = [], 0
    if len(series) >= 6:
        half = len(series) // 2
        def ctr(part):
            imp = sum(float(m.get("impressions") or 0) for m in part)
            clk = sum(float(m.get("clicks") or 0) for m in part)
            return (clk / imp * 100) if imp else None
        early, late = ctr(series[:half]), ctr(series[half:])
        if early and late and late < early * 0.7:
            score += 40
            signals.append({"name": "Click-through is falling",
                            "value": f"{early:.2f}% then {late:.2f}%",
                            "why": "the same people have seen it enough times "
                                   "to stop noticing it"})
    if age >= 21:
        score += 20
        signals.append({"name": "Age", "value": f"{age} days",
                        "why": "three weeks is where most cold audiences "
                               "have seen a creative more than twice"})
    if (x.get("cpa") or 0) and (x.get("roas") or 0) and x["roas"] < 1:
        score += 30
        signals.append({"name": "Below break-even",
                        "value": f"ROAS {x['roas']}",
                        "why": "it is costing more than it returns"})
    if x.get("impressions", 0) < MIN_IMPRESSIONS:
        return {"ok": True, "score": None, "signals": signals, "age_days": age,
                "message": f"only {int(x.get('impressions') or 0):,} "
                           f"impressions so far, which is too little to call "
                           f"tired. Fatigue is measured, not assumed."}
    return {"ok": True, "score": min(100, score), "signals": signals,
            "age_days": age,
            "message": (f"fatigue {min(100, score)} out of 100"
                        + (": " + "; ".join(s["name"].lower()
                                            for s in signals)
                           if signals else ", nothing worrying yet"))}


# ---------------------------------------------------------------------------
# THE AUDIENCE ENGINE
# ---------------------------------------------------------------------------
def save_audience(r, *, audience_id="", name="", type="PROSPECTING",
                  definition=None) -> dict:
    """One provider-neutral definition. A field no platform understands is
    refused HERE, at save time, rather than dropped silently at launch."""
    nm = str(name or "").strip()
    if not nm:
        return {"ok": False, "message": "an audience needs a name"}
    if type not in AUDIENCE_TYPES:
        return {"ok": False,
                "message": f"{type!r} is not an audience type. They are: "
                           + ", ".join(AUDIENCE_TYPES)}
    d = _D(definition)
    unknown = [k for k in d if k not in TARGET_FIELDS]
    if unknown:
        return {"ok": False, "unknown": unknown,
                "message": f"this engine cannot target on "
                           f"{', '.join(unknown)}. It can target on: "
                           + ", ".join(sorted(TARGET_FIELDS))}
    rec = r.put("audiences", {"id": audience_id or rid("aud", r.ws, nm.lower()),
                              "name": nm, "type": type, "definition": d})
    cov = coverage(d)
    return {"ok": True, "id": rec["id"], "coverage": cov,
            "message": f"{nm!r} saved. " + _coverage_sentence(cov)}


def map_to_provider(definition, provider) -> dict:
    """The canonical definition as one platform's targeting.

    WHAT A PLATFORM CANNOT EXPRESS IS RETURNED AS DROPPED, not omitted.
    Quietly ignoring a targeting clause is how a campaign reaches an
    audience nobody chose, and it is invisible until the invoice."""
    p = str(provider or "").lower()
    if p not in TARGET_SUPPORT:
        return {"ok": False, "targeting": {}, "dropped": [],
                "message": f"this engine has no adapter for {provider!r}"}
    d = _D(definition)
    keep = {k: v for k, v in d.items() if k in TARGET_SUPPORT[p]}
    drop = [k for k in d if k not in TARGET_SUPPORT[p]]
    return {"ok": True, "provider": p, "targeting": keep,
            "dropped": drop,
            "message": (f"{p} can express all of it" if not drop else
                        f"{p} cannot target on "
                        + ", ".join(TARGET_FIELDS.get(k, k) for k in drop)
                        + f". Those {len(drop)} clause(s) are DROPPED for "
                          f"{p}, so its audience is wider than the one you "
                          f"defined. Narrow it another way or leave {p} out.")}


def coverage(definition) -> list:
    """Every platform against one definition. The audience step of the
    wizard draws this before anybody commits a budget."""
    return [map_to_provider(definition, p) for p in TARGET_SUPPORT]


def _coverage_sentence(cov) -> str:
    bad = [c for c in _L(cov) if c.get("dropped")]
    if not bad:
        return "Every platform can express this definition exactly."
    return (f"{len(bad)} platform(s) cannot express all of it: "
            + "; ".join(f"{c['provider']} drops "
                        + ", ".join(c["dropped"]) for c in bad) + ".")


# ---------------------------------------------------------------------------
# CREATIVE EXPERIMENTS. A winner is declared by arithmetic over a floor,
# or it is not declared at all.
# ---------------------------------------------------------------------------
EXPERIMENT_STATES = ("DRAFT", "RUNNING", "DONE", "ABANDONED")


def start_experiment(r, *, name="", creative_ids=None, metric="cpa",
                     hypothesis="") -> dict:
    ids = [x for x in _L(creative_ids) if r.one("creatives", x)]
    if len(ids) < 2:
        return {"ok": False,
                "message": "an experiment needs at least two creatives that "
                           "exist; a test with one arm is an anecdote"}
    if metric not in ("cpa", "roas", "ctr", "cvr"):
        return {"ok": False,
                "message": f"{metric!r} is not a judgeable metric. They "
                           f"are: cpa, roas, ctr, cvr"}
    xid = rid("cexp", r.ws, name or now())
    r.put("creative_experiments", {
        "id": xid, "name": name or "Untitled experiment",
        "hypothesis": hypothesis, "metric": metric,
        "variants": ids, "status": "RUNNING", "winner": "",
        "started_at": now(), "ended_at": ""})
    return {"ok": True, "id": xid,
            "message": (f"experiment running over {len(ids)} creative(s) on "
                        f"{metric}. It will refuse a winner below "
                        f"{MIN_IMPRESSIONS:,} impressions and "
                        f"{MIN_CONVERSIONS} conversions per arm.")}


def judge_experiment(r, experiment_id) -> dict:
    """Declare a winner only when every arm has earned an opinion."""
    x = r.one("creative_experiments", experiment_id)
    if not x:
        return {"ok": False, "message": "no such experiment"}
    perf = {p["id"]: p for p in creative_performance(r)}
    arms = []
    for cid in _L(x.get("variants")):
        p = perf.get(cid) or {}
        arms.append({"creative_id": cid, "name": p.get("name") or cid,
                     "impressions": p.get("impressions") or 0,
                     "conversions": p.get("conversions") or 0,
                     "value": p.get(x.get("metric")),
                     "enough": ((p.get("impressions") or 0) >= MIN_IMPRESSIONS
                                and (p.get("conversions") or 0)
                                >= MIN_CONVERSIONS)})
    thin = [a for a in arms if not a["enough"]]
    if thin:
        return {"ok": True, "status": "RUNNING", "arms": arms,
                "message": (f"{len(thin)} arm(s) are below the sample floor "
                            f"({MIN_IMPRESSIONS:,} impressions, "
                            f"{MIN_CONVERSIONS} conversions). No winner is "
                            f"declared from insufficient data; keep it "
                            f"running.")}
    lower_is_better = x.get("metric") == "cpa"
    scored = [a for a in arms if a["value"] is not None]
    scored.sort(key=lambda a: a["value"], reverse=not lower_is_better)
    best, worst = scored[0], scored[-1]
    edge = ((worst["value"] / max(best["value"], 0.01))
            if lower_is_better else
            (best["value"] / max(worst["value"], 0.01)))
    if edge < 1.3:
        return {"ok": True, "status": "RUNNING", "arms": arms,
                "message": (f"no arm leads by 30 percent on "
                            f"{x['metric']}; the difference so far is "
                            f"{edge:.2f}x, which is noise wearing a "
                            f"ranking. Keep it running.")}
    x.update({"status": "DONE", "winner": best["creative_id"],
              "ended_at": now()})
    r.put("creative_experiments", x)
    return {"ok": True, "status": "DONE", "arms": arms,
            "winner": best["name"],
            "message": (f"{best['name']!r} wins on {x['metric']} by "
                        f"{edge:.1f}x over {worst['name']!r}, every arm "
                        f"past the floor. Recorded.")}


def briefs(r, count=3) -> dict:
    """Turn what the matrix has PROVEN into the next creatives to make.

    Deterministic: briefs come from measured winners, not from a model's
    imagination. With no verdicts it refuses, because a brief invented
    from nothing sends real production money in a random direction. The
    drafts land unpublished in the library for a human or the content
    pipeline to fill in."""
    learned = learn(r)
    winners = {f["attribute"]: f for f in _L(learned.get("findings"))
               if f.get("state") == "winner"}
    if not winners:
        return {"ok": False, "made": 0,
                "message": ("nothing has earned a verdict yet, so there is "
                            "nothing honest to brief. Run creatives past "
                            "the sample floor first; the matrix will name "
                            "the winning attributes and the briefs write "
                            "themselves.")}
    base = {a: w.get("leader") for a, w in winners.items()}
    made = []
    for i in range(max(1, min(int(count or 1), 10))):
        nm = ("Brief " + str(i + 1) + ": "
              + ", ".join(f"{a}={v}" for a, v in list(base.items())[:3]))
        got = save_creative(
            r, name=nm, type=str(base.get("type") or "UGC"),
            concept=str(base.get("concept") or ""),
            angle=str(base.get("angle") or ""),
            hook=str(base.get("hook") or ""),
            persona=str(base.get("persona") or ""),
            cta=str(base.get("cta") or ""),
            funnel_stage=str(base.get("funnel_stage") or "COLD"),
            publish=False)
        if got.get("ok"):
            made.append(got["id"])
    return {"ok": True, "made": len(made), "ids": made,
            "attributes": base,
            "message": (f"{len(made)} brief(s) drafted from the measured "
                        f"winners ({', '.join(f'{a}: {v}' for a, v in base.items() if v)}). "
                        f"They are unpublished drafts: fill in the copy "
                        f"(or route creative_rotate through the content "
                        f"pipeline) and publish v1.")}


def audience_rows(r) -> list:
    out = []
    for a in r.all("audiences"):
        cov = coverage(a.get("definition"))
        out.append({"id": a.get("id"), "name": a.get("name"),
                    "type": a.get("type"),
                    "definition": a.get("definition"),
                    "fields": len(_D(a.get("definition"))),
                    "full_support": [c["provider"] for c in cov
                                     if not c["dropped"]],
                    "partial": [c["provider"] for c in cov if c["dropped"]],
                    "note": _coverage_sentence(cov),
                    "created_at": a.get("created_at", "")})
    return out


def saturation(r, audience_id) -> dict:
    """How worked an audience is. Measured, and refused when thin."""
    groups = [g for g in r.all("ad_groups")
              if g.get("audience_id") == audience_id]
    if not groups:
        return {"ok": True, "level": None,
                "message": "nothing has run against this audience yet"}
    ids = {g.get("id") for g in groups}
    imp = clicks = conv = 0.0
    for m in r.all("ad_metrics"):
        if m.get("ad_group_id") in ids:
            imp += float(m.get("impressions") or 0)
            clicks += float(m.get("clicks") or 0)
            conv += float(m.get("conversions") or 0)
    if imp < MIN_IMPRESSIONS:
        return {"ok": True, "level": None, "impressions": int(imp),
                "message": f"only {int(imp):,} impressions, which is too "
                           f"little to call saturated"}
    ctr = clicks / imp * 100
    level = "HIGH" if ctr < 0.6 else ("MEDIUM" if ctr < 1.2 else "LOW")
    advice = {"HIGH": "expand the audience, change the creative, or reduce "
                      "spend here",
              "MEDIUM": "watch it; a new creative usually buys more room",
              "LOW": "there is room to spend more here"}[level]
    return {"ok": True, "level": level, "ctr": round(ctr, 2),
            "impressions": int(imp), "conversions": int(conv),
            "message": f"saturation {level.lower()} at {ctr:.2f}% "
                       f"click-through over {int(imp):,} impressions. {advice}."}
