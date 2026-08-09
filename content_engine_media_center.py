"""
content_engine_media_center.py
============================================================================
THE MEDIA BUYING OS SECTION. This replaces the 16-tab media UI completely.

DECISION FIRST. The founder's order and the spec's section 32: the first
screen answers "what needs me today", not "how many impressions were
there". Numbers come with denominators, absences render as absences, and
every button that could cost money routes through the order queue that
already holds the approval tiers.

WHAT THIS FILE IS ALLOWED TO DO: read the engines and draw HTML. It calls
content_engine_media_os / _plan / _perf / _creative for every fact, and
POSTS to /mediaos/* and /media/* for every action. It computes nothing of
its own, because a screen with its own arithmetic eventually disagrees
with the engine it fronts.

THE LIVE CONTROLS SURVIVE. The email OS rebuild once silently dropped the
outbox and the founder found out from the silence. So: the agent band with
its OFF/OBSERVE/PROPOSE ladder, the orders board with approve and execute,
the Google pulls, the GA4/GSC tracking boards and the media agent's draft
flow all keep their existing handlers and endpoints. Same names, same
wires, new rooms.

Every element id is prefixed mc- because the dashboard renders every
section at once and a bare id collides with someone else's.
============================================================================
"""

from __future__ import annotations

import html
import json
import logging

import content_engine_media_creative as MC
import content_engine_media_os as M
import content_engine_media_perf as MF
import content_engine_media_plan as MP

log = logging.getLogger("content_engine.media_center")


def e(v) -> str:
    return html.escape(str("" if v is None else v), quote=True)


def _n(v, dash="--"):
    """A number or an honest dash. Never a fake zero."""
    if v is None or v == "":
        return dash
    if isinstance(v, float):
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    return f"{v:,}" if isinstance(v, int) else e(v)


def _money(v, cur="EUR"):
    return "--" if v in (None, "") else f"{float(v):,.2f} {e(cur)}"


#: The screens. One tuple, used by the nav, the panels and the gates, so
#: a tab cannot exist without a panel or a panel without a tab.
SCREENS = (
    ("cmd", "🎯", "Command Centre", "What needs you today"),
    ("camps", "📋", "Campaigns", "Everything, with its real state"),
    ("wiz", "🧭", "New Campaign", "The eight steps"),
    ("launch", "🚀", "Launch Centre", "Checked before it costs anything"),
    ("plan", "📐", "Planner", "Budget, allocation, what-if"),
    ("creat", "🎨", "Creatives", "The library and what it learned"),
    ("aud", "👥", "Audiences", "Who, and what each platform drops"),
    ("perf", "📈", "Performance", "Five grains, one arithmetic"),
    ("attr", "🧾", "Attribution", "Five models that admit they disagree"),
    ("anom", "⚠️", "Anomalies & Verdicts", "What broke its own baseline"),
    ("plat", "🔌", "Platforms & Tracking", "Connections, pulls, tags"),
)


# ---------------------------------------------------------------------------
# SMALL KIT. One <table> element per table; the row-per-grid mistake made
# every row size its own columns and nothing lined up.
# ---------------------------------------------------------------------------
def table(heads, rows, empty="nothing here yet") -> str:
    if not rows:
        return f"<p class='mc-empty'>{e(empty)}</p>"
    h = "".join(f"<th>{e(x)}</th>" for x in heads)
    b = "".join("<tr>" + "".join(
        f"<td>{c if isinstance(c, str) and c.startswith('<') else e(c)}</td>"
        for c in row) + "</tr>" for row in rows)
    return ("<div class='mc-scroll'><table class='mc-tbl'>"
            f"<thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>")


def card(title, body, sub="") -> str:
    return ("<div class='mc-card'><p class='mc-ct'>" + e(title) + "</p>"
            + (f"<p class='mc-cs'>{e(sub)}</p>" if sub else "")
            + body + "</div>")


def kpi(label, value, of="") -> str:
    return ("<div class='mc-kpi'><b>" + value + "</b>"
            f"<span>{e(label)}</span>"
            + (f"<i>{e(of)}</i>" if of else "") + "</div>")


def _band(ctx) -> str:
    """The agent band. Same switch, same handlers, same honesty."""
    level = str(ctx.get("media_auto_level") or "unknown").lower()
    verd = ctx.get("media_verdicts") or {}
    n_v = len(verd.get("verdicts") or ())
    orders = [o for o in (ctx.get("media_orders") or ())
              if o.get("status") == "open"]
    blind = verd.get("blind") or []
    word = {"off": "OFF - pulls run, the agent stays silent",
            "observe": "OBSERVE 24/7 - judging, writing verdicts, "
                       "drafting nothing",
            "propose": "PROPOSE - verdicts become drafts in the queue",
            }.get(level, "switch state could not be read")

    def _lvl(lv, lab):
        on = " s3on" if level == lv else ""
        return (f"<button class='s3lvl{on}' "
                f"onclick=\"mediaAutoSet('{lv}',this)\">{lab}</button>")

    return ("<div class='s3band'>"
            "<div class='s3who'><p class='s3k'>Your media buying agent</p>"
            f"<p class='s3state'><b>{e(word)}</b></p>"
            f"<p class='s3sub'>{n_v} verdict(s) standing &middot; "
            f"{len(orders)} draft(s) waiting for your approval"
            + (f" &middot; blind on {len(blind)} rule(s)" if blind else "")
            + ". Nothing spends without your click; there is no auto-spend "
              "level at all.</p></div>"
            "<div class='s3cmds'>"
            "<button class='cta s3go' onclick=\"act('/ads/pull')\">"
            "Pull platforms now</button>"
            "<button class='cta' onclick=\"act('/ads/interlock')\">"
            "Rebuild interlock</button>"
            "<button class='cta a2draft' onclick='mediaOptimize(this)'>"
            "Run the rules now</button>"
            "<button class='cta' onclick='mcPost(\"/mediaos/propose\",{},"
            "this)'>Judge baselines now</button>"
            "</div>"
            "<div class='s3ladder' role='group' aria-label='media agent level'>"
            + _lvl("off", "OFF") + _lvl("observe", "OBSERVE")
            + _lvl("propose", "PROPOSE") + "</div></div>")


