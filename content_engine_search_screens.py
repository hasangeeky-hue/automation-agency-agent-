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


# ---------------------------------------------------------------------------
# GEO / AI SEARCH VISIBILITY (spec 40-43)
# ---------------------------------------------------------------------------
#: Spec 41. What one prompt observation can say. MENTIONED and CITED are
#: different facts: an answer can name you without linking you, and that
#: distinction is the whole point of the citation work.
OBSERVED = ("CITED", "MENTIONED", "ABSENT", "NOT RUN")

#: A prompt observed fewer times than this has not earned a trend line.
#: AI answers vary between runs, so one observation is an anecdote.
MIN_RUNS = 3


def prompt_state(row) -> dict:
    """What one prompt's observations actually establish."""
    d = _D(row)
    runs = _L(d.get("runs"))
    if not runs:
        return {"state": "NOT RUN", "runs": 0,
                "why": "this prompt has never been observed"}
    cited = sum(1 for x in runs if _D(x).get("cited"))
    mentioned = sum(1 for x in runs if _D(x).get("mentioned"))
    n = len(runs)
    state = ("CITED" if cited else "MENTIONED" if mentioned else "ABSENT")
    trend = (f"{cited} of {n} runs cited, {mentioned} of {n} mentioned")
    if n < MIN_RUNS:
        return {"state": state, "runs": n, "provisional": True,
                "why": (f"{trend}. Only {n} observation(s): AI answers "
                        f"vary between runs, so this is an anecdote until "
                        f"there are {MIN_RUNS}.")}
    return {"state": state, "runs": n, "provisional": False,
            "rate": round(cited / n * 100, 1), "why": trend}


def ai_visibility(r, data=None) -> str:
    """Spec 40. The command centre for AI search visibility."""
    d = _D(data)
    prompts = _L(d.get("prompts"))
    if not prompts:
        return ("<p class='ss-h'>AI SEARCH VISIBILITY</p>"
                + empty("No prompts tracked",
                        "Nothing has been asked of any AI provider yet. "
                        "Every figure on this screen comes from an "
                        "observation this engine actually ran; none are "
                        "modelled, so the screen stays empty until it has "
                        "run some.",
                        "Add prompts", "ssPrompts()"))
    total = len(prompts)
    states = {}
    runs_total = 0
    for x in prompts:
        st = prompt_state(x)
        states[st["state"]] = states.get(st["state"], 0) + 1
        runs_total += st["runs"]
    ran = total - states.get("NOT RUN", 0)
    src = d.get("source") or "AI observation engine"
    def pct(n):
        return round(n / ran * 100, 1) if ran else None
    return ("<p class='ss-h'>AI SEARCH VISIBILITY</p><div class='ss-kpis'>"
            + metric("Tracked prompts", total, source=src)
            + metric("Observed", ran, source=src)
            + metric("Citation rate %", pct(states.get("CITED", 0)),
                     source=src, polarity="positive")
            + metric("Mention rate %",
                     pct(states.get("CITED", 0)
                         + states.get("MENTIONED", 0)),
                     source=src, polarity="positive")
            + metric("Observations", runs_total, source=src)
            + "</div>"
            + "<p class='ss-note'>Rates are over the "
            + str(ran) + " prompt(s) actually observed, not over all "
            + str(total) + ". A prompt that has never run is excluded "
            + "rather than counted as absent, because not asking is not "
            + "the same as not appearing.</p>")


def prompt_tracker(r, prompts=None) -> str:
    """Spec 41. Every prompt, provider and observation."""
    items = _L(prompts)
    if not items:
        return ("<p class='ss-h'>PROMPT TRACKER</p>"
                + empty("No prompts",
                        "Add the prompts your buyers would actually type "
                        "into an AI assistant. This engine observes what "
                        "you give it; it does not invent a prompt list.",
                        "Add prompts", "ssPrompts()"))
    body = ""
    for x in items[:50]:
        d = _D(x)
        st = prompt_state(d)
        tone = {"CITED": "success", "MENTIONED": "warning",
                "ABSENT": "danger"}.get(st["state"], "neutral")
        body += ("<tr><td>" + e(str(d.get("prompt"))[:58]) + "</td>"
                 + "<td>" + e(d.get("provider") or "not recorded")
                 + "</td>"
                 + "<td class='so-" + tone + "'>" + st["state"]
                 + ("<br><span class='ss-meta'>provisional</span>"
                    if st.get("provisional") else "") + "</td>"
                 + "<td>" + str(st["runs"]) + "</td>"
                 + "<td>" + e(st["why"])[:70] + "</td>"
                 + "<td>" + e(d.get("competitor") or "none seen") + "</td>"
                 + "<td>" + TK.button("Re-run", variant="ai",
                                      size="compact",
                                      onclick="ssRerun()") + "</td>"
                 + "</tr>")
    heads = ("Prompt", "Provider", "State", "Runs", "Evidence",
             "Competitor seen", "Action")
    return ("<p class='ss-h'>PROMPT TRACKER</p>"
            + "<p class='ss-note'>A prompt observed fewer than "
            + str(MIN_RUNS) + " times is marked provisional. AI answers "
            + "vary between runs, and one observation is an anecdote.</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "".join("<th>" + e(h) + "</th>" for h in heads)
            + "</tr></thead><tbody>" + body + "</tbody></table></div>")


def citation_gap(r, gaps=None) -> str:
    """Spec 42. Sources AI answers cite for competitors and not for us."""
    items = _L(gaps)
    if not items:
        return ("<p class='ss-h'>CITATION GAP</p>"
                + empty("No citation gap on record",
                        "A gap needs observed citations for both us and a "
                        "competitor on the same prompts. Until both exist "
                        "there is nothing to compare, and a list of "
                        "'authoritative sources' invented without them is "
                        "just a directory.",
                        "Run prompt observations", "ssRerun()"))
    body = ""
    for g in items[:40]:
        d = _D(g)
        body += ("<tr><td>" + e(d.get("source")) + "</td>"
                 + "<td>" + e(d.get("topic") or "unclassified") + "</td>"
                 + "<td>" + _n(d.get("our_citations"), "0") + "</td>"
                 + "<td>" + _n(d.get("competitor_citations")) + "</td>"
                 + "<td>" + e(d.get("relevance") or "not scored") + "</td>"
                 + "<td>" + e(d.get("strategy") or "not recommended yet")
                 + "</td></tr>")
    heads = ("Source cited by the AI", "Topic", "Our citations",
             "Competitor citations", "Relevance", "Recommended strategy")
    return ("<p class='ss-h'>CITATION GAP</p>"
            + "<p class='ss-note'>" + str(len(items)) + " source(s) that "
            + "AI answers draw on for a competitor and not for us. This "
            + "is where AI answers get their evidence, which is a "
            + "different question from where search ranks you.</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "".join("<th>" + e(h) + "</th>" for h in heads)
            + "</tr></thead><tbody>" + body + "</tbody></table></div>")


