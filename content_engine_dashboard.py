"""
content_engine_dashboard.py
============================================================================
The Business Control Center UI. Plain-English, chart-led, no machine jargon.
Pure render functions: they take primitives (jobs, connector status, health,
budget) and return HTML. content_engine_api.py gathers the data and calls
dashboard_html(); everything here is offline-testable.

Design: a professional dark data-dashboard. Semantic status colors (green=live,
amber=needs a key) always carry a label, never color alone. Numbers are tabular.
Charts + the full system map are hand-drawn inline SVG (no libraries; works on
the VPS with no internet). Panels with no data yet show a clean empty state.
============================================================================
"""

from __future__ import annotations

CSS = """
:root{--bg:#080B14;--s1:#0F1626;--s2:#0B111F;--line:#1B2640;--line2:#132038;
--ink:#EDF1FB;--mut:#8E9BBE;--dim:#59668A;--teal:#2FE3D2;--violet:#8B7CFF;
--good:#3FD98B;--warn:#F5B14C;--bad:#FF6B93;--blue:#4C8DFF}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.tnum{font-variant-numeric:tabular-nums;font-feature-settings:'tnum'}
.wrap{max-width:1260px;margin:0 auto;padding:20px 18px 70px}
/* top bar */
.bar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;
padding-bottom:16px;margin-bottom:18px;border-bottom:1px solid var(--line2)}
.brand{display:flex;align-items:center;gap:11px}
.logo{width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,var(--teal),var(--violet));display:grid;place-items:center;color:#04121a;font-weight:800;font-size:15px}
h1{font-size:17px;margin:0;letter-spacing:-.01em;font-weight:700}
.brand small{display:block;color:var(--mut);font-size:11.5px;font-weight:400}
.status{display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--mut);background:var(--s1);border:1px solid var(--line);border-radius:99px;padding:5px 11px}
.status .dot{width:8px;height:8px;border-radius:50%}
.logout{color:var(--mut);font-size:12px;border:1px solid var(--line);border-radius:8px;padding:6px 11px;text-decoration:none}
.note{background:#101d33;border:1px solid #26456f;border-radius:10px;padding:11px 14px;font-size:12.5px;color:var(--mut);margin-bottom:16px}
.note b{color:var(--teal)}
/* section label */
.sec{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim);font-weight:700;margin:22px 2px 10px}
/* kpi */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:11px}
.kpi{background:linear-gradient(180deg,var(--s1),var(--s2));border:1px solid var(--line);border-radius:12px;padding:14px 15px}
.kpi .lab{color:var(--mut);font-size:11px;letter-spacing:.03em;text-transform:uppercase;font-weight:600}
.kpi .val{font-size:26px;font-weight:750;margin-top:6px;letter-spacing:-.02em;line-height:1}
.kpi .val small{font-size:15px;color:var(--dim);font-weight:600}
.kpi .sub{font-size:11.5px;margin-top:6px;display:flex;align-items:center;gap:5px}
/* grid + cards */
.grid{display:grid;gap:11px;margin-bottom:2px}
.g2{grid-template-columns:1fr 1fr}.g3{grid-template-columns:1fr 1fr 1fr}
.card{background:var(--s1);border:1px solid var(--line);border-radius:13px;padding:15px 16px}
.full{grid-column:1/-1}
.ch{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:3px}
.ct{font-size:13.5px;font-weight:700;margin:0}
.cx{font-size:11.5px;color:var(--dim)}
.cc{color:var(--mut);font-size:12px;margin:2px 0 14px}
/* status pill */
.pill{display:inline-flex;align-items:center;gap:5px;font-size:10.5px;font-weight:700;border-radius:99px;padding:2px 8px;letter-spacing:.02em}
.p-live{color:var(--good);background:rgba(63,217,139,.12)}
.p-need{color:var(--warn);background:rgba(245,177,76,.12)}
.pill .dot{width:6px;height:6px;border-radius:50%}
/* funnel */
.fn{display:flex;flex-direction:column;gap:6px}
.fr{display:flex;align-items:center;gap:10px}
.fbar{height:28px;border-radius:6px;display:flex;align-items:center;padding:0 9px;color:#05131f;font-weight:750;font-size:12px;min-width:30px}
.fr .fl{width:118px;color:var(--mut);font-size:12px;flex-shrink:0}
/* bars */
.bars{display:flex;flex-direction:column;gap:8px}
.br{display:flex;align-items:center;gap:10px}.br .bl{width:96px;font-size:12px;color:var(--mut)}
.track{flex:1;height:11px;background:var(--s2);border-radius:99px;overflow:hidden}.track i{display:block;height:100%;border-radius:99px}
.br .bv{width:46px;text-align:right;font-size:11.5px;color:var(--ink)}
/* automations */
.autos{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.grp .gh{font-size:11.5px;color:var(--violet);font-weight:700;margin:0 0 9px;letter-spacing:.02em;display:flex;justify-content:space-between}
.chip{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:12px;padding:6px 0;border-bottom:1px solid var(--line2)}
.chip .nm{display:flex;align-items:center;gap:8px}.chip .dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
/* feed */
.feed{display:flex;flex-direction:column}
.fe{display:flex;gap:11px;padding:8px 0;border-bottom:1px solid var(--line2)}
.fe .tm{color:var(--dim);font-size:11px;width:78px;flex-shrink:0;padding-top:1px}
.fe .tx{font-size:12.5px}.fe .tx b{font-weight:650}
/* suggestions */
.sug{display:flex;gap:9px;padding:8px 0;border-bottom:1px solid var(--line2);font-size:12.5px;color:var(--mut)}
.sug .i{color:var(--warn);flex-shrink:0}
/* approvals + command */
.appr{display:flex;flex-direction:column;gap:8px}
.ap{display:flex;align-items:center;gap:10px;background:var(--s2);border:1px solid var(--line);border-radius:10px;padding:9px 11px}
.ap .apt{flex:1;font-size:12.5px}.ap .apk{font-size:11px;color:var(--mut)}
.btn{border:none;border-radius:8px;padding:6px 12px;font-weight:700;font-size:12px;cursor:pointer}
.ok{background:var(--good);color:#04140a}.no{background:transparent;border:1px solid var(--line);color:var(--mut)}
.cmd{display:flex;gap:8px;flex-wrap:wrap;margin-top:2px}
.cmd select,.cmd input{flex:1;min-width:130px;background:var(--s2);border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:9px 11px;font:inherit}
.cmd button{background:var(--teal);color:#04121a;font-weight:700;border:none;border-radius:8px;padding:9px 15px;cursor:pointer}
.empty{color:var(--dim);font-size:12.5px;padding:16px 0;text-align:center}
pre{background:var(--s2);border:1px solid var(--line);border-radius:8px;padding:10px;overflow:auto;font-size:11.5px;color:#B9C4E0;max-height:200px;margin-top:8px}
.maplegend{display:flex;gap:16px;flex-wrap:wrap;font-size:11.5px;color:var(--mut);margin-top:12px}
.links{margin-top:16px;font-size:12px;color:var(--dim)}.links a{color:var(--teal);text-decoration:none}
@media(max-width:900px){.g2,.g3{grid-template-columns:1fr}}
"""


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- data shaping ------------------------------------------------------------
def _autos(st: dict) -> dict:
    def L(k):
        return bool(st.get(k))
    social = L("social_linkedin") or L("social_twitter") or L("social_facebook")
    gsc = L("google_gsc_ga4")
    return {
        "Content factory": [
            ("Writes articles", True), ("SEO / AI-answer tuning", True),
            ("Quality + legal check", True), ("Publish to website", L("wordpress_publish")),
            ("Post to social", social)],
        "Lead machine": [
            ("Find leads (web/LinkedIn)", L("web_search") or L("linkedin_leads")),
            ("Score hot/warm/cold", True), ("Group into segments", True),
            ("Write cold emails", True), ("Send + answer replies", L("email_send"))],
        "Brain & controls": [
            ("Learns what works", True), ("Measures results", gsc),
            ("Your approval gate", True), ("$200/month cap", True), ("Ads optimizer", True)],
        "Google hub": [
            ("Sheets = your data", L("google_sheets")), ("Drive = content store", L("google_drive")),
            ("Gmail = sending", L("email_send")), ("Runs on your VPS", True),
            ("Health monitor", True)],
    }


