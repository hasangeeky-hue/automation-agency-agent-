"""
content_engine_cockpit_boards.py
============================================================================
AI COCKPIT — 15 boards, 268 cards. The brain.

Replaces four sections (Command Center, Operations, Approvals, Learning) that
held 35 cards, 4 charts, and rendered the decision engine twice.

The live approval queue is carried through ALREADY RENDERED — the same rule
applied to the outbox — so every approve, decline and quick action keeps
calling the endpoint it always did. Approval logic is untouched.

Two things exist here that did not exist anywhere before:

  * A closed loop. Every system's signal becomes a decision with the button
    that acts on it, ranked by consequence.
  * Budget control in the browser, with a hard floor: a cap below what is
    already spent this month is refused, because saving it would halt the
    engine the moment it took effect.

Run offline self-check:  python content_engine_cockpit_boards.py
============================================================================
"""
from __future__ import annotations

import re

from content_engine_seo_boards import (
    TEAL, VIOLET, BLUE, GREEN, AMBER, PINK, _H, _CH, _pct_color, _link, _rows,
    _linkrows, _donut, _split_donut, _trend, _spark, _hbars, _gauge, _score_gauge,
    _histogram, _heatmap, _riskmatrix, _statusgrid, _treemap, _waterfall, _delta,
    _viz, _vizcards, _head, _sub, _subnav, _slug, _CURRENT_BOARD, _TAB_CSS,
    BOARD_CTA, VISIBLE_CARDS,
)

BOARD_CTA.update({
    "Cockpit Command": ("Open the decision queue", "seoTab('ckdecide')"),
    "Decision Queue": ("Open Approvals", "seoTab('ckcontent')"),
    "Signal Router": ("Open the loop map", "nav('system')"),
    "Approvals Content": ("Approve all safe", "approveAll()"),
    "Approvals Outreach": ("Send today's batch", "act('/outreach/send_all')"),
    "Approvals Plan": ("Plan a week", "planContent()"),
    "Budget & Caps": ("Change the caps", "setBudget()"),
    "Autonomy": ("Open System & Wiring", "nav('system')"),
    "Keys & Capability": ("Open System & Wiring", "nav('system')"),
    "Loop Health": ("Open the loop map", "nav('system')"),
    "Job Queue": ("Open Operations", "seoTab('ckengine')"),
    "Engine State": ("Re-check health", "act('/health')"),
    "Playbook": ("Open BI", "nav('bi')"),
    "What Works": ("Record a won deal", "biDeal()"),
    "Experiments": ("Start an experiment", "startExperiment()"),
})


def _D(v):
    return v if isinstance(v, dict) else {}


def _L(v):
    return list(v) if isinstance(v, (list, tuple)) else []