def ai_visibility_detail(r, row=None) -> str:
    """Spec 43. One prompt: what the provider actually said."""
    d = _D(row)
    if not d.get("prompt"):
        return ("<p class='ss-h'>AI VISIBILITY DETAIL</p>"
                + empty("No prompt selected",
                        "This screen shows what a provider actually "
                        "answered for one prompt, so it will not choose "
                        "one for you.",
                        "Open the tracker", "seoTab('seogeoai')"))
    st = prompt_state(d)
    runs = _L(d.get("runs"))
    rows = "".join(
        "<tr><td>" + e(str(_D(x).get("at"))[:16]) + "</td>"
        + "<td>" + e(_D(x).get("provider") or "not recorded") + "</td>"
        + "<td>" + ("cited" if _D(x).get("cited") else
                    "mentioned" if _D(x).get("mentioned") else "absent")
        + "</td>"
        + "<td>" + e(str(_D(x).get("answer") or "")[:90]) + "</td>"
        + "</tr>" for x in runs[:15])
    return ("<p class='ss-h'>AI VISIBILITY DETAIL</p>"
            + "<div class='ss-doc'>"
            + "<div class='ss-docrow'><span>Prompt</span><b>"
            + e(d.get("prompt")) + "</b></div>"
            + "<div class='ss-docrow'><span>State</span><b>"
            + st["state"] + " &middot; " + e(st["why"])[:80] + "</b></div>"
            + "<div class='ss-docrow'><span>Competitors seen</span><b>"
            + e(", ".join(str(x) for x in _L(d.get("competitors")))
               or "none recorded") + "</b></div>"
            + "</div>"
            + (("<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
                "<th>Observed</th><th>Provider</th><th>Result</th>"
                "<th>Answer extract</th></tr></thead><tbody>"
                + rows + "</tbody></table></div>")
               if runs else
               "<p class='ss-note'>No observation is recorded for this "
               "prompt yet.</p>"))


# ---------------------------------------------------------------------------
# ANALYTICS AND THE FUNNEL (spec 44-47)
# ---------------------------------------------------------------------------
#: Spec 46. The funnel, in order, with the source each stage comes from.
#: Two different systems measure these, and the screen says which.
FUNNEL = (("Impressions", "Google Search Console"),
          ("Clicks", "Google Search Console"),
          ("Organic sessions", "GA4"),
          ("Engaged sessions", "GA4"),
          ("Conversions", "GA4"),
          ("Revenue", "GA4 / CRM"))


def search_analytics(r, totals=None) -> str:
    """Spec 44-45. Search performance joined to business outcome."""
    t = _D(totals)
    if not t:
        return ("<p class='ss-h'>SEARCH ANALYTICS</p>"
                + empty("No search analytics",
                        "Search Console and GA4 are not both joined yet. "
                        "This screen exists to put clicks next to money, "
                        "so it shows nothing until both sides are real.",
                        "Connect Google", "nav('map')"))
    return ("<p class='ss-h'>SEARCH ANALYTICS</p><div class='ss-kpis'>"
            + metric("Organic clicks", t.get("clicks"),
                     source="Google Search Console")
            + metric("Organic sessions", t.get("sessions"), source="GA4")
            + metric("Conversions", t.get("conversions"), source="GA4")
            + metric("Revenue", t.get("revenue"), source="GA4 / CRM")
            + metric("Avg position", t.get("position"),
                     source="Rank tracker", polarity="negative")
            + "</div>"
            + "<p class='ss-note'>Clicks come from Search Console and "
            + "sessions from GA4. They will not match, and neither is "
            + "wrong: they count different things at different moments. "
            + "This screen shows both rather than picking one and calling "
            + "it traffic.</p>")


def search_funnel(r, stages=None) -> str:
    """Spec 46. Where search traffic is lost, with each rate named."""
    d = _D(stages)
    have = [(label, src, d.get(label.lower().replace(" ", "_")))
            for label, src in FUNNEL]
    real = [x for x in have if x[2] not in (None, "")]
    if len(real) < 2:
        return ("<p class='ss-h'>SEARCH FUNNEL</p>"
                + empty("Not enough stages measured",
                        "A funnel needs at least two measured stages. "
                        "Filling the gaps with estimates would produce a "
                        "shape that looks like insight and is arithmetic "
                        "on invented numbers.",
                        "Connect Google", "nav('map')"))
    top = float(real[0][2]) or 1.0
    body, prev = "", None
    for label, src, val in real:
        v = float(val)
        rate = ""
        if prev is not None and prev > 0:
            rate = f"{v / prev * 100:.2f}% of {prev_label.lower()}"
        body += ("<div class='ss-fun'><span>" + e(label) + "</span>"
                 + "<span class='ss-funbar'><span style='width:"
                 + str(max(2, int(v / top * 100))) + "%'></span></span>"
                 + "<i>" + _n(v) + "</i>"
                 + "<p>" + e(rate) + " &middot; source: " + e(src)
                 + "</p></div>")
        prev, prev_label = v, label
    missing = [x[0] for x in have if x[2] in (None, "")]
    return ("<p class='ss-h'>SEARCH FUNNEL</p>" + body
            + (("<p class='ss-note'>" + str(len(missing)) + " stage(s) "
                + "are not measured and are LEFT OUT rather than "
                + "estimated: " + e(", ".join(missing)) + ". A funnel "
                + "with an invented middle is worse than a short "
                + "one.</p>") if missing else ""))