_STAGES = ["Ideas", "Written", "Checked", "Waiting for you", "Published", "Measured"]
_STAGE_OF = {
    "created": 0, "site_ready": 0, "competitor_ready": 0, "planned": 0,
    "sourced": 0, "qualified": 0, "segmented": 0, "produced": 1, "drafted": 1,
    "seo_checked": 2, "AWAITING_APPROVAL": 3, "publishing": 4, "published": 4,
    "sending": 4, "sent": 4, "measuring": 4, "tracking": 4,
    "measured": 5, "tracked": 5, "learned": 5, "optimized": 5,
}
_FRIENDLY = {
    "created": "queued a new job", "site_ready": "researched your site",
    "competitor_ready": "analysed competitors", "planned": "planned the content",
    "produced": "wrote the content", "drafted": "drafted the emails",
    "seo_checked": "optimised it for search", "AWAITING_APPROVAL": "is waiting for your approval",
    "published": "published to your website", "sent": "sent the cold emails",
    "measuring": "is measuring results", "measured": "measured the results",
    "optimized": "finished and learned from it", "revision_needed": "needs a rewrite",
    "failed": "hit an error", "halted_budget": "paused — budget cap reached",
}


def _pipeline(jobs):
    c = [0] * len(_STAGES)
    for j in jobs:
        i = _STAGE_OF.get(j.get("status", ""))
        if i is not None:
            c[i] += 1
    return c


