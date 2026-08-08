"""
content_engine_os_screens.py
============================================================================
THE INTERFACE. Twenty-two screens behind one grouped rail.

THE INFORMATION ARCHITECTURE IS THE FOUNDER'S, NOT A COPY OF ANYONE'S
  Overview, Acquisition, Audience, Engagement, Automation, Analytics,
  Settings. The interaction patterns of a modern marketing tool (a rail of
  grouped destinations, a table that opens a detail, a wizard that reviews
  before it commits) are reproduced. The visual design, the words and the
  components are this engine's own.

ONE NAVIGATION GRAMMAR
  A rail, and a panel. Nothing else. The section this replaces carried a
  group rail, a run bar and a tab strip stacked on each other, which is
  three different ways of saying "go here" on one page and the reason the
  founder scored it zero. There is exactly one now.

THE CAMPAIGN DETAIL IS THE POINT OF THE WHOLE THING
  Left: the rendered email at the width it will be read, for a chosen
  recipient, with an Edit that writes to the same store the sender reads.
  Right: the funnel with denominators, the open curve, the links, and the
  recipient table. What you preview is what sends.

IDS ARE SCOPED "os-" because the old dashboard renders every section at
once and an unscoped id collides silently.
============================================================================
"""

from __future__ import annotations

import html as _html
import re

import content_engine_os_analytics as AN
import content_engine_os_audience as AUD
import content_engine_os_core as CORE
import content_engine_os_editors as ED
import content_engine_os_flows as FLOWS
import content_engine_os_schedule as SCHED
from content_engine_os_core import _D, _L

#: The rail. (group, [(id, label)]). One definition; the panels are built
#: from it, so a screen cannot exist without a way to reach it.
NAV = [
    ("", [("overview", "Overview")]),
    ("Acquisition", [("acqleads", "Leads"), ("acqcompanies", "Companies"),
                     ("acqsources", "Sources"), ("acqenrich", "Enrichment")]),
    ("Audience", [("audprofiles", "Profiles"), ("audlists", "Lists"),
                  ("audsegments", "Segments")]),
    ("Engagement", [("engcampaigns", "Campaigns"), ("engflows", "Flows"),
                    ("engtemplates", "Templates"), ("enginbox", "Inbox")]),
    ("Sending", [("sendqueue", "Queue"), ("senddeliver", "Deliverability"),
                 ("sendrules", "Send rules")]),
    ("Automation", [("autoagents", "Agents"), ("autoruns", "Agent runs")]),
    ("Analytics", [("ancampaign", "Campaign analytics"),
                   ("anlead", "Lead analytics"), ("anab", "A/B tests"),
                   ("anattrib", "Attribution")]),
    ("Data", [("dataexport", "Export"), ("dataimport", "Import"),
              ("datadrive", "Google Drive")]),
    ("Settings", [("setemail", "Email"), ("setdomains", "Domains"),
                  ("setintegrations", "Integrations"),
                  ("setcompliance", "Compliance"), ("setteam", "Team"),
                  ("setstorage", "Storage")]),
]

STATE_TONE = {"DRAFT": "mut", "REVIEW": "warn", "SCHEDULED": "warn",
              "QUEUED": "warn", "SENDING": "ok", "SENT": "ok",
              "COMPLETED": "ok", "CANCELLED": "mut", "FAILED": "bad",
              "BOUNCED": "bad", "SUPPRESSED": "bad", "PROCESSING": "warn",
              "DELIVERED": "ok", "LIVE": "ok", "PAUSED": "mut",
              "VERIFIED": "ok", "PENDING": "mut", "VERIFYING": "warn"}