def business_first(r, pages=None) -> str:
    """Spec 47. Traffic is not the ranking; conversion value is."""
    items = _L(pages)
    if not items:
        return ("<p class='ss-h'>BUSINESS-FIRST PRIORITY</p>"
                + empty("No conversion data joined",
                        "Without conversions per page, every priority "
                        "list is a traffic list wearing a business label. "
                        "Join GA4 conversions to see this.",
                        "Connect GA4", "nav('map')"))
    rows = []
    for x in items:
        d = _D(x)
        clicks = float(d.get("clicks") or 0)
        conv = d.get("conversions")
        if conv is None:
            rows.append((None, d, "no conversions joined to this page"))
            continue
        conv = float(conv)
        cvr = (conv / clicks * 100) if clicks else None
        rows.append((conv, d,
                     (f"{int(conv)} conversion(s) from {int(clicks)} "
                      f"clicks" + (f", {cvr:.2f}%" if cvr else ""))))
    rows.sort(key=lambda z: -(z[0] if z[0] is not None else -1))
    body = "".join(
        "<tr><td>" + e(str(_D(d).get("url"))[:52]) + "</td>"
        + "<td>" + _n(_D(d).get("clicks")) + "</td>"
        + "<td>" + (_n(c) if c is not None else "not measured") + "</td>"
        + "<td>" + e(why) + "</td></tr>" for c, d, why in rows[:30])
    return ("<p class='ss-h'>BUSINESS-FIRST PRIORITY</p>"
            + "<p class='ss-note'>Ranked by conversions, not clicks. A "
            + "page with ten thousand clicks and eight conversions sits "
            + "below one with two thousand clicks and ninety-four, which "
            + "is the whole point.</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "<th>URL</th><th>Clicks</th><th>Conversions</th>"
            + "<th>Basis</th></tr></thead><tbody>" + body
            + "</tbody></table></div>")


# ---------------------------------------------------------------------------
# AGENT CENTRE (spec 50-51)
# ---------------------------------------------------------------------------
#: Spec 50. The agents this OS actually has. Naming an agent that does
#: not exist is how an org chart becomes a lie.
AGENTS = ("SearchOrchestrator", "TechnicalAgent", "IndexabilityAgent",
          "KeywordAgent", "RankAgent", "SERPAgent", "CompetitorAgent",
          "ContentAgent", "InternalLinkAgent", "SchemaAgent",
          "BacklinkAgent", "AEOAgent", "GEOAgent", "EntityAgent",
          "AnalyticsAgent", "ExecutionAgent", "VerificationAgent")

#: Which of those are wired to real code today. The gap is the honest
#: work-remaining list, and the screen prints it rather than hiding it.
AGENTS_WIRED = ("RankAgent", "ContentAgent", "ExecutionAgent",
                "VerificationAgent")


def agent_centre(r) -> str:
    """Spec 50-51. Every run, its budget, and what it cost."""
    runs = r.all("search_agent_runs")
    wired = ("<div class='ss-doc'>"
             + "".join(
                 "<div class='ss-docrow'><span>" + e(a) + "</span><b>"
                 + ("wired" if a in AGENTS_WIRED else "declared, not wired")
                 + "</b></div>" for a in AGENTS)
             + "</div>"
             + "<p class='ss-note'>" + str(len(AGENTS_WIRED)) + " of "
             + str(len(AGENTS)) + " agents are wired to real code. The "
             + "rest are named because the spec names them, and they say "
             + "so rather than appearing to work.</p>")
    if not runs:
        return ("<p class='ss-h'>AGENT CENTRE</p>"
                + empty("No agent has run",
                        "Nothing has been dispatched yet. Runs appear "
                        "here with their budget and their cost the "
                        "moment one starts.",
                        "", "")
                + "<p class='ss-h'>AGENTS</p>" + wired)
    body = ""
    for x in sorted(runs, key=lambda y: str(y.get("started_at") or ""),
                    reverse=True)[:25]:
        d = _D(x)
        u, b = _D(d.get("used")), _D(d.get("budget"))
        tone = {"ESCALATED": "danger", "RUNNING": "info"}.get(
            d.get("state"), "neutral")
        body += ("<tr><td>" + e(d.get("agent")) + "</td>"
                 + "<td>" + e(str(d.get("objective"))[:44]) + "</td>"
                 + "<td class='so-" + tone + "'>" + e(d.get("state"))
                 + "</td>"
                 + "<td>" + str(u.get("max_steps", 0)) + " / "
                 + str(b.get("max_steps", 0)) + "</td>"
                 + "<td>" + str(round(u.get("max_cost_usd", 0), 3)) + " / "
                 + str(b.get("max_cost_usd", 0)) + "</td>"
                 + "<td>" + e(", ".join(_L(d.get("escalation")))
                              or "none") + "</td></tr>")
    return ("<p class='ss-h'>AGENT CENTRE</p>"
            + "<p class='ss-note'>" + str(len(runs)) + " run(s). Every "
            + "one carries a hard budget; exhausting it escalates to you "
            + "rather than looping.</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "<th>Agent</th><th>Objective</th><th>State</th>"
            + "<th>Steps</th><th>Cost USD</th><th>Escalated on</th>"
            + "</tr></thead><tbody>" + body + "</tbody></table></div>"
            + "<p class='ss-h'>AGENTS</p>" + wired)


CSS += """<style>
.ss-fun{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin:0 0 7px}
.ss-fun>span:first-child{width:130px;font-size:12px;color:var(--so-text)}
.ss-fun i{font-style:normal;font-size:12px;color:var(--so-text);
font-variant-numeric:tabular-nums}
.ss-fun p{width:100%;margin:0 0 0 139px;font-size:10px;
color:var(--so-text2)}
.ss-funbar{flex:1;min-width:120px;height:10px;border-radius:5px;
background:rgba(148,163,184,.18);overflow:hidden}
.ss-funbar span{display:block;height:100%;background:var(--so-primary-main)}
</style>"""


# ---------------------------------------------------------------------------
# RESEARCH BOARDS (spec 15-21)
# ---------------------------------------------------------------------------
#: Spec 17. Intent, and the fact that we may not know it. UNCLASSIFIED is
#: a real answer: a keyword whose intent nobody determined is not
#: informational by default, and guessing turns a research board into a
#: horoscope.
INTENT = ("TRANSACTIONAL", "COMMERCIAL", "INFORMATIONAL", "NAVIGATIONAL",
          "UNCLASSIFIED")

#: Spec 18. Volume below this is too thin for a monthly figure to mean
#: anything; providers round and estimate down here.
MIN_VOLUME = 10


def _kw_intent(row) -> str:
    d = _D(row)
    v = str(d.get("intent") or "").upper()
    return v if v in INTENT else "UNCLASSIFIED"