def _lead_funnel(jobs):
    found = verified = qualified = emailed = 0
    for j in jobs:
        if j.get("type") != "outreach_campaign":
            continue
        p = j.get("payload", {}) or {}
        found += len(p.get("raw_leads", []) or []) or len(p.get("leads", []) or [])
        verified += len(p.get("leads", []) or [])
        qualified += len((p.get("lead_qualifier", {}) or {}).get("results", []) or [])
        if p.get("send_ref") or p.get("outreach_send"):
            emailed += 1
    return [("Found", found), ("Verified", verified), ("Qualified", qualified),
            ("Emailed", emailed), ("Replied", 0), ("Booked", 0)]


# --- svg helpers -------------------------------------------------------------
def _donut(pct, color):
    import math
    r = 50
    circ = 2 * math.pi * r
    off = circ * (1 - min(100, max(0, pct)) / 100)
    return (f'<svg width="120" height="120" viewBox="0 0 120 120">'
            f'<circle cx="60" cy="60" r="{r}" fill="none" stroke="#16223c" stroke-width="14"/>'
            f'<circle cx="60" cy="60" r="{r}" fill="none" stroke="{color}" stroke-width="14" '
            f'stroke-linecap="round" stroke-dasharray="{circ:.0f}" stroke-dashoffset="{off:.0f}" '
            f'transform="rotate(-90 60 60)"/>'
            f'<text x="60" y="57" text-anchor="middle" fill="#EDF1FB" font-size="24" font-weight="750">{pct}%</text>'
            f'<text x="60" y="76" text-anchor="middle" fill="#8E9BBE" font-size="10">of budget</text></svg>')


_FN_COLORS = ["#4C8DFF", "#5A7BE8", "#8B7CFF", "#F5B14C", "#2FE3D2", "#3FD98B"]


def _funnel(rows, colors):
    mx = max((v for _, v in rows), default=0) or 1
    out = ['<div class="fn">']
    for i, (label, v) in enumerate(rows):
        w = max(5, round(v / mx * 100))
        out.append(f'<div class="fr"><span class="fl">{_esc(label)}</span>'
                   f'<div class="fbar" style="width:{w}%;background:{colors[i % len(colors)]}">{v}</div></div>')
    out.append("</div>")
    return "".join(out)


