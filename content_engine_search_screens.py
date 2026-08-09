"""
content_engine_search_screens.py
============================================================================
THE THREE SCREENS THAT MAKE THE LOOP OPERABLE.

Spec sections 12-14 (Command Center), 26-29 (Page Intelligence + the AI
Page Analyst + the before/after diff), 48-49 (Opportunities + Quick
Wins), and the UI rules 64-74 that govern all three.

WHY THESE THREE FIRST
  The loop engine and its boards exist, but a founder cannot yet DO
  anything with them: nothing shows what to work on, nothing shows why a
  page is losing, and nothing lets a change be reviewed before it is
  approved. These three close that. Everything else in the spec is
  additive once these work.

RULES ENFORCED HERE, NOT DESCRIBED
  - Every metric names its SOURCE on the screen (spec 73) and its
    freshness (spec 74). A number with no source is not rendered.
  - Every recommendation shows the twelve fields the loop demands, so a
    screen cannot display an opinion as an action (spec 102).
  - The diff viewer shows BEFORE and PROPOSED side by side with the
    evidence and the risk, and there is no approve path that skips it
    (spec 29).
  - Business value beats traffic: the opportunity sort is impact x
    confidence x business value / effort (spec 47, 49), and a page with
    10,000 clicks and 8 conversions ranks below one with 2,100 clicks and
    94 (the spec's own example).
  - Empty and error states name their cause and their fix (spec 71, 72).
============================================================================
"""

from __future__ import annotations

import html as _html

import content_engine_search_loop as SL
import content_engine_search_tokens as TK
from content_engine_os_core import _D, _L


def e(v) -> str:
    return _html.escape(str("" if v is None else v), quote=True)


def _n(v, dash="not measured"):
    if v in (None, "", {}):
        return dash
    if isinstance(v, float):
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    if isinstance(v, int):
        return f"{v:,}"
    return e(v)


#: Spec 73. A metric may only be shown WITH where it came from.
def metric(label, value, *, source, freshness="", target=None,
           polarity="neutral") -> str:
    if not source:
        return (f"<div class='ss-kpi'><span>{e(label)}</span>"
                f"<b>not shown</b><i>a metric with no named source is not "
                f"rendered here</i></div>")
    tline = ""
    if target is not None and value not in (None, ""):
        try:
            good = (float(value) <= float(target)) if polarity == "negative" \
                else (float(value) >= float(target))
            off = abs((float(value) - float(target)) / float(target) * 100)
            tline = (f"<i class='{'so-success' if good else 'so-danger'}'>"
                     f"Target {_n(target)} &middot; {off:.1f}% "
                     f"{'under' if float(value) <= float(target) else 'over'}"
                     f"</i>")
        except Exception:
            tline = ""
    return (f"<div class='ss-kpi'><span>{e(label)}</span>"
            f"<b>{_n(value, '--')}</b>{tline}"
            f"<i class='ss-src'>Source: {e(source)}"
            + (f" &middot; {e(freshness)}" if freshness else "") + "</i>"
            "</div>")


def empty(title, why, cta_label="", cta="") -> str:
    """Spec 71. Names the reason and offers the corrective action."""
    return (f"<div class='ss-empty'><b>{e(title)}</b><p>{e(why)}</p>"
            + (TK.button(cta_label, variant="primary", size="compact",
                         onclick=cta) if cta_label else "") + "</div>")


def error(title, cause, fix, cta_label="", cta="") -> str:
    """Spec 72. Never 'something went wrong'."""
    return (f"<div class='ss-error'><b>{e(title)}</b>"
            f"<p>Cause: {e(cause)}</p><p>Fix: {e(fix)}</p>"
            + (TK.button(cta_label, variant="primary", size="compact",
                         onclick=cta) if cta_label else "") + "</div>")