def domain_overview(r, d=None) -> str:
    """Spec 15. One domain, at a glance, with every figure sourced."""
    x = _D(d)
    if not x.get("domain"):
        return ("<p class='ss-h'>DOMAIN OVERVIEW</p>"
                + empty("No domain analysed",
                        "Enter a domain to pull its organic profile. Every "
                        "number on this board comes from a provider and "
                        "carries that provider's name, because two "
                        "providers will disagree and you need to know "
                        "which one you are reading.",
                        "Analyse a domain", "ssDomain()"))
    src = x.get("source") or "not recorded"
    return ("<p class='ss-h'>DOMAIN OVERVIEW &middot; "
            + e(x.get("domain")) + "</p><div class='ss-kpis'>"
            + metric("Authority", x.get("authority"), source=src)
            + metric("Organic keywords", x.get("keywords"), source=src)
            + metric("Organic traffic (est)", x.get("traffic"), source=src)
            + metric("Referring domains", x.get("referring_domains"),
                     source=src)
            + metric("Top 3 positions", x.get("top3"), source=src)
            + metric("Top 10 positions", x.get("top10"), source=src)
            + "</div>"
            + "<p class='ss-note'>Traffic here is a provider ESTIMATE "
            + "modelled from position and volume, not measured sessions. "
            + "Your own GA4 number is the measured one, and the two will "
            + "differ; this figure is for comparing domains to each "
            + "other, not for reporting your own traffic.</p>")


def organic_research(r, rows=None) -> str:
    """Spec 16. Every keyword a domain ranks for, and the movement."""
    items = _L(rows)
    if not items:
        return ("<p class='ss-h'>ORGANIC RESEARCH</p>"
                + empty("No ranking keywords pulled",
                        "This board lists what a domain already ranks for. "
                        "It reads a provider; it does not model rankings.",
                        "Run research", "ssResearch()"))
    body = ""
    for k in items[:60]:
        kd = _D(k)
        pos, prev = kd.get("position"), kd.get("prev_position")
        move, tone = "first seen", "neutral"
        if pos is not None and prev is not None:
            dlt = float(prev) - float(pos)
            move = ("no change" if abs(dlt) < 0.5
                    else ("up " if dlt > 0 else "down ")
                    + str(abs(round(dlt, 1))))
            tone = ("neutral" if abs(dlt) < 0.5
                    else "success" if dlt > 0 else "danger")
        body += ("<tr><td>" + e(str(kd.get("keyword"))[:44]) + "</td>"
                 + "<td>" + _n(pos) + "</td>"
                 + "<td class='so-" + tone + "'>" + e(move) + "</td>"
                 + "<td>" + _n(kd.get("volume")) + "</td>"
                 + "<td>" + e(_kw_intent(kd)) + "</td>"
                 + "<td>" + e(str(kd.get("url") or "not mapped")[:38])
                 + "</td></tr>")
    unc = sum(1 for k in items if _kw_intent(k) == "UNCLASSIFIED")
    heads = ("Keyword", "Position", "Movement", "Volume", "Intent", "URL")
    return ("<p class='ss-h'>ORGANIC RESEARCH</p>"
            + "<p class='ss-note'>" + str(len(items)) + " keyword(s). A "
            + "keyword with no previous position reads FIRST SEEN, not "
            + "'new', because it may simply be the first time we looked."
            + (" " + str(unc) + " have no classified intent and say so "
               + "rather than defaulting to informational." if unc else "")
            + "</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "".join("<th>" + e(h) + "</th>" for h in heads)
            + "</tr></thead><tbody>" + body + "</tbody></table></div>")


def keyword_explorer(r, rows=None) -> str:
    """Spec 17-18. Keywords with volume, difficulty and intent."""
    items = _L(rows)
    if not items:
        return ("<p class='ss-h'>KEYWORD EXPLORER</p>"
                + empty("No keywords researched",
                        "Search a seed term to pull volume, difficulty and "
                        "intent. Difficulty is a provider's model, not a "
                        "measurement, and this board labels it that way.",
                        "Explore keywords", "ssKeywords()"))
    body, thin = "", 0
    for k in items[:60]:
        kd = _D(k)
        vol = kd.get("volume")
        note = ""
        if vol is not None and float(vol) < MIN_VOLUME:
            thin += 1
            note = "below " + str(MIN_VOLUME) + "/mo, provider estimates "\
                   "are unreliable this low"
        kdiff = kd.get("difficulty")
        body += ("<tr><td>" + e(str(kd.get("keyword"))[:44]) + "</td>"
                 + "<td>" + _n(vol) + "</td>"
                 + "<td>" + (_n(kdiff) + " (modelled)"
                             if kdiff is not None else "not scored")
                 + "</td>"
                 + "<td>" + e(_kw_intent(kd)) + "</td>"
                 + "<td>" + _n(kd.get("cpc")) + "</td>"
                 + "<td>" + e(note or (str(kd.get("serp_note") or "")))
                 + "</td></tr>")
    heads = ("Keyword", "Volume/mo", "Difficulty", "Intent", "CPC",
             "Caveat")
    return ("<p class='ss-h'>KEYWORD EXPLORER</p>"
            + "<p class='ss-note'>Difficulty is a MODELLED score from a "
            + "provider, not something anyone measured. It is comparable "
            + "within one provider and meaningless across two."
            + (" " + str(thin) + " keyword(s) fall below "
               + str(MIN_VOLUME) + "/mo and are flagged: providers round "
               + "and estimate at that floor." if thin else "")
            + "</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "".join("<th>" + e(h) + "</th>" for h in heads)
            + "</tr></thead><tbody>" + body + "</tbody></table></div>")


def keyword_gap(r, rows=None, competitors=None) -> str:
    """Spec 19. What competitors rank for and we do not."""
    items = _L(rows)
    comps = [str(c) for c in _L(competitors)]
    if not items or not comps:
        return ("<p class='ss-h'>KEYWORD GAP</p>"
                + empty("No gap computed",
                        "A gap needs our rankings AND at least one "
                        "competitor's, pulled from the same provider on "
                        "the same day. Comparing two providers or two "
                        "dates produces a gap that is about the pull, not "
                        "about the websites.",
                        "Add a competitor", "ssCompetitors()"))
    body = ""
    for k in items[:60]:
        kd = _D(k)
        ours = kd.get("our_position")
        best = [(_D(x).get("position"), _D(x).get("domain"))
                for x in _L(kd.get("competitors"))
                if _D(x).get("position") is not None]
        best.sort()
        body += ("<tr><td>" + e(str(kd.get("keyword"))[:40]) + "</td>"
                 + "<td>" + (_n(ours) if ours is not None
                             else "not ranking") + "</td>"
                 + "<td>" + (str(best[0][0]) + " &middot; "
                             + e(str(best[0][1])) if best
                             else "none ranking") + "</td>"
                 + "<td>" + _n(kd.get("volume")) + "</td>"
                 + "<td>" + e(_kw_intent(kd)) + "</td>"
                 + "<td>" + e("we do not rank" if ours is None
                              else "they rank higher" if best
                              and float(best[0][0]) < float(ours)
                              else "we rank higher") + "</td></tr>")
    heads = ("Keyword", "Us", "Best competitor", "Volume", "Intent",
             "Gap")
    return ("<p class='ss-h'>KEYWORD GAP</p>"
            + "<p class='ss-note'>Against " + e(", ".join(comps[:4]))
            + ". A keyword where we do not rank reads NOT RANKING, never "
            + "position 100: an absence is not a bad position, and "
            + "averaging invented hundreds would corrupt every summary "
            + "above it.</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "".join("<th>" + e(h) + "</th>" for h in heads)
            + "</tr></thead><tbody>" + body + "</tbody></table></div>")