def _orders_board(ctx, limit=12) -> str:
    orders = list(ctx.get("media_orders") or ())
    if not orders:
        return ("<p class='mc-empty'>No orders in the queue. The agent "
                "writes one when a rule fires with full evidence; you "
                "approve it here before anything runs.</p>")
    rows = []
    for o in [x for x in orders if x.get("status") == "open"][:limit]:
        ev = o.get("evidence") or {}
        rows.append((
            e(o.get("code")), e(o.get("say"))[:110],
            e(f"{ev.get('metric', '')} vs {ev.get('threshold', '')}"),
            e(o.get("platform") or "-"),
            f"<button class='mc-btn' onclick=\"mediaApprove('{e(o.get('id'))}'"
            f",this)\">Approve</button> "
            f"<button class='mc-btn mc-go' onclick=\"mediaRun('{e(o.get('id'))}'"
            f",this)\">Execute</button>"))
    done = sum(1 for x in orders if x.get("status") != "open")
    return (table(("code", "what", "evidence", "platform", "decision"), rows,
                  "no open orders")
            + f"<p class='mc-note'>{done} order(s) already decided are on "
              f"the record.</p>")


# ---------------------------------------------------------------------------
# THE SCREENS
# ---------------------------------------------------------------------------
def s_cmd(r, ctx) -> str:
    try:
        sm = MF.summary(r)
    except Exception as ex:
        return card("Command Centre",
                    f"<p class='mc-empty'>the summary could not be computed: "
                    f"{e(type(ex).__name__)}</p>")
    cpa, roas = sm.get("cpa") or {}, sm.get("roas") or {}
    kpis = ("<div class='mc-kpis'>"
            + kpi("Spend, 30d", _n(sm.get("spend")))
            + kpi("Conversions", _n(sm.get("conversions")))
            + kpi("CPA", _n(cpa.get("value")), cpa.get("of") or "")
            + kpi("ROAS", _n(roas.get("value")), roas.get("of") or "")
            + kpi("Days with data", _n(sm.get("days_with_data")))
            + "</div>")
    act = sm.get("needs_action") or []
    watch = sm.get("watching") or []
    nj = sm.get("not_judged") or []
    acts = (table(("severity", "campaign", "what", "evidence"),
                  [(a["severity"].upper(), a["name"], a["means"],
                    a["evidence"][:120]) for a in (act + watch)[:10]],
            "No campaign has broken its own baseline. Quiet is a finding.")
            if (act or watch) else
            "<p class='mc-empty'>No campaign has broken its own baseline"
            + (f"; {len(nj)} cannot be judged yet for lack of history"
               if nj else "") + ". Quiet is a finding.</p>")
    disputed = sm.get("most_disputed") or []
    disp = table(("campaign", "spread", "why"),
                 [(d["name"], d["spread"], d["why"][:110])
                  for d in disputed],
                 "no conversion has an attributable touch yet")
    return (_band(ctx)
            + card("The numbers", kpis, "30 days, denominators attached")
            + card("Needs you today", acts)
            + card("Your approval queue", _orders_board(ctx))
            + card("Where the attribution models disagree most", disp,
                   "any single number you quote for these is a choice"))


def s_camps(r, ctx) -> str:
    camps = sorted(r.all("media_campaigns"),
                   key=lambda c: str(c.get("updated_at") or ""), reverse=True)
    rows = []
    for c in camps[:60]:
        w = MP.wizard_state(r, c.get("id"))
        rows.append((
            e(c.get("name")), e(c.get("provider") or "-"),
            e(c.get("objective")), e(c.get("state")),
            _money(c.get("budget_amount"), c.get("currency") or "EUR")
            + " " + e(str(c.get("budget_type") or "").lower()),
            f"{w['complete']}/{w['total']} steps",
            f"<button class='mc-btn' onclick=\"mcPost('/mediaos/validate',"
            f"{{campaign_id:'{e(c.get('id'))}'}},this)\">Validate</button> "
            f"<button class='mc-btn mc-go' onclick=\"mcTab('launch')\">"
            f"Pre-flight</button>"))
    body = table(("campaign", "platform", "objective", "state", "budget",
                  "wizard", "actions"), rows,
                 "No campaigns in the canonical model yet. Start one under "
                 "New Campaign; a sync will also pull what already runs on "
                 "a connected platform.")
    st = [s for s in (ctx.get("sync_runs") or ())][:1]
    sync = ("<button class='mc-btn' onclick=\"mcPost('/mediaos/sync',{},this)\">"
            "Sync with the platforms now</button>"
            "<p class='mc-note'>The database saying ACTIVE while the platform "
            "says PAUSED is the lie sync exists to catch."
            + (f" Last run: {e(str(st[0].get('completed_at'))[:16])}"
               if st else " No sync has run yet.") + "</p>")
    return card("Every campaign, with its real state", body) \
        + card("Synchronisation", sync)