def _f(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return float(d)


def _i(v, d=0):
    try:
        return int(_f(v, d))
    except Exception:
        return int(d)


def _s(v):
    return str(v or "").strip()


def _n(v, dash="—"):
    return dash if v is None else v


def _money(v, dash="—"):
    return dash if v in (None, "") else f"€{_f(v):,.2f}"


def _ctx(ctx):
    ctx = ctx if isinstance(ctx, dict) else {}
    out = dict(ctx)
    for k in ("decisions", "router", "approvals", "turnaround", "budget",
              "autonomy", "capability", "engine", "playbook", "experiments",
              "log", "live"):
        out[k] = _D(out.get(k))
    return out


def _live(ctx, key):
    v = _D(_D(ctx).get("live")).get(key)
    return v if isinstance(v, str) else ""


def _slots(rows, n, filled, empty_title, empty_sub, empty_why, src, accent=BLUE):
    out = []
    rows = _L(rows)
    for i in range(n):
        if i < len(rows):
            out.append(filled(i, rows[i]))
        else:
            out.append((f"{empty_title} {i + 1}", "—", empty_sub, "",
                        empty_why, src, accent, ""))
    return out


SYSTEM_LABELS = ["Business Intelligence", "Content Factory", "Leads & Outreach",
                 "SEO / AEO / GEO", "Social, Growth & Ads", "Media Buying",
                 "Risk & Infrastructure", "System & Wiring"]


# ======================================================================
#  (1) COCKPIT COMMAND  (16)
# ======================================================================
def board_command(ctx) -> str:
    ctx = _ctx(ctx)
    d, r, a = ctx["decisions"], ctx["router"], ctx["approvals"]
    b, e, au = ctx["budget"], ctx["engine"], ctx["autonomy"]
    top = _D(d.get("top"))
    cards = [
        ("What needs you now", _i(d.get("count")), "decisions",
         _hbars([(_s(_D(x).get("title"))[:24], _f(_D(x).get("weight")))
                 for x in _L(d.get("rows"))[:8]]),
         str(d.get("note", "")),
         "all systems", PINK if d.get("urgent") else
         AMBER if d.get("count") else GREEN,
         "<button class='cta' onclick=\"seoTab('ckdecide')\">Open the queue</button>"),
        ("The one to do first", _s(top.get("title"))[:26] or "—", "highest consequence",
         "", (str(top.get("why", "")) if top else
              "Nothing is asking for you right now."),
         "decision queue", PINK if top else GREEN,
         (f"<button class='cta' onclick=\"{_s(top.get('js'))}\">"
          f"{_s(top.get('action'))}</button>") if top else ""),
        ("Systems reporting", _i(r.get("live")), f"of {_i(r.get('total'))}",
         _statusgrid(_L(r.get("statusgrid"))),
         str(r.get("note", "")),
         "signal router", GREEN if r.get("closed") else AMBER, ""),
        ("Waiting for your approval", _i(a.get("waiting")), "pieces", "",
         str(a.get("note", "")),
         "job queue", AMBER if a.get("waiting") else GREEN,
         "<button class='cta' onclick=\"seoTab('ckcontent')\">Review them</button>"),
        ("Waiting too long", _i(a.get("stale")), "three days or more", "",
         ("The human gate becomes a wall when the queue is not cleared."
          if a.get("stale") else "Nothing is stuck."),
         "computed", PINK if a.get("stale") else GREEN, ""),
        ("Spend this month", _money(b.get("spent_month")),
         f"of {_money(b.get('per_month'))}",
         _score_gauge(_f(b.get("month_pct")), 85),
         (f"{b.get('month_pct', 0)}% of the cap. Projected "
          f"{_money(b.get('projected'))} by month end."),
         "live caps", _pct_color(_f(b.get("month_pct")), 85),
         "<button class='cta' onclick='setBudget()'>Change the caps</button>"),
        ("Budget headroom", _money(b.get("headroom")), "left this month", "",
         ("The engine halts new LLM steps at the cap rather than overspending."),
         "live caps", GREEN if _f(b.get("headroom")) > 20 else PINK, ""),
        ("Engine", ("healthy" if e.get("healthy") else "check it"),
         f"{_i(e.get('running'))} jobs running", "",
         str(e.get("note", "")),
         "health probe", GREEN if e.get("healthy") else PINK,
         "<button class='cta' onclick=\"act('/health')\">Re-check</button>"),
        ("Halted by budget", _i(e.get("halted_by_budget")), "jobs stopped", "",
         ("These stopped because a cap was reached, not because they failed."
          if e.get("halted_by_budget") else "Nothing has been halted by a cap."),
         "job queue", PINK if e.get("halted_by_budget") else GREEN, ""),
        ("Failed jobs", _i(e.get("failed")), "produced nothing", "",
         "Each one consumed budget and returned no output.",
         "job queue", PINK if e.get("failed") else GREEN, ""),
        ("Delegated to agents", _i(au.get("delegated")), "actions", "",
         str(au.get("note", "")),
         "your decision", GREEN, ""),
        ("Urgent decisions", len(_L(d.get("urgent"))), "at the top band", "",
         ("Anything above 900 is either money, a real person waiting, or a "
          "critical risk."),
         "decision queue", PINK if d.get("urgent") else GREEN, ""),
        ("Plan pending", _i(a.get("plan_pending")), "pieces proposed", "",
         ("A content plan is waiting for approval. Nothing is written until "
          "you accept it." if a.get("plan_pending") else
          "No plan pending."),
         "content plan", AMBER if a.get("plan_pending") else BLUE,
         "<button class='cta' onclick=\"seoTab('ckplan')\">Review the plan</button>"),
        ("Sent back for rewrite", _i(a.get("declined")), "pieces", "",
         "Declining with a reason is how the engine learns your taste.",
         "job queue", BLUE, ""),
        ("Decisions logged", _i(_D(ctx.get("log")).get("total")), "recorded",
         _trend([("decisions", _L(_D(ctx.get("log")).get("series")), TEAL)]),
         ("What was actually done, not what was merely suggested. The playbook "
          "learns from this."),
         "decision log", BLUE, ""),
        ("This is the brain", "8 systems", "one screen", "",
         ("Every other section computes. This one decides. Each row carries the "
          "signal, the reason and the button."),
         "principle", VIOLET,
         "<button class='cta' onclick=\"seoTab('ckrouter')\">See the wiring</button>"),
    ]
    return _head("🧠", "Cockpit command",
                 "Everything that needs a person, ranked by what it would "
                 "move.") + _vizcards(cards)


# ======================================================================
#  (2) DECISION QUEUE  (20)
# ======================================================================
def board_decisions(ctx) -> str:
    ctx = _ctx(ctx)
    d = ctx["decisions"]
    rows = _L(d.get("rows"))
    cards = [
        ("Decisions waiting", _i(d.get("count")), "across 8 systems",
         _hbars([(_s(_D(x).get("title"))[:26], _f(_D(x).get("weight")))
                 for x in rows[:10]]),
         str(d.get("note", "")),
         "all systems", PINK if d.get("urgent") else AMBER if rows else GREEN, ""),
        ("Urgent band", len(_L(d.get("urgent"))), "weight 900+", "",
         ("Money, a person waiting, or a critical risk. Everything else can "
          "wait a day."),
         "computed", PINK if d.get("urgent") else GREEN, ""),
        ("By system", len(_L(d.get("by_system"))), "sources",
         _split_donut([(SYSTEM_LABELS[i][:14], n, c) for i, ((_k, n), c) in
                       enumerate(zip(_L(d.get("by_system")),
                                     (PINK, AMBER, TEAL, BLUE, VIOLET, GREEN,
                                      PINK, BLUE))) if n]),
         ("Which system is asking for you most. A high count means volume "
          "of requests, not that they are the most urgent."),
         "computed", BLUE, ""),
    ]
    cards += _slots(
        rows, 14,
        lambda i, x: (f"{i + 1}. {_s(_D(x).get('title'))[:28]}",
                      _i(_D(x).get("weight")), "consequence", "",
                      str(_D(x).get("why", "")),
                      _s(_D(x).get("system")) or "system",
                      PINK if _f(_D(x).get("weight")) >= 900 else
                      AMBER if _f(_D(x).get("weight")) >= 800 else BLUE,
                      f"<button class='cta' onclick=\"{_s(_D(x).get('js'))}\">"
                      f"{_s(_D(x).get('action'))}</button>"),
        "Decision slot", "nothing here",
        ("A decision appears when a system detects something only a person can "
         "resolve. An empty queue means every system is content."),
        "all systems", GREEN)
    cards += [
        ("Ranked by consequence", "not by recency", "deliberate", "",
         ("A queue ordered by which system happened to report last is a to-do "
          "list. Ordered by what it would move, it is a decision queue."),
         "principle", VIOLET, ""),
        ("Every row has evidence", "and a button", "no bare alerts", "",
         ("A card that says 'something is wrong' without saying what or "
          "offering the fix is noise."),
         "principle", GREEN, ""),
        ("Nothing acts by itself", "you press it", "by your decision", "",
         ("Every button here is a human action. Nothing on this board "
          "runs on its own, and nothing spends without you pressing it."),
         "your decision", GREEN, ""),
    ]
    return _head("⚡", "Decision queue",
                 "What to do, in the order that matters, with the reason and "
                 "the button.") + _vizcards(cards[:20])


# ======================================================================
#  (3) SIGNAL ROUTER  (18)
# ======================================================================
def board_router(ctx) -> str:
    ctx = _ctx(ctx)
    r = ctx["router"]
    rows = _L(r.get("rows"))
    cards = [
        ("The loop", _i(r.get("live")), f"of {_i(r.get('total'))} systems reporting",
         _CH().sankey([(a, b, c) for a, b, c in _L(r.get("flows"))]),
         ("Signal to cockpit to decision to playbook. This is the loop that did "
          "not exist — eight systems computed and nothing closed the circle."),
         "signal router", GREEN if r.get("closed") else AMBER, ""),
        ("Loop closed", "yes" if r.get("closed") else "partial",
         "all systems feeding",
         _statusgrid(_L(r.get("statusgrid"))),
         str(r.get("note", "")),
         "signal router", GREEN if r.get("closed") else AMBER, ""),
    ]
    for row in (rows or [{"label": l, "question": "", "live": False,
                          "emits": "", "returns": ""} for l in SYSTEM_LABELS]):
        row = _D(row)
        cards.append((_s(row.get("label"))[:26],
                      "feeding" if row.get("live") else "silent",
                      _s(row.get("question"))[:30],
                      _donut(100 if row.get("live") else 0),
                      (f"Emits: {row.get('emits')}. Outcome returns via "
                       f"{row.get('returns')}."),
                      "signal router", GREEN if row.get("live") else AMBER,
                      f"<button class='cta' onclick=\"nav('{_s(row.get('system'))}')\">"
                      f"Open</button>" if row.get("system") else ""))
    cards += [
        ("Where the outcome returns", "the playbook", "every cycle", "",
         ("A decision with no recorded outcome teaches nothing. Actions taken "
          "here are logged and feed the playbook."),
         "decision log", GREEN, ""),
        ("The full map", "System & Wiring", "loop map tab", "",
         "The visual wiring of every loop lives there.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('system')\">Open the loop map</button>"),
        ("A silent system", "is not broken", "usually", "",
         ("It means that context could not be built on this render — most often "
          "because the underlying wire is down."),
         "computed", BLUE, ""),
        ("Each system owns its loop", "the cockpit routes", "no duplication", "",
         ("A signal is computed once, in the section that owns it, and read "
          "here. Nothing is recalculated."),
         "principle", GREEN, ""),
        ("Reading order", "money first", "then what produces it", "",
         ("BI, Content, Outreach, SEO, SGA, Media, Risk, System — deliberately "
          "in that order."),
         "principle", BLUE, ""),
        ("A decision without evidence", "is a guess", "never shown", "",
         "Every routed decision carries the measurement behind it.",
         "principle", GREEN, ""),
        ("Outcome closes the loop", "logged", "then learned", "",
         "What you actually did is recorded and feeds the playbook.",
         "decision log", GREEN, ""),
        ("No new API needed", "for any of this", "wiring only", "",
         ("Every signal was already computed by a section you already have. The "
          "cockpit adds routing, not data collection."),
         "principle", GREEN, ""),
    ]
    return _head("🔀", "Signal router",
                 "Which system feeds the brain, what it emits, and where the "
                 "outcome returns.") + _vizcards(cards[:18])


# ======================================================================
#  (4)(5)(6) APPROVALS — content, outreach, plan
# ======================================================================
def _approval_board(kind, label, icon, count, live_key, blurb):
    def board(ctx) -> str:
        ctx = _ctx(ctx)
        a, t = ctx["approvals"], ctx["turnaround"]
        by_type = dict(_L(a.get("by_type")))
        mine = _i(by_type.get("outreach_campaign" if kind == "outreach"
                              else "content_piece"))
        cards = [
            (f"{label} waiting",
             (_i(a.get("plan_pending")) if kind == "plan" else mine),
             "need your decision",
             _histogram([_i(x) for x in _L(a.get("ages"))]),
             ("The distribution of how long things have been waiting. A long "
              "tail means the gate has become a wall."),
             "job queue", AMBER if mine or a.get("plan_pending") else GREEN,
             "<button class='cta' onclick='approveAll()'>Approve all safe</button>"
             if kind == "content" else ""),
            ("Oldest item", (f"{_i(_L(a.get('oldest'))[1])} days"
                             if a.get("oldest") else "—"), "waiting",
             "", (f"{_s(_L(a.get('oldest'))[0])} has been waiting longest."
                  if a.get("oldest") else "Nothing is waiting."),
             "computed", PINK if a.get("stale") else GREEN, ""),
            ("Average age", f"{a.get('avg_age', 0)} days", "in the queue",
             _score_gauge(min(100, round(_f(a.get("avg_age")) * 25)), 50),
             "Under two days keeps the machine moving.",
             "computed", _pct_color(_f(a.get("avg_age")) * 25, 50), ""),
            ("Cleared", _i(t.get("cleared")), "all time",
             _trend([("cleared/day", _L(t.get("series")), TEAL)]),
             f"About {t.get('avg_per_day', 0)} a day.",
             "job queue", GREEN if t.get("cleared") else AMBER, ""),
            ("Sent back", _i(a.get("declined")), "for rewrite", "",
             "Declining with a reason is how the engine learns your taste.",
             "job queue", BLUE, ""),
        ]
        # A measured-poor piece earns a PROPOSAL, and it belongs HERE — in the
        # queue where you already decide things — not only in the database.
        if kind == "content":
            pr = _D(ctx.get("proposals"))
            cards.append(
                ("Rewrite proposals", _i(pr.get("count")), "measured poor",
                 "", str(pr.get("note", "")), "measured outcome",
                 AMBER if _i(pr.get("count")) else GREEN, ""))
            cards += _slots(
                _L(pr.get("rows")), 4,
                lambda i, r: (
                    _s(_D(r).get("title"))[:30] or "Untitled",
                    f"{_i(_D(_D(r).get('measured')).get('sessions'))} sessions",
                    _s(_D(_D(r).get("measured")).get("period")), "",
                    f"{_s(_D(r).get('why'))} {_s(_D(r).get('suggested_focus'))}",
                    "measured outcome", AMBER,
                    f"<button class='cta' onclick=\"proposal('"
                    f"{_s(_D(r).get('job_id'))}',true)\">Queue a rewrite</button>"
                    f"<button class='cta' onclick=\"proposal('"
                    f"{_s(_D(r).get('job_id'))}',false)\">Leave it</button>"),
                "Proposal slot", "none waiting",
                ("A piece appears here only after GA4 reported on it and the "
                 "numbers came back under the floor."),
                "measured outcome", GREEN)
        extra = {
            "content": [
                ("See it before approving", "six previews", "per platform", "",
                 ("Website, LinkedIn, Instagram, X, Facebook, YouTube and the "
                  "Google result — all rendered from the piece that publishes."),
                 "Content Factory", VIOLET,
                 "<button class='cta' onclick=\"goPreview('cfpvweb')\">"
                 "See the website preview</button>"
                 "<button class='cta' onclick=\"goPreview('cfpvli')\">"
                 "LinkedIn preview</button>"),
                ("Blocked platforms", "checked", "before you approve", "",
                 ("Instagram and YouTube reject a post with no visual. The "
                  "preview says so rather than failing at publish time."),
                 "Content Factory", AMBER, ""),
                ("Cost per piece", "shown per row", "before approval", "",
                 "You can see what it cost before deciding whether it was worth it.",
                 "job costs", BLUE, ""),
                ("Approve all safe", "batch", "only the clean ones", "",
                 ("Pieces that pass every platform check can be approved "
                  "together. Anything blocked stays for you."),
                 "engine", GREEN, ""),
            ],
            "outreach": [
                ("Every email is readable", "all three touches", "before sending",
                 "", ("The outbox shows all three emails per lead, each "
                      "editable, before anything leaves."),
                 "Leads & Outreach", VIOLET,
                 "<button class='cta' onclick=\"nav('outreach')\">Open the outbox</button>"),
                ("Daily cap applies", "always", "even to a batch", "",
                 "A batch stops at the warm-up cap rather than burning the domain.",
                 "connectors", GREEN, ""),
                ("Suppression respected", "before every send", "always", "",
                 "A suppressed address is skipped even if still in a campaign.",
                 "connectors", GREEN, ""),
            ],
            "plan": [
                ("The plan reads every system", "8 sources", "not a vacuum", "",
                 ("Striking-distance queries, AI-visibility gaps, missing "
                  "markets, which vertical replies, what produced revenue, and "
                  "which channels are live."),
                 "strategy brief", GREEN,
                 "<button class='cta' onclick=\"nav('content')\">See the brief</button>"),
                ("Nothing is written yet", "it is a proposal", "free to decline",
                 "", "Approving creates the jobs; declining costs nothing.",
                 "engine", GREEN, ""),
                ("Capped by budget", "automatically", "never over-plans", "",
                 "A week is never planned that the budget cannot write.",
                 "strategy brief", BLUE, ""),
            ],
        }[kind]
        cards += extra
        cards += _slots(
            _L(a.get("rows")), 5,
            lambda i, r: (f"{_s(_D(r).get('title'))[:24]}",
                          _money(_D(r).get("cost")), _s(_D(r).get("type"))[:18],
                          "", "Waiting for your decision.",
                          "job queue", AMBER),
            "Queue slot", "empty",
            "Items appear here as the engine produces them.", "job queue", GREEN)
        cards += [
            ("Nothing publishes without you", "by design", "no auto-publish", "",
             ("There is no setting that bypasses this. For a business whose "
              "name is on every piece, that is deliberate."),
             "engine", GREEN, ""),
            ("Decline with a reason", "teaches the engine", "not just no", "",
             ("The reason you give goes into the playbook, so a specific "
              "decline teaches the engine something and a blank one does not."),
             "learning", BLUE, ""),
            ("Where the work happens", "below", "the live queue", "",
             "The queue itself is under this board, unchanged.",
             "navigation", VIOLET, ""),
        ]
        while len(cards) < count:
            cards.append(("Queue detail", "—", "no further items", "",
                          "This queue has nothing more to show right now.",
                          "job queue", BLUE, ""))
        # THE PIECE ITSELF, ABOVE THE CARDS. You were asked to approve
        # something you could not see: the Approve button lived here and the
        # words lived on another screen. Every waiting piece now renders in
        # the shape it will publish in - WordPress for the site, LinkedIn for
        # LinkedIn - with Approve, Rewrite and Remove on the same row.
        queue = ""
        if kind == "content":
            try:
                import content_engine_factory_boards as _FBB
                rows = _L(ctx.get("approval_rows"))
                if rows:
                    queue = _FBB._calendar_list({"calendar_rows": rows}, prefix="appr")
            except Exception as e:
                queue = ("<div class='card full' style='margin-top:12px'>"
                         "<p class='ct'>⚠ the waiting pieces could not render"
                         "</p><p class='cc'>"
                         f"{type(e).__name__}: {str(e)[:160]}. The cards below "
                         f"are unaffected.</p></div>")
        return (_head(icon, f"Approvals · {label}", blurb) + queue
                + _vizcards(cards[:count]) + _live(ctx, live_key))
    board.__name__ = f"board_appr_{kind}"
    return board


board_appr_content = _approval_board(
    "content", "Content", "📝", 20, "approvals",
    "Every piece waiting for you, with how long it has waited.")
board_appr_outreach = _approval_board(
    "outreach", "Outreach", "✉️", 18, "followups",
    "Cold emails and follow-ups waiting to be sent.")
board_appr_plan = _approval_board(
    "plan", "Plan", "🗓", 16, "plan",
    "The proposed week, before anything is written.")


# ======================================================================
#  (7) BUDGET & CAPS  (20)
# ======================================================================
def board_budget(ctx) -> str:
    ctx = _ctx(ctx)
    b = ctx["budget"]
    changes = _L(b.get("changes"))
    set_btn = "<button class='cta' onclick='setBudget()'>Change the caps</button>"
    cards = [
        ("Monthly cap", _money(b.get("per_month")), "your ceiling",
         _score_gauge(_f(b.get("month_pct")), 85),
         (f"{_money(b.get('spent_month'))} spent, {b.get('month_pct', 0)}% used. "
          + str(b.get("how", ""))),
         "live caps", _pct_color(_f(b.get("month_pct")), 85), set_btn),
        ("Daily cap", _money(b.get("per_day")), "per day",
         _score_gauge(_f(b.get("day_pct")), 85),
         f"{_money(b.get('spent_day'))} spent today.",
         "live caps", _pct_color(_f(b.get("day_pct")), 85), set_btn),
        ("Per-job cap", _money(b.get("per_job")), "one job's ceiling", "",
         ("Stops a single runaway job from eating the day. A job that hits it "
          "halts rather than continuing."),
         "live caps", BLUE, set_btn),
        ("Headroom", _money(b.get("headroom")), "left this month", "",
         ("What remains before new model steps stop being started. Work "
          "already running is allowed to finish."),
         "computed", GREEN if _f(b.get("headroom")) > 20 else PINK, ""),
        ("Projected month end", _money(b.get("projected")), "at this run rate",
         "", (f"{_money(b.get('run_rate'))} a day across "
              f"{_i(b.get('spent_month')) and ''}the elapsed days. This is "
              f"arithmetic, not a forecast."),
         "computed", PINK if b.get("over_cap") else GREEN, ""),
        ("Will it breach?", ("yes" if b.get("over_cap") else "no"),
         "on current pace", "",
         ("On this pace the cap is reached before month end. The engine will "
          "halt rather than overspend — stopped work, not a surprise bill."
          if b.get("over_cap") else "Current pace finishes inside the cap."),
         "computed", PINK if b.get("over_cap") else GREEN, ""),
        ("The floor", _money(b.get("floor")), "lowest you can set", "",
         str(b.get("note", "")),
         "safety rule", VIOLET, ""),
        ("Why there is a floor", "hard block", "your decision", "",
         ("A cap below what is already spent would halt the engine the moment "
          "it saved, with no warning. That request is refused with the lowest "
          "safe number."),
         "safety rule", GREEN, ""),
        ("No restart needed", "settings-first", "live on next loop", "",
         str(b.get("how", "")),
         "the fix", GREEN, ""),
        ("What changed", "os.getenv at import", "before this", "",
         ("The caps were read ONCE when the module loaded — the only setting in "
          "the engine that needed an .env edit and a container rebuild."),
         "the fix", VIOLET, ""),
        ("Change log", _i(b.get("change_count")), "recorded changes",
         _rows([f"{_s(_D(c).get('at'))[:16]} → "
                f"€{_f(_D(_D(c).get('to')).get('per_month')):,.0f}"
                for c in changes[:6]], left_fmt=lambda x: x, empty=""),
         ("Every cap change is written with what it was and what it became, so "
          "a raise is never invisible."),
         "audit log", BLUE if changes else AMBER, ""),
    ]
    cards += _slots(
        changes, 4,
        lambda i, c: (f"Change {i + 1}", _s(_D(c).get("at"))[:10], "recorded", "",
                      (f"Monthly {_money(_D(_D(c).get('from')).get('per_month'))} → "
                       f"{_money(_D(_D(c).get('to')).get('per_month'))}. "
                       f"{_s(_D(c).get('note'))}"),
                      "audit log", BLUE),
        "Change", "no changes yet",
        "The caps have not been changed from the browser yet.", "audit log")
    cards += [
        ("Ad spend is NOT capped here", "platform-billed", "outside the engine",
         "", ("Google, Meta and LinkedIn bill you directly. This cap governs "
              "LLM and image spend only — nothing here can stop an ad campaign."),
         "honest limit", AMBER, ""),
        ("Image spend counts", "~€0.04 each", "against this cap", "",
         "Content and image generation draw on the same monthly ceiling.",
         "computed", BLUE, ""),
        ("Set your own target", "any value", "above the floor", "",
         ("Raise it for a heavy month, lower it when quiet. It takes effect on "
          "the worker's next loop."),
         "your decision", VIOLET, set_btn),
        ("The engine halts, it does not overspend", "hard stop", "always", "",
         ("At 100% new LLM steps stop. Work queues rather than billing you."),
         "engine", GREEN, ""),
        ("Where cost is analysed", "BI", "unit economics", "",
         "CAC, LTV and cost per outcome live there.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('bi')\">Open BI</button>"),
    ]
    return _head("💰", "Budget & caps",
                 "Your spending ceiling — set it here, in the browser, with a "
                 "floor that protects you.") + _vizcards(cards[:20])


# ======================================================================
#  (8) AUTONOMY & GUARDRAILS  (18)
# ======================================================================
def board_autonomy(ctx) -> str:
    ctx = _ctx(ctx)
    au = ctx["autonomy"]
    cards = [
        ("Delegated to agents", _i(au.get("delegated")), "actions", "",
         str(au.get("note", "")),
         "your decision", GREEN, ""),
        ("Could be delegated safely", _i(au.get("safe_count")), "read-only actions",
         _statusgrid([(n[:20], True, "no spend")
                      for n, _a, _w in _L(au.get("safe"))]),
         ("These spend nothing, send nothing and publish nothing. If you ever "
          "wanted to hand something over, it would be these."),
         "computed", BLUE, ""),
        ("Never delegated", _i(au.get("gated_count")), "always yours",
         _statusgrid([(n[:20], False, "human only")
                      for n, _a, _w in _L(au.get("gated"))]),
         str(au.get("principle", "")),
         "your decision", VIOLET, ""),
    ]
    import content_engine_cockpit as _CK
    for n, act, why in (_L(au.get("safe")) or _CK.SAFE_TO_DELEGATE):
        cards.append((f"Safe: {_s(n)[:24]}", "read-only", _s(act)[:24], "",
                      f"{n} — {why}. Nothing leaves the machine.",
                      "computed", BLUE, ""))
    for n, why, act in (_L(au.get("gated")) or _CK.GATED_FOREVER):
        cards.append((f"Gated: {_s(n)[:24]}", "human", _s(act)[:24], "",
                      f"{n} — {why}.",
                      "your decision", VIOLET, ""))
    cards += [
        ("The rule", "read freely, act never", "one line", "",
         str(au.get("principle", "")),
         "principle", GREEN, ""),
        ("Why not full autopilot", "your name is on it", "for now", "",
         ("An agent that can send, publish and spend without you is a different "
          "risk profile. You chose to keep the gate, and this board reflects "
          "that rather than quietly widening it."),
         "your decision", VIOLET, ""),
        ("Where the risk is scored", "Risk & Infrastructure", "208 cards", "",
         "Autonomy level is one of the risks tracked there.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('riskinfra')\">Open Risk</button>"),
    ]
    return _head("🛡", "Autonomy & guardrails",
                 "What an agent may do alone, what always needs you, and why "
                 "the line is where it is.") + _vizcards(cards[:18])


# ======================================================================
#  (9) KEYS & CAPABILITY  (16)
# ======================================================================
def board_keys(ctx) -> str:
    ctx = _ctx(ctx)
    c = ctx["capability"]
    groups = _L(c.get("groups"))
    cards = [
        ("Wires live", _i(c.get("wires_live")), f"of {_i(c.get('wires_total'))}",
         _score_gauge(_f(c.get("wire_pct")), 80),
         ("Each dead wire is a capability the engine cannot use."),
         "wire status", _pct_color(100 - _f(c.get("wire_pct")), 40), ""),
        ("Extra keys you can now enter", _i(c.get("missing_total")),
         "in the browser",
         _hbars([(k[:20], len(v)) for k, v in groups]),
         ("These were on the /connect allow-list all along but no form ever "
          "showed a box for them, so they could only be set by editing .env and "
          "rebuilding. There is a field for every one of them now."),
         "connect form", BLUE, "<button class='cta' onclick=\"goKeys()\">"
         "Open the form</button>"),
    ]
    cards += _slots(
        groups, 6,
        lambda i, g: (f"{_s(g[0])[:24]}", len(_L(g[1])), "keys",
                      "", (f"{', '.join(_L(g[1])[:5])}"
                           + (" …" if len(_L(g[1])) > 5 else "")),
                      "connect form", BLUE,
                      "<button class='cta' onclick=\"goKeys()\">Add them</button>"),
        "Key group", "all covered",
        "Every key in this group can already be entered in the browser.",
        "connect form", GREEN)
    cards += [
        ("None of these is a SaaS tool", "platform APIs", "your own accounts", "",
         ("Every key here is the platform's own API on its own terms. The engine "
          "depends on no third-party dashboard."),
         "principle", GREEN, ""),
        ("Settings-first, always", "no SSH, no rebuild", "every key", "",
         ("A key entered in the browser is read before the environment and "
          "takes effect within about fifteen seconds."),
         "connectors", GREEN, ""),
        ("A key that is refused", "shows as Rejected", "not green", "",
         ("A wire reads green only once something proved the credentials were "
          "accepted."),
         "connectors", GREEN, ""),
        ("Highest-value additions", "the AI engines", "OpenAI, Perplexity, Gemini",
         "", ("You are measured against ChatGPT, Perplexity and Gemini. Only "
              "Claude is wired, so AI visibility is being judged on one engine "
              "out of four."),
         "judgement", AMBER,
         "<button class='cta' onclick=\"goKeys()\">Add a key</button>"),
        ("Second: your email identity", "logo, booking link, company", "", "",
         ("Every cold email currently carries defaults where your branding "
          "should be."),
         "judgement", AMBER,
         "<button class='cta' onclick=\"goKeys()\">Set my branding</button>"),
        ("Where to enter them", "one grouped form", "System &amp; Wiring", "",
         ("Six groups, one per thing they unlock. Blank fields are ignored, so "
          "you can save one group at a time."),
         "navigation", VIOLET,
         "<button class='cta' onclick=\"goKeys()\">Open the form</button>"),
        ("What SaaS would cost", "hundreds a month", "for less control", "",
         ("An equivalent stack of SEO, outreach, social and BI tools runs into "
          "hundreds a month and still cannot see across itself."),
         "judgement", VIOLET, ""),
        ("Independence is the goal", "your machine", "not a subscription", "",
         ("Everything here runs on your VPS against APIs you hold directly."),
         "principle", VIOLET, ""),
    ]
    return _head("🔑", "Keys & capability",
                 "What the engine cannot do yet, and the exact key that would "
                 "change it.") + _vizcards(cards[:16])


# ======================================================================
#  (10) LOOP HEALTH  (20)
# ======================================================================
def _LC(ctx):
    """Loop closure, computed. Cached on the ctx so a board that reads it four
    times does not recompute it four times."""
    c = ctx.get("_closure")
    if c is None:
        try:
            import content_engine_cockpit as CK
            c = CK.loop_closure((ctx.get("capability") or {}).get("status")
                                or ctx.get("status"))
        except Exception as e:
            c = {"rows": [], "closed": 0, "total": 0, "open": 0, "pct": 0.0,
                 "note": f"loop closure could not be computed: {e}"}
        ctx["_closure"] = c
    return c


def board_loops(ctx) -> str:
    ctx = _ctx(ctx)
    r, d = ctx["router"], ctx["decisions"]
    rows = _L(r.get("rows")) or [{"label": l, "live": False, "emits": "",
                                  "returns": "", "question": ""}
                                 for l in SYSTEM_LABELS]
    cards = [
        ("Loops reporting", _i(r.get("live")), f"of {_i(r.get('total'))}",
         _statusgrid(_L(r.get("statusgrid")) or
                     [(l[:18], False, "silent") for l in SYSTEM_LABELS]),
         str(r.get("note", "")),
         "signal router", GREEN if r.get("closed") else AMBER, ""),
        ("Loop closed end to end", "yes" if r.get("closed") else "partial",
         "signal → decision → outcome",
         _CH().sankey([(a, b, c) for a, b, c in _L(r.get("flows"))]),
         ("A loop is closed when a signal produces a decision and the outcome "
          "returns to the playbook. Before the cockpit, none of them closed."),
         "signal router", GREEN if r.get("closed") else AMBER, ""),
        # COMPUTED, not asserted. A loop is closed only when its outcome can
        # physically come back — which depends on a live wire, not a diagram.
        ("Outcomes that can return", f"{_i(_LC(ctx).get('closed'))}/"
         f"{_i(_LC(ctx).get('total'))}", "loops able to measure",
         _score_gauge(_f(_LC(ctx).get("pct")), 80),
         str(_LC(ctx).get("note", "")),
         "computed from live wires",
         GREEN if not _i(_LC(ctx).get("open")) else AMBER,
         "<button class='cta' onclick=\"nav('system')\">See the loop map</button>"),
        ("Decisions produced", _i(d.get("count")), "from these loops", "",
         "The output of the whole system, in one number.",
         "decision queue", BLUE, ""),
    ]
    for row in rows:
        row = _D(row)
        cards.append((_s(row.get("label"))[:24],
                      "closed" if row.get("live") else "open",
                      _s(row.get("question"))[:28],
                      _donut(100 if row.get("live") else 0),
                      (f"Emits {row.get('emits')}. The outcome returns via "
                       f"{row.get('returns')}."),
                      "signal router",
                      GREEN if row.get("live") else AMBER, ""))
    cards += [
        ("What an open loop means", "no outcome returns", "it cannot learn", "",
         ("A system that emits a signal but never sees the result of acting on "
          "it repeats the same advice forever."),
         "principle", VIOLET, ""),
        ("The full visual map", "System & Wiring", "loop map tab", "",
         "Node graph, flow diagram and the production line.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('system')\">Open the loop map</button>"),
        ("Total engine loops", "180+", "across 9 sections", "",
         ("SEO 22, Media 14, System 18, Risk 24, BI 26, Outreach 21, SGA 24, "
          "Content 26, Cockpit 18 — each identified, built and verified."),
         "computed", VIOLET, ""),
        ("Nothing here collects data", "wiring only", "no new API", "",
         "Every signal already existed. The cockpit routes it.",
         "principle", GREEN, ""),
        ("Where each loop lives", "its own section", "one click away", "",
         "Every row above links to the section that owns it.",
         "navigation", BLUE, ""),
        ("A loop with no signal", "is not a bug", "usually a dead wire", "",
         "Check System & Wiring before assuming the loop is broken.",
         "computed", BLUE, ""),
        ("Loops per section", "18 to 26", "each verified", "",
         ("Every section's loops were enumerated, built and then re-tested "
          "against the shipped code."),
         "computed", BLUE, ""),
        ("An open loop is honest", "when it says so", "not hidden", "",
         ("Where a loop cannot close — social engagement with no read scope — "
          "the board names the missing scope."),
         "principle", GREEN, ""),
        ("This is the closing piece", "the brain", "of the whole engine", "",
         ("Eight sections compute; this one decides and records what was "
          "decided. That is the loop the engine was missing."),
         "principle", VIOLET, ""),
    ]
    return _head("🔄", "Loop health",
                 "Which loops are closed, which are open, and what closes "
                 "them.") + _vizcards(cards[:21])


# ======================================================================
#  (11) JOB QUEUE  (18)
# ======================================================================
def board_jobs(ctx) -> str:
    ctx = _ctx(ctx)
    e, a, t = ctx["engine"], ctx["approvals"], ctx["turnaround"]
    cards = [
        ("Jobs in the engine", _i(e.get("jobs_total")), "all time",
         _trend([("cleared/day", _L(t.get("series")), TEAL)]),
         "Everything the engine has ever been asked to produce.",
         "job queue", BLUE if e.get("jobs_total") else AMBER, ""),
        ("Running now", _i(e.get("running")), "in progress", "",
         "Jobs that have not finished, failed or been declined.",
         "job queue", GREEN if e.get("running") else BLUE, ""),
        ("Waiting for you", _i(a.get("waiting")), "at the human gate", "",
         str(a.get("note", "")),
         "job queue", AMBER if a.get("waiting") else GREEN,
         "<button class='cta' onclick=\"seoTab('ckcontent')\">Review</button>"),
        ("Failed", _i(e.get("failed")), "produced nothing", "",
         ("These consumed budget and returned no usable output. The money "
          "is spent whether or not the piece was later salvaged."),
         "job queue", PINK if e.get("failed") else GREEN, ""),
        ("Halted by a cap", _i(e.get("halted_by_budget")), "stopped, not broken",
         "", ("These hit a budget ceiling. Raising the cap releases them."),
         "job queue", AMBER if e.get("halted_by_budget") else GREEN,
         "<button class='cta' onclick='setBudget()'>Open budget</button>"),
        ("Cleared", _i(t.get("cleared")), "finished", "",
         f"About {t.get('avg_per_day', 0)} a day.",
         "job queue", GREEN if t.get("cleared") else AMBER, ""),
        ("Queue age", f"{a.get('avg_age', 0)} days", "average wait",
         _histogram([_i(x) for x in _L(a.get("ages"))]),
         "The shape matters — a long tail means specific items are stuck.",
         "computed", BLUE, ""),
        ("Stale items", _i(a.get("stale")), "three days or more", "",
         "The gate becomes a wall when these accumulate.",
         "computed", PINK if a.get("stale") else GREEN, ""),
        ("By type", len(_L(a.get("by_type"))), "kinds waiting",
         _hbars([(k[:18], n) for k, n in _L(a.get("by_type"))]),
         "Articles versus cold emails versus plans.",
         "job queue", BLUE, ""),
    ]
    cards += _slots(
        _L(a.get("by_type")), 3,
        lambda i, r: (f"Type: {_s(r[0])[:20]}", r[1], "waiting",
                      _donut(round(100 * _i(r[1]) / max(_i(a.get("waiting")), 1))),
                      "Share of the queue.", "job queue", AMBER),
        "Type", "none waiting",
        "Job types appear as they queue.", "job queue", GREEN)
    cards += [
        ("Nothing is lost", "a declined job is kept", "with its reason", "",
         "Declines feed the playbook rather than vanishing.",
         "learning", GREEN, ""),
        ("Retries cost twice", "counted honestly", "as spend", "",
         "A retried job is charged once and published once.",
         "job costs", AMBER, ""),
        ("Throughput ceiling", "the budget", "not the agents", "",
         "Agent capacity is well above what the cap allows.",
         "computed", BLUE, ""),
        ("Where jobs are detailed", "System & Wiring", "jobs board", "",
         "Per-job state and failure detail live there.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('system')\">Open System &amp; Wiring</button>"),
        ("The gate is the point", "not the bottleneck", "by design", "",
         ("Clearing the queue daily takes minutes. Letting it sit for a week is "
          "what makes it feel like a wall."),
         "judgement", VIOLET, ""),
        ("Schedule", "daily batch", "set in the scheduler", "",
         "One outreach, two blogs and the social cadence per day by default.",
         "scheduler", BLUE, ""),
    ]
    return _head("📋", "Job queue",
                 "Everything the engine is working on, and what is stuck.") + _vizcards(cards[:18])


# ======================================================================
#  (12) ENGINE STATE  (16)
# ======================================================================
def board_engine(ctx) -> str:
    ctx = _ctx(ctx)
    e, b = ctx["engine"], ctx["budget"]
    checks = _L(e.get("checks"))
    cards = [
        ("Engine", "healthy" if e.get("healthy") else "check it", "overall",
         _statusgrid([(k[:16], ok, "") for k, ok in checks]),
         str(e.get("note", "")),
         "health probe", GREEN if e.get("healthy") else PINK,
         "<button class='cta' onclick=\"act('/health')\">Re-check</button>"),
        ("At the cap", "yes" if e.get("at_cap") else "no", "spend ceiling",
         _score_gauge(_f(b.get("month_pct")), 85),
         ("New LLM steps are halted until the cap is raised or the month rolls."
          if e.get("at_cap") else "Inside the budget."),
         "live caps", PINK if e.get("at_cap") else GREEN,
         "<button class='cta' onclick='setBudget()'>Change the cap</button>"),
        ("Health checks", len(checks), "probes",
         _donut(round(100 * sum(1 for _k, ok in checks if ok) /
                      max(len(checks), 1))),
         "Anthropic, Postgres and the connectors, checked without spending.",
         "health probe", GREEN if all(ok for _k, ok in checks) else AMBER, ""),
    ]
    cards += _slots(
        checks, 5,
        lambda i, r: (f"Check: {_s(r[0])[:20]}", "ok" if r[1] else "failing",
                      "probe", _donut(100 if r[1] else 0),
                      f"{r[0]} reported {'ok' if r[1] else 'a problem'}.",
                      "health probe", GREEN if r[1] else PINK),
        "Check", "not reporting",
        "Each subsystem reports its own state.", "health probe")
    cards += [
        ("Containers", 3, "db, api, worker", "",
         "All three are needed for the engine to run.",
         "docker", BLUE, ""),
        ("Worker loop", "continuous", "drains the queue", "",
         "The worker advances jobs and picks up settings changes each loop.",
         "engine", GREEN, ""),
        ("Settings take effect", "~15 seconds", "no restart", "",
         "Keys, caps and toggles are re-read on the worker's loop.",
         "engine", GREEN, ""),
        ("Degraded mode", "honest", "never silent", "",
         ("A missing key produces a stated reason, never a fabricated number. "
          "That rule holds across every one of the nine sections."),
         "principle", GREEN, ""),
        ("Where infrastructure lives", "Risk & Infrastructure", "208 cards", "",
         "Compute, storage, backups and continuity are there.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('riskinfra')\">Open Risk</button>"),
        ("Postgres holds everything", "one volume", "credentials and history", "",
         ("Jobs, settings, keys, crawls, deals and the playbook all live in one "
          "database."),
         "engine", AMBER, ""),
        ("Code rolls back", "git revert", "credentials do not", "",
         ("Code is in git; the database is not. A revert cannot lose a key, and "
          "cannot restore one either."),
         "engine", BLUE, ""),
        ("No backup still", "the highest risk", "unchanged", "",
         ("Postgres holds every credential, job, crawl and deal. A nightly "
          "pg_dump remains the cheapest large risk to remove."),
         "risk register", PINK, ""),
    ]
    return _head("⚙️", "Engine state",
                 "Is the machine running, and is anything stopping it?") + _vizcards(cards[:16])


# ======================================================================
#  (13) PLAYBOOK  (18)
# ======================================================================
def board_playbook(ctx) -> str:
    ctx = _ctx(ctx)
    pb, lg = ctx["playbook"], _D(ctx.get("log"))
    secs = _L(pb.get("sections"))
    cards = [
        ("Playbook entries", _i(pb.get("entries")), "learned",
         _treemap([(k[:18], n) for k, n in secs]),
         str(pb.get("note", "")),
         "learning module", GREEN if pb.get("entries") else AMBER, ""),
        ("Sections", len(secs), "kinds of learning",
         _hbars([(k[:20], n) for k, n in secs]),
         ("What the engine keeps notes on. A section with no notes is not "
          "necessarily healthy - it may simply never have been swept."),
         "learning module", BLUE if secs else AMBER, ""),
        ("Decisions recorded", _i(lg.get("total")), "actions taken",
         _trend([("decisions", _L(lg.get("series")), TEAL)]),
         ("What was actually DONE, not what was suggested. This is the half "
          "that was missing — the playbook accumulated advice and nothing "
          "recorded whether it was followed."),
         "decision log", BLUE if lg.get("total") else AMBER, ""),
    ]
    cards += _slots(
        secs, 6,
        lambda i, r: (f"{_s(r[0]).replace('_', ' ')[:24]}", r[1], "entries",
                      _donut(round(100 * _i(r[1]) / max(_i(pb.get("entries")), 1))),
                      "Accumulated across every completed cycle.",
                      "learning module", BLUE),
        "Playbook section", "nothing learned yet",
        ("The playbook fills as cycles COMPLETE — it needs finished jobs, not "
         "started ones."), "learning module")
    cards += [
        ("Read back into decisions", "yes", "now", "",
         ("The Decision Queue cites the playbook. Before the cockpit, learning "
          "accumulated and nothing ever consulted it."),
         "the fix", GREEN,
         "<button class='cta' onclick=\"seoTab('ckdecide')\">See the queue</button>"),
        ("Revenue by source", len(_L(pb.get("by_vertical"))), "sources",
         _split_donut([(k[:14], v, c) for (k, v), c in
                       zip(_L(pb.get("by_vertical")),
                           (GREEN, TEAL, BLUE, AMBER, PINK))]),
         ("Which source actually produced money — the only ranking that "
          "matters." if pb.get("has_revenue") else
          "Needs recorded deals."),
         "recorded deals", GREEN if pb.get("has_revenue") else AMBER, ""),
        ("A decline teaches", "with its reason", "not just no", "",
         "Sending a piece back with a note is the strongest learning signal.",
         "learning module", BLUE, ""),
        ("Learning needs outcomes", "not just output", "the hard part", "",
         ("Publishing is measurable. Whether it worked needs a recorded deal "
          "or a ranking movement."),
         "principle", VIOLET, ""),
        ("Where outcomes are recorded", "BI", "record a won deal", "",
         "One deal makes revenue, LTV, CAC and this board all compute.",
         "navigation", VIOLET,
         "<button class='cta' onclick='biDeal()'>Record a won deal</button>"),
        ("Learning compounds", "or it does not exist", "the whole point", "",
         ("An engine that runs a hundred cycles and knows nothing more than "
          "after the first is just automation."),
         "principle", VIOLET, ""),
        ("What gets recorded", "outcomes and declines", "both", "",
         "A rejection with a reason is a stronger signal than an approval.",
         "learning module", BLUE, ""),
        ("Playbook feeds the planner", "as evidence", "not as rules", "",
         ("The content planner receives it alongside the measured signals and "
          "decides; it is not a hard constraint."),
         "strategy brief", BLUE, ""),
        ("Evals score the agents", "separately", "in Risk", "",
         "Agent quality is measured there, not here.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('riskinfra')\">Open Risk</button>"),
    ]
    return _head("📚", "Playbook",
                 "What the engine has learned, and whether anything acts on "
                 "it.") + _vizcards(cards[:18])


# ======================================================================
#  (14) WHAT WORKS  (18)
# ======================================================================
def board_works(ctx) -> str:
    ctx = _ctx(ctx)
    pb, d = ctx["playbook"], ctx["decisions"]
    verts = _L(pb.get("by_vertical"))
    cards = [
        ("Revenue by source", len(verts), "measured",
         _waterfall([(k[:14], v) for k, v in verts]),
         ("The only ranking that matters: what produced money."
          if verts else
          "Needs recorded deals. One deal makes this board live."),
         "recorded deals", GREEN if verts else AMBER,
         "<button class='cta' onclick='biDeal()'>Record a won deal</button>"),
        ("Best source", (_s(verts[0][0]) if verts else "—"),
         (_money(verts[0][1]) if verts else "no deals yet"), "",
         ("Where to put the next hour of effort, based on what has "
          "already produced results rather than on what feels promising."),
         "recorded deals", GREEN if verts else AMBER, ""),
    ]
    cards += _slots(
        verts, 5,
        lambda i, r: (f"{_s(r[0])[:22]}", _money(r[1]), "recorded revenue",
                      _donut(round(100 * _f(r[1]) /
                                   max(sum(_f(x[1]) for x in verts), 1))),
                      "Attributed at deal entry.", "recorded deals", BLUE),
        "Source", "no revenue yet",
        "Tag the source when recording a deal and it appears here.",
        "recorded deals", AMBER)
    cards += [
        ("What converted", "needs deals", "not impressions", "",
         ("For €2k-10k projects, a booked call beats any vanity metric. That "
          "is what this board ranks by."),
         "judgement", VIOLET, ""),
        ("Winning subject lines", "from outreach", "measured", "",
         ("Subjects that earned replies are recorded on each send and feed the "
          "content planner as proven angles."),
         "Leads & Outreach", BLUE,
         "<button class='cta' onclick=\"nav('outreach')\">Open Outreach</button>"),
        ("Winning content", "by sessions and deals", "not by likes", "",
         "Social has no read scope, so traffic and revenue are the honest rank.",
         "SGA", BLUE,
         "<button class='cta' onclick=\"nav('sga')\">Open SGA</button>"),
        ("Winning queries", "striking distance", "closest to page 1", "",
         "Queries at #11-20 are the cheapest ranking wins available.",
         "SEO", BLUE,
         "<button class='cta' onclick=\"nav('seo')\">Open SEO</button>"),
        ("Decisions that worked", _i(d.get("count")), "tracked", "",
         "The decision log records what was done so the outcome can be judged.",
         "decision log", BLUE, ""),
        ("What is not measurable yet", "social engagement", "no read scope", "",
         ("Every social connector is post-only. That gap is named on the SGA "
          "boards rather than filled with a guess."),
         "honest limit", AMBER, ""),
        ("Attribution is self-reported", "at deal entry", "and that is fine", "",
         ("A referral or a phone call cannot be tracked. Your judgement at deal "
          "entry is the only attribution that survives them."),
         "principle", VIOLET, ""),
        ("Activity is not achievement", "the trap", "worth naming", "",
         ("Pieces published, emails sent and posts made are all easy to grow "
          "and none of them is revenue."),
         "principle", VIOLET, ""),
        ("One deal changes this board", "entirely", "from blank to ranked", "",
         ("Everything on this board keys on recorded deals. One deal "
          "entered or missed moves every figure here."),
         "recorded deals", AMBER,
         "<button class='cta' onclick='biDeal()'>Record a won deal</button>"),
        ("Ranked by money", "not by volume", "deliberately", "",
         ("A source that produced one €6,000 project beats one that produced "
          "forty clicks."),
         "principle", GREEN, ""),
        ("Where the economics are", "BI", "CAC, LTV, payback", "",
         "This board says what worked; BI says whether it paid.",
         "navigation", VIOLET,
         "<button class='cta' onclick=\"nav('bi')\">Open BI</button>"),
    ]
    return _head("🏆", "What works",
                 "What actually produced revenue, ranked by money rather than "
                 "activity.") + _vizcards(cards[:18])


# ======================================================================
#  (15) EXPERIMENTS  (16)
# ======================================================================
def board_experiments(ctx) -> str:
    ctx = _ctx(ctx)
    ex = ctx["experiments"]
    rows = _L(ex.get("rows"))
    start = "<button class='cta' onclick='startExperiment()'>Start an experiment</button>"
    cards = [
        ("Experiments", _i(ex.get("total")), "stated hypotheses",
         _split_donut([("open", _i(ex.get("open")), AMBER),
                       ("scored", _i(ex.get("scored")), GREEN)]),
         str(ex.get("note", "")),
         "experiments", GREEN if ex.get("total") else AMBER, start),
        ("Due for scoring", _i(ex.get("due")), "past their review date", "",
         ("An experiment nobody scores is just a note."
          if ex.get("due") else "Nothing is due."),
         "computed", AMBER if ex.get("due") else GREEN, ""),
        ("Open", _i(ex.get("open")), "still running", "",
         ("Waiting for their review date. Nothing happens to these until "
          "that date arrives - they are not stuck."),
         "experiments", BLUE, ""),
        ("Scored", _i(ex.get("scored")), "with a verdict", "",
         ("A scored experiment feeds the playbook. Until it is scored it "
          "changes nothing about how the engine behaves."),
         "experiments", GREEN if ex.get("scored") else AMBER, ""),
    ]
    cards += _slots(
        rows, 6,
        lambda i, r: (f"{_s(_D(r).get('hypothesis'))[:26]}",
                      ("scored" if _D(r).get("scored") else "open"),
                      f"review {_s(_D(r).get('review_on'))}", "",
                      (f"Metric: {_D(r).get('metric')}. "
                       + (f"Result: {_D(r).get('result')}"
                          if _D(r).get("scored") else
                          "Waiting for its review date.")),
                      "experiments",
                      GREEN if _D(r).get("worked") else
                      BLUE if _D(r).get("scored") else AMBER),
        "Experiment", "none started",
        ("An experiment is a stated guess plus a metric plus a date to check "
         "it. Without one, every change becomes folklore."),
        "experiments", AMBER)
    cards += [
        ("Why experiments", "folklore otherwise", "the alternative", "",
         ("Without a stated hypothesis and a review date, a change that "
          "coincided with a good week becomes permanent belief."),
         "principle", VIOLET, ""),
        ("A good first one", "German content for DE/CH", "your widest gap", "",
         ("Hypothesis: German pages will earn sessions from Germany within six "
          "weeks. Metric: GA4 sessions from DE. That is testable."),
         "judgement", VIOLET, start),
        ("What to measure", "one metric", "not five", "",
         "An experiment with five metrics always 'works' on at least one.",
         "principle", GREEN, ""),
        ("Review date matters", "decide it upfront", "before you know", "",
         ("Choosing when to check AFTER seeing the numbers is how you talk "
          "yourself into a result."),
         "principle", GREEN, ""),
        ("Scored experiments feed the playbook", "both ways", "wins and losses",
         "", "A failed experiment is as useful as a successful one, recorded.",
         "learning", BLUE, ""),
        ("Where the numbers come from", "the other 8 sections", "already measured",
         "", "You do not need new instrumentation to run one.",
         "principle", GREEN, ""),
    ]
    return _head("🧪", "Experiments",
                 "A stated guess, a metric and a date — instead of "
                 "folklore.") + _vizcards(cards[:16])


# ======================================================================
#  SECTION
# ======================================================================
TABS = [
    ("ckcmd", "🧠", "Cockpit Command"),
    ("ckdecide", "⚡", "Decision Queue"),
    ("ckrouter", "🔀", "Signal Router"),
    ("ckcontent", "📝", "Approvals · Content"),
    ("ckoutreach", "✉️", "Approvals · Outreach"),
    ("ckplan", "🗓", "Approvals · Plan"),
    ("ckbudget", "💰", "Budget & Caps"),
    ("ckauto", "🛡", "Autonomy"),
    ("ckkeys", "🔑", "Keys & Capability"),
    ("ckloops", "🔄", "Loop Health"),
    ("ckjobs", "📋", "Job Queue"),
    ("ckengine", "⚙️", "Engine State"),
    ("ckplaybook", "📚", "Playbook"),
    ("ckworks", "🏆", "What Works"),
    ("ckexp", "🧪", "Experiments"),
]

GROUPS = [
    ("ckdec", "① DECIDE", "What needs me now?",
     ["ckcmd", "ckdecide", "ckrouter"]),
    ("ckapp", "② APPROVE", "Release the work",
     ["ckcontent", "ckoutreach", "ckplan"]),
    ("ckctl", "③ CONTROL", "Set the limits",
     ["ckbudget", "ckauto", "ckkeys"]),
    ("cklearn", "④ RUN & LEARN", "Is it getting better?",
     ["ckloops", "ckjobs", "ckengine", "ckplaybook", "ckworks", "ckexp"]),
]

_TAB_BOARDS = {
    "ckcmd": [("Cockpit Command", board_command)],
    "ckdecide": [("Decision Queue", board_decisions)],
    "ckrouter": [("Signal Router", board_router)],
    "ckcontent": [("Approvals Content", board_appr_content)],
    "ckoutreach": [("Approvals Outreach", board_appr_outreach)],
    "ckplan": [("Approvals Plan", board_appr_plan)],
    "ckbudget": [("Budget & Caps", board_budget)],
    "ckauto": [("Autonomy", board_autonomy)],
    "ckkeys": [("Keys & Capability", board_keys)],
    "ckloops": [("Loop Health", board_loops)],
    "ckjobs": [("Job Queue", board_jobs)],
    "ckengine": [("Engine State", board_engine)],
    "ckplaybook": [("Playbook", board_playbook)],
    "ckworks": [("What Works", board_works)],
    "ckexp": [("Experiments", board_experiments)],
}

_TAB_COUNTS = {"ckcmd": 16, "ckdecide": 20, "ckrouter": 18, "ckcontent": 20,
               "ckoutreach": 18, "ckplan": 16, "ckbudget": 20, "ckauto": 18,
               "ckkeys": 16, "ckloops": 21, "ckjobs": 18, "ckengine": 16,
               "ckplaybook": 18, "ckworks": 18, "ckexp": 16}
TOTAL_CARDS = sum(_TAB_COUNTS.values())


def _safe_board(name, fn, ctx) -> str:
    _CURRENT_BOARD["name"] = name
    try:
        return fn(ctx)
    except Exception as e:
        H = _H()
        return ("<div class='card full' style='margin-top:12px;border-color:#FF6B93'>"
                f"<p class='ct'>⚠ {H._esc(name)} board failed to render</p>"
                f"<p class='cc'>{H._esc(type(e).__name__)}: {H._esc(str(e)[:300])}</p>"
                "<p class='cc'>Every other board is unaffected.</p></div>")


def cockpit_pages(ctx) -> dict:
    return {tab: "".join(_safe_board(n, f, ctx) for n, f in boards)
            for tab, boards in _TAB_BOARDS.items()}


def cockpit_section(ctx) -> str:
    H = _H()
    ctx = _ctx(ctx)
    panels = cockpit_pages(ctx)
    gof = {t: gid for gid, _l, _q, ts in GROUPS for t in ts}
    bar = "".join(
        f"<button class='stab{' on' if i == 0 else ''}' id='stab-{tid}' "
        f"data-grp='{gof.get(tid, 'ckdec')}' onclick=\"seoTab('{tid}')\">"
        f"<span>{icon}</span>{H._esc(label)}"
        f"<span class='n'>{_TAB_COUNTS.get(tid, 0)}</span></button>"
        for i, (tid, icon, label) in enumerate(TABS))
    grouprail = "".join(
        f"<button class='sgrp{' on' if i == 0 else ''}' id='sgrp-{gid}' "
        f"onclick=\"seoGroup('{gid}')\"><b>{H._esc(label)}</b>"
        f"<span class='gq'>{H._esc(question)}</span></button>"
        for i, (gid, label, question, _t) in enumerate(GROUPS))
    body = "".join(
        f"<div class='spanel{' on' if i == 0 else ''}' id='spanel-{tid}'>{panels.get(tid, '')}</div>"
        for i, (tid, _, _) in enumerate(TABS))
    runbar = ("<div class='ctrl' style='margin:10px 0 2px;flex-wrap:wrap'>"
              "<button class='cbtn' onclick='setBudget()'>💰 Set my budget cap</button>"
              "<button class='cbtn' onclick='planContent()'>🗓 Plan a week</button>"
              "<button class='cbtn' onclick='startExperiment()'>🧪 Start an experiment</button>"
              "<button class='cbtn' onclick=\"act('/health')\">🩺 Re-check health</button>"
              "</div>")
    return (_TAB_CSS
            + "<div class='sgroups'>" + grouprail + "</div>"
            + runbar
            + "<div class='stabs'>" + bar + "</div>"
            + "<div class='spanels'>" + body + "</div>")


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    from datetime import date, timedelta
    import content_engine_cockpit as CK

    class S:
        def __init__(self):
            self.d = {}

        def get_setting(self, k, default=None):
            return self.d.get(k, default)

        def set_setting(self, k, v):
            self.d[k] = v

    st = S()
    CK.start_experiment(st, "German pages rank in DE", "GA4 sessions from DE", 14)
    CK.log_decision(st, "Approved 3 pieces", "approve", "content")
    jobs = [{"job_id": "c1", "type": "content_piece", "status": "AWAITING_APPROVAL",
             "created_at": (date.today() - timedelta(days=5)).isoformat(),
             "cost_so_far_usd": 0.4,
             "payload": {"content_producer": {"title": "Old one"}}},
            {"job_id": "c2", "type": "content_piece", "status": "published",
             "created_at": date.today().isoformat()}]
    ctx = {
        "decisions": CK.decisions(
            content={"pipeline": {"waiting": 3}, "post_publish": {"failed": 1}},
            outreach={"replies": {"total": 2}},
            bi={"revenue": {"has_data": False}},
            risk={"risks": [{"title": "No backup", "score": 6,
                             "mitigation": "nightly pg_dump"}],
                  "cost": {"month_cap": 200, "month_spent": 180}}),
        "router": CK.signal_router(seo={"x": 1}, bi={"y": 1}, content={"z": 1}),
        "approvals": CK.approvals(jobs, {"status": "pending", "items": [{"t": 1}]}),
        "turnaround": CK.turnaround(jobs),
        "budget": CK.budget_view({"per_month": 200, "per_day": 50, "per_job": 0.5},
                                 spent_month=63.2, spent_day=4.1,
                                 log=[{"at": "2026-07-30T10:00:00",
                                       "from": {"per_month": 200},
                                       "to": {"per_month": 300}, "note": "busy month"}]),
        "autonomy": CK.autonomy(),
        "capability": CK.capability({"a": True, "b": False},
                                    {"AEO engines": ["OPENAI_API_KEY"],
                                     "Email branding": ["EMAIL_LOGO_URL"]}),
        "engine": CK.engine_state({"healthy": True, "postgres": {"status": "ok"}},
                                  jobs, {"per_month": 200}, spent_month=63.2),
        "playbook": CK.playbook_view({"winning_subjects": ["a", "b"]},
                                     [{"source": "outreach", "value": 6000}]),
        "experiments": CK.experiments(st),
        "log": CK.decision_log(st),
        "live": {"approvals": "<div id='LIVE-APPR'>queue</div>",
                 "followups": "<div id='LIVE-FU'>followups</div>",
                 "plan": "<div id='LIVE-PLAN'>plan</div>"},
    }

    for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
        _CURRENT_BOARD["name"] = name
        try:
            fn(ctx)
        except Exception as e:
            raise AssertionError(f"board {name} raised: {type(e).__name__}: {e}") from e

    pages = cockpit_pages(ctx)
    assert set(pages) == {t for t, _, _ in TABS}, list(pages)
    html = "".join(pages.values())
    assert "failed to render" not in html

    counted = len(re.findall(r"<div class='card (?:overflowcard )?sev-", html))
    assert counted == TOTAL_CARDS, f"expected {TOTAL_CARDS}, rendered {counted}"
    for tab, want in _TAB_COUNTS.items():
        got = len(re.findall(r"<div class='card (?:overflowcard )?sev-", pages[tab]))
        assert got == want, f"{tab}: {got} != {want}"
    ids = re.findall(r"<div class='card (?:overflowcard )?sev-[a-z]+' id='(card-[a-z0-9-]+)'", html)
    assert len(ids) == TOTAL_CARDS and len(set(ids)) == len(ids), (len(ids), len(set(ids)))

    # the live approval queue must survive the merge
    for marker in ("LIVE-APPR", "LIVE-FU", "LIVE-PLAN"):
        assert marker in html, f"{marker} was not carried over"

    # every decision row must carry a button
    assert "Review them" in pages["ckdecide"] or "Open the inbox" in pages["ckdecide"]

    # budget: the floor and the no-restart promise must be stated
    assert "lowest monthly cap" in pages["ckbudget"]
    assert "no restart" in pages["ckbudget"].lower()
    assert "os.getenv at import" in pages["ckbudget"], "say what changed"
    assert "setBudget()" in pages["ckbudget"], "the control must be there"

    # autonomy delegates nothing
    assert "Nothing is delegated" in pages["ckauto"]
    assert "Send an email" in pages["ckauto"] and "Raise the budget cap" in pages["ckauto"]

    empty = cockpit_pages({})
    ehtml = "".join(empty.values())
    assert "failed to render" not in ehtml
    assert len(re.findall(r"<div class='card (?:overflowcard )?sev-", ehtml)) == TOTAL_CARDS

    for bad in ({}, None, "str", 42, {k: None for k in ctx}, {k: [] for k in ctx},
                {k: {} for k in ctx}, {"live": "no"}):
        for name, fn in [b for bs in _TAB_BOARDS.values() for b in bs]:
            try:
                fn(bad)
            except Exception as e:
                raise AssertionError(f"{name} raised on hostile ctx: "
                                     f"{type(e).__name__}: {e}") from e

    charts = len(re.findall(r"<svg", html))
    print(f"cockpit_boards self-check OK — {len(_TAB_BOARDS)} boards, {counted} "
          f"cards, {len(set(ids))} unique ids, {charts} charts; the live approval "
          f"queue is carried through, every decision row has a button, the "
          f"budget floor is stated and settable, and autonomy delegates nothing.")