def position_tracking(r, rows=None, meta=None) -> str:
    """Spec 20-21. Tracked positions over time, with the pull dated."""
    items = _L(rows)
    m = _D(meta)
    if not items:
        return ("<p class='ss-h'>POSITION TRACKING</p>"
                + empty("Nothing tracked",
                        "Add the keywords you want watched. Tracking is "
                        "the only ranking number here that is measured "
                        "rather than estimated, so it is the one worth "
                        "keeping.",
                        "Track keywords", "ssTrack()"))
    up = sum(1 for x in items if _D(x).get("delta") is not None
             and float(_D(x)["delta"]) > 0.5)
    down = sum(1 for x in items if _D(x).get("delta") is not None
               and float(_D(x)["delta"]) < -0.5)
    flat = len(items) - up - down
    body = ""
    for x in items[:60]:
        d = _D(x)
        dl = d.get("delta")
        tone = ("neutral" if dl is None or abs(float(dl)) < 0.5
                else "success" if float(dl) > 0 else "danger")
        body += ("<tr><td>" + e(str(d.get("keyword"))[:40]) + "</td>"
                 + "<td>" + _n(d.get("position")) + "</td>"
                 + "<td class='so-" + tone + "'>"
                 + (("+" if dl and float(dl) > 0 else "")
                    + str(round(float(dl), 1)) if dl is not None
                    else "no prior pull") + "</td>"
                 + "<td>" + _n(d.get("best")) + "</td>"
                 + "<td>" + e(d.get("device") or "not recorded") + "</td>"
                 + "<td>" + e(d.get("location") or "not recorded")
                 + "</td></tr>")
    heads = ("Keyword", "Position", "Change", "Best ever", "Device",
             "Location")
    return ("<p class='ss-h'>POSITION TRACKING</p><div class='ss-kpis'>"
            + metric("Tracked", len(items), source="rank tracker")
            + metric("Improved", up, source="rank tracker",
                     polarity="positive")
            + metric("Declined", down, source="rank tracker",
                     polarity="negative")
            + metric("Unchanged", flat, source="rank tracker")
            + "</div>"
            + "<p class='ss-note'>Last pull: "
            + e(m.get("pulled_at") or "not recorded") + ". Device and "
            + "location are shown per keyword because a position without "
            + "them is not a fact: the same query ranks differently on "
            + "mobile in Munich and desktop in Boston.</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "".join("<th>" + e(h) + "</th>" for h in heads)
            + "</tr></thead><tbody>" + body + "</tbody></table></div>")


# ---------------------------------------------------------------------------
# THE SHELL (spec 4-7) AND THE COMPONENT LIBRARY (spec 97)
# ---------------------------------------------------------------------------
#: Spec 6. How old a pull may be before the screens built on it stop
#: being current. Two floors, because a crawl and a rank pull age at very
#: different speeds and one number for both would be wrong for both.
STALE_HOURS = {"Google Search Console": 48, "GA4": 48, "Crawler": 168,
               "Rank tracker": 48, "Backlink provider": 336,
               "AI observation engine": 168}
DEFAULT_STALE_HOURS = 72

#: Spec 6. What a source can be. NEVER CONNECTED and NO DATA YET are
#: different problems with different fixes, so they are different states.
SOURCE_STATE = ("FRESH", "STALE", "NO DATA YET", "NEVER CONNECTED",
                "ERROR")


def source_state(row, now_hours=None) -> dict:
    """One source: is what it gave us still worth trusting?"""
    d = _D(row)
    name = str(d.get("name") or "unnamed source")
    if not d.get("connected"):
        return {"name": name, "state": "NEVER CONNECTED",
                "why": "no credential has been attached to this source"}
    if d.get("error"):
        return {"name": name, "state": "ERROR",
                "why": str(d.get("error"))[:90]}
    age = d.get("age_hours")
    if age is None:
        return {"name": name, "state": "NO DATA YET",
                "why": ("connected, but nothing has been pulled. This is "
                        "not the same as an empty result: nobody has "
                        "asked yet.")}
    limit = STALE_HOURS.get(name, DEFAULT_STALE_HOURS)
    age = float(age)
    if age > limit:
        return {"name": name, "state": "STALE", "age": age,
                "why": (f"last pull was {int(age)}h ago; anything built "
                        f"on it is older than the {limit}h this source "
                        f"is trusted for")}
    return {"name": name, "state": "FRESH", "age": age,
            "why": f"pulled {int(age)}h ago, within {limit}h"}


def data_freshness(r, sources=None) -> str:
    """Spec 6. Every source, its age, and what that costs the screens."""
    items = _L(sources)
    if not items:
        return ("<div class='ss-bar ss-bar-warn'>No source is declared. "
                "Every screen below is drawing on nothing, and says so "
                "individually rather than showing zeros.</div>")
    states = [source_state(x) for x in items]
    bad = [s for s in states
           if s["state"] in ("STALE", "ERROR", "NEVER CONNECTED")]
    chips = "".join(
        "<span class='ss-chip ss-chip-"
        + {"FRESH": "ok", "STALE": "warn", "ERROR": "bad",
           "NEVER CONNECTED": "off", "NO DATA YET": "off"}[s["state"]]
        + "' title='" + e(s["why"]) + "'>" + e(s["name"])
        + "<b>" + s["state"] + "</b></span>" for s in states)
    head = ("Every source is current."
            if not bad else
            str(len(bad)) + " of " + str(len(states)) + " source(s) are "
            + "not current. Screens built on them are showing the last "
            + "thing that arrived, not the truth as of now.")
    return ("<div class='ss-bar" + ("" if not bad else " ss-bar-warn")
            + "'><p>" + e(head) + "</p><div class='ss-chips'>" + chips
            + "</div></div>")