def s_wiz(r, ctx) -> str:
    steps = "".join(
        f"<div class='mc-step'><b>{i + 1}</b><div><p>{e(lab)}</p>"
        f"<span>{e(why)}</span></div></div>"
        for i, (_k, lab, why) in enumerate(MP.WIZARD_STEPS))
    plats = []
    for p in M.PROVIDERS:
        live, why = M.Adapter(p).available()
        cannot = [o for o in M.OBJECTIVES if not M.supports(p, o)["ok"]]
        plats.append((e(p), "✓ connected" if live else "not connected",
                      e(M.LEVEL_WORDS.get(p, "ad group")),
                      e(", ".join(cannot) or "all objectives"), e(why)[:80]))
    cap = table(("platform", "status", "middle level is called",
                 "cannot do", "detail"), plats)
    objs = "".join(f"<option value='{e(o)}'>{e(o)}</option>"
                   for o in M.OBJECTIVES)
    kpis = "".join(f"<option value='{e(k)}'>{e(k)}</option>" for k in MP.KPIS)
    provs = "".join(f"<option value='{e(p)}'>{e(p)}</option>"
                    for p in M.PROVIDERS)
    form = (
        "<div class='mc-form'>"
        "<label>Name<input id='mc-cname' placeholder='Autumn leads DE'>"
        "</label>"
        f"<label>Objective<select id='mc-cobj'>{objs}</select></label>"
        f"<label>Primary KPI<select id='mc-ckpi'>{kpis}</select></label>"
        f"<label>Platform<select id='mc-cprov'>{provs}</select></label>"
        "<label>Budget type<select id='mc-cbt'>"
        "<option value='DAILY'>DAILY</option>"
        "<option value='LIFETIME'>LIFETIME</option></select></label>"
        "<label>Budget amount<input id='mc-cbud' type='number' min='0' "
        "placeholder='50'></label>"
        "<label>Start (optional)<input id='mc-cstart' type='date'></label>"
        "<label>End (optional)<input id='mc-cend' type='date'></label>"
        "<button class='mc-btn mc-go' onclick='mcNewCampaign(this)'>"
        "Save draft (steps 1-3)</button>"
        "<p class='mc-note'>Saving costs nothing. The draft appears under "
        "Campaigns; audience, creative and tracking attach below; launch "
        "happens in the Launch Centre behind the pre-flight.</p></div>")
    drafts = [c for c in r.all("media_campaigns")
              if c.get("state") in ("DRAFT", "VALIDATION_FAILED")]
    cont = []
    for c in drafts[:20]:
        w = MP.wizard_state(r, c.get("id"))
        nxt = w.get("next") or {}
        cont.append((e(c.get("name")), f"{w['complete']}/{w['total']}",
                     e(nxt.get("label") or "Review"),
                     e(nxt.get("why") or "everything is attached"),
                     _attach_controls(r, c)))
    contin = table(("draft", "done", "next step", "why", "attach"), cont,
                   "no drafts in progress")
    return (card("The eight steps",
                 f"<div class='mc-steps'>{steps}</div>",
                 "read from the record, so closing the tab loses nothing")
            + card("Step 2 first: what each platform can actually do", cap)
            + card("Start a draft", form)
            + card("Continue a draft", contin))


def _attach_controls(r, c) -> str:
    cid = e(c.get("id"))
    auds = "".join(f"<option value='{e(a.get('id'))}'>{e(a.get('name'))}"
                   f"</option>" for a in r.all("audiences")[:50])
    cres = "".join(f"<option value='{e(x.get('id'))}'>{e(x.get('name'))}"
                   f"</option>" for x in r.all("creatives")[:50])
    if not auds:
        auds = "<option value=''>no audiences yet - make one first</option>"
    if not cres:
        cres = "<option value=''>no creatives yet - make one first</option>"
    return (f"<select id='mc-aud-{cid}'>{auds}</select>"
            f"<select id='mc-cre-{cid}'>{cres}</select>"
            f"<input id='mc-lp-{cid}' placeholder='https://landing.page'>"
            f"<button class='mc-btn' onclick=\"mcAttach('{cid}',this)\">"
            f"Attach group + ad</button>")


def s_launch(r, ctx) -> str:
    cands = [c for c in r.all("media_campaigns")
             if c.get("state") in ("DRAFT", "READY", "SCHEDULED",
                                   "VALIDATION_FAILED")]
    if not cands:
        return card("Launch Centre",
                    "<p class='mc-empty'>Nothing is waiting to launch. "
                    "Draft a campaign under New Campaign first.</p>")
    out = []
    for c in cands[:12]:
        pf = MP.pre_flight(r, c.get("id"))
        lights = "".join(
            "<div class='mc-check mc-" + x["state"].lower() + "'>"
            + {"OK": "✓", "WARNING": "⚠", "ERROR": "✗"}[x["state"]]
            + f" <b>{e(x['name'])}</b><span>{e(x['detail'])[:100]}</span></div>"
            for x in pf["checks"])
        cid = e(c.get("id"))
        btns = (
            f"<button class='mc-btn mc-go' onclick=\"mcPost('/mediaos/launch',"
            f"{{campaign_id:'{cid}'}},this)\">Launch (queues an order)"
            f"</button> "
            f"<input id='mc-when-{cid}' type='datetime-local'> "
            f"<button class='mc-btn' onclick=\"mcLaunchAt('{cid}',this)\">"
            f"Schedule</button>"
            if pf["ok"] else
            f"<p class='mc-note'>blocked: {e(', '.join(pf['errors']))}. "
            f"Launch stays off until every blocking error clears.</p>")
        out.append(card(f"{c.get('name')} ({pf['level']})",
                        lights + btns, pf["message"][:160]))
    return ("<p class='mc-note'>A launch never talks to a platform from "
            "here. It queues ONE order in the media queue and waits behind "
            "the same approval tier as every other spend.</p>" + "".join(out))