# ---------------------------------------------------------------------------
# OPPORTUNITIES (spec 48-49) - the entry point of the whole loop
# ---------------------------------------------------------------------------
#: Spec 49. impact x confidence x business value / effort. Declared once.
WEIGHT = {"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0, "UNKNOWN": 1.0}


def score(opportunity) -> dict:
    """The ranking, with its arithmetic exposed. Never a bare number."""
    o = _D(opportunity)
    imp = WEIGHT.get(str(o.get("impact") or "").upper(), 1.0)
    biz = WEIGHT.get(str(o.get("business_value") or "").upper()
                     .split(" ")[0], 1.0)
    eff = WEIGHT.get(str(o.get("effort") or "MEDIUM").upper(), 2.0)
    try:
        conf = float(o.get("confidence") or 0.5)
    except Exception:
        conf = 0.5
    val = (imp * conf * biz) / max(eff, 0.5)
    return {"score": round(val, 2),
            "why": (f"impact {imp:g} x confidence {conf:.2f} x business "
                    f"{biz:g} / effort {eff:g}"),
            "business_unknown": "UNKNOWN" in str(o.get("business_value")
                                                 or "").upper()}


def opportunities(r, ctx=None) -> str:
    """Spec 48. Everything worth doing, ranked by business impact."""
    items = [x for x in r.all("search_initiatives")
             if x.get("state") in ("DISCOVERED", "ANALYZED", "RECOMMENDED")]
    if not items:
        return (f"<p class='ss-h'>OPPORTUNITIES</p>"
                + empty("No open opportunities",
                        "Nothing has been detected yet, or everything "
                        "detected has already been accepted. Run a "
                        "ranking pull or a crawl and the detectors will "
                        "open work here.",
                        "Run detection", "act('/searchos/detect')"))
    rows = []
    for it in items:
        rec = _D(it.get("recommendation"))
        sc = score(rec)
        rows.append((sc["score"], it, rec, sc))
    rows.sort(key=lambda x: -x[0])
    body = ""
    for i, (val, it, rec, sc) in enumerate(rows[:25], 1):
        body += (
            "<div class='ss-opp'>"
            f"<span class='ss-rank'>#{i}</span>"
            "<div class='ss-oppbody'>"
            f"<b>{e(rec.get('problem'))[:110]}</b>"
            f"<p class='ss-ev'>Evidence: "
            + e("; ".join(str(x) for x in _L(rec.get("evidence")))[:150])
            + "</p>"
            f"<p class='ss-meta'>Impact {e(rec.get('impact'))} &middot; "
            f"business {e(rec.get('business_value'))} &middot; "
            f"confidence {e(rec.get('confidence'))} &middot; effort "
            f"{e(rec.get('effort'))} &middot; risk {e(rec.get('risk'))} "
            f"&middot; agent {e(rec.get('agent'))}</p>"
            f"<p class='ss-meta'>Score {val} = {e(sc['why'])}</p>"
            + ("<p class='ss-meta so-warning'>business value is UNKNOWN, "
               "so this ranks on search impact alone. Joining conversion "
               "data would change this order.</p>"
               if sc["business_unknown"] else "")
            + f"<p class='ss-meta'>Verification: "
              f"{e(rec.get('verification_method'))} &middot; success "
              f"metric: {e(rec.get('success_metric'))}</p>"
            "</div><div class='ss-oppcta'>"
            + TK.button("Analyze", variant="ai", size="compact",
                        onclick=f"ssAnalyze('{e(it.get('id'))}')")
            + TK.button("Accept", variant="primary", size="compact",
                        onclick=f"ssAccept('{e(it.get('id'))}')")
            + TK.button("Dismiss", variant="ghost", size="compact",
                        onclick=f"ssDismiss('{e(it.get('id'))}')")
            + "</div></div>")
    quick = [x for x in rows
             if _D(x[2]).get("effort") in ("LOW", "MEDIUM")
             and _D(x[2]).get("impact") == "HIGH"]
    return ("<p class='ss-h'>OPPORTUNITIES</p>"
            f"<p class='ss-note'>{len(rows)} open &middot; ranked by "
            f"impact x confidence x business value / effort, and every "
            f"row shows that arithmetic. {len(quick)} are quick wins "
            f"(high impact, low or medium effort).</p>" + body)


# ---------------------------------------------------------------------------
# PAGE INTELLIGENCE (spec 26-29)
# ---------------------------------------------------------------------------
def page_intelligence(r, url, *, metrics=None, source="Google Search "
                                                     "Console") -> str:
    """Spec 26-28. Everything known about one URL, with the analyst."""
    m = _D(metrics)
    if not m:
        return ("<p class='ss-h'>PAGE INTELLIGENCE</p>"
                + empty(f"No data for {url}",
                        "No Search Console rows are joined to this URL "
                        "yet. Connect Search Console or run a pull; "
                        "nothing is estimated to fill this page.",
                        "Connect Search Console", "nav('map')"))
    inits = [x for x in r.all("search_initiatives")
             if str(x.get("target")) == str(url)]
    kpis = "".join([
        metric("Clicks", m.get("clicks"), source=source,
               freshness=m.get("freshness", "")),
        metric("Impressions", m.get("impressions"), source=source),
        metric("CTR %", m.get("ctr"), source=source, polarity="positive"),
        metric("Position", m.get("position"), source="Rank tracker",
               target=m.get("target_position"), polarity="negative"),
        metric("Conversions", m.get("conversions"), source="GA4"),
    ])
    # the analyst reads what is here; it invents nothing
    findings, hypotheses = [], []
    pos, prev = m.get("position"), m.get("previous_position")
    if pos is not None and prev is not None:
        try:
            d = float(pos) - float(prev)
            if d >= 1:
                findings.append(f"position moved from {float(prev):g} to "
                                f"{float(pos):g}")
                hypotheses.append("a competitor may have refreshed, or the "
                                  "SERP shape changed; check the SERP "
                                  "before assuming content decay")
        except Exception:
            pass
    if m.get("internal_links") is not None and \
            float(m.get("internal_links") or 0) < 4:
        findings.append(f"only {int(float(m['internal_links']))} internal "
                        f"link(s) point here")
        hypotheses.append("authority flow may be the constraint rather "
                          "than the content itself")
    analyst = ("<div class='ss-ai'><h4>&#10022; AI PAGE ANALYST</h4>"
               + ("".join(f"<p><b>FACT:</b> {e(f)}</p>" for f in findings)
                  + "".join(f"<p class='ss-hyp'>HYPOTHESIS: {e(h)}</p>"
                            for h in hypotheses)
                  if findings else
                  "<p class='ss-hyp'>Nothing crossed a threshold on the "
                  "data joined to this page. That is a finding, not a "
                  "gap in the analysis.</p>")
               + TK.button("Generate optimisation", variant="ai",
                           size="compact",
                           onclick=f"ssOptimize('{e(url)}')")
               + "</div>")
    hist = ("".join(
        f"<li>{e(x.get('state'))} &middot; {e(str(x.get('state_at'))[:10])}"
        f" &middot; {e(_D(x.get('recommendation')).get('action'))[:60]}"
        f"</li>" for x in inits[:8])
        or "<li>no initiative has ever run against this page</li>")
    return (f"<p class='ss-h'>PAGE INTELLIGENCE</p>"
            f"<p class='ss-note'>{e(url)}</p>"
            f"<div class='ss-kpis'>{kpis}</div>"
            + analyst
            + f"<p class='ss-h'>ACTION HISTORY</p><ul class='ss-hist'>"
            + hist + "</ul>")


def diff_viewer(*, field, before, proposed, evidence, risk="MEDIUM",
                initiative_id="") -> str:
    """Spec 29. No AI change is approvable without seeing the diff."""
    if not str(proposed or "").strip():
        return error("Nothing to review",
                     "the optimisation produced no proposed value",
                     "run the analyst again, or edit the field by hand")
    return (
        "<div class='ss-diff'>"
        "<p class='ss-difth'>REVIEW OPTIMIZATION</p>"
        f"<p class='ss-meta'>{e(field.upper())}</p>"
        f"<div class='ss-before'><span>BEFORE</span><p>{e(before) or '(empty)'}</p></div>"
        f"<div class='ss-after'><span>PROPOSED</span><p>{e(proposed)}</p></div>"
        f"<p class='ss-ev'>Evidence: {e(evidence)}</p>"
        f"<p class='ss-meta'>Risk: {e(risk)}"
        + (" &middot; this class is human-only and cannot be "
           "auto-approved" if str(risk).upper() == "CRITICAL" else "")
        + "</p><div class='ss-diffcta'>"
        + TK.button("Reject", variant="danger", size="compact",
                    onclick=f"ssReject('{e(initiative_id)}')")
        + TK.button("Edit", variant="secondary", size="compact",
                    onclick=f"ssEdit('{e(initiative_id)}')")
        + TK.button("Approve", variant="primary", size="compact",
                    onclick=f"ssApprove('{e(initiative_id)}')")
        + "</div></div>")


# ---------------------------------------------------------------------------
# COMMAND CENTER (spec 12-14)
# ---------------------------------------------------------------------------
def command_center(r, *, totals=None, source="Google Search Console",
                   health=None) -> str:
    """Spec 13. Answers: how is search performing, what changed, what is
    broken, what should we do next."""
    t = _D(totals)
    b = SL.board(r)
    kpis = "".join([
        metric("Organic clicks", t.get("clicks"), source=source),
        metric("Impressions", t.get("impressions"), source=source),
        metric("Conversions", t.get("conversions"), source="GA4"),
        metric("Revenue", t.get("revenue"), source="GA4 / CRM"),
        metric("Avg position", t.get("position"), source="Rank tracker",
               polarity="negative"),
    ]) if t else ""
    hb = ""
    if health:
        from content_engine_search_board import health_breakdown
        hb = ("<p class='ss-h'>SEARCH HEALTH</p>" + health_breakdown(health))
    return ("<p class='ss-h'>SEARCH COMMAND CENTER</p>"
            + (f"<div class='ss-kpis'>{kpis}</div>" if kpis else
               empty("No search performance data",
                     "Search Console is not connected, or no pull has run "
                     "for this window. Every number on this screen names "
                     "its source, so none are shown until there is one.",
                     "Connect Search Console", "nav('map')"))
            + hb
            + "<p class='ss-h'>WHAT SHOULD WE DO NEXT?</p>"
            + opportunities(r)
            + "<p class='ss-h'>WORK IN FLIGHT</p>"
            + f"<p class='ss-note'>{e(b['message'])}</p>")


CSS = TK.css() + """<style>
.ss-h{font-size:11px;letter-spacing:1.4px;color:var(--so-text2);
font-weight:700;margin:16px 0 6px}
.ss-note{color:var(--so-text2);font-size:11px;margin:4px 0}
.ss-kpis{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 10px}
.ss-kpi{flex:1;min-width:150px;border:1px solid var(--so-border);
border-radius:var(--so-radius-card);padding:11px 14px;
background:var(--so-surface)}
.ss-kpi b{display:block;font-size:26px;font-weight:600;
color:var(--so-text);font-variant-numeric:tabular-nums}
.ss-kpi span{font-size:10px;text-transform:uppercase;letter-spacing:.5px;
color:var(--so-text2)}
.ss-kpi i{font-style:normal;font-size:10px;display:block;
color:var(--so-text2)}
.ss-src{opacity:.85}
.ss-opp{display:flex;gap:12px;border:1px solid var(--so-border);
border-radius:var(--so-radius-card);padding:11px 14px;margin:0 0 8px;
background:var(--so-surface)}
.ss-rank{font-size:16px;font-weight:700;color:var(--so-primary-main);
min-width:34px}
.ss-oppbody{flex:1}.ss-oppbody b{font-size:13px;color:var(--so-text)}
.ss-ev,.ss-meta{font-size:11px;color:var(--so-text2);margin:2px 0}
.ss-oppcta{display:flex;flex-direction:column;gap:5px}
.ss-ai{border:1px solid var(--so-ai-main);border-radius:
var(--so-radius-card);padding:11px 14px;margin:8px 0;
background:var(--so-surface)}
.ss-ai h4{margin:0 0 6px;font-size:11px;letter-spacing:1px;
color:var(--so-ai-main)}
.ss-ai p{font-size:12px;margin:0 0 5px;color:var(--so-text)}
.ss-hyp{color:var(--so-text2)!important}
.ss-hist{margin:2px 0 0 16px;padding:0;color:var(--so-text2);
font-size:11px}
.ss-diff{border:1px solid var(--so-border);border-radius:
var(--so-radius-card);padding:13px 16px;background:var(--so-surface)}
.ss-difth{font-size:11px;letter-spacing:1.2px;color:var(--so-text2);
font-weight:700;margin:0 0 8px}
.ss-before,.ss-after{border-left:3px solid var(--so-border);
padding:5px 10px;margin:5px 0}
.ss-after{border-left-color:var(--so-ai-main)}
.ss-before span,.ss-after span{font-size:9px;letter-spacing:1px;
color:var(--so-text2)}
.ss-before p,.ss-after p{margin:2px 0;font-size:13px;color:var(--so-text)}
.ss-diffcta{display:flex;gap:7px;margin-top:9px}
.ss-empty,.ss-error{border:1px solid var(--so-border);border-radius:
var(--so-radius-card);padding:13px 16px;background:var(--so-surface)}
.ss-error{border-color:var(--so-danger-main)}
.ss-empty b,.ss-error b{display:block;font-size:13px;margin-bottom:4px}
.ss-empty p,.ss-error p{font-size:12px;color:var(--so-text2);margin:2px 0 8px}
</style>"""


# ---------------------------------------------------------------------------
# SITE AUDIT (spec 22-25)
# ---------------------------------------------------------------------------
#: Spec 22. The categories a crawl is judged on, declared once so the
#: overview, the issue board and the score cannot name different sets.
AUDIT_CATEGORIES = ("Crawlability", "HTTPS", "Indexability",
                    "Internal Linking", "Structured Data", "Performance",
                    "International SEO", "Metadata", "Content")

#: Spec 23. Severity drives order, and each says what it MEANS, so the
#: word is readable without the colour.
SEVERITY = {"CRITICAL": ("danger", "traffic is at risk right now"),
            "HIGH": ("danger", "will cost traffic if left"),
            "MEDIUM": ("warning", "worth fixing in this cycle"),
            "LOW": ("neutral", "housekeeping"),
            "NOTICE": ("neutral", "informational")}


def site_audit(r, crawl=None) -> str:
    """Spec 22. Health WITH its components; never a bare score."""
    c = _D(crawl)
    pages = _L(c.get("pages"))
    if not pages:
        return ("<p class='ss-h'>SITE AUDIT</p>"
                + empty("No crawl on record",
                        "The crawler has not run for this site, so there "
                        "is nothing to audit. A health score invented "
                        "without a crawl would be the most confident "
                        "wrong number on the dashboard.",
                        "Run a crawl", "act('/seo/crawl')"))
    issues = _L(c.get("issues"))
    by_sev = {}
    for i in issues:
        by_sev.setdefault(str(_D(i).get("severity") or "NOTICE").upper(),
                          []).append(i)
    comp, missing = {}, []
    for cat in AUDIT_CATEGORIES:
        rel = [i for i in issues if str(_D(i).get("category") or "") == cat]
        key = cat.lower().replace(" ", "_")
        checked = [x for x in pages if _D(x).get(key) is not None]
        if not rel and not checked:
            missing.append(cat)
            continue
        comp[cat] = max(0, round(100 - (len(rel) / max(len(pages), 1)) * 100))
    from content_engine_search_board import health_breakdown
    errs = len(by_sev.get("CRITICAL", [])) + len(by_sev.get("HIGH", []))
    return ("<p class='ss-h'>SITE AUDIT</p><div class='ss-kpis'>"
            + metric("Pages crawled", len(pages), source="crawler",
                     freshness=str(c.get("at", ""))[:16])
            + metric("Errors", errs, source="crawler")
            + metric("Warnings", len(by_sev.get("MEDIUM", [])),
                     source="crawler")
            + metric("Notices", len(by_sev.get("LOW", []))
                     + len(by_sev.get("NOTICE", [])), source="crawler")
            + "</div>" + health_breakdown(comp)
            + ((f"<p class='ss-note'>{len(missing)} category/categories "
                f"were NOT measured by this crawl and are left out of the "
                f"score rather than counted as healthy: "
                f"{e(chr(44).join(missing))}.</p>") if missing else ""))


def issues_board(r, crawl=None) -> str:
    """Spec 23-24. Every problem with its impact and its fix path."""
    c = _D(crawl)
    issues = _L(c.get("issues"))
    if not issues:
        return ("<p class='ss-h'>ISSUES</p>"
                + empty("No issues detected",
                        "Either the crawl found nothing or no crawl has "
                        "run. Check the audit date before reading this as "
                        "a clean bill of health.",
                        "Run a crawl", "act('/seo/crawl')"))
    order = {k: n for n, k in enumerate(SEVERITY)}
    issues = sorted(issues, key=lambda i: order.get(
        str(_D(i).get("severity") or "NOTICE").upper(), 9))
    rows = ""
    for i in issues[:40]:
        d = _D(i)
        sev = str(d.get("severity") or "NOTICE").upper()
        tone, means = SEVERITY.get(sev, ("neutral", ""))
        urls = _L(d.get("urls"))
        rows += ("<tr>"
                 f"<td class='so-{tone}'>{e(sev)}<br>"
                 f"<span class='ss-meta'>{e(means)}</span></td>"
                 f"<td>{e(d.get(chr(116)+chr(105)+chr(116)+chr(108)+chr(101)) or d.get(chr(105)+chr(115)+chr(115)+chr(117)+chr(101)))}</td>"
                 f"<td>{_n(len(urls) or d.get(chr(99)+chr(111)+chr(117)+chr(110)+chr(116)), chr(45)+chr(45))}</td>"
                 f"<td>{_n(d.get(chr(105)+chr(109)+chr(112)+chr(114)+chr(101)+chr(115)+chr(115)+chr(105)+chr(111)+chr(110)+chr(115)+chr(95)+chr(97)+chr(116)+chr(95)+chr(114)+chr(105)+chr(115)+chr(107)))}</td>"
                 f"<td>{e(d.get(chr(99)+chr(97)+chr(116)+chr(101)+chr(103)+chr(111)+chr(114)+chr(121)) or chr(117)+chr(110)+chr(115)+chr(101)+chr(116))}</td>"
                 f"<td>{e(d.get(chr(102)+chr(105)+chr(114)+chr(115)+chr(116)+chr(95)+chr(115)+chr(101)+chr(101)+chr(110)) or chr(110)+chr(111)+chr(116)+chr(32)+chr(114)+chr(101)+chr(99)+chr(111)+chr(114)+chr(100)+chr(101)+chr(100))}</td>"
                 "<td>"
                 + TK.button("Generate fix", variant="ai", size="compact",
                             onclick="ssFix()")
                 + "</td></tr>")
    heads = ("Severity", "Issue", "URLs", "Impressions at risk",
             "Category", "First seen", "Action")
    return ("<p class='ss-h'>ISSUES</p>"
            f"<p class='ss-note'>{len(issues)} open, worst first. "
            f"Traffic at risk shows only where impressions are joined to "
            f"the URL; where they are not it reads not measured rather "
            f"than zero.</p>"
            "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "".join(f"<th>{e(h)}</th>" for h in heads)
            + "</tr></thead><tbody>" + rows + "</tbody></table></div>")


def crawled_pages(r, crawl=None, limit=60) -> str:
    """Spec 25. Every URL and its real state; unchecked is never a pass."""
    c = _D(crawl)
    pages = _L(c.get("pages"))
    if not pages:
        return ("<p class='ss-h'>CRAWLED PAGES</p>"
                + empty("No crawled pages",
                        "The crawler has not run, so this table has "
                        "nothing true to list.",
                        "Run a crawl", "act('/seo/crawl')"))
    rows = ""
    for x in pages[:limit]:
        d = _D(x)
        idx = d.get("indexable")
        tone = ("success" if idx else
                "danger" if idx is False else "neutral")
        word = ("indexable" if idx else
                "noindex" if idx is False else "not checked")
        rows += ("<tr>"
                 f"<td>{e(str(d.get(chr(117)+chr(114)+chr(108)))[:60])}</td>"
                 f"<td>{_n(d.get(chr(115)+chr(116)+chr(97)+chr(116)+chr(117)+chr(115)), chr(45)+chr(45))}</td>"
                 f"<td class='so-{tone}'>{word}</td>"
                 f"<td>{e(str(d.get(chr(116)+chr(105)+chr(116)+chr(108)+chr(101)) or chr(0))[:44]) or chr(109)+chr(105)+chr(115)+chr(115)+chr(105)+chr(110)+chr(103)}</td>"
                 f"<td>{_n(d.get(chr(119)+chr(111)+chr(114)+chr(100)+chr(95)+chr(99)+chr(111)+chr(117)+chr(110)+chr(116)))}</td>"
                 f"<td>{_n(d.get(chr(105)+chr(110)+chr(116)+chr(101)+chr(114)+chr(110)+chr(97)+chr(108)+chr(95)+chr(108)+chr(105)+chr(110)+chr(107)+chr(115)))}</td>"
                 f"<td>{_n(d.get(chr(99)+chr(108)+chr(105)+chr(99)+chr(107)+chr(115)))}</td>"
                 "</tr>")
    heads = ("URL", "HTTP", "Indexable", "Title", "Words",
             "Internal links", "Clicks")
    return ("<p class='ss-h'>CRAWLED PAGES</p>"
            f"<p class='ss-note'>{len(pages)} crawled, showing "
            f"{min(limit, len(pages))}. A field the crawl did not check "
            f"reads not checked, never a pass.</p>"
            "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "".join(f"<th>{e(h)}</th>" for h in heads)
            + "</tr></thead><tbody>" + rows + "</tbody></table></div>")


CSS += """<style>
.ss-scroll{overflow-x:auto}
.ss-tbl{border-collapse:collapse;width:100%;font-size:12px}
.ss-tbl th{color:var(--so-text2);text-transform:uppercase;font-size:10px;
letter-spacing:.4px;text-align:left;padding:6px 8px;
border-bottom:1px solid var(--so-border)}
.ss-tbl td{padding:6px 8px;border-bottom:1px solid var(--so-border);
color:var(--so-text);font-variant-numeric:tabular-nums;vertical-align:top}
</style>"""


# ---------------------------------------------------------------------------
# CONTENT (spec 30-34)
# ---------------------------------------------------------------------------
#: Spec 30. The health words a content row may carry. Declared once so the
#: inventory, the decay board and the filters cannot name different sets.
CONTENT_HEALTH = ("GROWING", "STABLE", "DECAYING", "DEAD", "NOT MEASURED")

#: Spec 32. A decline this size over the window is decay rather than noise.
DECAY_CLICK_DROP = 20.0
DECAY_MIN_CLICKS = 30


def content_health(row) -> dict:
    """One row's verdict, with the numbers it rests on. Never a bare word."""
    d = _D(row)
    now_c, was_c = d.get("clicks"), d.get("previous_clicks")
    if now_c is None or was_c is None:
        return {"state": "NOT MEASURED",
                "why": "no before-and-after clicks are joined to this URL"}
    try:
        now_c, was_c = float(now_c), float(was_c)
    except Exception:
        return {"state": "NOT MEASURED", "why": "clicks are not numeric"}
    if (now_c + was_c) < DECAY_MIN_CLICKS:
        return {"state": "NOT MEASURED",
                "why": (f"{int(now_c + was_c)} clicks across both windows, "
                        f"under the {DECAY_MIN_CLICKS} floor. A verdict "
                        f"here would be noise wearing a label.")}
    if was_c == 0:
        return {"state": "GROWING" if now_c > 0 else "DEAD",
                "why": "no clicks in the previous window"}
    pct = (now_c - was_c) / was_c * 100
    if pct <= -DECAY_CLICK_DROP:
        st = "DECAYING"
    elif pct >= DECAY_CLICK_DROP:
        st = "GROWING"
    elif now_c == 0:
        st = "DEAD"
    else:
        st = "STABLE"
    return {"state": st, "pct": round(pct, 1),
            "why": f"clicks {int(was_c)} to {int(now_c)}, {pct:+.1f}%"}


def content_inventory(r, rows=None) -> str:
    """Spec 30. Every content page with its performance and its verdict."""
    items = _L(rows)
    if not items:
        return ("<p class='ss-h'>CONTENT INVENTORY</p>"
                + empty("No content rows",
                        "No pages are joined to search data yet. Connect "
                        "Search Console and run a crawl; an inventory "
                        "without performance is just a sitemap.",
                        "Connect Search Console", "nav('map')"))
    body = ""
    counts = {}
    for x in items[:60]:
        d = _D(x)
        h = content_health(d)
        counts[h["state"]] = counts.get(h["state"], 0) + 1
        tone = {"GROWING": "success", "DECAYING": "danger",
                "DEAD": "danger", "STABLE": "neutral"}.get(h["state"],
                                                           "neutral")
        body += ("<tr>"
                 + "<td>" + e(str(d.get("url"))[:52]) + "</td>"
                 + "<td>" + e(d.get("topic") or "uncategorised") + "</td>"
                 + "<td>" + _n(d.get("clicks")) + "</td>"
                 + "<td>" + _n(d.get("conversions")) + "</td>"
                 + "<td class='so-" + tone + "'>" + h["state"]
                 + "<br><span class='ss-meta'>" + e(h["why"])[:60]
                 + "</span></td>"
                 + "<td>" + e(d.get("updated") or "not recorded") + "</td>"
                 + "</tr>")
    summary = ", ".join(f"{v} {k.lower()}" for k, v in sorted(counts.items()))
    heads = ("URL", "Topic", "Clicks", "Conversions", "Health", "Updated")
    return ("<p class='ss-h'>CONTENT INVENTORY</p>"
            + "<p class='ss-note'>" + str(len(items)) + " pages: "
            + e(summary) + ". A page without before-and-after clicks reads "
            + "NOT MEASURED rather than being called stable.</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "".join("<th>" + e(h) + "</th>" for h in heads)
            + "</tr></thead><tbody>" + body + "</tbody></table></div>")


def content_decay(r, rows=None) -> str:
    """Spec 32. Only pages that measurably declined, worst first."""
    items = []
    for x in _L(rows):
        h = content_health(x)
        if h["state"] == "DECAYING":
            items.append((h.get("pct", 0), x, h))
    if not items:
        return ("<p class='ss-h'>CONTENT DECAY</p>"
                + empty("Nothing is measurably decaying",
                        "Either no page dropped more than "
                        + str(int(DECAY_CLICK_DROP)) + " percent, or too "
                        "few pages carry before-and-after clicks to judge. "
                        "Quiet is a finding, but check the inventory for "
                        "how many read NOT MEASURED.",
                        "Open inventory", "seoTab('seocontent')"))
    items.sort(key=lambda z: z[0])
    body = ""
    for pct, x, h in items[:30]:
        d = _D(x)
        body += ("<tr><td>" + e(str(d.get("url"))[:52]) + "</td>"
                 + "<td class='so-danger'>" + f"{pct:+.1f}%" + "</td>"
                 + "<td>" + _n(d.get("previous_clicks")) + "</td>"
                 + "<td>" + _n(d.get("clicks")) + "</td>"
                 + "<td>" + _n(d.get("position")) + "</td>"
                 + "<td>" + e(d.get("updated") or "not recorded") + "</td>"
                 + "<td>" + TK.button("Analyze decay", variant="ai",
                                      size="compact",
                                      onclick="ssDecay()") + "</td></tr>")
    heads = ("URL", "Change", "Was", "Now", "Position", "Last updated",
             "Action")
    return ("<p class='ss-h'>CONTENT DECAY</p>"
            + "<p class='ss-note'>" + str(len(items)) + " page(s) declined "
            + "by " + str(int(DECAY_CLICK_DROP)) + " percent or more on at "
            + "least " + str(DECAY_MIN_CLICKS) + " clicks. Anything thinner "
            + "is left out rather than reported as decay.</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "".join("<th>" + e(h) + "</th>" for h in heads)
            + "</tr></thead><tbody>" + body + "</tbody></table></div>")


def content_gap(r, gaps=None) -> str:
    """Spec 31. Topics with demand that we do not cover."""
    items = _L(gaps)
    if not items:
        return ("<p class='ss-h'>CONTENT GAP</p>"
                + empty("No gap analysis on record",
                        "A gap needs competitor coverage and search demand "
                        "joined together. Neither is on record yet, and a "
                        "gap list invented without them would send real "
                        "writing budget in a random direction.",
                        "Run competitor research", "act('/seo/competitors')"))
    body = ""
    for g in items[:40]:
        d = _D(g)
        body += ("<tr><td>" + e(d.get("topic")) + "</td>"
                 + "<td>" + _n(d.get("demand")) + "</td>"
                 + "<td>" + e(d.get("intent") or "unclassified") + "</td>"
                 + "<td>" + _n(d.get("competitor_coverage")) + "</td>"
                 + "<td>" + _n(d.get("our_coverage"), "none") + "</td>"
                 + "<td>" + e(d.get("business_value") or "UNKNOWN") + "</td>"
                 + "<td>" + e(d.get("page_type") or "not recommended yet")
                 + "</td><td>"
                 + TK.button("Create brief", variant="primary",
                             size="compact", onclick="ssBrief()")
                 + "</td></tr>")
    heads = ("Topic", "Demand", "Intent", "Competitor coverage",
             "Our coverage", "Business value", "Recommended page type",
             "Action")
    return ("<p class='ss-h'>CONTENT GAP</p>"
            + "<p class='ss-note'>" + str(len(items)) + " topic(s) where "
            + "demand exists and our coverage does not.</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "".join("<th>" + e(h) + "</th>" for h in heads)
            + "</tr></thead><tbody>" + body + "</tbody></table></div>")


#: Spec 33. What a brief must carry before anything is written against it.
BRIEF_FIELDS = ("topic", "primary_keyword", "secondary", "intent",
                "business_goal", "audience", "page_type", "competitors",
                "outline", "questions", "entities", "internal_links",
                "cta", "schema")


def check_brief(brief) -> dict:
    d = _D(brief)
    missing = [f for f in BRIEF_FIELDS if not d.get(f)]
    if missing:
        return {"ok": False, "code": "BRIEF_INCOMPLETE", "missing": missing,
                "message": ("a brief is what a writer or an agent works "
                            "from, so it is refused until it carries: "
                            + ", ".join(missing))}
    return {"ok": True, "message": "brief complete"}


def content_brief(brief=None) -> str:
    """Spec 33. The brief, or an honest account of what it still needs."""
    chk = check_brief(brief)
    if not chk["ok"]:
        return ("<p class='ss-h'>CONTENT BRIEF</p>"
                + empty("Brief incomplete",
                        chk["message"],
                        "Generate the missing parts", "ssBriefFill()"))
    d = _D(brief)
    rows = "".join(
        "<div class='ss-docrow'><span>" + e(f.replace("_", " ").title())
        + "</span><b>" + e(str(d.get(f))[:160]) + "</b></div>"
        for f in BRIEF_FIELDS)
    return ("<p class='ss-h'>CONTENT BRIEF</p><div class='ss-doc'>" + rows
            + "</div><div class='ss-diffcta'>"
            + TK.button("Save brief", variant="secondary", size="compact",
                        onclick="ssBriefSave()")
            + TK.button("Generate draft", variant="ai", size="compact",
                        onclick="ssDraft()") + "</div>")


def content_editor(brief=None, draft="") -> str:
    """Spec 34. Three panes: the brief, the draft, and what is missing."""
    d = _D(brief)
    text = str(draft or "")
    if not text.strip():
        return ("<p class='ss-h'>CONTENT EDITOR</p>"
                + empty("No draft yet",
                        "Generate a draft from an approved brief, or paste "
                        "one. The optimisation panel scores what is "
                        "actually written, so it stays empty until there "
                        "is text.",
                        "Generate draft", "ssDraft()"))
    low = text.lower()
    qs = _L(d.get("questions"))
    ents = _L(d.get("entities"))
    q_hit = [q for q in qs if str(q).lower()[:40] in low]
    e_hit = [x for x in ents if str(x).lower() in low]
    def cov(hit, total, label):
        if not total:
            return ("<div class='ss-docrow'><span>" + label
                    + "</span><b>not measured: the brief lists none</b>"
                    + "</div>")
        return ("<div class='ss-docrow'><span>" + label + "</span><b>"
                + str(len(hit)) + " of " + str(len(total)) + "</b></div>")
    return ("<p class='ss-h'>CONTENT EDITOR</p>"
            + "<div class='ss-doc'>"
            + "<div class='ss-docrow'><span>Words</span><b>"
            + str(len(text.split())) + "</b></div>"
            + cov(q_hit, qs, "Question coverage")
            + cov(e_hit, ents, "Entity coverage")
            + "</div>"
            + "<p class='ss-note'>Coverage counts a question or entity as "
            + "covered only when its words actually appear in the draft. "
            + "It is a check on what was written, not a judgement of "
            + "quality, and it says so rather than implying a score.</p>"
            + "<div class='ss-diffcta'>"
            + TK.button("Save draft", variant="secondary", size="compact",
                        onclick="ssSave()")
            + TK.button("Publish", variant="primary", size="compact",
                        onclick="ssPublish()") + "</div>")


CSS += """<style>
.ss-doc{border:1px solid var(--so-border);border-radius:
var(--so-radius-card);padding:12px 15px;background:var(--so-surface);
margin:6px 0}
.ss-docrow{display:flex;justify-content:space-between;gap:14px;
border-bottom:1px solid var(--so-border);padding:5px 0;font-size:12px}
.ss-docrow span{color:var(--so-text2)}
.ss-docrow b{color:var(--so-text);text-align:right}
</style>"""


# ---------------------------------------------------------------------------
# BACKLINKS (spec 36-37)
# ---------------------------------------------------------------------------
def backlinks_overview(r, data=None) -> str:
    """Spec 36. The link profile and its direction of travel."""
    d = _D(data)
    refs = _L(d.get("referring_domains"))
    if not refs and d.get("backlinks") is None:
        return ("<p class='ss-h'>BACKLINKS</p>"
                + empty("No backlink data on record",
                        "No backlink provider is connected. Link counts "
                        "are the easiest number in SEO to invent, so this "
                        "screen shows none until a provider supplies "
                        "them.",
                        "Connect a provider", "nav('map')"))
    src = d.get("source") or "backlink provider"
    new, lost = _L(d.get("new")), _L(d.get("lost"))
    return ("<p class='ss-h'>BACKLINKS</p><div class='ss-kpis'>"
            + metric("Backlinks", d.get("backlinks"), source=src)
            + metric("Referring domains", len(refs) or
                     d.get("referring_domain_count"), source=src)
            + metric("New", len(new) or None, source=src)
            + metric("Lost", len(lost) or None, source=src,
                     polarity="negative")
            + "</div>"
            + ("<p class='ss-note'>Net movement: "
               + str(len(new) - len(lost)) + " domain(s) this window. A "
               + "profile that only ever grows usually means lost links "
               + "are not being tracked, not that none were lost.</p>"
               if (new or lost) else
               "<p class='ss-note'>No new or lost domains are recorded "
               "for this window, which may mean nothing changed or may "
               "mean the provider does not supply the delta.</p>"))


def backlink_gap(r, gaps=None) -> str:
    """Spec 37. Domains linking to competitors and not to us."""
    items = _L(gaps)
    if not items:
        return ("<p class='ss-h'>BACKLINK GAP</p>"
                + empty("No gap on record",
                        "A gap needs both our profile and at least one "
                        "competitor's, from the same provider. Comparing "
                        "two different providers' link counts produces a "
                        "difference that is about the providers, not the "
                        "websites.",
                        "Connect a provider", "nav('map')"))
    body = ""
    for g in items[:40]:
        d = _D(g)
        body += ("<tr><td>" + e(d.get("domain")) + "</td>"
                 + "<td>" + ("yes" if d.get("we_have") else "no") + "</td>"
                 + "<td>" + _n(d.get("competitor_links")) + "</td>"
                 + "<td>" + _n(d.get("authority")) + "</td>"
                 + "<td>" + e(d.get("relevance") or "not scored") + "</td>"
                 + "<td>" + e(d.get("link_type") or "unknown") + "</td>"
                 + "<td>" + TK.button("Research", variant="secondary",
                                      size="compact",
                                      onclick="ssResearch()") + "</td>"
                 + "</tr>")
    heads = ("Referring domain", "We have it", "Competitor links",
             "Authority", "Relevance", "Link type", "Action")
    return ("<p class='ss-h'>BACKLINK GAP</p>"
            + "<p class='ss-note'>" + str(len(items)) + " domain(s) link "
            + "to a competitor and not to us. This screen researches; it "
            + "never sends outreach, because automated link outreach is "
            + "how a domain earns a reputation nobody wants.</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "".join("<th>" + e(h) + "</th>" for h in heads)
            + "</tr></thead><tbody>" + body + "</tbody></table></div>")


# ---------------------------------------------------------------------------
# AEO (spec 38-39)
# ---------------------------------------------------------------------------
#: Spec 38. How well a question is answered. Four states, not two.
COVERAGE = ("STRONG", "WEAK", "MISSING", "NOT ASSESSED")


def answer_coverage(row) -> dict:
    """Judged from what is on the page, or NOT ASSESSED. Never guessed."""
    d = _D(row)
    if d.get("answer_words") is None:
        return {"state": "NOT ASSESSED",
                "why": ("no page has been checked against this question "
                        "yet")}
    try:
        words = float(d.get("answer_words") or 0)
    except Exception:
        return {"state": "NOT ASSESSED", "why": "answer length unreadable"}
    if words <= 0:
        return {"state": "MISSING", "why": "no answer found on any page"}
    if words < 40:
        return {"state": "WEAK",
                "why": f"{int(words)} words, too short to answer it fully"}
    return {"state": "STRONG", "why": f"{int(words)} words on the page"}


def aeo_questions(r, rows=None) -> str:
    """Spec 38. Questions with demand, and whether we answer them."""
    items = _L(rows)
    if not items:
        return ("<p class='ss-h'>AEO QUESTIONS</p>"
                + empty("No tracked questions",
                        "Nothing is being tracked yet. Questions come "
                        "from Search Console queries, People Also Ask "
                        "observations and your own list; none are "
                        "invented here.",
                        "Pull Search Console", "act('/seo/inspect')"))
    counts, body = {}, ""
    for x in items[:50]:
        d = _D(x)
        c = answer_coverage(d)
        counts[c["state"]] = counts.get(c["state"], 0) + 1
        tone = {"STRONG": "success", "WEAK": "warning",
                "MISSING": "danger"}.get(c["state"], "neutral")
        body += ("<tr><td>" + e(str(d.get("question"))[:64]) + "</td>"
                 + "<td>" + _n(d.get("demand")) + "</td>"
                 + "<td>" + e(d.get("page") or "none") + "</td>"
                 + "<td class='so-" + tone + "'>" + c["state"]
                 + "<br><span class='ss-meta'>" + e(c["why"])[:52]
                 + "</span></td>"
                 + "<td>" + _n(d.get("position")) + "</td>"
                 + "<td>" + TK.button("Improve answer", variant="ai",
                                      size="compact",
                                      onclick="ssAnswer()") + "</td>"
                 + "</tr>")
    heads = ("Question", "Demand", "Answering page", "Coverage",
             "Position", "Action")
    return ("<p class='ss-h'>AEO QUESTIONS</p>"
            + "<p class='ss-note'>" + str(len(items)) + " tracked: "
            + e(", ".join(f"{v} {k.lower()}"
                          for k, v in sorted(counts.items())))
            + ". A question nobody has checked a page against reads NOT "
            + "ASSESSED rather than missing, because those are different "
            + "facts.</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "".join("<th>" + e(h) + "</th>" for h in heads)
            + "</tr></thead><tbody>" + body + "</tbody></table></div>")


def answer_detail(r, row=None) -> str:
    """Spec 39. One question, and exactly what our answer is missing."""
    d = _D(row)
    if not d.get("question"):
        return ("<p class='ss-h'>ANSWER DETAIL</p>"
                + empty("No question selected",
                        "This screen answers one question about one "
                        "question, so it will not pick one for you.",
                        "Open questions", "seoTab('seoaeo2')"))
    c = answer_coverage(d)
    missing = _L(d.get("missing_points"))
    return ("<p class='ss-h'>ANSWER DETAIL</p>"
            + "<div class='ss-doc'>"
            + "<div class='ss-docrow'><span>Question</span><b>"
            + e(d.get("question")) + "</b></div>"
            + "<div class='ss-docrow'><span>Demand</span><b>"
            + _n(d.get("demand")) + "</b></div>"
            + "<div class='ss-docrow'><span>Answering page</span><b>"
            + e(d.get("page") or "none") + "</b></div>"
            + "<div class='ss-docrow'><span>Coverage</span><b>"
            + c["state"] + " &middot; " + e(c["why"]) + "</b></div>"
            + "</div>"
            + ("<p class='ss-h'>WHAT THE ANSWER IS MISSING</p><ul "
               "class='ss-hist'>"
               + "".join("<li>" + e(m) + "</li>" for m in missing)
               + "</ul>"
               if missing else
               "<p class='ss-note'>Nothing is recorded as missing. That "
               "is either a complete answer or an unexamined one; the "
               "coverage state above says which.</p>")
            + TK.button("Improve answer", variant="ai", size="compact",
                        onclick="ssAnswer()"))