def attention(r, items=None) -> str:
    """Spec 7. What needs a human, above everything else on the page."""
    xs = _L(items)
    if not xs:
        return ("<div class='ss-bar ss-bar-ok'><p>Nothing is waiting on "
                "you. This band stays empty rather than filling itself "
                "with things that are merely interesting.</p></div>")
    rows = "".join(
        "<div class='ss-att'><span class='ss-att-k'>"
        + e(_D(x).get("kind") or "needs a decision") + "</span>"
        + "<b>" + e(str(_D(x).get("what"))[:80]) + "</b>"
        + "<i>" + e(str(_D(x).get("why") or "no reason recorded")[:90])
        + "</i>"
        + TK.button(_D(x).get("action") or "Open", variant="primary",
                    size="compact",
                    onclick=_D(x).get("onclick") or "void 0")
        + "</div>" for x in xs[:8])
    return ("<div class='ss-bar ss-bar-warn'><p>" + str(len(xs))
            + " item(s) are waiting on you. Nothing here proceeds "
            + "without a person: every send, publish and spend stops at "
            + "this band.</p>" + rows + "</div>")


def shell(r, ctx=None) -> str:
    """Spec 4-5. The frame every search screen sits inside."""
    c = _D(ctx)
    site = c.get("site") or "no site configured"
    mode = c.get("mode") or "NORMAL"
    ver = c.get("version") or "not stamped"
    degraded = str(mode).upper() != "NORMAL"
    return ("<div class='ss-shell" + (" ss-shell-deg" if degraded else "")
            + "'><div class='ss-shell-id'>"
            + "<b>SEARCH INTELLIGENCE</b><span>" + e(site) + "</span>"
            + "</div><div class='ss-shell-meta'>"
            + "<span>mode <b>" + e(str(mode)) + "</b></span>"
            + "<span>build <b>" + e(str(ver)) + "</b></span>"
            + "</div></div>"
            + (("<div class='ss-bar ss-bar-warn'><p>This OS is running "
                "DEGRADED. Screens still render, but a degraded run is "
                "not a clean run and no result from it should be filed "
                "as evidence.</p></div>") if degraded else "")
            + data_freshness(r, c.get("sources"))
            + attention(r, c.get("attention")))


def nav_map(r) -> str:
    """Spec 5. The whole OS on one page, so nothing is stranded."""
    import content_engine_seo_boards as B
    labels = dict((t[0], t[2]) for t in B.TABS)
    body = ""
    for gid, glabel, question, tabs in B.GROUPS:
        body += ("<div class='ss-navg'><p><b>" + e(glabel)
                 + "</b><span>" + e(question) + "</span></p><div>"
                 + "".join(
                     "<button class='ss-navb' onclick=\"seoTab('"
                     + t + "')\">" + e(labels.get(t, t)) + "</button>"
                     for t in tabs) + "</div></div>")
    orphans = [t[0] for t in B.TABS
               if not any(t[0] in g[3] for g in B.GROUPS)]
    return ("<p class='ss-h'>WHERE EVERYTHING IS</p>"
            + "<p class='ss-note'>" + str(len(B.TABS)) + " screen(s) in "
            + str(len(B.GROUPS)) + " group(s), each group answering one "
            + "question. A screen reachable only by scrolling is a "
            + "screen nobody uses, so every one of them is listed "
            + "here.</p>" + body
            + (("<p class='ss-note so-danger'>" + str(len(orphans))
                + " screen(s) belong to NO group and can only be reached "
                + "by accident: " + e(", ".join(orphans)) + "</p>")
               if orphans else ""))


def component_library(r) -> str:
    """Spec 97. Every primitive, rendered, so the system is inspectable."""
    states = "".join(TK.status(s) for s in TK.STATUS)
    btns = "".join(TK.button(v.title(), variant=v, size="compact",
                             onclick="void 0") for v in TK.CTA)
    # metric() REFUSES a value with no named source. The library proves
    # that by calling it wrongly and catching the raise, rather than
    # printing a claim that it would refuse. A design system that only
    # describes its own rules cannot be trusted to enforce them.
    try:
        metric("Without a source", 1420)
        refused = "DID NOT REFUSE, which is a bug in the token module"
    except TypeError:
        refused = ("refused: metric() will not render a number that "
                   "cannot name where it came from")
    metrics = (metric("With a source", 1420, source="Google Search Console")
               + metric("Not measured", None,
                        source="Google Search Console"))
    return ("<p class='ss-h'>COMPONENT LIBRARY</p>"
            + "<p class='ss-note'>Rendered from the token module itself, "
            + "not redrawn here. If a component changes, this page "
            + "changes with it; a component gallery maintained by hand "
            + "drifts from the product within a week and then lies about "
            + "it.</p>"
            + "<p class='ss-h2'>Status, " + str(len(TK.STATUS))
            + " states</p><div class='ss-lib'>" + states + "</div>"
            + "<p class='ss-note'>Every status carries a dot AND a word. "
            + "Colour alone excludes anyone who cannot separate red from "
            + "green, which is one man in twelve.</p>"
            + "<p class='ss-h2'>Actions, " + str(len(TK.CTA))
            + " variants</p><div class='ss-lib'>" + btns + "</div>"
            + "<p class='ss-note'>These are the only variants that "
            + "exist. Asking the token module for a variant outside this "
            + "list raises rather than quietly rendering a grey "
            + "button.</p>"
            + "<p class='ss-h2'>Metrics</p><div class='ss-kpis'>"
            + metrics + "</div>"
            + "<p class='ss-note'>Sourceless metric, live: " + e(refused)
            + ". An absent value reads 'not measured' "
            + "rather than zero. Those two rules are why the numbers on "
            + "this OS can be argued with.</p>"
            + "<p class='ss-h2'>Empty and error</p>"
            + empty("An empty state names the fix",
                    "It says what is missing, why it is missing, and "
                    "what to press. A shrug with a magnifying glass is "
                    "not a state.", "Do the thing", "void 0")
            + error("An error state names the failure",
                    "provider returned 503 after 3 retries",
                    "retry the pull, or connect a second provider")
            + "<p class='ss-note'>error() takes three arguments and will "
            + "not construct without the third. An error that says what "
            + "broke but not what to do about it is a dead end wearing a "
            + "red border.</p>")