def s_plan(r, ctx) -> str:
    alloc = MP.allocate(r, MF._live_budget(r) or 3000)
    arows = [(x["provider"], _n(x.get("amount")),
              f"{x.get('share', 0) * 100:.0f}%",
              _n(x.get("average_roas")), _n(x.get("marginal_roas")),
              x["why"][:120]) for x in (alloc.get("rows") or [])]
    atab = (table(("platform", "amount", "share", "avg ROAS",
                   "marginal ROAS", "why"), arows, alloc.get("message", ""))
            + f"<p class='mc-note'>{e(alloc.get('message', ''))}</p>")
    plans = [(p.get("objective"), _money(p.get("budget"), p.get("currency")),
              f"{p.get('period_start') or '?'} to {p.get('period_end') or '?'}",
              _n(p.get("target_cpa")), _n(p.get("target_roas")),
              e(p.get("kpi") or "-"))
             for p in r.all("media_plans")[:20]]
    ptab = table(("objective", "budget", "period", "target CPA",
                  "target ROAS", "KPI"), plans,
                 "no media plan saved yet")
    objs = "".join(f"<option value='{e(o)}'>{e(o)}</option>"
                   for o in M.OBJECTIVES)
    kpis = "".join(f"<option value='{e(k)}'>{e(k)}</option>" for k in MP.KPIS)
    form = ("<div class='mc-form'>"
            f"<label>Objective<select id='mc-pobj'>{objs}</select></label>"
            "<label>Budget<input id='mc-pbud' type='number' min='1' "
            "placeholder='3000'></label>"
            f"<label>KPI<select id='mc-pkpi'>{kpis}</select></label>"
            "<label>From<input id='mc-pfrom' type='date'></label>"
            "<label>To<input id='mc-pto' type='date'></label>"
            "<label>Target CPA<input id='mc-pcpa' type='number' min='0'>"
            "</label>"
            "<button class='mc-btn mc-go' onclick='mcSavePlan(this)'>"
            "Save the plan</button></div>")
    sim = ("<div class='mc-form'>"
           "<label>Budget now<input id='mc-snow' type='number' "
           "placeholder='3000'></label>"
           "<label>What if<input id='mc-swhat' type='number' "
           "placeholder='6000'></label>"
           "<button class='mc-btn' onclick='mcSimulate(this)'>Simulate"
           "</button></div><div id='mc-simout'><p class='mc-empty'>"
           "Ranges come back, never one number. With no history it says "
           "so instead of inventing a benchmark.</p></div>")
    return (card("Allocation on marginal return", atab,
                 "the next euro, not the average euro")
            + card("Saved plans", ptab)
            + card("New plan", form)
            + card("What if", sim))


def s_creat(r, ctx) -> str:
    # ONE pass for every creative's numbers, then a fatigue read per row.
    perf = {x["id"]: x for x in MC.creative_performance(r)}
    rows = []
    for c in r.all("creatives")[:40]:
        px = perf.get(c.get("id")) or {}
        fat = {}
        try:
            fat = MC.fatigue(r, c.get("id")) or {}
        except Exception:
            pass
        rows.append((e(c.get("name")), e(c.get("type") or "-"),
                     e(c.get("angle") or "-"), e(c.get("hook") or "-")[:40],
                     e(c.get("funnel_stage") or "-"),
                     _n(px.get("spend") or None),
                     _n(fat.get("score"), "not measured")))
    lib = table(("creative", "format", "angle", "hook", "stage", "spend",
                 "fatigue"), rows,
                "The library is empty. A creative is a concept with "
                "attributes, not a lone image; the attributes are what "
                "the engine learns from.")
    dims = "".join(f"<option value='{e(a)}'>{e(a)}</option>"
                   for a in MC.ATTRIBUTES)
    mx = {}
    try:
        mx = MC.matrix(r, "angle") or {}
    except Exception:
        pass
    verdict = (mx.get("verdict") or {})
    mtab = ("<div class='mc-form'><label>Dimension"
            f"<select id='mc-mdim' onchange='mcMatrix(this)'>{dims}</select>"
            "</label></div><div id='mc-mout'>"
            + table(("value", "spend", "conversions", "CPA"),
                    [(x.get("value"), _n(x.get("spend")),
                      _n(x.get("conversions")), _n(x.get("cpa")))
                     for x in (mx.get("rows") or [])[:12]],
                    "nothing measured per angle yet")
            + f"<p class='mc-note'>{e(verdict.get('message', ''))}</p></div>")
    learned = {}
    try:
        learned = MC.learn(r) or {}
    except Exception:
        pass
    lrn = ("<p class='mc-note'>" + e(learned.get("message", "")) + "</p>"
           + table(("attribute", "finding"),
                   [(f.get("attribute") or f.get("dimension") or "-",
                     (f.get("message") or f.get("finding") or "")[:130])
                    for f in (learned.get("findings") or [])[:10]],
                   "nothing has earned a verdict yet"))
    types = "".join(f"<option value='{e(t)}'>{e(t)}</option>"
                    for t in MC.CREATIVE_TYPES)
    stages = "".join(f"<option value='{e(s)}'>{e(s)}</option>"
                     for s in MC.FUNNEL_STAGES)
    form = ("<div class='mc-form'>"
            "<label>Name<input id='mc-crname'></label>"
            f"<label>Format<select id='mc-crtype'>{types}</select></label>"
            "<label>Concept<input id='mc-crconcept' "
            "placeholder='Save 30%'></label>"
            "<label>Angle<input id='mc-crangle' "
            "placeholder='pain-point'></label>"
            "<label>Hook<input id='mc-crhook' "
            "placeholder='Still booking by phone?'></label>"
            "<label>Persona<input id='mc-crpersona' "
            "placeholder='practice manager'></label>"
            "<label>CTA<input id='mc-crcta' placeholder='Book a call'>"
            "</label>"
            f"<label>Funnel stage<select id='mc-crstage'>{stages}</select>"
            "</label>"
            "<label>Headline<input id='mc-crhead'></label>"
            "<label>Primary text<input id='mc-crtext'></label>"
            "<button class='mc-btn mc-go' onclick='mcNewCreative(this)'>"
            "Save + publish v1</button>"
            "<p class='mc-note'>Versions are immutable: publishing again "
            "appends v2 and v1 stays measurable.</p></div>")
    return (card("The library", lib)
            + card("The matrix: attributes, not just creatives", mtab,
                   "verdicts refuse to speak below the sample floor")
            + card("What the engine has learned", lrn)
            + card("New creative", form))