# --- THE SYSTEM MAP: every component + every labeled connection --------------
def _system_map(st):
    def c(k):
        return "#3FD98B" if st.get(k) else "#F5B14C"
    social_live = st.get("social_linkedin") or st.get("social_twitter") or st.get("social_facebook")
    g_on = st.get("google_sheets") or st.get("google_drive")
    P = []

    def box(x, y, w, h, col, title, sub="", tcol="#EDF1FB"):
        s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="#0B111F" stroke="{col}" stroke-width="1.3"/>'
        yt = y + (h / 2 + 4) if not sub else y + h / 2 - 2
        s += f'<text x="{x+w/2}" y="{yt:.0f}" text-anchor="middle" fill="{tcol}" font-size="11" font-weight="600">{title}</text>'
        if sub:
            s += f'<text x="{x+w/2}" y="{y+h/2+11:.0f}" text-anchor="middle" fill="#8E9BBE" font-size="9">{sub}</text>'
        return s

    def wire(x1, y1, x2, y2, col="#33507e", dash="", label="", lx=None, ly=None):
        mx = (x1 + x2) / 2
        s = (f'<path d="M{x1} {y1} C {mx} {y1}, {mx} {y2}, {x2} {y2}" fill="none" '
             f'stroke="{col}" stroke-width="1.3" {dash} marker-end="url(#arw)" opacity="0.85"/>')
        if label:
            s += (f'<text x="{lx or mx:.0f}" y="{(ly or (y1+y2)/2 - 4):.0f}" text-anchor="middle" '
                  f'fill="#8E9BBE" font-size="9">{label}</text>')
        return s

    P.append('<svg width="100%" viewBox="0 0 1220 640" style="max-width:100%;height:auto">'
             '<defs><marker id="arw" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto">'
             '<path d="M0,0 L6,3 L0,6" fill="#5a79aa"/></marker></defs>')

    # column labels
    for lx, txt in [(95, "SOURCES"), (300, "TRIGGER"), (620, "ENGINE (your VPS)"),
                    (900, "GOOGLE HUB"), (1120, "CHANNELS")]:
        P.append(f'<text x="{lx}" y="26" text-anchor="middle" fill="#59668A" font-size="10" '
                 f'font-weight="700" letter-spacing="1">{txt}</text>')

    # SOURCES (left)
    src = [("Web search", c("web_search"), 60), ("Web scraper", c("web_search"), 108),
           ("LinkedIn", c("linkedin_leads"), 156), ("Search Console", c("google_gsc_ga4"), 224),
           ("Analytics (GA4)", c("google_gsc_ga4"), 272)]
    for name, col, y in src:
        P.append(box(20, y, 150, 38, col, name))
    # n8n trigger
    P.append(box(230, 470, 140, 40, "#8B7CFF", "n8n", "cron + webhooks"))

    # ENGINE big container
    P.append('<rect x="420" y="46" width="400" height="470" rx="12" fill="#0D1526" stroke="#2FE3D2" stroke-width="1.6"/>')
    P.append('<text x="620" y="70" text-anchor="middle" fill="#2FE3D2" font-size="13" font-weight="750">Automation Engine</text>')
    P.append('<text x="620" y="86" text-anchor="middle" fill="#8E9BBE" font-size="9.5">orchestrator · runs 24/7</text>')
    # inner blocks
    P.append(box(445, 100, 350, 34, "#4C8DFF", "Orchestrator", "decides the next step for every job"))
    P.append('<rect x="445" y="146" width="350" height="70" rx="7" fill="#0B111F" stroke="#2b3a5c"/>')
    P.append('<text x="455" y="163" fill="#8B7CFF" font-size="9.5" font-weight="700">CONTENT AGENTS</text>')
    P.append('<text x="455" y="180" fill="#C7D0EA" font-size="10">site · competitor · strategist · writer</text>')
    P.append('<text x="455" y="196" fill="#C7D0EA" font-size="10">SEO/AEO tuner · quality &amp; legal · publisher</text>')
    P.append('<text x="455" y="210" fill="#8E9BBE" font-size="9">→ images + video (phase 2)</text>')
    P.append('<rect x="445" y="228" width="350" height="70" rx="7" fill="#0B111F" stroke="#2b3a5c"/>')
    P.append('<text x="455" y="245" fill="#8B7CFF" font-size="9.5" font-weight="700">LEAD MACHINE</text>')
    P.append('<text x="455" y="262" fill="#C7D0EA" font-size="10">sourcing · verify · qualifier · segmenter</text>')
    P.append('<text x="455" y="278" fill="#C7D0EA" font-size="10">outreach writer · reply responder</text>')
    P.append('<text x="455" y="292" fill="#8E9BBE" font-size="9">cold-email first, then paid marketing</text>')
    P.append(box(445, 310, 168, 34, "#4C8DFF", "Ads optimizer", "SEO + performance"))
    P.append(box(627, 310, 168, 34, "#4C8DFF", "Learning agent", "gets smarter monthly"))
    P.append(box(445, 356, 168, 34, "#3FD98B", "Approval gate", "your yes/no"))
    P.append(box(627, 356, 168, 34, "#3FD98B", "Budget guard", "$200/mo hard cap"))
    # Claude + Postgres (below engine, inside)
    P.append(box(445, 404, 168, 40, "#3FD98B", "Claude", "Opus 4.8 / Haiku 4.5"))
    P.append(box(627, 404, 168, 40, "#2FE3D2", "Postgres", "engine memory"))
    P.append(box(445, 458, 350, 40, "#2FE3D2", "Control dashboard", "this screen · localhost:8000"))

    # GOOGLE HUB
    P.append(f'<rect x="850" y="60" width="180" height="150" rx="10" fill="#0D1526" stroke="{"#3FD98B" if g_on else "#F5B14C"}" stroke-width="1.5"/>')
    P.append('<text x="940" y="82" text-anchor="middle" fill="#EDF1FB" font-size="11.5" font-weight="700">Google Workspace</text>')
    P.append(box(866, 96, 148, 32, c("google_sheets"), "Sheets", "your dashboard data"))
    P.append(box(866, 134, 148, 32, c("google_drive"), "Drive", "content as JSON"))
    P.append(box(866, 172, 148, 32, c("email_send"), "Gmail", "sending"))

    # CHANNELS (right)
    ch = [("Website (WordPress)", c("wordpress_publish"), 60),
          ("LinkedIn", c("social_linkedin"), 100), ("X / Twitter", c("social_twitter"), 140),
          ("Facebook", c("social_facebook"), 180),
          ("Instagram", "#F5B14C", 220), ("TikTok", "#F5B14C", 260),
          ("Email out (SMTP)", c("email_send"), 316),
          ("Replies in (IMAP)", c("email_reply_inbound"), 356)]
    for name, col, y in ch:
        P.append(box(1050, y, 160, 34, col, name))

    # WIRES
    # sources -> engine (bundle into orchestrator)
    for _, _, y in src:
        P.append(wire(170, y + 19, 420, 117, "#33507e"))
    P.append('<text x="300" y="150" text-anchor="middle" fill="#8E9BBE" font-size="9.5">leads · research · SEO data</text>')
    # n8n -> engine
    P.append(wire(370, 490, 420, 250, "#5b4fb0", label="triggers", lx=400, ly=350))
    # engine -> google hub
    P.append(wire(820, 130, 850, 130, "#2FE3D2", label="mirror + content", lx=838, ly=118))
    # engine -> channels (publish/post)
    P.append(wire(820, 200, 1050, 90, "#2FE3D2", label="publish", lx=940, ly=150))
    P.append(wire(820, 240, 1050, 180, "#2FE3D2"))
    P.append(wire(820, 300, 1050, 240, "#2FE3D2", label="post", lx=940, ly=290))
    P.append(wire(820, 330, 1050, 333, "#2FE3D2", label="send email", lx=940, ly=328))
    # replies in -> engine (back arrow)
    P.append(wire(1050, 373, 820, 470, "#33507e", dash='stroke-dasharray="4 3"', label="answer replies", lx=940, ly=455))

    P.append("</svg>")

    legend = ('<div class="maplegend">'
              '<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#3FD98B;margin-right:5px"></span>Connected &amp; running</span>'
              '<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#F5B14C;margin-right:5px"></span>Ready — needs its key</span>'
              '<span><span style="color:#5a79aa">→</span> data flows this way</span></div>')
    return "".join(P) + legend