CSS += """<style>
.ss-shell{display:flex;justify-content:space-between;align-items:center;
gap:12px;flex-wrap:wrap;padding:11px 14px;border-radius:10px;
border:1px solid var(--so-line);background:var(--so-surface);margin:0 0 9px}
.ss-shell-deg{border-color:var(--so-warning-main)}
.ss-shell-id b{font-size:12px;letter-spacing:.09em;color:var(--so-text)}
.ss-shell-id span{margin-left:9px;font-size:12px;color:var(--so-text2)}
.ss-shell-meta{display:flex;gap:14px;font-size:10px;color:var(--so-text2);
letter-spacing:.05em}
.ss-shell-meta b{color:var(--so-text);font-weight:600}
.ss-bar{padding:9px 13px;border-radius:9px;border:1px solid var(--so-line);
background:var(--so-surface);margin:0 0 9px}
.ss-bar>p{margin:0;font-size:11px;color:var(--so-text2);line-height:1.55}
.ss-bar-warn{border-color:var(--so-warning-main)}
.ss-bar-ok{border-color:var(--so-line)}
.ss-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.ss-chip{display:inline-flex;gap:6px;align-items:center;font-size:10px;
padding:3px 8px;border-radius:20px;border:1px solid var(--so-line);
color:var(--so-text2)}
.ss-chip b{font-weight:600;letter-spacing:.04em}
.ss-chip-ok{border-color:var(--so-success-main);color:var(--so-success-main)}
.ss-chip-warn{border-color:var(--so-warning-main);color:var(--so-warning-main)}
.ss-chip-bad{border-color:var(--so-danger-main);color:var(--so-danger-main)}
.ss-chip-off{opacity:.72}
.ss-att{display:flex;gap:10px;align-items:center;flex-wrap:wrap;
padding:7px 0;border-top:1px solid var(--so-line);margin-top:7px}
.ss-att-k{font-size:9px;letter-spacing:.08em;text-transform:uppercase;
color:var(--so-text2);min-width:112px}
.ss-att b{font-size:12px;color:var(--so-text);font-weight:600}
.ss-att i{flex:1;min-width:180px;font-style:normal;font-size:10px;
color:var(--so-text2)}
.ss-navg{margin:0 0 11px}
.ss-navg>p{margin:0 0 6px;display:flex;gap:9px;align-items:baseline;
flex-wrap:wrap}
.ss-navg>p b{font-size:11px;letter-spacing:.07em;color:var(--so-text)}
.ss-navg>p span{font-size:10px;color:var(--so-text2)}
.ss-navg>div{display:flex;flex-wrap:wrap;gap:6px}
.ss-navb{font-size:11px;padding:5px 10px;border-radius:7px;cursor:pointer;
border:1px solid var(--so-line);background:transparent;color:var(--so-text2)}
.ss-navb:hover{color:var(--so-text);border-color:var(--so-primary-main)}
.ss-lib{display:flex;flex-wrap:wrap;gap:8px;align-items:center;
padding:11px;border-radius:9px;border:1px solid var(--so-line);
background:var(--so-surface);margin:0 0 7px}
.ss-h2{margin:14px 0 6px;font-size:10px;letter-spacing:.09em;
text-transform:uppercase;color:var(--so-text2)}
</style>"""


# ---------------------------------------------------------------------------
# DATA ARCHITECTURE, CMS AND REPORTING (spec 75-78, 85-86)
# ---------------------------------------------------------------------------
import content_engine_search_data as DAT  # noqa: E402


def data_model(r) -> str:
    """Spec 75. Every entity, its key, and the credential rule."""
    rows = "".join(
        "<tr><td>" + e(n) + "</td><td><code>" + e(k) + "</code></td>"
        + "<td>" + e(w) + "</td></tr>" for n, k, w in DAT.ENTITIES)
    return ("<p class='ss-h'>THE CANONICAL MODEL</p>"
            + "<p class='ss-note'>" + str(len(DAT.ENTITIES))
            + " entities, one list. A table that exists in the store but "
            + "not here is an orphan: nothing retains it, nothing backs "
            + "it up and nothing deletes it.</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "<th>Entity</th><th>Identified by</th><th>What it is</th>"
            + "</tr></thead><tbody>" + rows + "</tbody></table></div>"
            + "<div class='ss-bar ss-bar-warn'><p><b>Credentials.</b> "
            + e(DAT.CREDENTIAL_RULE) + "</p></div>")


def identity_rules(r, sample=None) -> str:
    """Spec 76. What the normaliser does, proved on a real string."""
    probe = str(sample or
                "HTTPS://Example.com/Guide/?utm_source=x&page=2#top")
    n = DAT.normalize_url(probe)
    kw = DAT.normalize_keyword("  Tattoo Needles ", "de")
    did = "".join("<li>" + e(c) + "</li>" for c in n["changed"])
    didnt = "".join("<li>" + e(c) + "</li>" for c in n["not_done"])
    kwnot = "".join("<li>" + e(c) + "</li>" for c in kw["not_done"])
    return ("<p class='ss-h'>IDENTITY RULES</p>"
            + "<p class='ss-note'>Two records are the same thing only "
            + "when a rule says so, and every rule is listed. A "
            + "normaliser that works silently is impossible to argue "
            + "with on the day two pages turn out to have merged.</p>"
            + "<div class='ss-doc'><div class='ss-docrow'>"
            + "<span>Input</span><b><code>" + e(probe)
            + "</code></b></div><div class='ss-docrow'>"
            + "<span>Identity</span><b><code>" + e(n["url"])
            + "</code></b></div></div>"
            + "<p class='ss-h2'>What it changed</p><ul class='ss-ul'>"
            + did + "</ul>"
            + "<p class='ss-h2'>What it deliberately did NOT change</p>"
            + "<ul class='ss-ul ss-ul-warn'>" + didnt + "</ul>"
            + "<p class='ss-h2'>Keywords</p>"
            + "<div class='ss-doc'><div class='ss-docrow'>"
            + "<span>Input</span><b><code>  Tattoo Needles  </code> in "
            + "market <code>de</code></b></div>"
            + "<div class='ss-docrow'><span>Key</span><b><code>"
            + e(kw["key"]) + "</code></b></div></div>"
            + "<ul class='ss-ul ss-ul-warn'>" + kwnot + "</ul>")


def retention_board(r) -> str:
    """Spec 77. How long everything is kept, and why."""
    plan = DAT.retention_plan()
    gaps = [x for x in plan if x["state"] == "NO POLICY"]
    rows = "".join(
        "<tr><td>" + e(x["entity"]) + "</td>"
        + "<td class='so-" + ("danger" if x["state"] == "NO POLICY"
                              else "neutral") + "'>" + e(x["state"])
        + "</td>"
        + "<td>" + (str(x["days"]) + " days" if x["days"] else "no expiry")
        + "</td><td>" + e(x["why"]) + "</td></tr>" for x in plan)
    return ("<p class='ss-h'>RETENTION</p>"
            + "<p class='ss-note'>Every policy carries its reason. A "
            + "retention rule with no reason gets reopened every year "
            + "and settled by whoever speaks loudest."
            + ((" " + str(len(gaps)) + " entity(ies) have NO policy and "
                + "grow forever by accident rather than on purpose.")
               if gaps else "") + "</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "<th>Entity</th><th>State</th><th>Kept</th><th>Why</th>"
            + "</tr></thead><tbody>" + rows + "</tbody></table></div>")


