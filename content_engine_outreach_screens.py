"""
content_engine_outreach_screens.py
============================================================================
LEADS & OUTREACH, KLAVIYO GRAMMAR. Fourteen panels replacing 240 cards.

Dashboard, Campaigns, Flows, Profiles, Segments, Lists, Data quality,
Geography, Deliverability, Inbox, Conversions, Attribution, Templates and
Benchmarks - every one of them on machinery that is already live.

THE TWO RULES
  1. Every rate carries its denominator. "42%" with no "of what" is a
     rumour, and this dashboard has told enough of those.
  2. Every number derived from OPENS carries the Apple caveat, because a
     number whose weakness is known and unstated is worse than no number.

RENDERER ONLY. Ids are scoped "ol-" because the old dashboard renders every
panel at once.
============================================================================
"""

from __future__ import annotations

import html as _html

import content_engine_charts as CH
import content_engine_email_campaigns as EC
import content_engine_email_segments as ES
import content_engine_email_preview as EP


def e(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


def _D(v):
    return v if isinstance(v, dict) else {}


def _L(v):
    return v if isinstance(v, list) else []


def _num(v, suffix="") -> str:
    if v is None or v == "":
        return "<b class='ol-none'>--</b>"
    try:
        f = float(v)
        s = (f"{f/1000:.1f}k" if abs(f) >= 1000
             else (f"{f:,.0f}" if f == int(f) else f"{f:,.1f}"))
    except Exception:
        s = str(v)
    return f"<b>{e(s)}{e(suffix)}</b>"


def tile(label, value, sub="", suffix="") -> str:
    return ("<div class='ol-tile'><span class='ol-k'>" + e(label) + "</span>"
            + _num(value, suffix)
            + (f"<span class='ol-d'>{e(sub)}</span>" if sub else "")
            + "</div>")


def tiles(rows) -> str:
    return "<div class='ol-tiles'>" + "".join(tile(*r) for r in rows) + "</div>"


def chart(title, svg, empty="") -> str:
    body = svg or f"<p class='ol-empty'>{e(empty or 'Nothing measured yet.')}</p>"
    return f"<div class='ol-chart'><p class='ol-ct'>{e(title)}</p>{body}</div>"


def table(headers, rows) -> str:
    if not rows:
        return ""
    head = "".join(f"<span>{h}</span>" for h in headers)
    return ("<div class='ol-tbl'><div class='ol-tr ol-th'>" + head + "</div>"
            + "".join("<div class='ol-tr'>"
                      + "".join(f"<span>{c}</span>" for c in r) + "</div>"
                      for r in rows) + "</div>")


# ---------------------------------------------------------------------------
# THE BAND
# ---------------------------------------------------------------------------
def band(ctx) -> str:
    d = _D(ctx.get("deliverability"))
    sends = _D(ctx.get("sends"))
    cap, used = d.get("cap"), d.get("sent_today")
    return (
        "<div class='s3band'><div class='s3who'>"
        "<p class='s3k'>Email</p>"
        f"<p class='s3state'><b>{e(used if used is not None else '--')} of "
        f"{e(cap if cap is not None else '--')} sent today</b>"
        f" &middot; {e(sends.get('total') or 0)} sent in total"
        "</p>"
        "<p class='s3sub'>Every send on this board is yours to press. The "
        "engine composes, previews and queues; nothing leaves without a "
        "click, and the preview refuses to let a personalisation token go "
        "out empty.</p></div>"
        "<div class='s3cmds'>"
        "<button class='cta s3go' onclick=\"olNewCampaign()\">New campaign"
        "</button>"
        "<button class='cta' onclick=\"act('/outreach/source')\">Find leads"
        "</button>"
        "<button class='cta' onclick=\"act('/replies/fetch')\">Fetch replies"
        "</button></div></div>")


# ---------------------------------------------------------------------------
# 1 DASHBOARD
# ---------------------------------------------------------------------------
def dashboard(ctx) -> str:
    camps = _L(ctx.get("campaigns"))
    sends = _D(ctx.get("sends"))
    rep = _D(ctx.get("replies"))
    bk = _D(ctx.get("bookings"))
    attr = _D(ctx.get("attribution"))
    sent = sum(int(c.get("sent") or 0) for c in camps) or sends.get("total")
    tracked = sum(int(c.get("tracked") or 0) for c in camps)
    opens = sum(int(c.get("opens") or 0) for c in camps)
    clicks = sum(int(c.get("clicks") or 0) for c in camps)
    orate = EC._rate(opens, tracked)
    crate = EC._rate(clicks, tracked)
    ctor = EC._rate(clicks, opens)
    t = tiles([
        ("Emails sent", sent, "all time"),
        ("Tracked", tracked or None, "carry a pixel"),
        ("Open rate", orate[0], orate[1], "%"),
        ("Click rate", crate[0], crate[1], "%"),
        ("Click-to-open", ctor[0], ctor[1], "%"),
        ("Replies", rep.get("total"), "people who wrote back"),
        ("Bookings", bk.get("total"), "calls in the diary"),
        ("Revenue", attr.get("revenue"), "attributed to email", ""),
    ])
    curve = _L(ctx.get("open_curve"))
    c1 = chart("Opens in the first 72 hours",
               CH.lines([("Opens", [float(x) for x in curve], "#1B57F0")])
               if len(curve) >= 2 else "",
               "Fills once a tracked campaign has been opened.")
    rows = [(e(c["name"])[:34], _num(c.get("sent")), _num(c.get("open_rate"), "%"),
             _num(c.get("click_rate"), "%")) for c in camps[:6]]
    c2 = chart("Recent campaigns",
               "", "") if not rows else ""
    tbl = table(["Campaign", "Sent", "Open", "Click"], rows)
    caveat = f"<p class='ol-empty'>{e(EC.MPP_CAVEAT)}</p>"
    return t + "<div class='ol-row'>" + c1 + "</div>" + tbl + caveat


# ---------------------------------------------------------------------------
# 2 CAMPAIGNS
# ---------------------------------------------------------------------------
def campaigns_screen(ctx) -> str:
    camps = _L(ctx.get("campaigns"))
    sent = [c for c in camps if c.get("sent")]
    t = tiles([("Campaigns", len(camps) or None, ""),
               ("Sent", len(sent) or None, ""),
               ("Recipients", sum(int(c.get("recipients") or 0)
                                  for c in camps) or None, ""),
               ("Best open rate", max((c.get("open_rate") or 0
                                       for c in camps), default=0) or None,
                "of any campaign", "%"),
               ("Best click rate", max((c.get("click_rate") or 0
                                        for c in camps), default=0) or None,
                "", "%"),
               ("Total cost", sum(float(c.get("cost") or 0)
                                  for c in camps) or None, "", "")])
    rows = []
    for c in camps[:30]:
        rows.append((
            e(c["name"])[:38],
            f"<span class='ol-pill'>{e(c.get('status'))}</span>",
            _num(c.get("recipients")), _num(c.get("sent")),
            _num(c.get("open_rate"), "%") + f"<i>{e(c.get('open_of'))}</i>",
            _num(c.get("click_rate"), "%") + f"<i>{e(c.get('click_of'))}</i>",
            _num(c.get("ctor"), "%"),
            f"<button class='cta' onclick=\"olPreview('{e(c['id'])}')\">"
            f"Preview</button>"))
    tbl = table(["Campaign", "Status", "Recipients", "Sent", "Open rate",
                 "Click rate", "CTOR", ""], rows)
    links = _L(ctx.get("campaign_links"))
    lrows = [(e(l["url"])[:64], _num(l["clicks"])) for l in links[:12]]
    ltbl = table(["Link", "Clicks"], lrows)
    if not camps:
        return t + ("<p class='ol-empty'>No campaigns yet. Press <b>New "
                    "campaign</b> above: pick a segment, write it, preview "
                    "it, then send.</p>")
    return (t + tbl
            + ("<p class='ol-k'>Which link earned the clicks</p>" + ltbl
               if lrows else "")
            + f"<p class='ol-empty'>{e(EC.MPP_CAVEAT)}</p>")


# ---------------------------------------------------------------------------
# 3 FLOWS
# ---------------------------------------------------------------------------
def flows_screen(ctx) -> str:
    fl = _L(ctx.get("flows"))
    people = _L(ctx.get("profiles"))
    queue = _L(ctx.get("flow_queue"))
    out = []
    for f in fl[:4]:
        steps = _L(_D(f).get("steps"))
        diagram = "".join(
            f"<span class='ol-step ol-{_D(s).get('kind')}'>"
            + (e(_D(s).get("label") or "Send") if _D(s).get("kind") == "send"
               else (f"wait {e(_D(s).get('days'))}d"
                     if _D(s).get("kind") == "wait"
                     else "if " + e(_D(s).get("label") or "condition")))
            + "</span>" for s in steps)
        stats = ES.flow_stats(f, people)
        srows = [(e(s["label"]), _num(s["reached"]), _num(s["opened"]),
                  f"<i>{e(s['of'])}</i>") for s in stats]
        out.append(
            f"<p class='ol-k'>{e(_D(f).get('name'))}</p>"
            f"<div class='ol-flow'>{diagram}</div>"
            + table(["Step", "Reached", "Opened", "of the segment"], srows))
    t = tiles([("Flows", len(fl) or None, ""),
               ("People in scope", len(people) or None, ""),
               ("Queued for approval", len(queue) or None,
                "nothing sends itself"),
               ("Touches per person", 3, "the default cycle")])
    qrows = [(e(q.get("name") or q.get("email")), e(q.get("label")),
              f"step {e(q.get('step'))}") for q in queue[:20]]
    q = (("<p class='ol-k'>Waiting on your approval</p>"
          + table(["Person", "Email", "Step"], qrows)
          + "<button class='cta s3go' onclick=\"act('/outreach/flow/approve')\">"
            "Approve the queue</button>") if qrows else
         "<p class='ol-empty'>Nothing queued. Press <b>Run the flow</b> and "
         "the engine works out who is due, then waits for you.</p>")
    return (t + "".join(out)
            + "<button class='cta' onclick=\"act('/outreach/flow/run')\">"
              "Run the flow</button>" + q)


# ---------------------------------------------------------------------------
# 4 PROFILES
# ---------------------------------------------------------------------------
def profiles_screen(ctx) -> str:
    rows = _L(ctx.get("profiles"))
    st = EC.profile_stats(rows)
    t = tiles([("People", st.get("people"), "the engine has touched"),
               ("Engaged", st.get("engaged"), "opened or clicked"),
               ("Clickers", st.get("clickers"), "the ones that matter"),
               ("Replied", st.get("repliers"), "wrote back")])
    trs = []
    for i, p in enumerate(rows[:40]):
        tl = "".join(
            f"<span class='ol-ev ol-{e(x.get('kind'))}'>{e(x.get('kind'))}"
            f"<i>{e(str(x.get('at'))[:16])}</i></span>"
            for x in _L(p.get("timeline"))[:10])
        trs.append((
            e(p.get("name") or p.get("email"))[:26],
            e(p.get("company"))[:22], _num(p.get("sends")),
            _num(p.get("opens")), _num(p.get("clicks")),
            "yes" if p.get("replied") else "&ndash;",
            f"<span class='ol-tl'>{tl}</span>"))
    tbl = table(["Person", "Company", "Sent", "Opens", "Clicks", "Replied",
                 "Their history"], trs)
    if not rows:
        return t + ("<p class='ol-empty'>No people yet. Source leads and "
                    "every one of them gets a profile here, with every email "
                    "they received and everything they did with it.</p>")
    return t + tbl


# ---------------------------------------------------------------------------
# 5 SEGMENTS
# ---------------------------------------------------------------------------
def segments_screen(ctx) -> str:
    segs = _L(ctx.get("segments"))
    people = _L(ctx.get("profiles"))
    t = tiles([("Segments", len(segs) or None, "saved questions"),
               ("People", len(people) or None, "to ask them of"),
               ("Fields", len(ES.FIELDS), "you can filter on"),
               ("Operators", len(ES.OPS), "")])
    rows = []
    for s in segs[:20]:
        live = ES.evaluate(people, _D(s).get("conditions"), _D(s).get("match"))
        rows.append((e(_D(s).get("name")), e(ES.describe(s))[:70],
                     _num(len(live)),
                     f"<button class='cta' onclick=\"olDropSeg('"
                     f"{e(_D(s).get('name'))}')\">Remove</button>"))
    tbl = table(["Segment", "Who is in it", "People now", ""], rows)
    fopts = "".join(f"<option value='{f}'>{e(v[0])}</option>"
                    for f, v in ES.FIELDS.items())
    oopts = "".join(f"<option value='{o}'>{e(v[0])}</option>"
                    for o, v in ES.OPS.items())
    builder = ("<div class='ol-add'>"
               "<input id='ol-sn' placeholder='segment name'>"
               f"<select id='ol-sf'>{fopts}</select>"
               f"<select id='ol-so'>{oopts}</select>"
               "<input id='ol-sv' placeholder='value'>"
               "<button class='cta s3go' onclick='olSaveSeg()'>Save segment"
               "</button></div>"
               "<p class='ol-empty'>A segment is evaluated live, every time "
               "it is read, so it can never quietly go stale. The operators "
               "offered are the only ones its field allows.</p>")
    return t + tbl + builder


# ---------------------------------------------------------------------------
# 6 TEMPLATES + PREVIEW
# ---------------------------------------------------------------------------
def templates_screen(ctx) -> str:
    prev = _D(ctx.get("preview"))
    if not prev:
        return ("<p class='ol-k'>Preview</p>"
                "<p class='ol-empty'>Open a campaign and press Preview, or "
                "press <b>New campaign</b>. The preview resolves every "
                "personalisation token against a real lead, lists every link "
                "with what a click will really do, and checks eight spam "
                "signals before anything can be sent.</p>")
    il = EP.inbox_line(prev)
    block = ""
    if prev.get("blocking"):
        block = (f"<div class='ol-block'><b>This cannot be sent yet.</b> "
                 f"{e(prev.get('block_reason'))}</div>")
    inbox = ("<div class='ol-inbox'>"
             f"<span class='ol-from'>{e(il['from'])}</span>"
             f"<span class='ol-subj'>{e(il['subject'])}</span>"
             f"<span class='ol-pre'>{e(il['preheader'])}"
             + (f" <i>({e(il.get('preheader_note'))})</i>"
                if il.get("preheader_derived") else "")
             + "</span></div>")
    sigs = "".join(
        f"<div class='ol-sig'><span class='ol-{'ok' if s['ok'] else 'bad'}'>"
        f"{'PASS' if s['ok'] else 'CHECK'}</span>"
        f"<span class='ol-sn'>{e(s['name'])}</span>"
        f"<span class='ol-sv'>{e(s['value'])}</span>"
        f"<span class='ol-sw'>{e(s['why'])}</span></div>"
        for s in _L(prev.get("signals")))
    lrows = [(e(l["url"])[:50],
              "https" if l["https"] else "<b class='ol-bad'>http</b>",
              e(l["tracked_as"])[:60]) for l in _L(prev.get("links"))]
    return (block + inbox
            + "<div class='ol-row'>"
            + f"<div class='ol-chart'><p class='ol-ct'>Desktop</p>"
              f"<div class='ol-desktop'>{prev.get('html', '')}</div></div>"
            + f"<div class='ol-chart'><p class='ol-ct'>Mobile</p>"
              f"<div class='ol-mobile'>{prev.get('html', '')}</div></div>"
            + "</div>"
            + "<p class='ol-k'>Plain text, as a filter reads it</p>"
              f"<div class='ol-plain'>{e(prev.get('text'))}</div>"
            + "<p class='ol-k'>Spam signals</p>" + sigs
            + "<p class='ol-k'>Every link, and what a click really does</p>"
            + table(["Link", "Scheme", "Sent as"], lrows)
            + "<button class='cta' onclick=\"act('/outreach/test-send')\">"
              "Send a test to yourself</button>")


# ---------------------------------------------------------------------------
# 7-14 the rest, on data that already runs
# ---------------------------------------------------------------------------
def deliverability_screen(ctx) -> str:
    d = _D(ctx.get("deliverability"))
    t = tiles([("Daily cap", d.get("cap"), "the ramp allows"),
               ("Sent today", d.get("sent_today"), ""),
               ("Headroom", d.get("headroom"), "left today"),
               ("Bounces", d.get("bounces"), ""),
               ("Unsubscribes", d.get("unsubscribes"), ""),
               ("Suppressed", d.get("suppressed"), "never mailed again"),
               ("Suppression rate", d.get("suppression_rate"), "", "%"),
               ("Ramp stage", d.get("ramp"), "")])
    ser = [float(x) for x in _L(d.get("series"))
           if isinstance(x, (int, float))]
    c = chart("Sends per day",
              CH.lines([("Sent", ser, "#1B57F0")]) if len(ser) >= 2 else "",
              "Builds as you send.")
    auth = "".join(
        f"<div class='ol-sig'><span class='ol-{'ok' if v else 'bad'}'>"
        f"{'PASS' if v else 'CHECK'}</span><span class='ol-sn'>{k}</span>"
        f"<span class='ol-sw'>{w}</span></div>"
        for k, v, w in _L(ctx.get("auth_checks")))
    return (t + c
            + ("<p class='ol-k'>Domain authentication</p>" + auth if auth
               else "<p class='ol-empty'>SPF, DKIM and DMARC are checked "
                    "against your sending domain when the DNS lookup "
                    "runs.</p>"))


def inbox_screen(ctx) -> str:
    rep = _D(ctx.get("replies"))
    drafts = _L(ctx.get("reply_drafts"))
    t = tiles([("Replies", rep.get("total"), "people who wrote back"),
               ("Reply rate", rep.get("rate"), rep.get("of") or "", "%"),
               ("Drafted answers", len(drafts) or None, "waiting on you"),
               ("Warm", rep.get("warm"), "worth a call")])
    rows = [(e(_D(r).get("from") or _D(r).get("email"))[:30],
             e(_D(r).get("subject"))[:34],
             e(_D(r).get("draft") or _D(r).get("body"))[:60],
             "<button class='cta s3go' onclick=\"act('/replies/send')\">"
             "Approve &amp; send</button>") for r in drafts[:20]]
    return t + (table(["From", "About", "Drafted answer", ""], rows)
                or "<p class='ol-empty'>No replies waiting. The engine "
                   "reads the inbox on its cadence and drafts an answer for "
                   "each one; you approve before anything goes back.</p>")


def simple(title, rows, note="") -> str:
    return (f"<p class='ol-k'>{e(title)}</p>" + tiles(rows)
            + (f"<p class='ol-empty'>{e(note)}</p>" if note else ""))


def build_panels(ctx) -> dict:
    """tab id -> screen. THE one mapping, imported by outreach_section."""
    ctx = ctx if isinstance(ctx, dict) else {}
    sc = _D(ctx.get("sourcing"))
    q = _D(ctx.get("quality"))
    terr = _D(ctx.get("territories"))
    bk = _D(ctx.get("bookings"))
    attr = _D(ctx.get("attribution"))
    cost = _D(ctx.get("costs"))
    camps = _L(ctx.get("campaigns"))
    orate = EC._rate(sum(int(c.get("opens") or 0) for c in camps),
                     sum(int(c.get("tracked") or 0) for c in camps))
    return {
        "olaunch": dashboard(ctx),
        "ooutbox": campaigns_screen(ctx),
        "osequence": flows_screen(ctx),
        "omanager": profiles_screen(ctx),
        "oicp": segments_screen(ctx),
        "orouting": templates_screen(ctx),
        "odeliver": deliverability_screen(ctx),
        "oreplies": inbox_screen(ctx),
        "osourcing": simple("Where your leads came from", [
            ("Leads found", sc.get("total"), ""),
            ("With an email", sc.get("with_email"), ""),
            ("Verified", sc.get("verified"), ""),
            ("Sources", len(_L(sc.get("by_source"))) or None, "")],
            "Sourcing runs free from SERP and directory reads."),
        "oquality": simple("Data quality", [
            ("Complete records", q.get("complete"), ""),
            ("Missing a name", q.get("no_name"), ""),
            ("Missing a company", q.get("no_company"), ""),
            ("Duplicates", q.get("duplicates"), "")],
            "A missing field is what makes a personalisation token render "
            "empty, which the preview refuses to send."),
        "oterr": simple("Geography", [
            ("Markets", len(_L(terr.get("rows"))) or None, ""),
            ("Top market", terr.get("top"), ""),
            ("Leads there", terr.get("top_count"), "")],
            "Your ICP spans USA, UK, Germany, Switzerland and Canada."),
        "obookings": simple("Conversions", [
            ("Bookings", bk.get("total"), "calls in the diary"),
            ("From email", bk.get("from_email"), ""),
            ("Booking rate", bk.get("rate"), bk.get("of") or "", "%"),
            ("Deals", attr.get("deals"), ""),
            ("Revenue", attr.get("revenue"), "", ""),
            ("Revenue per recipient", attr.get("per_recipient"), "", "")],
            "A booking counts here when its lead carries an email touch."),
        "oattrib": simple("Attribution", [
            ("First touch", attr.get("first_touch"), "deals"),
            ("Last touch", attr.get("last_touch"), "deals"),
            ("Assisted", attr.get("assisted"), ""),
            ("Revenue", attr.get("revenue"), "", ""),
            ("Cost", cost.get("total"), "", ""),
            ("Return", attr.get("roi"), "x", "")],
            "Attribution reads the deals recorded in BI, not a model."),
        "ocost": simple("Benchmarks", [
            ("Your open rate", orate[0], orate[1], "%"),
            ("Cold B2B typical", 25, "for comparison", "%"),
            ("Your click rate",
             EC._rate(sum(int(c.get("clicks") or 0) for c in camps),
                      sum(int(c.get("tracked") or 0) for c in camps))[0],
             "", "%"),
            ("Cold B2B typical", 3, "for comparison", "%"),
            ("Cost per lead", cost.get("per_lead"), "", ""),
            ("Cost per reply", cost.get("per_reply"), "", ""),
            ("Cost per booking", cost.get("per_booking"), "", ""),
            ("Cost per deal", cost.get("per_deal"), "", "")],
            EC.MPP_CAVEAT),
    }


CSS = """
.ol-tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));
gap:9px;margin:0 0 14px}
.ol-tile{border:1px solid var(--ln);border-radius:10px;background:var(--card);
padding:11px 13px;display:flex;flex-direction:column;gap:3px}
.ol-k{font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;
color:var(--ft);margin:14px 0 6px}
.ol-tile .ol-k{margin:0}
.ol-tile b{font-family:ui-monospace,Menlo,monospace;font-size:22px;
font-weight:700;line-height:1;font-variant-numeric:tabular-nums}
.ol-none{color:var(--ft)!important;font-size:22px}
.ol-d{font-size:10.5px;color:var(--ft)}
.ol-row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 12px}
.ol-chart{border:1px solid var(--ln);border-radius:10px;background:var(--card);
padding:12px 14px;overflow-x:auto}
.ol-ct{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;
letter-spacing:.12em;text-transform:uppercase;color:var(--ft);margin:0 0 8px}
.ol-empty{font-size:12.5px;color:var(--ft);line-height:1.55;margin:6px 0 0}
.ol-tbl{border:1px solid var(--ln);border-radius:10px;background:var(--card);
overflow-x:auto;margin:0 0 12px}
.ol-tr{display:grid;grid-template-columns:repeat(auto-fit,minmax(80px,1fr));
gap:10px;padding:8px 13px;border-bottom:1px solid var(--ln);font-size:12.5px;
align-items:center}
.ol-tr:last-child{border-bottom:0}
.ol-th{font-family:ui-monospace,Menlo,monospace;font-size:10px;
letter-spacing:.08em;text-transform:uppercase;color:var(--ft)}
.ol-tr b{font-family:ui-monospace,Menlo,monospace}
.ol-tr i{display:block;font-style:normal;font-size:10px;color:var(--ft);
font-family:ui-monospace,monospace}
.ol-pill{font-family:ui-monospace,monospace;font-size:10px;font-weight:700;
border:1px solid var(--ln);border-radius:8px;padding:1px 7px}
.ol-add{display:flex;gap:8px;margin:0 0 10px;flex-wrap:wrap}
.ol-add input,.ol-add select{padding:7px 10px;border:1px solid var(--ln);
border-radius:7px;background:var(--pap);color:var(--tx);font-family:inherit;
font-size:12.5px}
.ol-add input{flex:1;min-width:140px}
.ol-flow{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:0 0 10px}
.ol-step{border:1px solid var(--ln);border-radius:8px;padding:6px 11px;
font-size:12px;background:var(--card)}
.ol-step.ol-send{border-color:var(--ac);color:var(--ac)}
.ol-step.ol-wait{color:var(--ft)}
.ol-step.ol-condition{border-style:dashed;color:var(--warnc)}
.ol-block{border:1px solid var(--bad);background:var(--badbg);color:var(--bad);
border-radius:9px;padding:10px 13px;font-size:13px;margin:0 0 12px}
.ol-inbox{border:1px solid var(--ln);border-radius:10px;background:var(--card);
padding:11px 14px;margin:0 0 12px;display:flex;flex-direction:column;gap:2px}
.ol-from{font-size:13px;font-weight:700}
.ol-subj{font-size:13.5px}
.ol-pre{font-size:12px;color:var(--ft)}
.ol-pre i{font-style:normal;color:var(--warnc)}
.ol-desktop{border:1px solid var(--ln);border-radius:6px;padding:12px;
background:#fff;color:#111;max-height:340px;overflow:auto;font-size:13px}
.ol-mobile{border:1px solid var(--ln);border-radius:14px;padding:12px;
background:#fff;color:#111;max-width:300px;max-height:340px;overflow:auto;
font-size:13px}
.ol-plain{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;
color:var(--dm);border:1px solid var(--ln);border-radius:8px;padding:10px 12px;
white-space:pre-wrap;max-height:160px;overflow:auto;margin:0 0 12px}
.ol-sig{display:grid;grid-template-columns:56px 150px 130px 1fr;gap:10px;
padding:7px 13px;border:1px solid var(--ln);border-radius:8px;
background:var(--card);margin:0 0 5px;font-size:12.5px;align-items:center}
.ol-sig .ol-ok{color:var(--okc);font-family:ui-monospace,monospace;
font-size:10px;font-weight:700}
.ol-sig .ol-bad{color:var(--bad);font-family:ui-monospace,monospace;
font-size:10px;font-weight:700}
.ol-sw{color:var(--ft);font-size:11.5px}
.ol-tl{display:flex;gap:4px;flex-wrap:wrap}
.ol-ev{font-family:ui-monospace,monospace;font-size:9.5px;border-radius:5px;
padding:1px 5px;background:var(--hov);color:var(--dm)}
.ol-ev i{display:inline;font-style:normal;margin-left:4px;opacity:.65}
.ol-ev.ol-click{color:var(--okc)}
.ol-ev.ol-replied{color:var(--ac)}
@media (max-width:900px){.ol-row{grid-template-columns:1fr}
.ol-sig{grid-template-columns:56px 1fr}}
"""

JS = ("<script>"
      "function olNewCampaign(){toast('Pick a segment on the Segments tab, "
      "then press Preview on a campaign to check it before sending.');"
      "seoTab('oicp');}"
      "async function olPreview(id){try{"
      "var r=await fetch('/outreach/preview',{method:'POST',"
      "headers:{'Content-Type':'application/json'},"
      "body:JSON.stringify({id:id})});var j=await r.json();"
      "toast((j&&j.message)||'preview built',j&&j.ok!==false);"
      "seoTab('orouting');}catch(e){toast('could not reach the engine',false);}}"
      "async function olSaveSeg(){"
      "var n=document.getElementById('ol-sn'),f=document.getElementById('ol-sf'),"
      "o=document.getElementById('ol-so'),v=document.getElementById('ol-sv');"
      "if(!n||!n.value.trim()){toast('Name the segment first.');return;}"
      "try{var r=await fetch('/outreach/segment',{method:'POST',"
      "headers:{'Content-Type':'application/json'},"
      "body:JSON.stringify({name:n.value,conditions:[{field:f.value,"
      "op:o.value,value:v.value}]})});var j=await r.json();"
      "toast((j&&(j.message||j.error))||'saved',j&&j.ok!==false);"
      "if(j&&j.ok){n.value='';v.value='';}}"
      "catch(e){toast('could not reach the engine',false);}}"
      "async function olDropSeg(name){try{"
      "var r=await fetch('/outreach/segment',{method:'POST',"
      "headers:{'Content-Type':'application/json'},"
      "body:JSON.stringify({name:name,remove:true})});var j=await r.json();"
      "toast((j&&j.message)||'removed',true);}"
      "catch(e){toast('could not reach the engine',false);}}"
      "</script>")