def e(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


def num(v, suffix="") -> str:
    """A measurement, or an honest dash. Never a zero standing in for an
    absence: zero bounces and no bounce reporting are different facts."""
    if v is None or v == "":
        return "<b class='os-none'>&mdash;</b>".replace("&mdash;", "--")
    try:
        f = float(v)
        s = (f"{f/1000:.1f}k" if abs(f) >= 1000
             else (f"{f:,.0f}" if f == int(f) else f"{f:,.1f}"))
    except Exception:
        s = str(v)
    return f"<b>{e(s)}{e(suffix)}</b>"


def pair(v) -> list:
    """A rate arrives as (percent, "N of D"). It is a TUPLE, and _L only
    accepts lists, so unpacking it through _L silently produced an empty
    list and an IndexError on the screen. One helper, used everywhere."""
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        return [v[0], v[1]]
    return [None, ""]


def pill(text, tone="mut") -> str:
    return f"<span class='os-pill os-{e(tone)}'>{e(text)}</span>"


def state_pill(s) -> str:
    return pill(str(s or "").title(), STATE_TONE.get(str(s or "").upper(), "mut"))


def tile(label, value, sub="", suffix="") -> str:
    return ("<div class='os-tile'><span class='os-k'>" + e(label) + "</span>"
            + num(value, suffix)
            + (f"<span class='os-d'>{e(sub)}</span>" if sub else "")
            + "</div>")


def tiles(rows) -> str:
    return "<div class='os-tiles'>" + "".join(tile(*r) for r in rows) + "</div>"


def rate_tile(label, pct_and_of, sub="") -> str:
    """A rate with its denominator, always. (pct, "N of D")."""
    pct, of = pair(pct_and_of)
    return tile(label, pct, sub or of, "%")


_NUMCELL = re.compile(r"^<b(?: class='os-none')?>(?:[\d,.\-]|--)")


def _numeric(rows, i) -> bool:
    """Is column i a measurement?

    num() is the only thing in this file that emits "<b>" followed by a
    digit or a dash, so the test is exact rather than a guess. A person's
    name is also bold, which is why the digit matters: without it the
    Profiles screen would right-align everybody's name."""
    seen = False
    for r in rows:
        if i >= len(r):
            continue
        cell = str(r[i] or "").strip()
        if not cell:
            continue
        if not _NUMCELL.match(cell):
            return False
        seen = True
    return seen


def table(headers, rows, empty="Nothing here yet.", *, dataset="") -> str:
    """ONE table element, not a stack of grids.

    Every row used to be its own CSS grid, which meant every row sized its
    own columns independently and nothing lined up with the row above it.
    A real table shares one set of column widths by construction, which is
    the entire reason the element exists.

    Numeric columns are found and right-aligned with tabular figures, so
    30 sits under 750 rather than beside it."""
    if not rows:
        return f"<p class='os-empty'>{e(empty)}</p>"
    num_cols = {i for i in range(len(headers)) if _numeric(rows, i)}

    def cls(i):
        return " class='os-r'" if i in num_cols else ""

    head = "".join(f"<th{cls(i)}>{h}</th>" for i, h in enumerate(headers))
    body = "".join(
        "<tr>" + "".join(f"<td{cls(i)}>{c}</td>" for i, c in enumerate(r))
        + "</tr>" for r in rows)
    dl = (f"<div class='os-dl'>{download_menu(dataset)}</div>"
          if dataset else "")
    return (dl + "<div class='os-tbl'><table><thead><tr>" + head
            + "</tr></thead><tbody>" + body + "</tbody></table></div>")


def download_menu(dataset) -> str:
    """Every table you can read, you can take away."""
    if not dataset:
        return ""
    return ("<span class='os-d'>Download</span>"
            + "".join(f"<a class='os-mini' href='/os/export/{e(dataset)}."
                      f"{f}' download>{f.upper()}</a>"
                      for f in ("csv", "xlsx", "json")))


def panel(title, note, body) -> str:
    return ("<div class='os-head'><h3>" + e(title) + "</h3>"
            + (f"<p>{e(note)}</p>" if note else "") + "</div>" + body)


def section(title, body) -> str:
    return f"<div class='os-sec'><p class='os-st'>{e(title)}</p>{body}</div>"


# ---------------------------------------------------------------------------
# Small charts, written here so the screens carry no chart dependency
# ---------------------------------------------------------------------------
def bars(rows, key="value", label="label", height=120) -> str:
    rows = [r for r in _L(rows)]
    if not rows:
        return "<p class='os-empty'>Nothing measured yet.</p>"
    top = max([float(_D(r).get(key) or 0) for r in rows] + [1])
    # A bar 200px wide because there are only three days is a chart that
    # lies about how much data it has. Cap the width; do not stretch.
    w = max(6, min(48, int(560 / max(1, len(rows))) - 4))
    out = []
    for i, r in enumerate(rows):
        v = float(_D(r).get(key) or 0)
        h = max(1, int((v / top) * (height - 22)))
        x = i * (w + 4)
        out.append(f"<rect x='{x}' y='{height - 18 - h}' width='{w}' "
                   f"height='{h}' rx='2' class='os-bar'><title>"
                   f"{e(_D(r).get(label))}: {e(v)}</title></rect>")
        if len(rows) <= 16:
            raw = str(_D(r).get(label) or "")
            # An ISO day truncated from the front reads "2026-0" on every
            # bar, which is the same six characters repeated. Show the part
            # that differs.
            txt = raw[5:] if re.match(r"^\d{4}-\d{2}-\d{2}$", raw) else raw[:7]
            out.append(f"<text x='{x + w/2}' y='{height - 5}' class='os-bl' "
                       f"text-anchor='middle'>{e(txt)}</text>")
    return (f"<svg viewBox='0 0 {len(rows)*(w+4)} {height}' class='os-svg' "
            f"preserveAspectRatio='none'>" + "".join(out) + "</svg>")


def funnel(stages) -> str:
    """stages: [(label, n, "n of d")]. The width is the share of the first
    stage, so the drop is a shape rather than a column of numbers."""
    stages = [s for s in _L(stages)]
    top = max([float(s[1] or 0) for s in stages] + [1])
    out = []
    for label, n, of in stages:
        pct = (float(n or 0) / top) * 100
        out.append(
            "<div class='os-fn'><span class='os-fl'>" + e(label) + "</span>"
            f"<span class='os-fbar'><i style='width:{pct:.1f}%'></i></span>"
            + num(n) + f"<span class='os-d'>{e(of)}</span></div>")
    return "<div class='os-funnel'>" + "".join(out) + "</div>"


def donut(parts, size=120) -> str:
    parts = [(k, float(v or 0)) for k, v in _L(parts) if float(v or 0) > 0]
    total = sum(v for _, v in parts)
    if not total:
        return "<p class='os-empty'>Nothing measured yet.</p>"
    r, c = size / 2 - 12, size / 2
    circ = 2 * 3.14159 * r
    off, segs, key = 0.0, [], []
    for i, (k, v) in enumerate(parts[:6]):
        frac = v / total
        segs.append(f"<circle cx='{c}' cy='{c}' r='{r}' fill='none' "
                    f"stroke-width='14' class='os-seg os-seg{i}' "
                    f"stroke-dasharray='{circ*frac:.2f} {circ:.2f}' "
                    f"stroke-dashoffset='{-off:.2f}'></circle>")
        key.append(f"<span class='os-key'><i class='os-seg{i}'></i>"
                   f"{e(k)} {int(v)}</span>")
        off += circ * frac
    return (f"<div class='os-donut'><svg viewBox='0 0 {size} {size}' "
            f"width='{size}' height='{size}'>" + "".join(segs) + "</svg>"
            + "<div class='os-keys'>" + "".join(key) + "</div></div>")


# ---------------------------------------------------------------------------
# THE BAND
# ---------------------------------------------------------------------------
def band(ctx) -> str:
    s = _D(ctx.get("summary"))
    q = _D(ctx.get("queue_counts"))
    sender = ctx.get("sender_why") or ""
    return (
        "<div class='os-band'><div class='os-bwho'>"
        "<p class='os-bk'>Email and lead engagement</p>"
        f"<p class='os-bstate'><b>{e(s.get('profiles') or 0)} people</b>"
        f" &middot; {e(s.get('campaigns') or 0)} campaigns"
        f" &middot; {e(s.get('sent') or 0)} emails sent"
        f" &middot; <b>{e(q.get('QUEUED') or 0)} waiting for your approval</b>"
        "</p>"
        f"<p class='os-bsub'>{e(sender)}. Agents research, qualify, write and "
        "queue. Nothing reaches a mail provider until you approve it, and "
        "every recipient refused by a gate is listed with the reason.</p>"
        "</div><div class='os-bcmds'>"
        "<button class='cta os-go' onclick=\"osNav('engcampaigns')\">"
        "Campaigns</button>"
        "<button class='cta' onclick=\"osAct('/os/sync')\">Re-read the "
        "engine</button>"
        "<button class='cta' onclick=\"osNav('sendqueue')\">Queue</button>"
        "</div></div>")


# ---------------------------------------------------------------------------
# 1 OVERVIEW
# ---------------------------------------------------------------------------
def overview(ctx) -> str:
    s = _D(ctx.get("summary"))
    acq = _D(ctx.get("acquisition"))
    t = _D(ctx.get("totals"))
    stages = _D(s.get("stages"))
    body = (
        section("Acquisition", tiles([
            ("New leads", acq.get("leads"), "people the agents found"),
            ("Qualified", s.get("qualified"), "past the first stage"),
            ("Agent qualified", acq.get("ai_qualified"), "carry a score"),
            ("Email ready", s.get("emailable"), "valid, not suppressed"),
            ("Companies", acq.get("companies"), ""),
            ("Average score", acq.get("avg_score"), "out of 100")])),
        section("Engagement", tiles([
            ("Emails sent", t.get("sent"), ""),
            ("Delivered", t.get("delivered"), "reported by the provider"),
            ("Opened", t.get("unique_opens"), "unique people"),
            ("Clicked", t.get("unique_clicks"), "unique people"),
            ("Unsubscribed", t.get("unsubscribes"), ""),
            ("Complaints", t.get("complaints"), "")])
            + "<p class='os-note'>" + e(AN.MPP_CAVEAT) + "</p>"),
        section("Pipeline", funnel([
            ("Contacted", stages.get("CONTACTED", 0), ""),
            ("Engaged", stages.get("ENGAGED", 0), "opened or clicked"),
            ("Interested", stages.get("INTERESTED", 0), ""),
            ("Meeting", stages.get("MEETING", 0), ""),
            ("Opportunity", stages.get("OPPORTUNITY", 0), ""),
            ("Customer", stages.get("CUSTOMER", 0), "")])),
        section("What the agents did", tiles([
            ("Runs", s.get("runs"), "recorded"),
            ("Actions", s.get("actions"), "each one audited"),
            ("Profiles written", s.get("profiles"), ""),
            ("Messages resolved", s.get("messages"), "")])),
        section("Sending, last 30 days",
                bars(_L(ctx.get("by_day")), key="sent", label="day")),
    )
    return panel("Overview",
                 "The questions a founder asks, in the order he asks them: "
                 "who did we find, what did we send, what came back.",
                 "".join(body))


# ---------------------------------------------------------------------------
# 2 ACQUISITION
# ---------------------------------------------------------------------------
def acq_leads(ctx) -> str:
    rows = _L(ctx.get("profiles"))[:200]
    body = table(
        ["Person", "Company", "Stage", "Score", "Sent", "Opens", "Clicks", ""],
        [[f"<b>{e(r.get('name'))}</b><br><span class='os-d'>"
          f"{e(r.get('email'))}</span>",
          e(r.get("company") or ""),
          state_pill(r.get("lead_stage") or "NEW"),
          num(r.get("lead_score")), num(r.get("emails_sent")),
          num(r.get("opens")), num(r.get("clicks")),
          f"<button class='os-mini' onclick=\"osProfile('{e(r.get('id'))}')\">"
          f"Open</button>"] for r in rows],
        "No leads yet. The sourcing agent writes them here as it finds them.")
    return panel("Leads",
                 "A lead is the opportunity. The person is a profile, and one "
                 "company can produce several leads over time, which is why "
                 "they are separate records rather than columns on each other.",
                 tiles([("Leads", _D(ctx.get("acquisition")).get("leads"), ""),
                        ("Shown", len(rows), "most engaged first")]) + body)


def acq_companies(ctx) -> str:
    rows = _L(ctx.get("companies"))[:200]
    return panel("Companies",
                 "One row per organisation, with the people attached to it.",
                 table(["Company", "Website", "Country", "People"],
                       [[f"<b>{e(c.get('name'))}</b>", e(c.get("website") or ""),
                         e(c.get("country") or ""), num(c.get("people"))]
                        for c in rows],
                       "No companies recorded yet."))


def acq_sources(ctx) -> str:
    acq = _D(ctx.get("acquisition"))
    src = _L(acq.get("by_source"))
    serper = _D(ctx.get("connectors")).get("serper")
    finder = (
        "<div class='os-form'>"
        "<input id='os-mv' class='os-in' placeholder='Business type, for "
        "example tax consultants, dentists, law firms'>"
        "<input id='os-mc' class='os-in' placeholder='City, for example "
        "Zurich, Munich, Manchester'>"
        "<select id='os-mn' class='os-in'>"
        "<option value='10'>10 leads</option>"
        "<option value='20' selected>20 leads</option>"
        "<option value='30'>30 leads</option>"
        "<option value='40'>40 leads</option></select>"
        "<button class='cta' onclick='osFindLeads()'"
        + ("" if serper else " disabled") + ">Find leads</button></div>"
        + ("" if serper else
           "<p class='os-warn'>Serper is not connected, so nothing can be "
           "sourced. Save SERPER_API_KEY on the System Map first.</p>")
        + "<p class='os-note'>This reads real local businesses (name, phone, "
          "website, rating), finds a verified address for each, and writes "
          "them in as profiles and leads. Nothing is emailed by this button: "
          "they enter the normal path of qualify, write, preview, your "
          "approval, then a capped send.</p>")
    return panel("Sources",
                 "Where every person in this workspace came from, and where "
                 "to find more.",
                 section("Find local businesses", finder)
                 + section("Where they came from",
                           donut([(k, v) for k, v in src])
                           + table(["Source", "People"],
                                   [[e(k), num(v)] for k, v in src],
                                   "Nothing has been sourced yet.")))


def acq_enrich(ctx) -> str:
    acq = _D(ctx.get("acquisition"))
    gaps = _D(ctx.get("field_gaps"))
    return panel(
        "Enrichment",
        "A missing field is not cosmetic: it is what makes a personalisation "
        "token render empty, and the preview refuses to send that.",
        tiles([("Enriched", pair(acq.get("enrichment"))[0],
                pair(acq.get("enrichment"))[1], "%"),
               ("Agent qualified", acq.get("ai_qualified"), "carry a score"),
               ("Average score", acq.get("avg_score"), "")])
        + table(["Field", "Missing", "Why it matters"],
                [[e(k), num(v.get("missing")), e(v.get("why"))]
                 for k, v in gaps.items()],
                "Nothing to report yet."))


# ---------------------------------------------------------------------------
# 3 AUDIENCE
# ---------------------------------------------------------------------------
def profile_table(rows) -> str:
    """The rows alone, so a search can replace them without redrawing the
    whole screen."""
    return table(["Person", "Company", "Country", "Consent", "Sent", "Opens",
               "Clicks", "Last activity", ""],
              [[f"<b>{e(r.get('name'))}</b><br><span class='os-d'>"
                f"{e(r.get('email'))}</span>",
                e(r.get("company") or ""), e(r.get("country") or ""),
                state_pill(r.get("consent")), num(r.get("emails_sent")),
                num(r.get("opens")), num(r.get("clicks")),
                e(str(r.get("last_activity_at") or "")[:10]),
                f"<button class='os-mini' onclick=\"osProfile"
                f"('{e(r.get('id'))}')\">Open</button>"] for r in rows],
              "Nobody matches.", dataset="profiles")


def aud_profiles(ctx) -> str:
    rows = _L(ctx.get("profiles"))
    total = _D(ctx.get("summary")).get("profiles") or len(rows)
    return panel(
        "Profiles",
        "The person. Click one to see everything that has happened to them, "
        "in order, including the exact emails they were sent.",
        "<div class='os-form'>"
        "<input id='os-psearch' class='os-in' placeholder='Search name, "
        "email, company, country or industry' "
        "onkeydown='if(event.key===\'Enter\')osSearch()'>"
        "<button class='cta' onclick='osSearch()'>Search</button>"
        "<button class='os-mini' onclick='osSearchClear()'>Clear</button>"
        f"<span class='os-note'>{e(total)} people. The list below shows the "
        "most engaged 250; search looks at all of them.</span></div>"
        + f"<div id='os-plist'>{profile_table(rows[:250])}</div>")


def aud_lists(ctx) -> str:
    rows = _L(ctx.get("lists"))
    form = ("<div class='os-form'><input id='os-ln' class='os-in' "
            "placeholder='List name, for example German clinics'>"
            "<input id='os-ld' class='os-in' placeholder='What is it for?'>"
            "<button class='cta' onclick='osSaveList()'>Create list</button>"
            "</div>")
    return panel(
        "Lists",
        "A list is static: people are in it because somebody put them there. "
        "It goes stale quietly, which is why most audiences should be a "
        "segment instead.",
        form + table(["List", "What it is for", "People", "Created"],
                     [[f"<b>{e(l.get('name'))}</b>", e(l.get("description")),
                       num(l.get("members")), e(str(l.get("created_at"))[:10])]
                      for l in rows], "No lists yet."))


def aud_segments(ctx) -> str:
    rows = _L(ctx.get("segments"))
    fields = "".join(f"<option value='{e(k)}'>{e(_D(v).get('label'))}</option>"
                     for k, v in AUD.FIELDS.items())
    ops = "".join(f"<option value='{e(o)}'>{e(AUD.OP_WORDS.get(o, o))}</option>"
                  for o in AUD.SEGMENT_OPS)
    builder = (
        "<div class='os-builder'>"
        "<input id='os-sn' class='os-in' placeholder='Segment name'>"
        "<div class='os-cond'><span class='os-cw'>People where</span>"
        f"<select id='os-sf' class='os-in'>{fields}</select>"
        f"<select id='os-so' class='os-in'>{ops}</select>"
        "<input id='os-sv' class='os-in' placeholder='value'></div>"
        "<div id='os-conds' class='os-conds'></div>"
        "<div class='os-brow'>"
        "<select id='os-sm' class='os-in'><option value='AND'>match ALL "
        "conditions</option><option value='OR'>match ANY condition</option>"
        "</select>"
        "<button class='os-mini' onclick='osAddCond()'>+ Add condition</button>"
        "<button class='os-mini' onclick='osAddGroup()'>+ Add a bracket"
        "</button>"
        "<button class='os-mini' onclick='osCountSeg()'>Count people</button>"
        "<button class='os-mini' onclick='osClearSeg()'>Start again</button>"
        "<button class='cta' onclick='osSaveSeg()'>Save segment</button></div>"
        "<p class='os-note' id='os-scount'>A segment is a question asked of "
        "every profile each time you look, so it can never go stale.</p></div>")
    return panel(
        "Segments",
        "Fourteen comparisons over twenty one fields, nested with AND and OR "
        "to any depth. Nothing here is hard coded, so you can ask a question "
        "nobody wrote code for.",
        builder + table(["Segment", "The rule, in words", "People now", ""],
                        [[f"<b>{e(s.get('name'))}</b>", e(s.get("described")),
                          num(s.get("size")),
                          f"<button class='os-mini' onclick=\"osEditSeg"
                          f"('{e(s.get('id'))}')\">Edit</button> "
                          f"<a class='os-mini' href='/os/export/profiles.csv"
                          f"?segment={e(s.get('id'))}' download>CSV</a> "
                          f"<button class='os-mini' onclick=\"osDropSeg"
                          f"('{e(s.get('id'))}')\">Remove</button>"]
                         for s in rows], "No segments yet.")
        + "<p class='os-note'>A bracket nests one group inside the rule, "
          "which covers \"in Germany AND (a good score OR a big company)\". "
          "The evaluator handles six levels; this builder writes two, which "
          "is every question anybody has actually asked of it.</p>")


# ---------------------------------------------------------------------------
# 4 ENGAGEMENT
# ---------------------------------------------------------------------------
def eng_campaigns(ctx) -> str:
    rows = _L(ctx.get("campaigns"))
    body = table(
        ["Subject", "State", "Recipients", "Sent", "Opens", "Clicks",
         "Open rate", "Edited", ""],
        [[f"<b>{e(c.get('subject') or c.get('name'))}</b>"
          + (f"<br><span class='os-d'>{e(c.get('name'))}</span>"
             if c.get("subject") else ""),
          state_pill(c.get("state")), num(c.get("recipients")),
          num(c.get("sent")), num(c.get("opens")), num(c.get("clicks")),
          num(pair(c.get("open_rate"))[0], "%")
          + f"<br><span class='os-d'>"
            f"{e(pair(c.get('open_rate'))[1])}</span>",
          num(c.get("edited") or None),
          f"<button class='os-mini os-primary' onclick=\"osCamp"
          f"('{e(c.get('id'))}')\">Open</button>"] for c in rows],
        "No campaigns yet. Press Re-read the engine, or create one below.",
        dataset="campaigns")
    wizard = (
        "<div class='os-form'>"
        "<input id='os-cn' class='os-in' placeholder='Campaign name'>"
        "<select id='os-ck' class='os-in'>"
        "<option value='all'>Everyone eligible</option>"
        "<option value='segment'>A segment</option>"
        "<option value='list'>A list</option></select>"
        "<select id='os-ca' class='os-in'>"
        + "".join(f"<option value='{e(s.get('id'))}'>{e(s.get('name'))}"
                  f"</option>" for s in _L(ctx.get("segments")) + _L(ctx.get("lists")))
        + "</select>"
        "<input id='os-cs' class='os-in' placeholder='Subject line'>"
        "<button class='cta' onclick='osSaveCamp()'>Create draft</button></div>")
    return panel(
        "Campaigns",
        "One row per campaign, and the row is the subject line, because that "
        "is what you wrote and what a recipient sees. Open one to read the "
        "real email, for a real person, before it goes anywhere.",
        tiles([("Campaigns", len(rows), ""),
               ("Sent", sum(int(c.get("sent") or 0) for c in rows), ""),
               ("Hand edited", sum(int(c.get("edited") or 0) for c in rows),
                "emails you corrected")])
        + body + section("New campaign", wizard))


def eng_flows(ctx) -> str:
    rows = _L(ctx.get("flows"))
    cards = []
    for f in rows:
        cards.append(
            "<div class='os-flow'><div class='os-fhead'>"
            f"<b>{e(f.get('name'))}</b>{state_pill(f.get('status'))}</div>"
            + (f"<p class='os-warn'>{e(f.get('invalid_reason'))}</p>"
               if not f.get("valid") else "")
            + tiles([("In the flow", f.get("in_flow"), "right now"),
                     ("Completed", f.get("completed"), ""),
                     ("Goal met", f.get("goal_met"), ""),
                     ("Steps", f.get("nodes"), f"{f.get('edges')} arrows")])
            + ED.flow_canvas(f, _L(ctx.get("campaigns")), _L(ctx.get("lists")))
            + "<div class='os-brow'>"
            + (f"<button class='cta' onclick=\"osAct('/os/flow/pause',"
               f"{{id:'{e(f.get('id'))}'}})\">Pause</button>"
               if f.get("status") == "LIVE" else
               f"<button class='cta' onclick=\"osAct('/os/flow/activate',"
               f"{{id:'{e(f.get('id'))}'}})\">Activate</button>")
            + f"<button class='os-mini' onclick=\"osAct('/os/flow/advance',"
              f"{{}})\">Move everyone forward</button>"
            + "</div></div>")
    return panel(
        "Flows",
        "A flow is a graph, not a list, because your sequence branches: what "
        "you send someone who opened is not what you send someone who did "
        "not. A live flow queues; it never sends.",
        "".join(cards) or "<p class='os-empty'>No flows yet.</p>")


def graph_svg(graph) -> str:
    """The flow as a picture. Read only here; the shape is the point, and a
    drag and drop canvas that lies about what the backend stored would be
    worse than a diagram that does not."""
    nodes = _L(_D(graph).get("nodes"))
    edges = _L(_D(graph).get("edges"))
    if not nodes:
        return ""
    xs = [int(_D(n).get("position_x") or 0) for n in nodes]
    ys = [int(_D(n).get("position_y") or 0) for n in nodes]
    ox, oy = min(xs) - 20, min(ys) - 20
    w, h = max(xs) - ox + 220, max(ys) - oy + 70
    pos = {_D(n).get("id"): (int(_D(n).get("position_x") or 0) - ox,
                             int(_D(n).get("position_y") or 0) - oy)
           for n in nodes}
    out = []
    for ed in edges:
        a = pos.get(_D(ed).get("source_node_id"))
        b = pos.get(_D(ed).get("target_node_id"))
        if not a or not b:
            continue
        out.append(f"<path d='M{a[0]+90},{a[1]+40} C{a[0]+90},{a[1]+70} "
                   f"{b[0]+90},{b[1]-30} {b[0]+90},{b[1]}' class='os-edge'/>")
        if _D(ed).get("condition"):
            out.append(f"<text x='{(a[0]+b[0])/2+96}' y='{(a[1]+b[1])/2+40}' "
                       f"class='os-bl'>{e(_D(ed).get('condition'))}</text>")
    for n in nodes:
        n = _D(n)
        x, y = pos.get(n.get("id"), (0, 0))
        t = str(n.get("type") or "")
        cfg = _D(n.get("config"))
        detail = (f"{cfg.get('hours')}h" if t == "WAIT" else
                  f"touch {cfg.get('touch') or 1}" if t == "SEND_EMAIL" else
                  str(cfg.get("field") or cfg.get("event")
                      or cfg.get("objective") or "")[:22])
        out.append(f"<rect x='{x}' y='{y}' width='180' height='40' rx='6' "
                   f"class='os-node os-n{t[:4].lower()}'/>"
                   f"<text x='{x+12}' y='{y+18}' class='os-nt'>"
                   f"{e(t.replace('_', ' ').title())}</text>"
                   f"<text x='{x+12}' y='{y+32}' class='os-nd'>{e(detail)}</text>")
    return (f"<div class='os-graph'><svg viewBox='0 0 {w} {h}' "
            f"style='min-width:{min(w, 760)}px'>" + "".join(out) + "</svg></div>")


def eng_templates(ctx) -> str:
    rows = _L(ctx.get("templates"))
    return panel(
        "Templates",
        "An agent returns a structured document (heading, text, button, "
        "image) and this engine renders it to table based, inline styled "
        "HTML that survives Outlook. A published version is never "
        "overwritten, so what you sent stays readable after you edit it.",
        table(["Template", "Subject", "Version", "Versions kept", "Blocks",
               "Updated", ""],
              [[f"<b>{e(t.get('name'))}</b>", e(t.get("subject")),
                num(t.get("version")), num(t.get("versions")),
                num(t.get("blocks")), e(str(t.get("updated_at"))[:10]),
                f"<button class='os-mini' onclick=\"osTemplate"
                f"('{e(t.get('id'))}')\">Edit</button>"]
               for t in rows],
              "No templates yet. Your live campaigns carry their copy on the "
              "campaign itself, which is why they still preview correctly.")
        + section("Build one", ED.block_editor(_D(ctx.get("edit_template")))))


# ---------------------------------------------------------------------------
# 5 SENDING
# ---------------------------------------------------------------------------
def send_queue(ctx) -> str:
    counts = _D(ctx.get("queue_counts"))
    rows = _L(ctx.get("queue_rows"))[:200]
    return panel(
        "Queue",
        "Every recipient is a row with a state. That is what makes a crash "
        "resumable and a double send impossible: pressing the button twice "
        "cannot queue the same person twice.",
        tiles([(k.title(), counts.get(k) or None, "") for k in CORE.JOB_STATES])
        + "<div class='os-brow'>"
          "<button class='cta' onclick=\"osAct('/os/queue/work')\">"
          "Send approved</button>"
          "<span class='os-note'>Only rows you approved are picked up, and "
          "every gate is re-checked at send time in case somebody "
          "unsubscribed while waiting.</span></div>"
        + table(["Recipient", "Campaign", "State", "Approved", "Tries",
                 "Provider", "Result"],
                [[e(r.get("email")), e(r.get("campaign")),
                  state_pill(r.get("status")),
                  pill("yes", "ok") if r.get("approved") else pill("no", "warn"),
                  num(r.get("attempts")), e(r.get("provider")),
                  e(r.get("error") or r.get("sent_at") or "")]
                 for r in rows], "The queue is empty.", dataset="queue"))


_VERDICT_TONE = {"scanner": "warn", "silent": "bad", "looking": "warn",
                 "overmailed": "warn"}


def send_deliver(ctx) -> str:
    d = _D(ctx.get("deliverability"))
    h = _D(ctx.get("hygiene"))
    rows = _L(h.get("rows"))
    counts = [("Scanners", len(_L(h.get("scanner"))),
               "their clicks are a machine"),
              ("No sign of life", len(_L(h.get("silent"))),
               "sent to, never opened"),
              ("Opening, never clicking", len(_L(h.get("looking"))),
               "the offer is not landing"),
              ("Over-mailed", len(_L(h.get("overmailed"))),
               f"past {h.get('over')} emails"),
              ("Resting", h.get("resting"), "parked, not suppressed")]
    return panel(
        "Deliverability",
        "Bounces and complaints decide whether anything you send arrives. "
        "Below them is the list itself: who should stop receiving email, and "
        "why, in one place.",
        tiles([("Sent", d.get("sent"), ""),
               ("Bounced", d.get("bounced"), "reported by the provider"),
               ("Complaints", d.get("complaints"), ""),
               ("Unsubscribes", d.get("unsubscribes"), ""),
               ("Suppressed", d.get("suppressed"), "will never be emailed")])
        + section("The address your links point at",
                  (lambda pb: (
                      tiles([("Public address", None,
                              (pb.get("host") or pb.get("url") or "not set")[:40]),
                             ("State", None, pb.get("state", "unknown"))])
                      + (f"<p class='os-warn'>{e(pb.get('why'))}</p>"
                         if not pb.get("ok") else
                         f"<p class='os-note'>{e(pb.get('why'))}</p>")))
                  (_D(ctx.get("public_base"))))
        + section("Bounces, read out of your mailbox",
                  tiles([("Bounces recorded", _D(ctx.get("bounces")).get("total"), ""),
                         ("Permanent", _D(ctx.get("bounces")).get("hard"),
                          "suppressed"),
                         ("Temporary", _D(ctx.get("bounces")).get("soft"),
                          "recorded, not suppressed"),
                         ("Addresses", _D(ctx.get("bounces")).get("addresses"),
                          "distinct"),
                         ("Being watched", _D(ctx.get("bounces")).get("watching"),
                          "rested after four")])
                  + "<div class='os-brow'>"
                    "<button class='cta' onclick=\"osAct('/os/bounces/read')\""
                  + ("" if _D(ctx.get("bounces")).get("ready") else " disabled")
                  + ">Read the mailbox now</button>"
                    "<button class='os-mini' onclick=\"osAct("
                    "'/os/bounces/reread')\">Re-read everything</button>"
                    "<span class='os-note'>"
                  + e(_D(ctx.get("bounces")).get("why")) + "</span></div>"
                  + "<p class='os-note'>SMTP has no delivery receipt, so a "
                    "failure arrives later as an email in the same mailbox "
                    "everything else lands in. A 5.x.x status is permanent "
                    "and suppresses; a 4.x.x is a full mailbox or a server "
                    "having a bad day and does not. Four temporary failures "
                    "rest the address rather than suppressing it, because a "
                    "suppression cannot be undone without asking them.</p>")
        + section("How hard this list is being worked", tiles([
            ("People", h.get("people"), "in this workspace"),
            ("Most emails to one person", h.get("worst"), ""),
            ("Average each", h.get("average"), "")]
            + [(lab, n or None, why) for lab, n, why in counts]))
        + section("Who should stop receiving email",
                  "<div class='os-brow'>"
                  "<button class='cta' onclick=\"osClean('silent')\">"
                  "Rest everyone with no sign of life</button>"
                  "<button class='os-mini' onclick=\"osClean('overmailed')\">"
                  "Rest the over-mailed</button>"
                  "<span class='os-note'>Rest is not suppression. They stay "
                  "in every count and every segment; the gate simply refuses "
                  "to send until the date passes, because burning a real "
                  "prospect for ever is the expensive mistake and a "
                  "suppression cannot be undone without asking them.</span>"
                  "</div>"
                  + table(["Person", "Sent", "Opens", "Clicks", "What it is",
                           "What to do", ""],
                          [[f"<b>{e(r.get('email'))}</b>"
                            + (f"<br><span class='os-d'>{e(r.get('company'))}"
                               f"</span>" if r.get("company") else ""),
                            num(r.get("sent")), num(r.get("opens")),
                            num(r.get("clicks")),
                            pill(r.get("code"),
                                 _VERDICT_TONE.get(r.get("code"), "mut"))
                            + f"<br><span class='os-d'>{e(r.get('why'))}"
                              f"</span>",
                            e(r.get("action")),
                            (pill("resting to " + r.get("rest_until"), "ok")
                             + f"<br><button class='os-mini' onclick="
                               f"\"osWake('{e(r.get('email'))}')\">Wake"
                               f"</button>"
                             if r.get("resting") == "yes" else
                             f"<button class='os-mini' onclick=\"osRest"
                             f"('{e(r.get('email'))}')\">Rest 90 days"
                             f"</button>")]
                           for r in rows],
                          "Nobody is being over-worked. Every address is "
                          "inside the limits.", dataset="hygiene"))
        + section("Why people are suppressed",
                  donut(list(_D(d.get("by_reason")).items()))))


# ---------------------------------------------------------------------------
# 6 AUTOMATION
# ---------------------------------------------------------------------------
def auto_agents(ctx) -> str:
    import content_engine_os_agents as AG
    allowed = "".join(f"<li><code>{e(a)}</code></li>" for a in AG.ACTIONS)
    refused = "".join(f"<li><code>{e(k)}</code> {e(v)}</li>"
                      for k, v in AG.HUMAN_ONLY.items())
    return panel(
        "Agents",
        "Agents do not touch the database and they do not touch a mail "
        "provider. They call one internal API, which enforces tenancy, "
        "validates, records what happened and returns plain data.",
        section("The one door",
                "<pre class='os-pre'>POST /internal/v1/agent\n"
                "{ \"agent\": \"lead_qualifier\",\n"
                "  \"action\": \"leads.upsert\",\n"
                "  \"params\": { \"email\": \"...\", \"score\": 82 } }</pre>")
        + section("What an agent may ask for", f"<ul class='os-ul'>{allowed}</ul>")
        + section("What only you may do", f"<ul class='os-ul'>{refused}</ul>")
        + section("The path every email takes",
                  "<pre class='os-pre'>agent or campaign\n"
                  "  -> resolve the audience\n"
                  "  -> consent check\n"
                  "  -> suppression check\n"
                  "  -> frequency check\n"
                  "  -> sender check\n"
                  "  -> rate limit check\n"
                  "  -> QUEUE\n"
                  "  -> your approval\n"
                  "  -> worker\n"
                  "  -> provider adapter</pre>"))


def auto_runs(ctx) -> str:
    rows = _L(ctx.get("agent_runs"))[:150]
    return panel(
        "Agent runs",
        "Every call an agent made, what it changed and what it cost. An "
        "action nobody can reconstruct afterwards gets blamed on the wrong "
        "thing.",
        table(["Agent", "Task", "Status", "Actions", "Cost", "Started",
               "Result"],
              [[e(r.get("agent")), f"<code>{e(r.get('task'))}</code>",
                state_pill(r.get("status")), num(r.get("actions")),
                num(r.get("cost"), " USD") if r.get("cost") else num(None),
                e(str(r.get("started_at"))[:16]), e(r.get("output"))]
               for r in rows],
              "No agent has called the OS yet."))


# ---------------------------------------------------------------------------
# 7 ANALYTICS
# ---------------------------------------------------------------------------
def an_campaign(ctx) -> str:
    t = _D(ctx.get("totals"))
    rows = _L(ctx.get("campaigns"))
    return panel(
        "Campaign analytics",
        "Read from a daily rollup rather than from raw events, so this page "
        "stays fast as the event table grows.",
        tiles([("Sent", t.get("sent"), ""),
               ("Unique opens", t.get("unique_opens"), ""),
               ("Unique clicks", t.get("unique_clicks"), "")])
        + "<div class='os-grid2'>"
        + section("Rates, each with its denominator",
                  "<div class='os-tiles'>"
                  + rate_tile("Open rate", t.get("open_rate"))
                  + rate_tile("Click rate", t.get("click_rate"))
                  + rate_tile("Human open rate", t.get("human_open_rate"),
                              "scanners removed")
                  + rate_tile("Human click rate", t.get("human_click_rate"),
                              "scanners removed")
                  + rate_tile("Click to open", t.get("ctor"))
                  + rate_tile("Unsubscribe rate", t.get("unsub_rate"))
                  + rate_tile("Complaint rate", t.get("complaint_rate"))
                  + "</div>"
                  + (f"<p class='os-warn'>"
                     f"{e(len(_L(_D(ctx.get('hygiene')).get('scanner'))))} "
                     f"recipient(s) are security scanners following every "
                     f"link. Both numbers are shown rather than one quietly "
                     f"corrected: the raw rate is what the tracker saw, the "
                     f"human rate is what to act on. They are listed under "
                     f"Sending, Deliverability.</p>"
                     if _L(_D(ctx.get("hygiene")).get("scanner")) else ""))
        + section("When people open",
                  bars(_L(ctx.get("open_curve")), key="opens", label="label"))
        + "</div>"
        + section("Links that were actually clicked",
                  table(["Link", "Clicks", "People"],
                        [[e(l.get("url")), num(l.get("clicks")),
                          num(l.get("people"))]
                         for l in _L(ctx.get("links"))],
                        "No clicks recorded yet."))
        + section("By campaign",
                  table(["Subject", "Sent", "Opens", "Clicks", "Open rate"],
                        [[e(c.get("subject") or c.get("name")),
                          num(c.get("sent")), num(c.get("opens")),
                          num(c.get("clicks")),
                          num(pair(c.get("open_rate"))[0], "%")]
                         for c in rows], "Nothing sent yet."))
        + f"<p class='os-note'>{e(AN.MPP_CAVEAT)}</p>")


def an_lead(ctx) -> str:
    acq = _D(ctx.get("acquisition"))
    st = _D(acq.get("stages"))
    return panel(
        "Lead analytics",
        "The acquisition side: how many people the agents found, how many "
        "survived qualification, and where they stalled.",
        tiles([("Leads", acq.get("leads"), ""),
               ("Scored", acq.get("ai_qualified"), "by the qualifier"),
               ("Average score", acq.get("avg_score"), ""),
               ("Companies", acq.get("companies"), "")])
        + section("Stages", bars([{"label": k[:6], "value": v}
                                  for k, v in st.items() if v]))
        + section("Sources", donut(_L(acq.get("by_source")))))


def an_attrib(ctx) -> str:
    a = _D(ctx.get("attribution"))
    rev = _D(ctx.get("revenue"))
    return panel(
        "Attribution",
        "Attribution here reads recorded conversions, not a model. A model "
        "would produce a bigger number and a smaller reason to believe it.",
        section("Money, from conversions this engine was told about",
                tiles([("Conversions", rev.get("conversions"), ""),
                       ("Customers", rev.get("customers"), "people"),
                       ("Revenue", rev.get("revenue"), rev.get("currency", "")),
                       ("Per recipient", rev.get("per_recipient"), ""),
                       ("Conversion rate", pair(rev.get("rate"))[0],
                        pair(rev.get("rate"))[1], "%")])
                + f"<p class='os-note'>{e(rev.get('basis'))}</p>"
                + "<div class='os-form'>"
                  "<input id='os-cve' class='os-in' placeholder='email'>"
                  "<input id='os-cvv' class='os-in' type='number' "
                  "placeholder='value'>"
                  "<input id='os-cvr' class='os-in' placeholder='reference, "
                  "for example a booking id'>"
                  "<button class='cta' onclick='osConversion()'>Record a "
                  "conversion</button></div>"
                + section("Or let your site record it",
                          "<p class='os-note'>Drop this on your thank-you "
                          "page and every booking records itself:</p>"
                          "<pre class='os-pre'>&lt;img src=\"" + e(
                              _D(ctx.get("connectors")).get("public_base")
                              and "https://YOUR-ENGINE" or "https://YOUR-ENGINE")
                          + "/t/v?e={{email}}&amp;value=2500\" "
                            "width=\"1\" height=\"1\" alt=\"\"&gt;</pre>"
                          "<p class='os-note'>It answers with a 1x1 image, so "
                          "it works on a page built in a website editor that "
                          "cannot run scripts.</p>"))
        + tiles([("First touch", a.get("first_touch"), "deals"),
               ("Last touch", a.get("last_touch"), "deals"),
               ("Assisted", a.get("assisted"), ""),
               ("Revenue", a.get("revenue"), ""),
               ("Cost", a.get("cost"), ""),
               ("Return", a.get("roi"), "", "x")])
        + section("Conversions by stage",
                  bars([{"label": k[:6], "value": v} for k, v in
                        _D(_D(ctx.get("summary")).get("stages")).items() if v])))


# ---------------------------------------------------------------------------
# 8 SETTINGS
# ---------------------------------------------------------------------------
def set_email(ctx) -> str:
    rows = _L(ctx.get("providers"))
    return panel(
        "Email",
        "One interface, many providers. The campaign engine never names an "
        "ESP, so swapping one for another is a setting rather than a "
        "rewrite. A provider with no key says so in words; add the key and "
        "it turns on with no rebuild.",
        table(["Provider", "State", "What it needs", "Prove it",
               "Webhook"],
              [[f"<b>{e(p.get('name'))}</b>"
                + (" " + pill("in use", "ok") if p.get("selected") else ""),
                pill("connected", "ok") if p.get("live")
                else pill("needs a key", "warn"),
                f"<code>{e(p.get('key_env'))}</code>",
                f"<button class='os-mini' onclick=\"osTestProvider"
                f"('{e(p.get('name'))}')\">Test</button>",
                (f"<code class='os-wh'>{e(p.get('webhook'))}</code>"
                 + (f"<br><button class='os-mini' onclick=\"osHook"
                    f"('{e(p.get('name'))}')\">Register</button>"
                    if p.get("can_register") else
                    "<br><span class='os-d'>paste this into its "
                    "dashboard</span>"))] for p in rows], "")
        + "<p class='os-note'>A key being present and a key working are "
          "different facts. Test makes a real authenticated call and prints "
          "what came back, because a screen showing a connected badge for a "
          "key with a typo in it is worse than an empty one. Nothing is "
          "sent by that button.</p>"
        + section("Prove one end to end",
                  "<div class='os-form'>"
                  "<select id='os-tp' class='os-in'>"
                  + "".join(f"<option value='{e(p.get('name'))}'>"
                            f"{e(p.get('name'))}</option>" for p in rows)
                  + "</select>"
                    "<input id='os-tt' class='os-in' placeholder='send the "
                    "test to which address?'>"
                    "<button class='cta' onclick='osSendTest()'>Send one test "
                    "email</button></div>"
                    "<p class='os-note'>Test checks the key. This sends one "
                    "real email through that adapter, which is the only way "
                    "its send path is ever exercised before a campaign "
                    "depends on it.</p>")
        + section("The rule that does not bend",
                  "<p class='os-note'>No agent and no request handler may "
                  "call a provider. Everything goes through the queue, and "
                  "the build fails if any other module so much as imports "
                  "the provider file.</p>"))


def set_domains(ctx) -> str:
    rows = _L(ctx.get("domains"))
    def check(c):
        c = _D(c)
        if not c:
            return "<span class='os-d'>not checked</span>"
        return " ".join(
            pill(f"{k.upper()} {_D(v).get('state')}",
                 {"pass": "ok", "fail": "bad"}.get(_D(v).get("state"), "warn"))
            for k, v in c.items())
    return panel(
        "Domains",
        "SPF, DKIM and DMARC read from real DNS. Three outcomes, never two: "
        "pass, fail, or could not check. A green tick because a resolver was "
        "missing is how a sending reputation ends.",
        "<div class='os-form'><input id='os-dm' class='os-in' "
        "placeholder='yourdomain.com'>"
        "<input id='os-ds' class='os-in' placeholder='DKIM selector "
        "(default)'>"
        "<button class='cta' onclick='osCheckDomain()'>Check DNS</button></div>"
        + table(["Domain", "State", "Records", "Checked"],
                [[f"<b>{e(d.get('domain'))}</b>", state_pill(d.get("state")),
                  check(d.get("checks")),
                  e(str(d.get("checked_at"))[:16] or d.get("note") or "")]
                 for d in rows], "No sender domain recorded yet."))


def set_integrations(ctx) -> str:
    rows = [p for p in _L(ctx.get("providers"))]
    return panel(
        "Integrations",
        "Klaviyo, HubSpot and the rest belong here as adapters, never inside "
        "the campaign engine. A client who connects their Klaviyo account "
        "syncs profiles and events through the adapter; nothing in this OS "
        "learns that Klaviyo exists.",
        table(["Integration", "State", "Key", "Notes"],
              [[f"<b>{e(p.get('name'))}</b>",
                pill("connected", "ok") if p.get("live") else pill("not connected", "mut"),
                f"<code>{e(p.get('key_env'))}</code>", e(p.get("docs"))]
               for p in rows if p.get("name") not in ("smtp",)], "")
        + section("Read out of Klaviyo",
                  "<div class='os-form'>"
                  "<select id='os-kw' class='os-in'>"
                  + "".join(f"<option value='{k}'>{k}</option>" for k in
                            ("profiles", "lists", "segments", "campaigns",
                             "flows", "metrics"))
                  + "</select>"
                    "<button class='cta' onclick='osKlaviyo()'>Pull</button>"
                    "<span class='os-note'>Profiles are written in as leads. "
                    "The rest is reported so you can see what is there "
                    "before this engine starts copying it.</span></div>")
        + section("Credential handling",
                  "<p class='os-note'>Keys are read from the environment on "
                  "the server and are never returned to this page. Nothing "
                  "on this screen has ever held a secret.</p>"))


def set_compliance(ctx) -> str:
    s = _D(ctx.get("summary"))
    d = _D(ctx.get("deliverability"))
    return panel(
        "Compliance",
        "Consent with its provenance, and suppression that overrides "
        "everything. Written for a founder sending into the EU, the UK, "
        "Switzerland, the USA and Canada.",
        tiles([("Suppressed", s.get("suppressed"), "never emailed again"),
               ("Unsubscribed", d.get("unsubscribes"), ""),
               ("Complaints", d.get("complaints"), "")])
        + section("Consent states",
                 table(["State", "What it means"],
                       [["SUBSCRIBED", "asked to hear from you, with a record "
                                       "of when and how"],
                        ["PENDING", "asked but not yet confirmed"],
                        ["UNSUBSCRIBED", "asked you to stop"],
                        ["SUPPRESSED", "put beyond reach by a bounce, a "
                                       "complaint or a legal request"],
                        ["NEVER_SUBSCRIBED", "cold outreach, which is lawful "
                                             "business to business in your "
                                             "markets with an unsubscribe "
                                             "and a postal address"]]))
        + section("Suppression reasons",
                  donut(list(_D(d.get("by_reason")).items())))
        + section("Somebody says the confirmation never arrived",
                  "<div class='os-form'>"
                  "<input id='os-rce' class='os-in' placeholder='email'>"
                  "<button class='cta' onclick='osResendConfirm()'>Send it "
                  "again</button></div>"
                  "<p class='os-note'>Refused for anybody already confirmed, "
                  "so this cannot become a way of emailing a subscriber "
                  "under cover of a system message.</p>")
        + section("Add a suppression",
                  "<div class='os-form'><input id='os-supe' class='os-in' "
                  "placeholder='email address'>"
                  "<select id='os-supr' class='os-in'>"
                  + "".join(f"<option>{e(r)}</option>"
                            for r in CORE.SUPPRESSION_REASONS)
                  + "</select><button class='cta' onclick='osSuppress()'>"
                    "Suppress</button></div>"))


# ---------------------------------------------------------------------------
# INBOX, SEND RULES, A/B, TEAM, STORAGE
# ---------------------------------------------------------------------------
def eng_inbox(ctx) -> str:
    """Replies, with the agent's draft answer beside each one.

    This replaces the old card block that used to be pasted onto this
    section. Same endpoints, so nothing about answering changed; it simply
    lives inside the OS now instead of beside it."""
    drafts = _L(ctx.get("replies"))
    cards = []
    for d in drafts[:60]:
        d = _D(d)
        did = e(d.get("id"))
        cards.append(
            "<div class='os-reply'>"
            f"<div class='os-rhead'><b>{e(d.get('from') or d.get('email'))}</b>"
            f"{state_pill(d.get('status') or 'draft')}"
            f"<span class='os-d'>{e(str(d.get('at') or '')[:16])}</span></div>"
            f"<p class='os-quote'>{e(str(d.get('incoming') or d.get('text') or '')[:600])}</p>"
            f"<input class='os-in' id='os-rs-{did}' "
            f"value='{e(d.get('subject'))}' placeholder='Subject'>"
            f"<textarea class='os-ta' rows='6' id='os-rb-{did}'>"
            f"{e(d.get('body') or d.get('draft'))}</textarea>"
            "<div class='os-brow'>"
            f"<button class='os-mini' onclick=\"osReplySave('{did}')\">"
            "Save the edit</button>"
            f"<button class='cta' onclick=\"osReplySend('{did}')\">"
            "Send this reply</button>"
            f"<button class='os-mini' onclick=\"osReplyDrop('{did}')\">"
            "Dismiss</button></div></div>")
    return panel(
        "Inbox",
        "Every reply, with an answer the agent drafted. Nothing here is sent "
        "until you press send, and what you edit is what leaves.",
        "<div class='os-brow'>"
        "<button class='cta' onclick=\"osAct('/replies/refresh')\">"
        "Fetch replies</button>"
        f"<span class='os-note'>{len(drafts)} waiting</span></div>"
        + ("".join(cards) or "<p class='os-empty'>No replies waiting. Press "
                             "Fetch replies to read the mailbox.</p>"))


def send_rules(ctx) -> str:
    r = _D(ctx.get("schedule"))
    w = _D(r.get("window"))
    return panel(
        "Send rules",
        "When an email is allowed to leave, and what happens when one fails. "
        "Your five markets span nine hours: a batch released at 09:00 in "
        "Munich reaches Vancouver at midnight, and a cold email that arrives "
        "at midnight is read at 08:00 under forty others.",
        tiles([("Window opens", w.get("from_hour"), "recipient local time", ":00"),
               ("Window closes", w.get("to_hour"), "recipient local time", ":00"),
               ("Weekdays only", None, "yes" if w.get("weekdays_only") else "no"),
               ("An hour's cap", r.get("hourly_cap"), r.get("why")),
               ("Room left this hour", r.get("room"), ""),
               ("Retry ladder", None, r.get("ladder")),
               ("Attempts before it stops", r.get("max_attempts"), "")])
        + section("Change the window",
                  "<div class='os-form'>"
                  "<input id='os-wf' class='os-in' type='number' min='0' "
                  f"max='23' value='{e(w.get('from_hour'))}' placeholder='from'>"
                  "<input id='os-wt' class='os-in' type='number' min='1' "
                  f"max='24' value='{e(w.get('to_hour'))}' placeholder='to'>"
                  "<select id='os-ww' class='os-in'>"
                  "<option value='1'"
                  + (" selected" if w.get("weekdays_only") else "")
                  + ">weekdays only</option><option value='0'"
                  + ("" if w.get("weekdays_only") else " selected")
                  + ">any day</option></select>"
                  "<input id='os-wh' class='os-in' type='number' min='1' "
                  f"max='1000' value='{e(r.get('hourly_cap'))}' "
                  "placeholder='per hour'>"
                  "<button class='cta' onclick='osSaveRules()'>Save</button>"
                  "</div>")
        + section("Timezones this engine knows",
                  "<p class='os-note'>" + e(", ".join(_L(r.get("zones"))))
                  + ". A profile's own timezone wins; the country is the "
                    "fallback; anything else is treated as UTC and labelled "
                    "approximate on the queue row rather than presented as a "
                    "fact.</p>"))


def an_ab(ctx) -> str:
    rows = [c for c in _L(ctx.get("campaigns")) if (c.get("variants") or 0) > 1]
    return panel(
        "A/B tests",
        "A subject line test, per campaign. Assignment is deterministic: the "
        "same person always lands on the same arm, so re-queueing or "
        "restarting the worker cannot move somebody mid-test and quietly "
        "invalidate the result.",
        table(["Campaign", "Arms", "Recipients", "Sent", "Opens", ""],
              [[f"<b>{e(c.get('subject') or c.get('name'))}</b>",
                num(c.get("variants")), num(c.get("recipients")),
                num(c.get("sent")), num(c.get("opens")),
                f"<button class='os-mini' onclick=\"osCamp"
                f"('{e(c.get('id'))}')\">Open</button>"] for c in rows],
              "No campaign is running more than one subject line yet. Add a "
              "second variant on a campaign and both arms appear here.")
        + section("End a test",
                  "<div class='os-form'>"
                  "<select id='os-abc' class='os-in'>"
                  + "".join(f"<option value='{e(c.get('id'))}'>"
                            f"{e(c.get('subject') or c.get('name'))}</option>"
                            for c in rows)
                  + "</select>"
                    "<input id='os-abv' class='os-in' placeholder='arm, or "
                    "leave blank to let the verdict decide'>"
                    "<button class='cta' onclick='osPromote()'>Make it the "
                    "only subject line</button></div>")
        + section("Why this screen refuses to crown a winner early",
                  "<p class='os-note'>Below roughly a hundred sends an arm, a "
                  "five point gap is noise. Declaring a winner off forty "
                  "emails is the most common way an A/B test makes a campaign "
                  "worse, so the verdict says \"too early\" in those words "
                  "until the arms are big enough to mean something.</p>"))


def set_team(ctx) -> str:
    spaces = _L(ctx.get("workspaces"))
    people = _L(ctx.get("members"))
    return panel(
        "Team",
        "Workspaces keep data apart. Nothing crosses a boundary: a profile, "
        "a campaign and an event all carry a workspace, and the backend "
        "filters on it rather than trusting the page.",
        section("Workspaces",
                table(["Workspace", "Your role", "People", "Created", ""],
                      [[f"<b>{e(w.get('name'))}</b>", state_pill(w.get("role")),
                        num(w.get("members")), e(str(w.get("created_at"))[:10]),
                        f"<button class='os-mini' onclick=\"osSwitchWs"
                        f"('{e(w.get('id'))}')\">Switch</button>"]
                       for w in spaces], "")
                + "<div class='os-form'>"
                  "<input id='os-wsn' class='os-in' placeholder='New "
                  "workspace name'>"
                  "<button class='cta' onclick='osNewWs()'>Create</button>"
                  "</div>")
        + section("People in this workspace",
                  table(["Email", "Role", "What that allows", "Invited", ""],
                        [[e(m.get("email")), state_pill(m.get("role")),
                          e(m.get("grants")), e(m.get("invited_at")),
                          f"<button class='os-mini' onclick=\"osDropMember"
                          f"('{e(m.get('email'))}')\">Remove</button>"]
                         for m in people], "")
                  + "<div class='os-form'>"
                    "<input id='os-mem' class='os-in' placeholder='email'>"
                    "<select id='os-mrole' class='os-in'>"
                    + "".join(f"<option>{e(r)}</option>" for r in CORE.ROLES)
                    + "</select><button class='cta' onclick='osAddMember()'>"
                      "Add</button></div>")
        + section("Their own way in",
                  "<div class='os-form'>"
                  "<input id='os-pwe' class='os-in' placeholder='member email'>"
                  "<input id='os-pwp' class='os-in' type='password' "
                  "placeholder='a password of at least ten characters'>"
                  "<button class='cta' onclick='osSetPassword()'>Give them a "
                  "password</button>"
                  "<button class='os-mini' onclick='osClearPassword()'>Take "
                  "it away</button></div>"
                  + table(["Member", "Signs in on their own"],
                          [[e(k), pill("yes", "ok") if v
                            else pill("no", "mut")]
                           for k, v in _D(ctx.get("logins")).items()])
                  + "<p class='os-note'>They sign in at the same page with "
                    "their email and this password, and see only this "
                    "workspace at the role you gave them. Your dashboard "
                    "password still works and still means owner.</p>")
        + section("What this is not, plainly",
                  "<p class='os-note'>The dashboard session is still the only "
                  "way into this engine, and whoever holds it is the owner. "
                  "The people listed above scope data and record who did "
                  "what through the API; they do not yet hold their own "
                  "dashboard password. That is a real limit and it is said "
                  "here rather than implied by a screen that looks like more "
                  "than it is.</p>"))


def set_storage(ctx) -> str:
    b = _D(ctx.get("backend"))
    counts = _D(ctx.get("table_counts"))
    live = b.get("mode") == "postgres"
    return panel(
        "Storage",
        "Where this OS keeps its records, and how many of them there are.",
        tiles([("Backend", None, b.get("mode")),
               ("Tables", b.get("tables") or None, ""),
               ("Records", sum(counts.values()) or None, "in tables")])
        + f"<p class='os-note'>{e(b.get('why'))}</p>"
        + "<div class='os-brow'>"
          "<button class='cta' onclick=\"osAct('/os/migrate')\">"
          "Copy the JSON store into the tables</button>"
          "<span class='os-note'>A copy, never a move. The JSON stays exactly "
          "where it is, so setting OS_STORE=json puts the old world back with "
          "nothing lost.</span></div>"
        + (table(["Table", "Rows"],
                 [[f"<code>os_{e(k)}</code>", num(v)]
                  for k, v in sorted(counts.items(), key=lambda kv: -kv[1])
                  if v], "The tables are empty; press the button above.")
           if live else
           "<p class='os-empty'>Postgres is not in use, so there are no "
           "tables to count.</p>"))


# ---------------------------------------------------------------------------
# DATA: EXPORT, IMPORT, DRIVE
# ---------------------------------------------------------------------------
def import_preview(pv) -> str:
    """What the file would do, before it does it."""
    pv = _D(pv)
    if not pv.get("ok"):
        return (f"<p class='os-warn'>{e(pv.get('message'))}</p>"
                + (table(["Column in your file", "Mapped to"],
                         [[e(h), f"<code>{e(_D(pv.get('mapping')).get(i, ''))}"
                           f"</code>"]
                          for i, h in enumerate(_L(pv.get("header")))])
                   if pv.get("header") else ""))
    mapping = _D(pv.get("mapping"))
    header = _L(pv.get("header"))
    counts = [("New people", pv.get("new"), "will be written"),
              ("Already here", pv.get("update"), "updated, never duplicated"),
              ("Repeated in the file", pv.get("duplicate"), "kept once"),
              ("No usable address", pv.get("invalid"), "skipped"),
              ("Suppressed", pv.get("suppressed"), "skipped on purpose")]
    fields = _L(pv.get("fields"))
    def sel(i, cur):
        opts = "".join(
            f"<option value='{e(f)}'{' selected' if f == cur else ''}>"
            f"{e(f)}</option>" for f in fields)
        extra = ("" if cur in fields else
                 f"<option value='{e(cur)}' selected>{e(cur)}</option>")
        return (f"<select class='os-in os-map' data-i='{i}'>{extra}{opts}"
                f"</select>")
    return (
        "<div class='os-sec'>"
        + tiles([(lab, n or None, why) for lab, n, why in counts])
        + f"<p class='os-note'>{e(pv.get('message'))}</p>"
        + section("How the columns were read",
                  table(["Column in your file", "Read as"],
                        [[f"<b>{e(h)}</b>", sel(i, mapping.get(i, "skip"))]
                         for i, h in enumerate(header)]))
        + (section("Kept as custom properties",
                   "<p class='os-note'>"
                   + e(", ".join(_L(pv.get("custom"))))
                   + ". A column nobody recognises is kept against the "
                     "person rather than thrown away, and segments can "
                     "filter on it.</p>")
           if _L(pv.get("custom")) else "")
        + section("The first few rows, as they would be written",
                  table(["Email", "First name", "Company", "Country",
                         "Everything else"],
                        [[e(_D(r).get("email")), e(_D(r).get("first_name")),
                          e(_D(r).get("company")), e(_D(r).get("country")),
                          e(", ".join(f"{k}={v}" for k, v in
                                      _D(_D(r).get("properties")).items()))]
                         for r in _L(pv.get("sample"))]))
        + "<div class='os-brow'>"
          "<button class='cta os-go' onclick='osImportCommit()'>"
          f"Write {e(pv.get('new'))} new and update {e(pv.get('update'))}"
          "</button>"
          "<span class='os-note'>Nothing has been written yet.</span>"
          "</div></div>")



def data_export(ctx) -> str:
    rows = _L(ctx.get("datasets"))
    return panel(
        "Export",
        "Every table this engine holds, as a spreadsheet or as JSON. The "
        "workbook puts all of them in one file with a tab each, which is "
        "the version to open when you want to look rather than to load.",
        "<div class='os-brow'>"
        "<a class='cta os-go' href='/os/export/workbook.xlsx' download>"
        "Everything, one Excel workbook</a>"
        "<a class='cta' href='/os/export/everything.json' download>"
        "Everything, one JSON file</a>"
        "<span class='os-note'>The workbook opens in Excel, Numbers and "
        "Google Sheets. Nothing is styled: it is there to be filtered and "
        "pivoted, not admired.</span></div>"
        + table(["Table", "What is in it", "Columns", "Rows", "Download"],
                [[f"<b>{e(d.get('label'))}</b>",
                  f"<code>{e(d.get('name'))}</code>",
                  num(d.get("columns")), num(d.get("rows")),
                  download_menu(d.get("name"))] for d in rows],
                "Nothing to export yet."))


def data_import(ctx) -> str:
    lists = _L(ctx.get("lists"))
    return panel(
        "Import",
        "Bring a customer or lead list in from a CSV or an Excel file. It is "
        "read and shown to you first; nothing is written until you press the "
        "second button.",
        "<div class='os-form'>"
        "<input type='file' id='os-imp' class='os-in' "
        "accept='.csv,.xlsx,.xlsm,.json,text/csv'>"
        "<input id='os-impl' class='os-in' placeholder='Add them to a new "
        "list called... (optional)'>"
        "<button class='cta' onclick='osImportPreview()'>Read the file"
        "</button></div>"
        "<p class='os-note'>CSV, Excel or JSON, up to 8 MB. Column names are "
        "matched against the ones real exports use, so an Apollo, Sales "
        "Navigator or Maps file usually maps itself. A column nobody "
        "recognises is kept as a custom property rather than thrown away. "
        "A German Excel writes semicolons instead of commas and that is "
        "handled.</p>"
        "<div id='os-imprev'></div>"
        + section("What happens to a row",
                  table(["Outcome", "What it means"],
                        [["new", "written as a profile and a lead"],
                         ["already here", "the existing person is updated, "
                                          "never duplicated"],
                         ["repeated in the file", "kept once"],
                         ["no usable address", "skipped, and counted"],
                         ["suppressed", "skipped: somebody who asked you to "
                                        "stop is not un-asked by a "
                                        "spreadsheet"]]))
        + section("A sheet somebody keeps adding to",
                  "<div class='os-form'>"
                  "<input id='os-srn' class='os-in' placeholder='what to call "
                  "it'>"
                  "<input id='os-srid' class='os-in' placeholder='Google "
                  "Sheet id from its URL'>"
                  "<input id='os-srt' class='os-in' placeholder='tab name' "
                  "value='Sheet1'>"
                  "<input id='os-srd' class='os-in' type='number' value='1' "
                  "min='1' max='30'>"
                  "<button class='cta' onclick='osSaveSource()'>Read it every "
                  "N days</button>"
                  "<button class='os-mini' onclick=\"osAct('/os/source/run')\">"
                  "Read them all now</button></div>"
                  + table(["Source", "Tab", "Every", "Last read", "Result",
                           ""],
                          [[f"<b>{e(x.get('name'))}</b>", e(x.get("tab")),
                            num(x.get("every_days"), " days"),
                            e(str(x.get("last_at") or "never")[:16]),
                            e(str(x.get("last_result") or "")[:80]),
                            f"<button class='os-mini' onclick=\"osDropSource"
                            f"('{e(x.get('sheet_id'))}','{e(x.get('tab'))}')"
                            f"\">Remove</button>"]
                           for x in _L(ctx.get("sources"))],
                          "No recurring source yet.")
                  + "<p class='os-note'>Share the sheet with your Google "
                    "service account or it cannot be opened. Every row goes "
                    "through the same rules as an upload: existing people "
                    "are updated, suppressed addresses are skipped.</p>")
        + (section("Lists you already have",
                   table(["List", "People"],
                         [[e(l.get("name")), num(l.get("members"))]
                          for l in lists])) if lists else ""))


def data_drive(ctx) -> str:
    d = _D(ctx.get("drive"))
    last = _D(ctx.get("drive_last"))
    sh = _D(ctx.get("sheets"))
    shlast = _D(ctx.get("sheets_last"))
    return panel(
        "Google Drive and Sheets",
        "A copy of everything, in the folder your Google service account "
        "already has. Postgres stays the source of truth: this writes, and "
        "never reads back, so Drive cannot quietly become a second version "
        "of the answer.",
        tiles([("Connected", None, "yes" if d.get("ready") else "not yet"),
               ("Folder", None, (d.get("folder") or "not set")[:22]),
               ("Last written", None,
                str(last.get("at") or "never")[:16]),
               ("Files last time", len(_L(last.get("files"))) or None, "")])
        + f"<p class='os-note'>{e(d.get('why'))}</p>"
        + "<div class='os-brow'>"
          "<button class='cta' onclick=\"osAct('/os/drive/push')\""
        + ("" if d.get("ready") else " disabled")
        + ">Write everything to Drive now</button>"
        + (f"<a class='os-mini' href='{e(last.get('workbook'))}' "
           f"target='_blank' rel='noopener'>Open the last workbook</a>"
           if last.get("workbook", "").startswith("http") else "")
        + "</div>"
        + section("The same tables as tabs in your Sheet",
                  tiles([("Sheet connected", None,
                          "yes" if sh.get("ready") else "not yet"),
                         ("Tabs last time", len(_L(shlast.get("tabs"))) or None,
                          ""),
                         ("Last written", None,
                          str(shlast.get("at") or "never")[:16])])
                  + f"<p class='os-note'>{e(sh.get('why'))}</p>"
                  + "<div class='os-brow'>"
                    "<button class='cta' onclick=\"osAct('/os/sheets/push')\""
                  + ("" if sh.get("ready") else " disabled")
                  + ">Write the tabs now</button>"
                    "<span class='os-note'>Both mirrors also run once a day "
                    "from the worker, keyed on the date so a restart cannot "
                    "make them run twelve times.</span></div>")
        + section("What gets written",
                  table(["File", "What it is"],
                        [["<code>engagement-os-DATE.xlsx</code>",
                          "one workbook, one tab per table: people, leads, "
                          "companies, campaigns, every email sent, events, "
                          "consent, the queue, list hygiene and the daily "
                          "totals"],
                         ["<code>engagement-os-DATE.json</code>",
                          "the same data as JSON, for anything that reads a "
                          "feed rather than a spreadsheet"]]))
        + (section("Last run",
                   table(["File", "Result"],
                         [[e(f), pill("written", "ok")]
                          for f in _L(last.get("files"))]
                         + [[e(f), pill("refused", "bad")]
                            for f in _L(last.get("failed"))]))
           if last else ""))


# ---------------------------------------------------------------------------
# THE CAMPAIGN DETAIL. Two columns. This is the screen the founder wanted.
# ---------------------------------------------------------------------------
def campaign_detail(ctx, cid) -> str:
    camps = {c.get("id"): c for c in _L(ctx.get("campaigns"))}
    c = camps.get(cid)
    if not c:
        return "<p class='os-empty'>That campaign is not in this workspace.</p>"
    msgs = _L(ctx.get("messages"))
    t = _D(ctx.get("detail_totals"))
    prev = _D(ctx.get("detail_preview"))
    picker = "".join(
        f"<option value='{e(m.get('email'))}|{e(m.get('touch'))}'"
        + (" selected" if prev.get("email") == m.get("email")
           and str(prev.get("touch")) == str(m.get("touch")) else "")
        + f">{e(m.get('name') or m.get('email'))}"
        + (f" ({e(m.get('company'))})" if m.get("company") else "")
        + f" &middot; email {e(m.get('touch'))}</option>" for m in msgs[:300])

    left = (
        "<div class='os-col'>"
        "<div class='os-brow'>"
        f"<select id='os-who' class='os-in' onchange=\"osPreview('{e(cid)}')\">"
        + (picker or "<option>no recipients on this campaign</option>")
        + "</select>"
        "<button class='os-mini' onclick=\"osDev('desk')\">Desktop</button>"
        "<button class='os-mini' onclick=\"osDev('mob')\">Mobile</button>"
        "<button class='os-mini' onclick=\"osDev('txt')\">Plain text</button>"
        "</div>"
        + (("<div class='os-inbox'><span class='os-d'>From</span>"
            f"<b>{e(prev.get('from_name') or 'your sending address')}</b>"
            f"<span class='os-d'>Subject</span><b>{e(prev.get('subject'))}</b>"
            + (f"<span class='os-edited'>you edited this one</span>"
               if prev.get("edited") else "")
            + "</div>")
           if prev.get("ok") else "")
        + "<div id='os-render' class='os-render'>"
        + (_render_body(prev) if prev.get("ok") else
           "<p class='os-empty'>Pick a recipient to see the exact email they "
           "receive.</p>")
        + "</div>"
        + (("<div class='os-editor'>"
            "<p class='os-st'>Correct this email</p>"
            f"<input id='os-esub' class='os-in' value='{e(prev.get('subject'))}'>"
            f"<textarea id='os-ebody' class='os-ta' rows='10'>"
            f"{e(prev.get('body'))}</textarea>"
            f"<button class='cta' onclick=\"osSaveEdit('{e(cid)}')\">"
            "Save this version</button>"
            f"<button class='os-mini' onclick=\"osSendOne('{e(cid)}')\">"
            "Send this one now</button>"
            "<p class='os-note'>What you save here is what sends. The sender "
            "reads the same record this editor writes.</p></div>")
           if prev.get("ok") else "")
        + "</div>")

    right = (
        "<div class='os-col os-narrow'>"
        + section("This campaign", tiles([
            ("Recipients", c.get("recipients"), ""),
            ("Messages", c.get("messages"), "person and step"),
            ("Sent", t.get("sent"), ""),
            ("Hand edited", c.get("edited") or None, "by you")]))
        + section("Funnel", funnel([
            ("Recipients", c.get("recipients") or 0, ""),
            ("Sent", t.get("sent") or 0, pair(t.get("open_rate"))[1] + " sent"),
            ("Opened", t.get("unique_opens") or 0,
             pair(t.get("open_rate"))[1] + " opened"),
            ("Clicked", t.get("unique_clicks") or 0,
             pair(t.get("click_rate"))[1] + " clicked"),
            ("Unsubscribed", t.get("unsubscribes") or 0, "")]))
        + section("When they opened",
                  bars(_L(ctx.get("detail_curve")), key="opens", label="label"))
        + section("Links clicked",
                  table(["Link", "Clicks", "People"],
                        [[e(l.get("url")), num(l.get("clicks")),
                          num(l.get("people"))]
                         for l in _L(ctx.get("detail_links"))],
                        "No clicks yet."))
        + (section("Subject lines under test",
                   table(["Arm", "Subject", "Sent", "Opens", "Open rate"],
                         [[pill(v.get("variant"), "ok"), e(v.get("subject")),
                           num(v.get("sent")), num(v.get("opened")),
                           num(pair(v.get("open_rate"))[0], "%")
                           + f"<br><span class='os-d'>"
                             f"{e(pair(v.get('open_rate'))[1])}</span>"]
                          for v in _L(ctx.get("detail_variants"))])
                   + f"<p class='os-note'>"
                     f"{e(_D(ctx.get('detail_verdict')).get('message'))}</p>")
           if len(_L(ctx.get("detail_variants"))) > 1 else "")
        + (section("Before it goes",
                   "<div class='os-tiles'>"
                   + "".join(
                       tile(sig.get("name"),
                            None,
                            ("passes" if sig.get("ok") else "look at this")
                            + ": " + str(sig.get("value")))
                       for sig in _L(_D(ctx.get("detail_checks")).get("signals")))
                   + "</div>"
                   + table(["Link", "Where a click really goes", "Secure"],
                           [[e(l.get("url")), e(l.get("tracked_as")),
                             pill("https", "ok") if l.get("https")
                             else pill("http", "bad")]
                            for l in _L(_D(ctx.get("detail_checks")).get("links"))],
                           "This email carries no links.")
                   + (f"<p class='os-warn'>"
                      f"{e(_D(ctx.get('detail_checks')).get('block_reason'))}</p>"
                      if _D(ctx.get("detail_checks")).get("blocking") else ""))
           if _D(ctx.get("detail_checks")) else "")
        + section("Move this campaign",
                  "<div class='os-brow'>"
                  f"<button class='os-mini' onclick=\"osAct('/os/campaign/plan',"
                  f"{{id:'{e(cid)}'}})\">Review who would receive it</button>"
                  f"<button class='os-mini' onclick=\"osAct("
                  f"'/os/campaign/queue',{{id:'{e(cid)}'}})\">Queue</button>"
                  f"<button class='cta' onclick=\"osAct("
                  f"'/os/campaign/approve',{{id:'{e(cid)}'}})\">Approve</button>"
                  f"<button class='os-mini' onclick=\"osAct("
                  f"'/os/campaign/cancel',{{id:'{e(cid)}'}})\">Cancel</button>"
                  "</div><p class='os-note'>Review runs every gate the real "
                  "send runs, so the number it shows is the number that "
                  "leaves.</p>")
        + "</div>")

    recips = section("Recipients", table(
        ["Person", "Company", "Step", "Subject sent", "Opened", "Clicked",
         "Sent", ""],
        [[f"<b>{e(m.get('name') or m.get('email'))}</b>"
          f"<br><span class='os-d'>{e(m.get('email'))}</span>",
          e(m.get("company")), num(m.get("touch")),
          e(m.get("subject") or "") + (" " + pill("edited", "ok")
                                       if m.get("edited") else ""),
          num(m.get("opened") or None), num(m.get("clicked") or None),
          e(str(m.get("sent_at") or "")[:16]) or state_pill(m.get("state")),
          f"<button class='os-mini' onclick=\"osProfile"
          f"('{e(m.get('profile_id'))}')\">Open</button>"]
         for m in msgs[:250]], "Nobody has been sent this yet."))

    return ("<div class='os-dhead'><h3>"
            + e(c.get("subject") or c.get("name")) + "</h3>"
            + state_pill(c.get("state"))
            + f"<p>{e(c.get('name'))}</p></div>"
            "<div class='os-two'>" + left + right + "</div>" + recips)


def _render_body(prev) -> str:
    """The email itself. srcdoc keeps the campaign's own CSS from leaking
    into the dashboard, which is the only reliable way to show real email
    HTML inside another page."""
    html = prev.get("html") or ""
    if not html:
        return ("<pre class='os-plain'>" + e(prev.get("plain")
                                             or prev.get("body")) + "</pre>")
    return ("<iframe class='os-frame' id='os-frame' sandbox='' srcdoc=\""
            + e(html) + "\"></iframe>"
            "<pre class='os-plain' id='os-plaintext' style='display:none'>"
            + e(prev.get("plain") or prev.get("body")) + "</pre>")


# ---------------------------------------------------------------------------
# THE PROFILE DETAIL
# ---------------------------------------------------------------------------
def profile_detail(ctx, pid) -> str:
    p = _D(ctx.get("detail_profile"))
    if not p:
        return "<p class='os-empty'>That person is not in this workspace.</p>"
    rows = _L(ctx.get("detail_timeline"))
    props = _D(ctx.get("detail_props"))
    return (
        "<div class='os-dhead'><h3>"
        + e(" ".join(x for x in [p.get("first_name"), p.get("last_name")] if x)
            or p.get("email")) + "</h3>"
        + state_pill(p.get("consent"))
        + f"<p>{e(p.get('email'))}"
        + (f" &middot; {e(p.get('company'))}" if p.get("company") else "")
        + (f" &middot; {e(p.get('job_title'))}" if p.get("job_title") else "")
        + "</p></div>"
        + tiles([("Lead score", p.get("lead_score"), ""),
                 ("Stage", None, p.get("lead_stage") or "NEW"),
                 ("Emails sent", p.get("emails_sent"), ""),
                 ("Opens", p.get("opens"), ""),
                 ("Clicks", p.get("clicks"), ""),
                 ("Days since activity", p.get("days_since_activity"), "")])
        + "<div class='os-two'>"
        + "<div class='os-col'>" + section("Timeline",
            "<div class='os-tl'>" + "".join(
                f"<div class='os-tli'><span class='os-tlt'>"
                f"{e(str(r.get('at'))[:16])}</span>"
                f"<span class='os-tlk os-{e(r.get('kind'))}'></span>"
                f"<span><b>{e(r.get('what'))}</b>"
                + (f"<br><span class='os-d'>{e(r.get('detail'))}</span>"
                   if r.get("detail") else "") + "</span></div>"
                for r in rows) + "</div>"
            if rows else "<p class='os-empty'>Nothing has happened yet.</p>")
        + "</div>"
        + "<div class='os-col os-narrow'>"
        + section("What the agents learned",
                  table(["Property", "Value"],
                        [[e(k), e(v)] for k, v in props.items()],
                        "Nothing enriched yet."))
        + section("Consent",
                  "<div class='os-form'><select id='os-cst' class='os-in'>"
                  + "".join(f"<option{' selected' if s == p.get('consent') else ''}"
                            f">{e(s)}</option>" for s in CORE.CONSENT_STATES)
                  + "</select>"
                    f"<button class='cta' onclick=\"osConsent"
                    f"('{e(p.get('email'))}')\">Record</button></div>"
                    "<p class='os-note'>A consent change is stored with when "
                    "and how it happened, because a status with no provenance "
                    "is a claim rather than a defence.</p>")
        + "</div></div>")


# ---------------------------------------------------------------------------
# THE SHELL
# ---------------------------------------------------------------------------
PANELS = {
    "overview": overview,
    "acqleads": acq_leads, "acqcompanies": acq_companies,
    "acqsources": acq_sources, "acqenrich": acq_enrich,
    "audprofiles": aud_profiles, "audlists": aud_lists,
    "audsegments": aud_segments,
    "engcampaigns": eng_campaigns, "engflows": eng_flows,
    "engtemplates": eng_templates, "enginbox": eng_inbox,
    "sendqueue": send_queue, "senddeliver": send_deliver,
    "sendrules": send_rules,
    "autoagents": auto_agents, "autoruns": auto_runs,
    "ancampaign": an_campaign, "anlead": an_lead, "anattrib": an_attrib,
    "anab": an_ab,
    "setemail": set_email, "setdomains": set_domains,
    "setintegrations": set_integrations, "setcompliance": set_compliance,
    "setteam": set_team, "setstorage": set_storage,
    "dataexport": data_export, "dataimport": data_import,
    "datadrive": data_drive,
}


def build(ctx, live=None) -> str:
    """The whole section: one band, one rail, one panel area.

    `live` carries the older interactive blocks (the outbox, the replies
    inbox, the Maps form) already rendered. They are appended to the
    Overview panel rather than re-implemented, so every send button on them
    keeps calling the endpoint it always did."""
    ctx = _D(ctx)
    counts = {"engcampaigns": len(_L(ctx.get("campaigns"))) or None,
              "audprofiles": len(_L(ctx.get("profiles"))) or None,
              "audsegments": len(_L(ctx.get("segments"))) or None,
              "engflows": len(_L(ctx.get("flows"))) or None,
              "sendqueue": _D(ctx.get("queue_counts")).get("QUEUED") or None,
              "autoruns": len(_L(ctx.get("agent_runs"))) or None}
    rail, panels, first = [], [], True
    for group, items in NAV:
        if group:
            rail.append(f"<p class='os-grp'>{e(group)}</p>")
        for pid, label in items:
            on = " on" if first else ""
            rail.append(
                f"<button class='os-navi{on}' id='os-nav-{pid}' "
                f"onclick=\"osNav('{pid}')\">{e(label)}"
                + (f"<span class='os-n'>{counts[pid]}</span>"
                   if counts.get(pid) else "") + "</button>")
            fn = PANELS.get(pid)
            body = ""
            try:
                body = fn(ctx) if fn else ""
            except Exception as ex:
                body = (f"<p class='os-warn'>This screen could not be drawn: "
                        f"{e(type(ex).__name__)}: {e(str(ex))[:200]}</p>")
            if pid == "overview" and live:
                body += section("Your existing controls", str(live))
            panels.append(f"<div class='os-panel{on}' id='os-p-{pid}'>"
                          f"{body}</div>")
            first = False
    return ("<div class='osx'>" + CSS_TAG
            + "<style>" + ED.CSS + "</style>"
            + JS + ED.FLOW_JS + ED.BLOCK_JS + band(ctx)
            + "<div class='os-shell'>"
            + "<nav class='os-rail'>" + "".join(rail) + "</nav>"
            + "<div class='os-main'>" + "".join(panels) + "</div>"
            + "</div>"
            "<div class='os-overlay' id='os-overlay' onclick='osClose(event)'>"
            "<div class='os-sheet'><button class='os-x' onclick='osClose()'>"
            "Close</button><div id='os-detail'></div></div></div>"
            + ED.BOOT_JS + "</div>")


CSS = """
.osx{--osbg:var(--s1,#12161c);--os2:var(--s2,#171c24);--osln:var(--line,#252c37);
 --ostx:var(--ink,#e8ecf1);--osmut:var(--mut,#98a2b0);--osdim:var(--dim,#6b7481);
 --osac:var(--blue,#4c8dff);--osok:var(--good,#3fd98b);--oswarn:var(--warn,#f5b14c);
 --osbad:#ff6b93;font-size:14px;color:var(--ostx)}
.osx *{box-sizing:border-box}
.os-band{display:flex;gap:20px;justify-content:space-between;align-items:flex-start;
 flex-wrap:wrap;background:var(--os2);border:1px solid var(--osln);
 border-radius:10px;padding:18px 20px;margin:0 0 16px}
.os-bk{margin:0;font-size:11px;letter-spacing:.09em;text-transform:uppercase;
 color:var(--osdim)}
.os-bstate{margin:6px 0 4px;font-size:16px}
.os-bsub{margin:0;max-width:720px;color:var(--osmut);line-height:1.55}
.os-bcmds{display:flex;gap:8px;flex-wrap:wrap}
.os-shell{display:grid;grid-template-columns:212px minmax(0,1fr);gap:18px;
 align-items:start}
@media(max-width:900px){.os-shell{grid-template-columns:1fr}}
.os-rail{background:var(--os2);border:1px solid var(--osln);border-radius:10px;
 padding:10px;position:sticky;top:8px}
.os-grp{margin:14px 0 6px;padding:0 8px;font-size:10px;letter-spacing:.1em;
 text-transform:uppercase;color:var(--osdim)}
.os-navi{display:flex;justify-content:space-between;align-items:center;width:100%;
 gap:8px;background:none;border:0;color:var(--osmut);text-align:left;
 padding:7px 8px;border-radius:6px;cursor:pointer;font-size:13.5px}
.os-navi:hover{background:rgba(76,141,255,.08);color:var(--ostx)}
.os-navi.on{background:rgba(76,141,255,.14);color:var(--ostx);font-weight:600}
.os-navi .os-n{background:var(--osln);border-radius:9px;padding:1px 7px;
 font-size:11px;color:var(--ostx)}
.os-panel{display:none}.os-panel.on{display:block}
.os-head h3{margin:0 0 4px;font-size:19px}
.os-head p{margin:0 0 16px;color:var(--osmut);max-width:820px;line-height:1.55}
.os-sec{margin:18px 0}
.os-st{margin:0 0 8px;font-size:11px;letter-spacing:.09em;text-transform:uppercase;
 color:var(--osdim)}
.os-tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));
 gap:8px;margin:0 0 12px}
.os-tile{background:var(--os2);border:1px solid var(--osln);border-radius:8px;
 padding:11px 12px;display:flex;flex-direction:column;gap:2px}
.os-tile b{font-size:21px;font-variant-numeric:tabular-nums;line-height:1.15}
.os-k{font-size:11px;color:var(--osdim);text-transform:uppercase;
 letter-spacing:.06em}
.os-d{font-size:11.5px;color:var(--osmut)}
.os-none{color:var(--osdim)!important;font-weight:400!important}
.os-tbl{border:1px solid var(--osln);border-radius:8px;overflow-x:auto;
 background:var(--os2)}
.os-tbl table{width:100%;border-collapse:collapse;font-size:13px}
.os-tbl th,.os-tbl td{padding:10px 14px;text-align:left;vertical-align:middle;
 border-bottom:1px solid var(--osln)}
.os-tbl tbody tr:last-child td{border-bottom:0}
.os-tbl tbody tr:hover{background:rgba(76,141,255,.05)}
.os-tbl th{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;
 color:var(--osdim);background:rgba(255,255,255,.03);white-space:nowrap;
 position:sticky;top:0;z-index:1}
.os-tbl td b{font-variant-numeric:tabular-nums}
/* Numbers line up under numbers, which is the whole point of a column. */
.os-tbl .os-r{text-align:right;font-variant-numeric:tabular-nums;
 white-space:nowrap}
.os-tbl td:first-child{min-width:180px}
.os-narrow .os-tbl td,.os-narrow .os-tbl th{padding:8px 10px;
 word-break:break-word}
.os-narrow .os-tbl td:first-child{min-width:0}
.os-dl{display:flex;gap:6px;align-items:center;justify-content:flex-end;
 margin:0 0 6px}
.os-dl a{text-decoration:none}
.os-up{cursor:pointer}
.os-fxcanvas{transition:transform .12s ease}
.os-empty{color:var(--osdim);padding:14px 2px;margin:0}
.os-note{color:var(--osmut);font-size:12.5px;line-height:1.55;margin:8px 0 0;
 max-width:820px}
.os-warn{color:var(--oswarn);font-size:12.5px;margin:6px 0}
.os-pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;
 font-weight:600;white-space:nowrap}
.os-ok{background:rgba(63,217,139,.14);color:var(--osok)}
.os-warn.os-pill{background:rgba(245,177,76,.14);color:var(--oswarn)}
.os-bad{background:rgba(255,107,147,.14);color:var(--osbad)}
.os-mut{background:rgba(255,255,255,.06);color:var(--osmut)}
.os-mini{background:var(--os2);border:1px solid var(--osln);color:var(--ostx);
 border-radius:6px;padding:5px 10px;font-size:12px;cursor:pointer}
.os-mini:hover{border-color:var(--osac)}
.os-mini.os-primary{border-color:var(--osac);color:var(--osac)}
.os-brow{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:10px 0}
.os-form{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}
.os-in{background:var(--osbg);border:1px solid var(--osln);color:var(--ostx);
 border-radius:6px;padding:7px 10px;font-size:13px;min-width:150px}
.os-ta{width:100%;background:var(--osbg);border:1px solid var(--osln);
 color:var(--ostx);border-radius:6px;padding:10px;font-size:13px;
 font-family:ui-monospace,Menlo,Consolas,monospace;line-height:1.55}
.os-builder{background:var(--os2);border:1px solid var(--osln);border-radius:8px;
 padding:14px;margin:0 0 14px}
.os-cond{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:10px 0}
.os-cw{font-size:12px;color:var(--osdim)}
.os-conds .os-cond{border-top:1px dashed var(--osln);padding-top:10px}
.os-two{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);
 gap:18px;align-items:start}
@media(max-width:1000px){.os-two{grid-template-columns:1fr}}
.os-grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
 gap:18px}
.os-render{background:#fff;border:1px solid var(--osln);border-radius:8px;
 overflow:hidden;min-height:220px}
.os-frame{width:100%;height:560px;border:0;background:#fff;display:block}
.os-frame.mob{width:390px;margin:0 auto;height:620px;
 box-shadow:0 0 0 1px rgba(0,0,0,.12)}
.os-plain{white-space:pre-wrap;color:#1a1d21;background:#fff;padding:16px;
 margin:0;font-size:13px;line-height:1.6;max-height:560px;overflow:auto}
.os-inbox{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;
 background:var(--os2);border:1px solid var(--osln);border-radius:8px;
 padding:10px 12px;margin:0 0 8px}
.os-edited{color:var(--osok);font-size:11.5px}
.os-editor{margin:14px 0 0}
.os-editor .os-in{width:100%;margin:0 0 8px}
.os-funnel{display:flex;flex-direction:column;gap:6px}
.os-fn{display:grid;grid-template-columns:112px 1fr 60px auto;gap:10px;
 align-items:center}
.os-fl{font-size:12.5px;color:var(--osmut)}
.os-fbar{background:var(--osln);border-radius:4px;height:14px;overflow:hidden}
.os-fbar i{display:block;height:100%;background:var(--osac);border-radius:4px}
.os-svg{width:100%;height:auto}
.os-bar{fill:var(--osac);opacity:.8}
.os-bl{fill:var(--osdim);font-size:9px}
.os-donut{display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.os-seg{transform:rotate(-90deg);transform-origin:50% 50%}
.os-seg0{stroke:var(--osac)}.os-seg1{stroke:var(--osok)}
.os-seg2{stroke:var(--oswarn)}.os-seg3{stroke:var(--osbad)}
.os-seg4{stroke:#9b7bff}.os-seg5{stroke:#59c3d6}
.os-keys{display:flex;flex-direction:column;gap:5px;font-size:12px;
 color:var(--osmut)}
.os-key i{display:inline-block;width:9px;height:9px;border-radius:2px;
 margin-right:6px}
.os-key i.os-seg0{background:var(--osac)}.os-key i.os-seg1{background:var(--osok)}
.os-key i.os-seg2{background:var(--oswarn)}.os-key i.os-seg3{background:var(--osbad)}
.os-key i.os-seg4{background:#9b7bff}.os-key i.os-seg5{background:#59c3d6}
.os-graph{overflow-x:auto;background:var(--osbg);border:1px solid var(--osln);
 border-radius:8px;padding:10px;margin:10px 0}
.os-graph svg{height:auto}
.os-node{fill:var(--os2);stroke:var(--osln)}
.os-nsend{stroke:var(--osac)}.os-ncond{stroke:var(--oswarn)}
.os-ngoal{stroke:var(--osok)}.os-nai_a{stroke:#9b7bff}
.os-nt{fill:var(--ostx);font-size:11px;font-weight:600}
.os-nd{fill:var(--osdim);font-size:9.5px}
.os-edge{stroke:var(--osln);fill:none;stroke-width:1.5}
.os-flow{background:var(--os2);border:1px solid var(--osln);border-radius:8px;
 padding:14px;margin:0 0 14px}
.os-fhead{display:flex;gap:10px;align-items:center;margin:0 0 10px}
.os-tl{display:flex;flex-direction:column;gap:0}
.os-tli{display:grid;grid-template-columns:118px 14px 1fr;gap:8px;
 padding:8px 0;border-left:0}
.os-tlt{font-size:11.5px;color:var(--osdim);font-variant-numeric:tabular-nums}
.os-tlk{width:9px;height:9px;border-radius:50%;background:var(--osln);
 margin-top:4px;box-shadow:0 0 0 3px var(--osbg)}
.os-tlk.os-sent{background:var(--osac)}
.os-tlk.os-email_opened{background:var(--oswarn)}
.os-tlk.os-email_clicked{background:var(--osok)}
.os-tlk.os-discovered{background:var(--osdim)}
.os-tlk.os-enriched{background:#9b7bff}
.os-pre{background:var(--osbg);border:1px solid var(--osln);border-radius:8px;
 padding:12px;font-size:12px;line-height:1.6;overflow-x:auto;color:var(--osmut)}
.os-ul{margin:0;padding-left:18px;color:var(--osmut);line-height:1.7;
 font-size:13px}
.os-overlay{display:none;position:fixed;inset:0;background:rgba(6,9,13,.72);
 z-index:9000;padding:24px;overflow-y:auto}
.os-overlay.on{display:block}
.os-sheet{max-width:1240px;margin:0 auto;background:var(--osbg);
 border:1px solid var(--osln);border-radius:12px;padding:20px}
.os-x{float:right;background:none;border:1px solid var(--osln);
 color:var(--osmut);border-radius:6px;padding:5px 12px;cursor:pointer}
.os-dhead{display:flex;gap:10px;align-items:center;flex-wrap:wrap;
 margin:0 0 14px}
.os-dhead h3{margin:0;font-size:19px}
.os-dhead p{margin:0;color:var(--osmut);width:100%;font-size:13px}
.os-col{min-width:0}
.os-reply{background:var(--os2);border:1px solid var(--osln);border-radius:8px;
 padding:14px;margin:0 0 12px}
.os-rhead{display:flex;gap:10px;align-items:center;margin:0 0 8px}
.os-quote{margin:0 0 10px;padding:10px 12px;border-left:3px solid var(--osln);
 color:var(--osmut);font-size:13px;white-space:pre-wrap}
.os-reply .os-in{width:100%;margin:0 0 8px}
.os-wh{font-size:11px;word-break:break-all;color:var(--osmut)}
"""

CSS_TAG = "<style>" + CSS + "</style>"

JS = ("<script>"
      "function osNav(id){"
      "document.querySelectorAll('.osx .os-panel').forEach(function(p){"
      "p.classList.toggle('on',p.id==='os-p-'+id);});"
      "document.querySelectorAll('.osx .os-navi').forEach(function(b){"
      "b.classList.toggle('on',b.id==='os-nav-'+id);});"
      "var m=document.querySelector('.osx .os-main');if(m&&m.scrollIntoView)"
      "m.scrollIntoView({block:'start',behavior:'smooth'});}"

      "function osToast(j,fb){var m=(j&&(j.message||j.error))||fb;"
      "if(window.toast){toast(m,!(j&&j.ok===false));}else{console.log(m);}}"

      "async function osAct(url,body){try{"
      "var r=await fetch(url,{method:'POST',headers:{'Content-Type':"
      "'application/json'},body:JSON.stringify(body||{})});"
      "var j=await r.json();osToast(j,'done');return j;}"
      "catch(e){osToast({ok:false,message:'could not reach the engine'});}}"

      "function osOpen(html){document.getElementById('os-detail').innerHTML=html;"
      "document.getElementById('os-overlay').classList.add('on');}"
      "function osClose(ev){if(ev&&ev.target&&ev.target.id!=='os-overlay')return;"
      "document.getElementById('os-overlay').classList.remove('on');}"

      "async function osCamp(id){try{var r=await fetch('/os/campaign/'+id);"
      "osOpen(await r.text());}catch(e){osToast({ok:false,"
      "message:'could not load that campaign'});}}"
      "async function osProfile(id){try{var r=await fetch('/os/profile/'+id);"
      "osOpen(await r.text());}catch(e){osToast({ok:false,"
      "message:'could not load that person'});}}"

      "async function osPreview(cid){var w=document.getElementById('os-who');"
      "if(!w||!w.value)return;var p=w.value.split('|');try{"
      "var r=await fetch('/os/campaign/'+cid+'?email='+encodeURIComponent(p[0])"
      "+'&touch='+encodeURIComponent(p[1]||'1'));osOpen(await r.text());}"
      "catch(e){osToast({ok:false,message:'could not build that preview'});}}"

      "function osDev(mode){var f=document.getElementById('os-frame');"
      "var t=document.getElementById('os-plaintext');if(!f)return;"
      "if(mode==='txt'){f.style.display='none';if(t)t.style.display='block';return;}"
      "f.style.display='block';if(t)t.style.display='none';"
      "f.classList.toggle('mob',mode==='mob');}"

      "async function osSaveEdit(cid){"
      "var w=document.getElementById('os-who');"
      "var s=document.getElementById('os-esub');"
      "var b=document.getElementById('os-ebody');"
      "if(!w||!s||!b)return;var p=w.value.split('|');"
      "var j=await osAct('/os/message/save',{campaign_id:cid,email:p[0],"
      "touch:p[1]||1,subject:s.value,body:b.value});"
      "if(j&&j.ok)osPreview(cid);}"

      "var osConds=[];"
      "function osCurrent(){return {field:document.getElementById('os-sf').value,"
      "operator:document.getElementById('os-so').value,"
      "value:document.getElementById('os-sv').value};}"
      "function osAddCond(){osConds.push(osCurrent());"
      "document.getElementById('os-sv').value='';osDrawConds();}"
      "function osDrawConds(){var h=osConds.map(function(c,i){"
      "var body=c.group?(\"<span class='os-cw'>(</span>\"+c.conditions.map("
      "function(x){return \"<b>\"+x.field+\"</b> \"+x.operator.replace(/_/g,' ')"
      "+\" <b>\"+x.value+\"</b>\";}).join(\" \"+c.group+\" \")+"
      "\"<span class='os-cw'>)</span>\"):"
      "(\"<b>\"+c.field+\"</b> <span class='os-d'>\"+c.operator.replace(/_/g,' ')"
      "+\"</span> <b>\"+c.value+\"</b>\");"
      "return \"<div class='os-cond'><span class='os-cw'>and</span>\"+body+"
      "\" <button class='os-mini' onclick='osDropCond(\"+i+\")'>remove\"+"
      "\"</button>\"+(c.group?\" <button class='os-mini' onclick='osIntoGroup(\"+"
      "i+\")'>+ into the bracket</button>\":\"\")+\"</div>\";}).join('');"
      "document.getElementById('os-conds').innerHTML=h;}"
      "function osIntoGroup(i){if(!osConds[i]||!osConds[i].group)return;"
      "osConds[i].conditions.push(osCurrent());"
      "document.getElementById('os-sv').value='';osDrawConds();}"
      "function osDropCond(i){osConds.splice(i,1);osDrawConds();}"
      "function osTree(){var all=[osCurrent()].concat(osConds).filter("
      "function(c){return (c.field&&c.operator)||c.group;}).map(function(c){"
      "return c.group?{operator:c.group,conditions:c.conditions}:c;});"
      "return {operator:document.getElementById('os-sm').value,conditions:all};}"
      "async function osCountSeg(){var j=await osAct('/os/segment/count',"
      "{tree:osTree()});var el=document.getElementById('os-scount');"
      "if(el&&j)el.textContent=j.message||'';}"
      "async function osSaveSeg(){var n=document.getElementById('os-sn');"
      "if(!n||!n.value.trim()){osToast({ok:false,message:"
      "'name the segment first'});return;}"
      "await osAct('/os/segment/save',{name:n.value,tree:osTree()});}"
      "async function osDropSeg(id){await osAct('/os/segment/delete',{id:id});}"

      "async function osSaveList(){var n=document.getElementById('os-ln');"
      "var d=document.getElementById('os-ld');"
      "await osAct('/os/list/save',{name:n?n.value:'',"
      "description:d?d.value:''});}"

      "async function osSaveCamp(){"
      "var n=document.getElementById('os-cn'),k=document.getElementById('os-ck'),"
      "a=document.getElementById('os-ca'),s=document.getElementById('os-cs');"
      "await osAct('/os/campaign/save',{name:n?n.value:'',"
      "audience_kind:k?k.value:'all',audience_id:a?a.value:'',"
      "subject:s?s.value:''});}"

      "async function osCheckDomain(){var d=document.getElementById('os-dm');"
      "var s=document.getElementById('os-ds');"
      "await osAct('/os/domain/check',{domain:d?d.value:'',"
      "selector:s?s.value:''});}"

      "async function osSuppress(){var e2=document.getElementById('os-supe');"
      "var r=document.getElementById('os-supr');"
      "await osAct('/os/suppress',{email:e2?e2.value:'',"
      "reason:r?r.value:'MANUAL'});}"

      "async function osConsent(email){var s=document.getElementById('os-cst');"
      "await osAct('/os/consent',{email:email,status:s?s.value:''});}"

      "async function osFindLeads(){"
      "var v=document.getElementById('os-mv'),c=document.getElementById('os-mc'),"
      "n=document.getElementById('os-mn');"
      "if(!v||!v.value.trim()||!c||!c.value.trim()){osToast({ok:false,"
      "message:'say what to look for and where'});return;}"
      "osToast({ok:true,message:'searching; this takes a moment'});"
      "await osAct('/leads/maps',{vertical:v.value,city:c.value,"
      "count:parseInt(n?n.value:'20',10)});}"

      "async function osReplySave(id){"
      "var s=document.getElementById('os-rs-'+id),"
      "b=document.getElementById('os-rb-'+id);"
      "await osAct('/reply/edit',{id:id,subject:s?s.value:'',"
      "body:b?b.value:''});}"
      "async function osReplySend(id){await osReplySave(id);"
      "await osAct('/reply/send',{id:id});}"
      "async function osReplyDrop(id){await osAct('/reply/dismiss',{id:id});}"

      "async function osSaveRules(){"
      "var f=document.getElementById('os-wf'),t=document.getElementById('os-wt'),"
      "w=document.getElementById('os-ww'),h=document.getElementById('os-wh');"
      "await osAct('/os/rules',{from_hour:f?f.value:8,to_hour:t?t.value:17,"
      "weekdays_only:w?w.value==='1':true,hourly:h?h.value:40});}"

      "async function osNewWs(){var n=document.getElementById('os-wsn');"
      "await osAct('/os/workspace/create',{name:n?n.value:''});}"
      "async function osSwitchWs(id){var j=await osAct('/os/workspace/switch',"
      "{id:id});if(j&&j.ok)location.reload();}"
      "async function osAddMember(){var e2=document.getElementById('os-mem'),"
      "r=document.getElementById('os-mrole');"
      "await osAct('/os/member/add',{email:e2?e2.value:'',"
      "role:r?r.value:'member'});}"
      "async function osDropMember(email){"
      "await osAct('/os/member/remove',{email:email});}"

      "async function osTestProvider(name){"
      "osToast({ok:true,message:'asking '+name+'...'});"
      "await osAct('/os/provider/test',{name:name});}"
      "async function osHook(name){await osAct('/os/provider/webhook',"
      "{name:name});}"

      "async function osSendOne(cid){var w=document.getElementById('os-who');"
      "if(!w||!w.value)return;var p=w.value.split('|');"
      "if(!confirm('Send this exact email to '+p[0]+' now?'))return;"
      "await osSaveEdit(cid);"
      "await osAct('/os/send-one',{campaign_id:cid,email:p[0],"
      "touch:p[1]||1});osPreview(cid);}"

      "async function osRest(email){await osAct('/os/rest',{email:email,"
      "days:90});}"
      "async function osWake(email){await osAct('/os/rest',{email:email,"
      "wake:true});}"
      "async function osClean(kind){"
      "if(!confirm('Rest everyone in that group for 90 days? They are not "
      "suppressed and you can wake any of them.'))return;"
      "await osAct('/os/audience/clean',{kind:kind,days:90});}"

      "function osFileB64(f){return new Promise(function(res,rej){"
      "var r=new FileReader();r.onload=function(){"
      "res(String(r.result).split(',')[1]||'');};r.onerror=rej;"
      "r.readAsDataURL(f);});}"

      "async function osImportPreview(){"
      "var el=document.getElementById('os-imp');"
      "if(!el||!el.files||!el.files[0]){osToast({ok:false,message:"
      "'choose a file first'});return;}"
      "var f=el.files[0];"
      "if(f.size>8388608){osToast({ok:false,message:'that file is over 8 MB'});"
      "return;}"
      "osToast({ok:true,message:'reading '+f.name+'...'});"
      "var b64=await osFileB64(f);window.__osFile={name:f.name,b64:b64};"
      "try{var r=await fetch('/os/import/preview',{method:'POST',"
      "headers:{'Content-Type':'application/json'},"
      "body:JSON.stringify({filename:f.name,b64:b64})});"
      "document.getElementById('os-imprev').innerHTML=await r.text();}"
      "catch(e){osToast({ok:false,message:'could not read that file'});}}"

      "async function osImportCommit(){"
      "var f=window.__osFile;if(!f){osToast({ok:false,message:"
      "'read a file first'});return;}"
      "var l=document.getElementById('os-impl');"
      "if(!confirm('Write these people in? Existing profiles are updated, "
      "never duplicated.'))return;"
      "var j=await osAct('/os/import/commit',{filename:f.name,b64:f.b64,"
      "list_name:l?l.value:''});"
      "if(j&&j.ok)osImportPreview();}"

      "async function osSearch(){"
      "var q=document.getElementById('os-psearch');"
      "try{var r=await fetch('/os/profiles/search?q='+"
      "encodeURIComponent(q?q.value:''));"
      "document.getElementById('os-plist').innerHTML=await r.text();}"
      "catch(e){osToast({ok:false,message:'search failed'});}}"
      "function osSearchClear(){var q=document.getElementById('os-psearch');"
      "if(q)q.value='';osSearch();}"

      "function osAddGroup(){osConds.push({group:'OR',conditions:[osCurrent()]});"
      "document.getElementById('os-sv').value='';osDrawConds();}"
      "function osClearSeg(){osConds=[];osDrawConds();"
      "var n=document.getElementById('os-sn');if(n)n.value='';}"
      "async function osEditSeg(id){try{"
      "var r=await fetch('/os/segment/'+id);var j=await r.json();"
      "if(!j||!j.ok){osToast(j,'could not load that segment');return;}"
      "document.getElementById('os-sn').value=j.name||'';"
      "document.getElementById('os-sm').value=j.match||'AND';"
      "osConds=(j.conditions||[]).slice(1);"
      "var first=(j.conditions||[])[0]||{};"
      "if(first.field){document.getElementById('os-sf').value=first.field;"
      "document.getElementById('os-so').value=first.operator||'equals';"
      "document.getElementById('os-sv').value=first.value||'';}"
      "osDrawConds();osToast({ok:true,message:'loaded; saving under the same "
      "name replaces it'});}"
      "catch(e){osToast({ok:false,message:'could not load that segment'});}}"

      "async function osSendTest(){var p=document.getElementById('os-tp'),"
      "t=document.getElementById('os-tt');"
      "if(!t||!t.value){osToast({ok:false,message:'which address?'});return;}"
      "if(!confirm('Send one real email through '+p.value+' to '+t.value+'?'))"
      "return;await osAct('/os/provider/send-test',{name:p.value,to:t.value});}"
      "async function osKlaviyo(){var w=document.getElementById('os-kw');"
      "await osAct('/os/klaviyo/pull',{what:w?w.value:'profiles'});}"
      "async function osSetPassword(){"
      "var e2=document.getElementById('os-pwe'),p=document.getElementById('os-pwp');"
      "var j=await osAct('/os/member/password',{email:e2?e2.value:'',"
      "password:p?p.value:''});if(p)p.value='';}"
      "async function osClearPassword(){var e2=document.getElementById('os-pwe');"
      "await osAct('/os/member/password',{email:e2?e2.value:'',clear:true});}"
      "async function osConversion(){"
      "var e2=document.getElementById('os-cve'),v=document.getElementById('os-cvv'),"
      "r=document.getElementById('os-cvr');"
      "await osAct('/os/conversion',{email:e2?e2.value:'',"
      "value:parseFloat(v&&v.value||'0'),ref:r?r.value:''});}"
      "async function osSaveSource(){"
      "var n=document.getElementById('os-srn'),i=document.getElementById('os-srid'),"
      "t=document.getElementById('os-srt'),d=document.getElementById('os-srd');"
      "await osAct('/os/source/save',{name:n?n.value:'',sheet_id:i?i.value:'',"
      "tab:t?t.value:'Sheet1',every_days:parseInt(d&&d.value||'1',10)});}"
      "async function osDropSource(id,tab){"
      "await osAct('/os/source/drop',{sheet_id:id,tab:tab});}"
      "async function osPromote(){var c=document.getElementById('os-abc'),"
      "v=document.getElementById('os-abv');"
      "await osAct('/os/variant/promote',{campaign_id:c?c.value:'',"
      "variant:v?v.value:''});}"
      "async function osResendConfirm(){var e2=document.getElementById('os-rce');"
      "await osAct('/os/confirmation/resend',{email:e2?e2.value:''});}"

      "async function osTemplate(id){try{"
      "var r=await fetch('/os/template/'+id);osOpen(await r.text());"
      "setTimeout(function(){try{osBbBoot();}catch(e){}},0);}"
      "catch(e){osToast({ok:false,message:'could not open that template'});}}"
      "</script>")
