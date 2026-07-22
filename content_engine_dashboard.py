"""
content_engine_dashboard.py
============================================================================
The Business Control Center UI (Phase 1, redesigned). Plain-English, chart-led,
no machine jargon. Pure render functions: they take primitives (jobs, connector
status, health, budget) and return HTML. content_engine_api.py gathers the data
and calls dashboard_html(); everything here is offline-testable.

Charts are hand-drawn inline SVG (no external libraries, works on the VPS with
no internet). Numbers come from the live engine; panels with no data yet show a
clean empty state instead of fake figures.
============================================================================
"""

from __future__ import annotations

# --- palette / css ----------------------------------------------------------
CSS = """
:root{--bg:#0A0E1A;--panel:#121A2E;--panel2:#0E1524;--line:#1E2A45;--ink:#EEF2FF;
--mut:#93A0C4;--dim:#5D6A8C;--teal:#2FE3D2;--violet:#8B7CFF;--good:#46E08B;--warn:#F5B14C;--bad:#FF5C8A}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 80% -10%,#132038 0,var(--bg) 55%);
color:var(--ink);font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.tnum{font-variant-numeric:tabular-nums}
.wrap{max-width:1180px;margin:0 auto;padding:22px 16px 70px}
.note{background:#16233d;border:1px solid var(--teal);border-radius:12px;padding:10px 14px;font-size:12.5px;color:var(--mut);margin-bottom:16px}
.note b{color:var(--teal)}
.head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:4px}
.brand{display:flex;align-items:center;gap:11px}
.logo{width:34px;height:34px;border-radius:9px;background:linear-gradient(135deg,var(--teal),var(--violet));display:grid;place-items:center;color:#04121a;font-weight:800}
h1{font-size:20px;margin:0;letter-spacing:-.01em}
.tag{color:var(--mut);font-size:12.5px;margin:2px 0 20px}
.who{display:flex;align-items:center;gap:9px;color:var(--mut);font-size:12.5px}
.logout{color:var(--mut);font-size:12px;border:1px solid var(--line);border-radius:8px;padding:5px 10px;text-decoration:none}
.strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin-bottom:14px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:15px 16px}
.kpi .lab{color:var(--mut);font-size:11.5px;letter-spacing:.04em;text-transform:uppercase}
.kpi .val{font-size:27px;font-weight:750;margin-top:5px;letter-spacing:-.02em}
.kpi .sub{font-size:12px;margin-top:3px;color:var(--mut)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:17px}
.full{grid-column:1/-1}
.ct{font-size:14px;font-weight:700;margin:0}
.cc{color:var(--mut);font-size:12px;margin:3px 0 14px}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--mut);margin-top:10px}
.lg{display:inline-flex;align-items:center;gap:6px}.sw{width:10px;height:10px;border-radius:3px;display:inline-block}
.fn{display:flex;flex-direction:column;gap:7px}
.fr{display:flex;align-items:center;gap:10px}
.fbar{height:30px;border-radius:7px;display:flex;align-items:center;padding:0 10px;color:#04121a;font-weight:700;font-size:12.5px;min-width:34px}
.fr .fl{width:110px;color:var(--mut);font-size:12.5px;flex-shrink:0}
.bars{display:flex;flex-direction:column;gap:9px}
.br{display:flex;align-items:center;gap:10px}.br .bl{width:92px;font-size:12.5px;color:var(--mut)}
.track{flex:1;height:12px;background:var(--panel2);border-radius:99px;overflow:hidden}.track i{display:block;height:100%;border-radius:99px}
.br .bv{width:44px;text-align:right;font-size:12px;color:var(--ink)}
.autos{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px}
.grp .gh{font-size:12px;color:var(--violet);font-weight:700;margin:0 0 8px;letter-spacing:.02em}
.chip{display:flex;align-items:center;gap:8px;font-size:12.5px;padding:6px 0;border-bottom:1px solid #0f1930}
.dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.feed{display:flex;flex-direction:column}
.fe{display:flex;gap:12px;padding:9px 0;border-bottom:1px solid #0f1930}
.fe .tm{color:var(--dim);font-size:11.5px;width:70px;flex-shrink:0;padding-top:1px}
.fe .tx{font-size:13px}.fe .tx b{font-weight:650}
.appr{display:flex;flex-direction:column;gap:9px}
.ap{display:flex;align-items:center;gap:11px;background:var(--panel2);border:1px solid var(--line);border-radius:11px;padding:10px 12px}
.ap .apt{flex:1;font-size:13px}.ap .apk{font-size:11px;color:var(--mut)}
.btn{border:none;border-radius:9px;padding:7px 13px;font-weight:700;font-size:12.5px;cursor:pointer}
.ok{background:var(--good);color:#04140a}.no{background:transparent;border:1px solid var(--line);color:var(--mut)}
.cmd{display:flex;gap:8px;flex-wrap:wrap;margin-top:4px}
.cmd select,.cmd input{flex:1;min-width:130px;background:var(--panel2);border:1px solid var(--line);color:var(--ink);border-radius:9px;padding:9px 11px;font:inherit}
.cmd button{background:var(--teal);color:#04121a;font-weight:700;border:none;border-radius:9px;padding:9px 15px;cursor:pointer}
.empty{color:var(--dim);font-size:12.5px;padding:14px 0;text-align:center}
pre{background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:10px;overflow:auto;font-size:11.5px;color:#B9C4E0;max-height:220px;margin-top:8px}
.links{margin-top:12px;font-size:12px;color:var(--mut)}.links a{color:var(--teal);text-decoration:none}
@media(max-width:820px){.grid,.grid3{grid-template-columns:1fr}}
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
    "sourced": 0, "qualified": 0, "segmented": 0,
    "produced": 1, "drafted": 1,
    "seo_checked": 2,
    "AWAITING_APPROVAL": 3,
    "publishing": 4, "published": 4, "sending": 4, "sent": 4, "measuring": 4, "tracking": 4,
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


def _pipeline(jobs: list) -> list:
    counts = [0] * len(_STAGES)
    for j in jobs:
        i = _STAGE_OF.get(j.get("status", ""))
        if i is not None:
            counts[i] += 1
    return counts


def _lead_funnel(jobs: list) -> list:
    found = verified = qualified = emailed = replied = booked = 0
    for j in jobs:
        if j.get("type") != "outreach_campaign":
            continue
        p = j.get("payload", {}) or {}
        found += len(p.get("raw_leads", []) or []) or len(p.get("leads", []) or [])
        verified += len(p.get("leads", []) or [])
        lq = p.get("lead_qualifier", {}) or {}
        qualified += len(lq.get("results", []) or [])
        if p.get("send_ref") or p.get("outreach_send"):
            emailed += 1
    return [("Found", found), ("Verified", verified), ("Qualified", qualified),
            ("Emailed", emailed), ("Replied", replied), ("Booked", booked)]


# --- svg helpers -------------------------------------------------------------
def _donut(pct: int, color: str) -> str:
    import math
    r = 52
    circ = 2 * math.pi * r
    off = circ * (1 - min(100, max(0, pct)) / 100)
    return (
        f'<svg width="132" height="132" viewBox="0 0 132 132">'
        f'<circle cx="66" cy="66" r="{r}" fill="none" stroke="#182238" stroke-width="16"/>'
        f'<circle cx="66" cy="66" r="{r}" fill="none" stroke="{color}" stroke-width="16" '
        f'stroke-linecap="round" stroke-dasharray="{circ:.0f}" stroke-dashoffset="{off:.0f}" '
        f'transform="rotate(-90 66 66)"/>'
        f'<text x="66" y="62" text-anchor="middle" fill="#EEF2FF" font-size="26" font-weight="750">{pct}%</text>'
        f'<text x="66" y="82" text-anchor="middle" fill="#93A0C4" font-size="11">of budget</text></svg>')


_FN_COLORS = ["#37507e", "#4a6bd6", "#8B7CFF", "#F5B14C", "#2FE3D2", "#46E08B"]


def _funnel(rows: list, colors: list) -> str:
    mx = max((v for _, v in rows), default=0) or 1
    out = ['<div class="fn">']
    for i, (label, v) in enumerate(rows):
        w = max(6, round(v / mx * 100))
        out.append(f'<div class="fr"><span class="fl">{_esc(label)}</span>'
                   f'<div class="fbar" style="width:{w}%;background:{colors[i % len(colors)]}">{v}</div></div>')
    out.append("</div>")
    return "".join(out)


# --- login -------------------------------------------------------------------
def login_html(error: str = "") -> str:
    err = f'<p style="color:#FF5C8A;font-size:13px;margin:0 0 10px">{_esc(error)}</p>' if error else ""
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Sign in · Control Center</title><style>" + CSS +
            "body{display:flex;align-items:center;justify-content:center;min-height:100vh}"
            ".box{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:26px;width:330px;max-width:90vw}"
            "input{width:100%;margin-bottom:12px;background:var(--panel2);border:1px solid var(--line);color:var(--ink);border-radius:9px;padding:11px}"
            "button{width:100%;background:var(--teal);color:#04121a;font-weight:700;border:none;border-radius:9px;padding:11px;cursor:pointer}</style></head><body>"
            "<form class='box' method='post' action='/login'>"
            "<h1 style='font-size:18px;margin:0 0 2px'>Business Control Center</h1>"
            "<p class='tag' style='margin:0 0 16px'>Sign in to continue</p>" + err +
            "<input type='password' name='password' placeholder='Password' autofocus>"
            "<button type='submit'>Sign in</button></form></body></html>")


# --- dashboard ---------------------------------------------------------------
def dashboard_html(*, jobs, st, health, month_spent, month_cap, day_spent, day_cap,
                   taste_skills, has_password=False) -> str:
    jobs = jobs or []
    st = st or {}
    health = health or {}

    # KPIs
    published = sum(1 for j in jobs if _STAGE_OF.get(j.get("status", "")) in (4, 5)
                    and j.get("type") != "outreach_campaign")
    lead_rows = _lead_funnel(jobs)
    leads_found = lead_rows[0][1]
    emails_sent = lead_rows[3][1]
    autos = _autos(st)
    ok = sum(1 for grp in autos.values() for _, v in grp if v)
    total = sum(len(grp) for grp in autos.values())
    pct = round(month_spent / month_cap * 100) if month_cap else 0
    bar_col = "#46E08B" if pct < 70 else ("#F5B14C" if pct < 90 else "#FF5C8A")

    def kpi(lab, val, sub, sub_col="var(--mut)"):
        return (f'<div class="kpi"><div class="lab">{lab}</div>'
                f'<div class="val tnum">{val}</div>'
                f'<div class="sub" style="color:{sub_col}">{sub}</div></div>')

    strip = ("<div class='strip'>"
             + kpi("Content live · month", published, "articles &amp; posts published")
             + kpi("Leads collected", leads_found, "found by your agents")
             + kpi("Cold emails sent", emails_sent, "through your mail")
             + kpi("Spend · month", f"${month_spent:.0f}<span style='color:var(--dim);font-size:16px'>/{month_cap:.0f}</span>",
                   "on budget" if pct < 90 else "near cap", "var(--good)" if pct < 90 else "var(--warn)")
             + kpi("Agents healthy", f"{ok}<span style='color:var(--dim);font-size:16px'>/{total}</span>",
                   f"{total-ok} need a key" if ok < total else "all running",
                   "var(--warn)" if ok < total else "var(--good)")
             + "</div>")

    # budget + pipeline
    onboarding = "" if jobs else ("<div class='note'><b>Your control center is ready.</b> "
                                  "The charts fill up as your agents run and you connect keys. "
                                  "Create your first job or connect a channel to see it move.</div>")

    budget_card = (
        "<div class='card'><p class='ct'>Monthly AI budget</p>"
        f"<p class='cc'>You've used ${month_spent:.2f} of your ${month_cap:.0f} cap. "
        "The system pauses itself before it ever goes over.</p>"
        "<div style='display:flex;align-items:center;gap:22px'>" + _donut(pct, bar_col) +
        f"<div style='flex:1'><div style='font-size:12px;color:var(--mut);margin-bottom:6px'>Today's spend</div>"
        f"<div style='font-size:24px;font-weight:750' class='tnum'>${day_spent:.2f}</div>"
        f"<div style='font-size:12px;color:var(--mut)'>of ${day_cap:.0f}/day</div></div></div></div>")

    pl = _pipeline(jobs)
    pipeline_card = (
        "<div class='card'><p class='ct'>Content pipeline — where every piece is now</p>"
        "<p class='cc'>From idea to measured result. Anything at “waiting for you” needs a click.</p>"
        + (_funnel(list(zip(_STAGES, pl)), _FN_COLORS) if sum(pl)
           else "<div class='empty'>No content jobs yet.</div>") + "</div>")

    # lead funnel + automations status handled below
    lead_card = (
        "<div class='card'><p class='ct'>Lead funnel — stranger to booked call</p>"
        "<p class='cc'>How many people move through each step.</p>"
        + (_funnel(lead_rows, _FN_COLORS) if any(v for _, v in lead_rows)
           else "<div class='empty'>No leads yet — connect the lead finder to start.</div>") + "</div>")

    # automations
    groups = []
    for name, items in autos.items():
        chips = "".join(
            f"<div class='chip'><span class='dot' style='background:{'#46E08B' if v else '#F5B14C'}'></span>{_esc(lbl)}</div>"
            for lbl, v in items)
        groups.append(f"<div class='grp'><div class='gh'>{_esc(name)}</div>{chips}</div>")
    autos_card = ("<div class='card full' style='margin-bottom:12px'>"
                  "<p class='ct'>Your automations — live status</p>"
                  "<p class='cc'>Green = running now · Amber = ready, just needs its key connected.</p>"
                  "<div class='autos'>" + "".join(groups) + "</div></div>")

    # activity feed (last 8 jobs, newest first)
    fe = []
    for j in list(reversed(jobs))[:8]:
        verb = _FRIENDLY.get(j.get("status", ""), f"is at “{_esc(j.get('status',''))}”")
        kind = "Content" if j.get("type") != "outreach_campaign" else "Outreach"
        fe.append(f"<div class='fe'><span class='tm'>{_esc(str(j.get('job_id',''))[:10])}</span>"
                  f"<span class='tx'><b>{kind}</b> {verb}.</span></div>")
    feed_card = ("<div class='card'><p class='ct'>Live activity — what your agents did</p>"
                 "<p class='cc'>Newest first.</p><div class='feed'>"
                 + ("".join(fe) if fe else "<div class='empty'>No activity yet.</div>") + "</div></div>")

    # approvals (AWAITING_APPROVAL)
    ap = []
    for j in jobs:
        if j.get("status") != "AWAITING_APPROVAL":
            continue
        p = j.get("payload", {}) or {}
        title = (p.get("content_producer", {}) or {}).get("title") or p.get("category") or j.get("job_id")
        kind = "Website · ready to publish" if j.get("type") != "outreach_campaign" else "Email · ready to send"
        ap.append(f"<div class='ap'><div><div class='apt'>{_esc(title)}</div>"
                  f"<div class='apk'>{kind}</div></div>"
                  f"<button class='btn ok' disabled title='Approve via /jobs/{_esc(j.get('job_id'))}/approve'>Publish</button>"
                  f"<button class='btn no' disabled>Hold</button></div>")
    opts = "".join(f"<option value='{_esc(s)}'>{_esc(s)}</option>" for s in taste_skills)
    approve_card = ("<div class='card'><p class='ct'>Waiting for your approval</p>"
                    "<p class='cc'>Nothing goes live without you.</p><div class='appr'>"
                    + ("".join(ap) if ap else "<div class='empty'>Nothing waiting right now.</div>") + "</div>"
                    "<p class='ct' style='margin-top:16px'>Talk to an agent</p>"
                    "<div class='cmd'><select id='sk'>" + opts + "</select>"
                    "<input id='inp' placeholder='{\"site_url\":\"https://...\"}'>"
                    "<button onclick='runSkill()'>Run</button></div>"
                    "<pre id='out'>Pick an agent, add input, press Run.</pre></div>")

    # system map
    def mc(k):
        return "#46E08B" if st.get(k) else "#F5B14C"
    g_on = st.get("google_sheets") or st.get("google_drive")
    smap = ("<div class='card full'><p class='ct'>System map — how it all connects</p>"
            "<p class='cc'>Your agents live on the VPS; what they make lands in Google; then it goes to your channels. Green = connected.</p>"
            "<svg width='100%' height='200' viewBox='0 0 900 200' style='max-width:100%'>"
            "<defs><marker id='ar' markerWidth='8' markerHeight='8' refX='6' refY='3' orient='auto'>"
            "<path d='M0,0 L6,3 L0,6' fill='#2FE3D2'/></marker></defs>"
            "<rect x='20' y='76' width='150' height='48' rx='10' fill='#0E1524' stroke='#37507e'/>"
            "<text x='95' y='98' text-anchor='middle' fill='#EEF2FF' font-size='12.5' font-weight='600'>Web · LinkedIn</text>"
            "<text x='95' y='114' text-anchor='middle' fill='#93A0C4' font-size='10.5'>leads &amp; research</text>"
            "<rect x='330' y='55' width='230' height='90' rx='14' fill='#14203a' stroke='#2FE3D2' stroke-width='2'/>"
            "<text x='445' y='88' text-anchor='middle' fill='#2FE3D2' font-size='14' font-weight='750'>Your Agents (VPS)</text>"
            "<text x='445' y='108' text-anchor='middle' fill='#93A0C4' font-size='11'>write · score · decide · learn</text>"
            "<text x='445' y='126' text-anchor='middle' fill='#46E08B' font-size='11'>powered by Claude</text>"
            f"<rect x='700' y='20' width='180' height='70' rx='12' fill='#0E1524' stroke='{'#46E08B' if g_on else '#F5B14C'}'/>"
            "<text x='790' y='44' text-anchor='middle' fill='#EEF2FF' font-size='12.5' font-weight='700'>Google Workspace</text>"
            f"<text x='790' y='62' text-anchor='middle' fill='{'#46E08B' if g_on else '#F5B14C'}' font-size='10.5'>Sheets · Drive · Gmail</text>"
            "<text x='790' y='78' text-anchor='middle' fill='#93A0C4' font-size='10.5'>your data &amp; content</text>"
            f"<rect x='700' y='108' width='180' height='30' rx='8' fill='#0E1524' stroke='{mc('wordpress_publish')}'/>"
            "<text x='790' y='128' text-anchor='middle' fill='#EEF2FF' font-size='12'>Website (WordPress)</text>"
            f"<rect x='700' y='150' width='180' height='30' rx='8' fill='#0E1524' stroke='{'#46E08B' if (st.get('social_linkedin') or st.get('social_twitter') or st.get('social_facebook')) else '#F5B14C'}'/>"
            "<text x='790' y='170' text-anchor='middle' fill='#EEF2FF' font-size='12'>Social channels</text>"
            "<path d='M170,100 C 250,100 260,100 330,100' fill='none' stroke='#2FE3D2' stroke-width='1.6' marker-end='url(#ar)'/>"
            "<path d='M560,90 C 630,80 640,60 700,55' fill='none' stroke='#2FE3D2' stroke-width='1.6' marker-end='url(#ar)'/>"
            "<path d='M560,110 C 630,115 640,120 700,123' fill='none' stroke='#2FE3D2' stroke-width='1.6' marker-end='url(#ar)'/>"
            "<path d='M560,125 C 630,140 640,160 700,165' fill='none' stroke='#2FE3D2' stroke-width='1.6' marker-end='url(#ar)'/>"
            "</svg></div>")

    logout = "<a class='logout' href='/logout'>Sign out</a>" if has_password else ""
    healthy = health.get("healthy")
    script = ("<script>async function runSkill(){var sk=document.getElementById('sk').value,"
              "out=document.getElementById('out'),inp=document.getElementById('inp').value;"
              "out.textContent='Running '+sk+'…';try{var b=JSON.parse(inp||'{}');}"
              "catch(e){out.textContent='That input is not valid JSON.';return;}"
              "try{var r=await fetch('/skills/'+sk+'/taste',{method:'POST',"
              "headers:{'Content-Type':'application/json'},body:JSON.stringify({input:b})});"
              "out.textContent=JSON.stringify(await r.json(),null,2);}catch(e){out.textContent='Error: '+e;}}</script>")

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Business Control Center</title><style>" + CSS + "</style></head><body><div class='wrap'>"
        "<div class='head'><div class='brand'><div class='logo'>A</div>"
        "<h1>Anthropos — Business Control Center</h1></div>"
        "<div class='who'><span>" + ("All systems nominal" if healthy else "Check system health")
        + "</span><span class='dot' style='width:9px;height:9px;background:"
        + ("#46E08B" if healthy else "#F5B14C") + "'></span>" + logout + "</div></div>"
        "<p class='tag'>Every step of your automation, in plain English.</p>"
        + onboarding + strip
        + "<div class='grid'>" + budget_card + pipeline_card + "</div>"
        + "<div class='grid'>" + lead_card + feed_card + "</div>"
        + autos_card
        + "<div class='grid'>" + approve_card + smap + "</div>"
        + "<div class='links'><a href='/health'>health</a> · <a href='/jobs'>jobs</a> · <a href='/skills'>skills</a></div>"
        + "</div>" + script + "</body></html>")


if __name__ == "__main__":
    # Offline render check with an empty engine + a couple of sample jobs.
    demo_jobs = [
        {"job_id": "job_a", "type": "content_piece", "status": "AWAITING_APPROVAL",
         "payload": {"content_producer": {"title": "24/7 price monitoring"}}, "cost_so_far_usd": 0.04},
        {"job_id": "job_b", "type": "content_piece", "status": "optimized", "payload": {}, "cost_so_far_usd": 0.11},
        {"job_id": "job_c", "type": "outreach_campaign", "status": "sent",
         "payload": {"leads": [{"email": "a@b.com"}], "send_ref": "x"}, "cost_so_far_usd": 0.02},
    ]
    html = dashboard_html(jobs=demo_jobs, st={"wordpress_publish": True, "google_sheets": False},
                          health={"healthy": True}, month_spent=0.17, month_cap=200,
                          day_spent=0.17, day_cap=50, taste_skills=["content_producer", "seo_optimizer"])
    assert "Control Center" in html and "<svg" in html and "Content pipeline" in html
    assert "24/7 price monitoring" in html  # approval shows real title
    empty = dashboard_html(jobs=[], st={}, health={"healthy": True}, month_spent=0, month_cap=200,
                           day_spent=0, day_cap=50, taste_skills=[])
    assert "control center is ready" in empty  # onboarding empty state
    assert "Sign in" in login_html()
    print("OK — dashboard renders (populated + empty), login page renders. No network.")