def s_aud(r, ctx) -> str:
    rows = []
    try:
        rows = MC.audience_rows(r)
    except Exception:
        rows = []
    atab = table(("audience", "type", "partial on", "size"),
                 [(x.get("name"), x.get("type"),
                   ", ".join(x.get("partial") or ()) or "expressed fully "
                                                        "everywhere",
                   _n(x.get("size"), "not measured")) for x in rows[:40]],
                 "No audiences yet. Define one provider-neutrally; the "
                 "mapper tells you what each platform drops.")
    types = "".join(f"<option value='{e(t)}'>{e(t)}</option>"
                    for t in MC.AUDIENCE_TYPES)
    fields = ", ".join(sorted(MC.TARGET_FIELDS)[:12]) + " ..."
    form = ("<div class='mc-form'>"
            "<label>Name<input id='mc-aname'></label>"
            f"<label>Type<select id='mc-atype'>{types}</select></label>"
            "<label>Definition (JSON)<textarea id='mc-adef' rows='3' "
            "placeholder='{\"countries\": [\"DE\"], "
            "\"job_titles\": [\"practice manager\"]}'></textarea></label>"
            "<button class='mc-btn mc-go' onclick='mcNewAudience(this)'>"
            "Save audience</button>"
            f"<p class='mc-note'>Fields any platform can target: {e(fields)}. "
            "A field none of them understands is refused at save time, with "
            "the list.</p></div>")
    return card("Audiences", atab) + card("New audience", form)


def s_perf(r, ctx) -> str:
    blocks = []
    for grain in ("DAILY", "WEEKLY", "MONTHLY"):
        ro = MF.rollup(r, grain=grain)
        tot = ro["totals"]
        rows = [(x["bucket"], x["name"], _n(x.get("spend")),
                 _n(x.get("impressions")), _n(x.get("clicks")),
                 _n((x.get("ctr") or {}).get("value")),
                 _n(x.get("conversions")),
                 _n((x.get("cpa") or {}).get("value")),
                 _n((x.get("roas") or {}).get("value")))
                for x in ro["rows"][-30:]]
        on = " mc-on" if grain == "DAILY" else ""
        blocks.append(
            f"<div class='mc-grain{on}' id='mc-grain-{grain}'>"
            + table(("bucket", "campaign", "spend", "impr", "clicks",
                     "CTR%", "conv", "CPA", "ROAS"), rows, ro["message"])
            + "<p class='mc-note'>totals: spend " + _n(tot.get("spend"))
            + " &middot; CPA " + _n((tot.get("cpa") or {}).get("value"))
            + " (" + e((tot.get("cpa") or {}).get("of") or "")
            + ") &middot; ROAS " + _n((tot.get("roas") or {}).get("value"))
            + "</p></div>")
    switch = "".join(
        f"<button class='mc-btn{' mc-go' if g == 'DAILY' else ''}' "
        f"onclick=\"mcGrain('{g}',this)\">{g}</button>"
        for g in ("DAILY", "WEEKLY", "MONTHLY"))
    cmpres = MF.compare(r)
    crows = [(m["metric"], _n(m.get("before")), _n(m.get("now")),
              (f"{m['change']:+.1f}%" if m.get("change") is not None
               else "--"), m["why"][:80]) for m in cmpres["moves"]]
    ctab = table(("metric", "last 7d before", "this 7d", "change", "why"),
                 crows)
    rec = MF.reconcile(r)
    rtab = (table(("campaign", "platform claims", "engine observed", "gap",
                   "why"),
                  [(x["name"], x["platform_claims"], x["engine_observed"],
                    x["gap"], x["why"][:110]) for x in rec["rows"][:15]],
                  rec["message"])
            + f"<p class='mc-note'>{e(rec['message'])}</p>")
    return (card("Rollups", f"<div class='mc-form'>{switch}</div>"
                 + "".join(blocks),
                 "the same numbers at whichever grain the question needs")
            + card("This week against last week", ctab)
            + card("Platform claims vs what this engine observed", rtab,
                   "neither number is corrected into the other"))


def s_attr(r, ctx) -> str:
    sp = MF.model_spread(r)
    stab = table(("campaign",) + MF.ATTRIBUTION_MODELS + ("spread", "why"),
                 [tuple([x["name"]] + [_n(x.get(m)) for m in
                                       MF.ATTRIBUTION_MODELS]
                        + [x["spread"], x["why"][:90]])
                  for x in sp["rows"][:20]], sp["message"])
    lt = MF.attribute(r, model="last_touch")
    note = ("<p class='mc-note'>" + e(lt.get("message", "")) + "</p>"
            "<p class='mc-note'>" + e(lt.get("convention", "")) + "</p>")
    return card("Five models, side by side", stab + note,
                "the disagreement is the information")