def cms_board(r, connected=None) -> str:
    """Spec 78. What each CMS can be asked to do, and what it cannot."""
    cur = str(connected or "manual").lower()
    body = ""
    for key, spec in DAT.CMS.items():
        on = (key == cur)
        can = "".join("<span class='ss-cap ss-cap-y'>" + e(c) + "</span>"
                      for c in spec["can"]) or \
            "<span class='ss-cap ss-cap-n'>nothing</span>"
        cannot = "".join("<span class='ss-cap ss-cap-n'>" + e(c)
                         + "</span>" for c in spec["cannot"])
        body += ("<div class='ss-cms" + (" on" if on else "") + "'>"
                 + "<p><b>" + e(spec["label"]) + "</b>"
                 + ("<i>connected</i>" if on else "") + "</p>"
                 + "<p class='ss-meta'>Auth: " + e(spec["auth"])
                 + "</p><div class='ss-caps'>" + can + cannot + "</div>"
                 + "<p class='ss-meta'>" + e(spec["notes"]) + "</p></div>")
    demo = DAT.apply_change(cur, "update_title", "/guide",
                            before="Old", after="New")
    return ("<p class='ss-h'>CMS ADAPTERS</p>"
            + "<p class='ss-note'>A capability missing from an adapter "
            + "comes back UNSUPPORTED and becomes a work order. It never "
            + "silently does nothing, which is the failure that makes an "
            + "operator believe a fix landed.</p>" + body
            + "<p class='ss-h2'>What a change actually does</p>"
            + "<div class='ss-doc'><div class='ss-docrow'>"
            + "<span>Result</span><b>" + e(demo["state"])
            + "</b></div><div class='ss-docrow'><span>Why</span><b>"
            + e(demo["why"]) + "</b></div></div>"
            + "<p class='ss-note'>Dry run is the DEFAULT. A live write "
            + "needs the capability, a real difference, a non-empty new "
            + "value and a named approver. 'The agent decided' is not a "
            + "name.</p>")


def reports_board(r, report=None, schedules=None) -> str:
    """Spec 85-86. What a report contains, and what it refused."""
    rep = _D(report)
    scheds = _L(schedules)
    if not rep:
        return ("<p class='ss-h'>REPORTS</p>"
                + empty("No report built",
                        "A report is the artefact that outlives this "
                        "dashboard and gets forwarded to people who "
                        "cannot check it, so this one is assembled from "
                        "sourced figures or not at all.",
                        "Build a report", "ssReport()")
                + _sched_block(scheds))
    tone = {"CLEAN": "success", "QUALIFIED": "warning",
            "EMPTY": "danger"}.get(rep.get("state"), "neutral")
    secs = "".join(
        "<div class='ss-docrow'><span>" + e(_D(s).get("section"))
        + "</span><b>" + str(len(_L(_D(s).get("figures"))))
        + " sourced figure(s)</b></div>" for s in _L(rep.get("sections")))
    drops = "".join(
        "<li><b>" + e(_D(d).get("section") or _D(d).get("figure"))
        + "</b> " + e(_D(d).get("why")) + "</li>"
        for d in (_L(rep.get("dropped")) + _L(rep.get("unsourced"))))
    return ("<p class='ss-h'>REPORTS</p>"
            + "<p class='ss-note so-" + tone + "'>State: "
            + e(rep.get("state")) + ". Window: "
            + e(str(rep.get("window") or "not stated")) + ".</p>"
            + (("<div class='ss-bar ss-bar-warn'><p>"
                + e(rep.get("caveat")) + "</p></div>")
               if rep.get("caveat") else "")
            + "<div class='ss-doc'>" + (secs or
               "<div class='ss-docrow'><span>Sections</span><b>none "
               "survived</b></div>") + "</div>"
            + (("<p class='ss-h2'>What this report refused to print</p>"
                + "<ul class='ss-ul ss-ul-warn'>" + drops + "</ul>")
               if drops else
               "<p class='ss-note'>Nothing was dropped: every figure "
               "offered named its source.</p>")
            + _sched_block(scheds))


def _sched_block(scheds) -> str:
    """Schedules, which are recurring outbound sends and are gated."""
    if not scheds:
        return ("<p class='ss-h2'>Schedules</p><p class='ss-note'>None. "
                "A recurring report is a standing rule that emails "
                "people without anyone reading it first, so it needs a "
                "named owner before it exists.</p>")
    rows = "".join(
        "<tr><td>" + e(_D(s).get("cadence")) + "</td>"
        + "<td>" + str(len(_L(_D(s).get("recipients")))) + "</td>"
        + "<td class='so-" + ("success" if _D(s).get("state") == "SCHEDULED"
                              else "warning") + "'>"
        + e(_D(s).get("state")) + "</td>"
        + "<td>" + e(_D(s).get("approved_by") or "nobody yet") + "</td>"
        + "</tr>" for s in _L(scheds))
    return ("<p class='ss-h2'>Schedules</p>"
            + "<div class='ss-scroll'><table class='ss-tbl'><thead><tr>"
            + "<th>Cadence</th><th>Recipients</th><th>State</th>"
            + "<th>Approved by</th></tr></thead><tbody>" + rows
            + "</tbody></table></div>")


CSS += """<style>
.ss-ul{margin:0 0 10px;padding-left:17px}
.ss-ul li{font-size:11px;color:var(--so-text2);line-height:1.6;
margin:0 0 4px}
.ss-ul-warn li{color:var(--so-warning-main)}
.ss-cms{padding:10px 12px;border-radius:9px;border:1px solid var(--so-line);
margin:0 0 7px}
.ss-cms.on{border-color:var(--so-primary-main)}
.ss-cms>p{margin:0 0 5px;font-size:12px;color:var(--so-text)}
.ss-cms>p i{font-style:normal;margin-left:8px;font-size:9px;
letter-spacing:.08em;text-transform:uppercase;color:var(--so-primary-main)}
.ss-caps{display:flex;flex-wrap:wrap;gap:5px;margin:0 0 6px}
.ss-cap{font-size:10px;padding:2px 7px;border-radius:5px;
border:1px solid var(--so-line);color:var(--so-text2)}
.ss-cap-y{border-color:var(--so-success-main);color:var(--so-success-main)}
.ss-cap-n{border-color:var(--so-danger-main);color:var(--so-danger-main);
text-decoration:line-through}
</style>"""