# --- login -------------------------------------------------------------------
def login_html(error: str = "") -> str:
    err = f'<p style="color:#FF6B93;font-size:13px;margin:0 0 10px">{_esc(error)}</p>' if error else ""
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Sign in · Control Center</title><style>" + CSS +
            "body{display:flex;align-items:center;justify-content:center;min-height:100vh}"
            ".box{background:var(--s1);border:1px solid var(--line);border-radius:14px;padding:26px;width:330px;max-width:90vw}"
            "input{width:100%;margin-bottom:12px;background:var(--s2);border:1px solid var(--line);color:var(--ink);border-radius:9px;padding:11px}"
            "button{width:100%;background:var(--teal);color:#04121a;font-weight:700;border:none;border-radius:9px;padding:11px;cursor:pointer}</style></head><body>"
            "<form class='box' method='post' action='/login'>"
            "<h1 style='font-size:17px;margin:0 0 2px'>Business Control Center</h1>"
            "<p style='color:#8E9BBE;font-size:12px;margin:0 0 16px'>Sign in to continue</p>" + err +
            "<input type='password' name='password' placeholder='Password' autofocus>"
            "<button type='submit'>Sign in</button></form></body></html>")


# --- dashboard ---------------------------------------------------------------
def dashboard_html(*, jobs, st, health, month_spent, month_cap, day_spent, day_cap,
                   taste_skills, has_password=False):
    jobs, st, health = jobs or [], st or {}, health or {}
    published = sum(1 for j in jobs if _STAGE_OF.get(j.get("status", "")) in (4, 5)
                    and j.get("type") != "outreach_campaign")
    lead_rows = _lead_funnel(jobs)
    leads_found, emails_sent = lead_rows[0][1], lead_rows[3][1]
    autos = _autos(st)
    ok = sum(1 for g in autos.values() for _, v in g if v)
    total = sum(len(g) for g in autos.values())
    pct = round(month_spent / month_cap * 100) if month_cap else 0
    bcol = "#3FD98B" if pct < 70 else ("#F5B14C" if pct < 90 else "#FF6B93")
    healthy = health.get("healthy")

    def kpi(lab, val, sub, col="var(--mut)", dot=""):
        d = f'<span class="dot" style="width:6px;height:6px;border-radius:50%;background:{dot}"></span>' if dot else ""
        return (f'<div class="kpi"><div class="lab">{lab}</div><div class="val tnum">{val}</div>'
                f'<div class="sub" style="color:{col}">{d}{sub}</div></div>')

    strip = ("<div class='kpis'>"
             + kpi("Content live", published, "published this month")
             + kpi("Leads collected", leads_found, "found by agents")
             + kpi("Cold emails", emails_sent, "sent this month")
             + kpi("Spend", f"${month_spent:.0f}<small>/{month_cap:.0f}</small>",
                   ("on budget" if pct < 90 else "near cap"),
                   "var(--good)" if pct < 90 else "var(--warn)",
                   "var(--good)" if pct < 90 else "var(--warn)")
             + kpi("Automations", f"{ok}<small>/{total}</small>",
                   (f"{total-ok} need a key" if ok < total else "all running"),
                   "var(--warn)" if ok < total else "var(--good)",
                   "var(--warn)" if ok < total else "var(--good)")
             + "</div>")

    onboarding = "" if jobs else ("<div class='note'><b>Your control center is ready.</b> "
                                  "The charts fill in as your agents run and you connect keys — no fake numbers here. "
                                  "Start a job or connect a channel to watch it move.</div>")

    # budget + pipeline
    budget = ("<div class='card'><div class='ch'><p class='ct'>Monthly AI budget</p>"
              f"<span class='cx'>${month_spent:.2f} / ${month_cap:.0f}</span></div>"
              "<p class='cc'>The system pauses itself before it ever goes over your cap.</p>"
              "<div style='display:flex;align-items:center;gap:20px'>" + _donut(pct, bcol) +
              f"<div><div style='font-size:11.5px;color:var(--mut)'>Today</div>"
              f"<div class='tnum' style='font-size:23px;font-weight:750'>${day_spent:.2f}</div>"
              f"<div style='font-size:11.5px;color:var(--dim)'>of ${day_cap:.0f}/day</div></div></div></div>")
    pl = _pipeline(jobs)
    pipeline = ("<div class='card'><p class='ct'>Content pipeline — where each piece is</p>"
                "<p class='cc'>Idea → written → checked → your approval → live → measured.</p>"
                + (_funnel(list(zip(_STAGES, pl)), _FN_COLORS) if sum(pl)
                   else "<div class='empty'>No content jobs yet.</div>") + "</div>")

    # lead funnel + activity
    lead = ("<div class='card'><p class='ct'>Lead funnel — stranger to booked call</p>"
            "<p class='cc'>How many people move through each step.</p>"
            + (_funnel(lead_rows, _FN_COLORS) if any(v for _, v in lead_rows)
               else "<div class='empty'>No leads yet — connect the lead finder.</div>") + "</div>")
    fe = []
    for j in list(reversed(jobs))[:8]:
        verb = _FRIENDLY.get(j.get("status", ""), f"is at “{_esc(j.get('status',''))}”")
        kind = "Content" if j.get("type") != "outreach_campaign" else "Outreach"
        fe.append(f"<div class='fe'><span class='tm'>{_esc(str(j.get('job_id',''))[:11])}</span>"
                  f"<span class='tx'><b>{kind}</b> {verb}.</span></div>")
    feed = ("<div class='card'><p class='ct'>Live activity</p><p class='cc'>What your agents did, newest first.</p>"
            "<div class='feed'>" + ("".join(fe) if fe else "<div class='empty'>No activity yet.</div>") + "</div></div>")

    # automations
    groups = []
    for name, items in autos.items():
        live_n = sum(1 for _, v in items if v)
        chips = "".join(
            f"<div class='chip'><span class='nm'><span class='dot' style='background:{'#3FD98B' if v else '#F5B14C'}'></span>{_esc(lbl)}</span>"
            f"<span class='pill {'p-live' if v else 'p-need'}'>{'live' if v else 'needs key'}</span></div>"
            for lbl, v in items)
        groups.append(f"<div class='grp'><div class='gh'><span>{_esc(name)}</span>"
                      f"<span style='color:var(--dim)'>{live_n}/{len(items)}</span></div>{chips}</div>")
    autos_card = ("<div class='card full'><p class='ct'>Your automations — live status</p>"
                  "<p class='cc'>Every capability we built, grouped. Green = running · Amber = ready, needs its key.</p>"
                  "<div class='autos'>" + "".join(groups) + "</div></div>")

    # business cost breakdown
    total_cost = sum(float(j.get("cost_so_far_usd", 0)) for j in jobs)
    content_cost = sum(float(j.get("cost_so_far_usd", 0)) for j in jobs if j.get("type") != "outreach_campaign")
    lead_cost = total_cost - content_cost
    cmx = max(content_cost, lead_cost, 0.01)
    cost = ("<div class='card'><p class='ct'>Where the money goes</p>"
            "<p class='cc'>Your AI spend, split by what it's doing.</p><div class='bars'>"
            f"<div class='br'><span class='bl'>Content</span><div class='track'><i style='width:{content_cost/cmx*100:.0f}%;background:#4C8DFF'></i></div><span class='bv tnum'>${content_cost:.2f}</span></div>"
            f"<div class='br'><span class='bl'>Leads/email</span><div class='track'><i style='width:{lead_cost/cmx*100:.0f}%;background:#8B7CFF'></i></div><span class='bv tnum'>${lead_cost:.2f}</span></div>"
            f"<div class='br'><span class='bl'>Total</span><div class='track'><i style='width:{total_cost/max(month_cap,0.01)*100:.0f}%;background:{bcol}'></i></div><span class='bv tnum'>${total_cost:.2f}</span></div>"
            "</div></div>")

    # SEO / AEO / GEO with suggestions
    gsc = st.get("google_gsc_ga4")
    if gsc:
        seo_body = "<div class='empty'>Connected — traffic &amp; ranking charts appear here after the first pull.</div>"
    else:
        seo_body = ("<div class='sug'><span class='i'>◆</span><span>Connect <b>Google Search Console</b> to track keyword rankings &amp; on-page SEO.</span></div>"
                    "<div class='sug'><span class='i'>◆</span><span>Connect <b>Google Analytics</b> to see traffic and which pages convert.</span></div>"
                    "<div class='sug'><span class='i'>◆</span><span>Your articles are already built for <b>AI answers</b> (ChatGPT/Google AI) — mentions show here once tracking is on.</span></div>")
    seo = ("<div class='card'><p class='ct'>SEO · AEO · GEO</p>"
           "<p class='cc'>Search, AI-answer and geo visibility — with next-step suggestions.</p>" + seo_body + "</div>")

    # approvals + command
    ap = []
    for j in jobs:
        if j.get("status") != "AWAITING_APPROVAL":
            continue
        p = j.get("payload", {}) or {}
        title = (p.get("content_producer", {}) or {}).get("title") or p.get("category") or j.get("job_id")
        kind = "Website · ready to publish" if j.get("type") != "outreach_campaign" else "Email · ready to send"
        ap.append(f"<div class='ap'><div style='flex:1'><div class='apt'>{_esc(title)}</div><div class='apk'>{kind}</div></div>"
                  f"<button class='btn ok' disabled>Publish</button><button class='btn no' disabled>Hold</button></div>")
    opts = "".join(f"<option value='{_esc(s)}'>{_esc(s)}</option>" for s in taste_skills)
    approve = ("<div class='card'><p class='ct'>Waiting for your approval</p><p class='cc'>Nothing goes live without you.</p>"
               "<div class='appr'>" + ("".join(ap) if ap else "<div class='empty'>Nothing waiting right now.</div>") + "</div>"
               "<p class='ct' style='margin-top:15px'>Talk to an agent</p>"
               "<div class='cmd'><select id='sk'>" + opts + "</select>"
               "<input id='inp' placeholder='{\"site_url\":\"https://...\"}'><button onclick='runSkill()'>Run</button></div>"
               "<pre id='out'>Pick an agent, add input, press Run.</pre></div>")

    logout = "<a class='logout' href='/logout'>Sign out</a>" if has_password else ""
    script = ("<script>async function runSkill(){var sk=document.getElementById('sk').value,"
              "out=document.getElementById('out'),inp=document.getElementById('inp').value;"
              "out.textContent='Running '+sk+'…';try{var b=JSON.parse(inp||'{}');}"
              "catch(e){out.textContent='That input is not valid JSON.';return;}"
              "try{var r=await fetch('/skills/'+sk+'/taste',{method:'POST',headers:{'Content-Type':'application/json'},"
              "body:JSON.stringify({input:b})});out.textContent=JSON.stringify(await r.json(),null,2);}"
              "catch(e){out.textContent='Error: '+e;}}</script>")

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Business Control Center</title><style>" + CSS + "</style></head><body><div class='wrap'>"
        "<div class='bar'><div class='brand'><div class='logo'>A</div>"
        "<div><h1>Anthropos — Control Center</h1><small>Your automation, in plain English</small></div></div>"
        "<div style='display:flex;gap:9px;align-items:center'><span class='status'><span class='dot' style='background:"
        + ("#3FD98B" if healthy else "#F5B14C") + "'></span>" + ("All systems nominal" if healthy else "Check health")
        + "</span>" + logout + "</div></div>"
        + onboarding + strip
        + "<div class='sec'>Money &amp; production</div>"
        + "<div class='grid g2'>" + budget + pipeline + "</div>"
        + "<div class='grid g2' style='margin-top:11px'>" + cost + seo + "</div>"
        + "<div class='sec'>Leads &amp; activity</div>"
        + "<div class='grid g2'>" + lead + feed + "</div>"
        + "<div class='sec'>Every automation</div>" + autos_card
        + "<div class='sec'>System map — how everything is wired</div>"
        + "<div class='card full'><p class='cc' style='margin-top:0'>Every part of your system and how data flows between them. "
        "Green boxes are connected; amber are ready and just need their key.</p>" + _system_map(st) + "</div>"
        + "<div class='sec'>Approvals &amp; controls</div>"
        + "<div class='grid g2'>" + approve
        + "<div class='card'><p class='ct'>System health</p><p class='cc'>Live checks on the engine's core parts.</p>"
        + "".join(
            f"<div class='chip'><span class='nm'><span class='dot' style='background:"
            + ({'ok': '#3FD98B', 'fail': '#FF6B93'}.get((health.get(k) or {}).get('status'), '#8E9BBE'))
            + f"'></span>{lbl}</span><span class='cx'>{_esc((health.get(k) or {}).get('status','—'))}</span></div>"
            for k, lbl in [("anthropic", "Claude API"), ("postgres", "Database (memory)"), ("connectors", "Connectors")])
        + "</div></div>"
        + "<div class='links'><a href='/health'>health</a> · <a href='/jobs'>jobs</a> · <a href='/skills'>skills</a></div>"
        + "</div>" + script + "</body></html>")