def s_anom(r, ctx) -> str:
    sc = MF.scan(r, save=False)
    arows = [(a["severity"].upper(), a["name"], a["type"],
              f"{_n(a.get('current'))} vs {_n(a.get('baseline'))} "
              f"({_n(a.get('ratio'))}x)",
              a["evidence"][:110]) for a in sc["anomalies"][:20]]
    atab = (table(("severity", "campaign", "what", "numbers", "evidence"),
                  arows, "No campaign has broken its own baseline.")
            + f"<p class='mc-note'>{e(sc['message'])}</p>")
    nj = table(("campaign", "why it is not judged"),
               [(x["name"], x["why"]) for x in sc["not_judged"][:10]],
               "every campaign has enough history to judge")
    btn = ("<div class='mc-form'>"
           "<button class='mc-btn mc-go' onclick=\"mcPost('/mediaos/propose'"
           ",{},this)\">Turn anomalies into verdicts</button>"
           "<p class='mc-note'>Each verdict lands in the order queue below "
           "with metric, threshold, window and source, and waits for your "
           "click. There is no auto-spend level at all.</p></div>")
    return (card("What broke its own baseline", atab)
            + card("Refused for lack of history", nj,
                   "a red badge on 3 days of data is a coin toss")
            + btn
            + card("The order queue", _orders_board(ctx)))


def s_plat(r, ctx, legacy_campaigns="", legacy_tracking="") -> str:
    rows = []
    for p in M.PROVIDERS:
        live, why = M.Adapter(p).available()
        rows.append((e(p), "✓ live" if live else "not connected",
                     e(why)[:110]))
    ptab = (table(("platform", "status", "detail"), rows)
            + "<div class='mc-form'>"
              "<button class='mc-btn' onclick=\"nav('map')\">Connect a "
              "platform (Connect board)</button>"
              "<button class='mc-btn' onclick='runAds()'>Pull Google Ads "
              "data</button>"
              "<button class='mc-btn' onclick='runInterlock()'>Rebuild "
              "cross-channel</button>"
              "<button class='mc-btn' onclick='openEcon()'>Set unit "
              "economics</button></div>"
              "<p class='mc-note'>Keys are entered on the Connect board "
              "only. Nothing here reads or shows a credential; the screen "
              "flips live the moment the connector authorises.</p>")
    caps = table(("platform",) + M.OBJECTIVES,
                 [tuple([row["provider"]]
                        + [(e(row[o]) if row.get(o) else "cannot")
                           for o in M.OBJECTIVES])
                  for row in M.capability_table()])
    out = (card("Connections", ptab)
           + card("What each platform can do", caps,
                  "three answers exist: yes, no, and not connected"))
    if legacy_campaigns:
        out += card("Drafts from the media agent", legacy_campaigns,
                    "the AI buyer's draft flow, unchanged wires")
    if legacy_tracking:
        out += card("Website tracking (GA4 / Search Console)",
                    legacy_tracking)
    return out


# ---------------------------------------------------------------------------
# ASSEMBLY
# ---------------------------------------------------------------------------
def build_panels(r, ctx, legacy_campaigns="", legacy_tracking="") -> dict:
    makers = {"cmd": lambda: s_cmd(r, ctx),
              "camps": lambda: s_camps(r, ctx),
              "wiz": lambda: s_wiz(r, ctx),
              "launch": lambda: s_launch(r, ctx),
              "plan": lambda: s_plan(r, ctx),
              "creat": lambda: s_creat(r, ctx),
              "aud": lambda: s_aud(r, ctx),
              "perf": lambda: s_perf(r, ctx),
              "attr": lambda: s_attr(r, ctx),
              "anom": lambda: s_anom(r, ctx),
              "plat": lambda: s_plat(r, ctx, legacy_campaigns,
                                     legacy_tracking)}
    out = {}
    for tid, _i, label, _q in SCREENS:
        try:
            out[tid] = makers[tid]()
        except Exception as ex:      # a broken screen admits it, never blanks
            log.exception("media screen %s failed", tid)
            out[tid] = (f"<div class='mc-card'><p class='mc-ct'>{e(label)}"
                        f"</p><p class='mc-empty'>this screen could not be "
                        f"drawn: {e(type(ex).__name__)}: {e(str(ex)[:120])}"
                        f"</p></div>")
    return out


def section(ctx, legacy_campaigns="", legacy_tracking="") -> str:
    """The whole Media Buying OS section for the assembled dashboard."""
    ctx = dict(ctx or {})
    r = None
    try:
        import content_engine_api as A
        r = M.repo(A.get_store())
    except Exception as ex:
        log.warning("media center has no repo: %s", ex)
    if r is None:
        panels = {tid: ("<div class='mc-card'><p class='mc-ct'>"
                        + e(label) + "</p><p class='mc-empty'>the store is "
                        "not reachable, so this screen has nothing true to "
                        "show</p></div>")
                  for tid, _i, label, _q in SCREENS}
        panels["plat"] = s_plat_safe(ctx, legacy_campaigns, legacy_tracking)
    else:
        panels = build_panels(r, ctx, legacy_campaigns, legacy_tracking)
    nav = "".join(
        f"<button class='mc-tab{' mc-on' if i == 0 else ''}' "
        f"id='mc-tab-{tid}' onclick=\"mcTab('{tid}')\">"
        f"<span>{icon}</span>{e(label)}<i>{e(q)}</i></button>"
        for i, (tid, icon, label, q) in enumerate(SCREENS))
    body = "".join(
        f"<div class='mc-panel{' mc-on' if i == 0 else ''}' "
        f"id='mc-panel-{tid}'>{panels.get(tid, '')}</div>"
        for i, (tid, _i2, _l, _q) in enumerate(SCREENS))
    return ("<div class='mc-root'>" + CSS + JS
            + f"<div class='mc-tabs'>{nav}</div>" + body + "</div>")


def s_plat_safe(ctx, legacy_campaigns="", legacy_tracking="") -> str:
    out = ""
    if legacy_campaigns:
        out += card("Drafts from the media agent", legacy_campaigns)
    if legacy_tracking:
        out += card("Website tracking", legacy_tracking)
    return out or "<p class='mc-empty'>nothing to show without the store</p>"


CSS = """<style>
.mc-root{--mc-ln:var(--line,#1B2640);--mc-mut:var(--mut,#8FA0C8);
--mc-ink:var(--ink,#E8EEFF);--mc-card:var(--s1,#0E1526);
--mc-go:var(--blue,#4C8DFF);font-size:13px}
.mc-tabs{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 14px}
.mc-tab{display:flex;flex-direction:column;align-items:flex-start;gap:2px;
background:var(--mc-card);border:1px solid var(--mc-ln);border-radius:9px;
padding:7px 11px;color:var(--mc-mut);cursor:pointer;min-width:120px;
text-align:left}
.mc-tab i{font-style:normal;font-size:10px;opacity:.65}
.mc-tab.mc-on{color:var(--mc-ink);border-color:var(--mc-go)}
.mc-panel{display:none}.mc-panel.mc-on{display:block}
.mc-card{background:var(--mc-card);border:1px solid var(--mc-ln);
border-radius:11px;padding:13px 15px;margin:0 0 12px}
.mc-ct{font-weight:700;color:var(--mc-ink);margin:0 0 2px}
.mc-cs{color:var(--mc-mut);font-size:11px;margin:0 0 8px}
.mc-empty{color:var(--mc-mut);font-size:12px;margin:6px 0}
.mc-note{color:var(--mc-mut);font-size:11px;margin:7px 0 0}
.mc-kpis{display:flex;flex-wrap:wrap;gap:10px}
.mc-kpi{display:flex;flex-direction:column;background:rgba(76,141,255,.06);
border:1px solid var(--mc-ln);border-radius:9px;padding:9px 13px;
min-width:110px}
.mc-kpi b{font-size:18px;font-variant-numeric:tabular-nums;
color:var(--mc-ink)}
.mc-kpi span{font-size:10px;color:var(--mc-mut);text-transform:uppercase;
letter-spacing:.4px}
.mc-kpi i{font-style:normal;font-size:10px;color:var(--mc-mut)}
.mc-scroll{overflow-x:auto}
.mc-tbl{border-collapse:collapse;width:100%;font-size:12px}
.mc-tbl th{color:var(--mc-mut);text-transform:uppercase;font-size:10px;
letter-spacing:.4px;text-align:left;padding:5px 9px;
border-bottom:1px solid var(--mc-ln)}
.mc-tbl td{padding:6px 9px;border-bottom:1px solid var(--mc-ln);
color:var(--mc-ink);font-variant-numeric:tabular-nums;
vertical-align:top}
.mc-btn{background:none;border:1px solid var(--mc-ln);border-radius:7px;
color:var(--mc-ink);padding:4px 10px;font-size:12px;cursor:pointer;
margin:2px 4px 2px 0}
.mc-btn.mc-go{border-color:var(--mc-go);color:var(--mc-go)}
.mc-form{display:flex;flex-wrap:wrap;gap:9px;align-items:flex-end}
.mc-form label{display:flex;flex-direction:column;gap:3px;font-size:11px;
color:var(--mc-mut)}
.mc-form input,.mc-form select,.mc-form textarea{background:rgba(0,0,0,.25);
border:1px solid var(--mc-ln);border-radius:7px;color:var(--mc-ink);
padding:6px 9px;font-size:12px;min-width:130px}
.mc-steps{display:flex;flex-wrap:wrap;gap:9px}
.mc-step{display:flex;gap:8px;align-items:flex-start;
border:1px solid var(--mc-ln);border-radius:9px;padding:8px 11px;
min-width:170px}
.mc-step b{color:var(--mc-go)}
.mc-step p{margin:0;color:var(--mc-ink);font-size:12px}
.mc-step span{color:var(--mc-mut);font-size:10px}
.mc-check{display:flex;gap:7px;align-items:baseline;font-size:12px;
padding:3px 0;color:var(--mc-ink)}
.mc-check span{color:var(--mc-mut);font-size:11px}
.mc-check.mc-error{color:#FF6B93}.mc-check.mc-warning{color:#F5B14C}
.mc-check.mc-ok{color:#3FD98B}
.mc-grain{display:none}.mc-grain.mc-on{display:block}
</style>"""