if __name__ == "__main__":
    demo = [
        {"job_id": "job_a1b2", "type": "content_piece", "status": "AWAITING_APPROVAL",
         "payload": {"content_producer": {"title": "24/7 competitor price monitoring"}}, "cost_so_far_usd": 0.04},
        {"job_id": "job_c3d4", "type": "content_piece", "status": "optimized", "payload": {}, "cost_so_far_usd": 0.11},
        {"job_id": "job_e5f6", "type": "outreach_campaign", "status": "sent",
         "payload": {"leads": [{"email": "a@b.com"}], "send_ref": "x"}, "cost_so_far_usd": 0.02},
    ]
    html = dashboard_html(jobs=demo, st={"wordpress_publish": True, "social_linkedin": True, "google_sheets": False},
                          health={"healthy": True, "anthropic": {"status": "ok"}, "postgres": {"status": "ok"}},
                          month_spent=0.17, month_cap=200, day_spent=0.17, day_cap=50,
                          taste_skills=["content_producer", "seo_optimizer"])
    for need in ("Control Center", "System map", "Automation Engine", "Where the money goes",
                 "SEO · AEO · GEO", "24/7 competitor price monitoring", "<marker"):
        assert need in html, need
    assert "control center is ready" in dashboard_html(
        jobs=[], st={}, health={"healthy": True}, month_spent=0, month_cap=200,
        day_spent=0, day_cap=50, taste_skills=[])
    assert "Sign in" in login_html()
    print("OK — pro dashboard + full system map render (populated + empty). No network.")