JS = """<script>
/* The agent-band handlers live HERE now. The old media screens module
   defined them and it is gone; a button calling a function nobody defines
   is a dead control that looks alive, which is the worst kind. */
async function mediaAutoSet(level,btn){try{
var r=await fetch('/media/auto',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({level:level})});var j=await r.json();
toast((j&&(j.message||j.error))||('level '+level),j&&j.ok!==false);
if(j&&j.ok!==false){document.querySelectorAll('.s3lvl').forEach(
function(x){x.classList.remove('s3on');
if(x.textContent.toLowerCase().indexOf(level)===0)x.classList.add('s3on');});}}
catch(e){toast('could not reach the engine; the switch is unchanged',
false);}}
async function mediaOptimize(btn){var lab=btn?btn.textContent:'';
if(btn){btn.disabled=true;btn.textContent='Judging\\u2026';}
try{var r=await fetch('/media/optimize',{method:'POST'});
var j=await r.json();toast((j&&j.message)||'ran',j&&j.ok!==false);}
catch(e){toast('could not reach the engine',false);}
if(btn){btn.disabled=false;btn.textContent=lab;}}
async function mediaApprove(id,btn){try{
var r=await fetch('/media/approve',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({id:id})});var j=await r.json();
toast((j&&j.message)||'approved',j&&j.ok!==false);
if(btn)btn.textContent='Approved';}catch(e){
toast('could not reach the engine',false);}}
async function mediaRun(id,btn){var lab=btn?btn.textContent:'';
if(btn){btn.disabled=true;btn.textContent='Executing\\u2026';}
try{var r=await fetch('/media/run-orders',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({ids:[id]})});var j=await r.json();
toast((j&&j.message)||'ran',j&&j.ok!==false);}catch(e){
toast('could not reach the engine',false);}
if(btn){btn.disabled=false;btn.textContent=lab;}}
async function gtmDraft(name,btn){var lab=btn?btn.textContent:'';
if(btn){btn.disabled=true;btn.textContent='Drafting\\u2026';}
try{var r=await fetch('/gtm/draft',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({name:name})});var j=await r.json();
toast((j&&(j.result||j.message))||'drafted',j&&j.ok!==false);}
catch(e){toast('could not reach the engine',false);}
if(btn){btn.disabled=false;btn.textContent=lab;}}
function mcTab(t){document.querySelectorAll('.mc-panel').forEach(function(x){
x.classList.remove('mc-on');});
document.querySelectorAll('.mc-tab').forEach(function(x){
x.classList.remove('mc-on');});
var p=document.getElementById('mc-panel-'+t);if(p)p.classList.add('mc-on');
var b=document.getElementById('mc-tab-'+t);if(b)b.classList.add('mc-on');}
function mcGrain(g,btn){document.querySelectorAll('.mc-grain').forEach(
function(x){x.classList.remove('mc-on');});
var el=document.getElementById('mc-grain-'+g);if(el)el.classList.add('mc-on');
if(btn){btn.parentNode.querySelectorAll('.mc-btn').forEach(function(x){
x.classList.remove('mc-go');});btn.classList.add('mc-go');}}
async function mcPost(url,body,btn){var lab=btn?btn.textContent:'';
if(btn){btn.disabled=true;btn.textContent='Working\\u2026';}
try{var r=await fetch(url,{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify(body||{})});var j=await r.json();
toast((j&&(j.message||j.error))||'done',j&&j.ok!==false);
if(j&&j.ok!==false)setTimeout(function(){location.reload();},900);}
catch(e){toast('could not reach the engine; nothing changed',false);}
if(btn){btn.disabled=false;btn.textContent=lab;}}
function mcV(id){var el=document.getElementById(id);
return el?el.value:'';}
function mcNewCampaign(btn){mcPost('/mediaos/campaign',{
name:mcV('mc-cname'),objective:mcV('mc-cobj'),kpi:mcV('mc-ckpi'),
provider:mcV('mc-cprov'),budget_type:mcV('mc-cbt'),
budget_amount:mcV('mc-cbud'),start_at:mcV('mc-cstart'),
end_at:mcV('mc-cend')},btn);}
function mcAttach(cid,btn){mcPost('/mediaos/attach',{campaign_id:cid,
audience_id:mcV('mc-aud-'+cid),creative_id:mcV('mc-cre-'+cid),
landing_page_url:mcV('mc-lp-'+cid)},btn);}
function mcLaunchAt(cid,btn){mcPost('/mediaos/launch',{campaign_id:cid,
scheduled_at:mcV('mc-when-'+cid)},btn);}
function mcSavePlan(btn){mcPost('/mediaos/plan',{objective:mcV('mc-pobj'),
budget:mcV('mc-pbud'),kpi:mcV('mc-pkpi'),period_start:mcV('mc-pfrom'),
period_end:mcV('mc-pto'),target_cpa:mcV('mc-pcpa')},btn);}
async function mcSimulate(btn){var lab=btn?btn.textContent:'';
if(btn){btn.disabled=true;btn.textContent='Working\\u2026';}
try{var r=await fetch('/mediaos/simulate',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({budget:mcV('mc-swhat'),
compare_to:mcV('mc-snow')})});var j=await r.json();
var out=document.getElementById('mc-simout');
if(out){if(j&&j.ok===false){out.innerHTML='<p class="mc-empty">'
+(j.message||'no answer')+'</p>';}else{
var h='<p class="mc-note">'+(j.message||'')+'</p>';
(j.scenarios||[]).forEach(function(s){var c=s.conversions||{};
h+='<p class="mc-note"><b>'+s.label+'</b> '+s.budget
+': conversions '+(c.low!=null?c.low+' to '+c.high:'no range')
+' ('+(s.band||'')+')</p>';});
h+='<p class="mc-empty">'+(j.caveat||'')+'</p>';out.innerHTML=h;}}}
catch(e){toast('could not reach the engine',false);}
if(btn){btn.disabled=false;btn.textContent=lab;}}
function mcNewCreative(btn){mcPost('/mediaos/creative',{
name:mcV('mc-crname'),type:mcV('mc-crtype'),concept:mcV('mc-crconcept'),
angle:mcV('mc-crangle'),hook:mcV('mc-crhook'),persona:mcV('mc-crpersona'),
cta:mcV('mc-crcta'),funnel_stage:mcV('mc-crstage'),
headline:mcV('mc-crhead'),primary_text:mcV('mc-crtext'),publish:true},btn);}
function mcNewAudience(btn){var def={};
try{def=JSON.parse(mcV('mc-adef')||'{}');}catch(e){
toast('the definition is not valid JSON; nothing was saved',false);return;}
mcPost('/mediaos/audience',{name:mcV('mc-aname'),type:mcV('mc-atype'),
definition:def},btn);}
async function mcMatrix(sel){try{var r=await fetch('/mediaos/matrix',{
method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({dimension:sel.value})});var j=await r.json();
var out=document.getElementById('mc-mout');
if(out)out.innerHTML='<p class="mc-note">'+((j&&j.message)||'')+'</p>';}
catch(e){toast('could not reach the engine',false);}}
</script>"""
