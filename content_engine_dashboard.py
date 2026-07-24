"""
content_engine_dashboard.py
============================================================================
The Business Control Center UI — a tabbed, no-scroll dashboard.

Left menu = 13 pages: a mother OVERVIEW + 12 "machines". Each machine page shows
4 relational data views (chart + plain-English description) = 48 views total.
Tab switching is client-side JS, so you click a menu and see that page instead
of scrolling. The System Map page carries a plain-text DIAGNOSTIC table: which
wire is down, why, and what it breaks, so you know exactly what to fix.

Pure render functions (offline-testable). Charts + map are hand-drawn inline SVG
(no libraries; works on the VPS with no internet). Empty engine => clean empty
states, never fake numbers.
============================================================================
"""

from __future__ import annotations

CSS = """
:root{--bg:#080B14;--s1:#0F1626;--s2:#0B111F;--line:#1B2640;--line2:#132038;
--ink:#EDF1FB;--mut:#8E9BBE;--dim:#59668A;--teal:#2FE3D2;--violet:#8B7CFF;
--good:#3FD98B;--warn:#F5B14C;--bad:#FF6B93;--blue:#4C8DFF}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.tnum{font-variant-numeric:tabular-nums}
.top{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 18px;border-bottom:1px solid var(--line2);position:sticky;top:0;background:var(--bg);z-index:5}
.brand{display:flex;align-items:center;gap:10px}
.logo{width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,var(--teal),var(--violet));display:grid;place-items:center;color:#04121a;font-weight:800;font-size:14px}
h1{font-size:15.5px;margin:0;font-weight:700}.brand small{display:block;color:var(--mut);font-size:11px}
.status{display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--mut);background:var(--s1);border:1px solid var(--line);border-radius:99px;padding:5px 11px}
.status .d{width:8px;height:8px;border-radius:50%}
.logout{color:var(--mut);font-size:12px;border:1px solid var(--line);border-radius:8px;padding:6px 11px;text-decoration:none}
.shell{display:flex;gap:16px;max-width:1320px;margin:0 auto;padding:16px 16px 40px}
.side{width:212px;flex-shrink:0;display:flex;flex-direction:column;gap:4px;position:sticky;top:64px;align-self:flex-start;max-height:calc(100vh - 80px);overflow:auto}
.navb{display:flex;align-items:center;gap:10px;background:transparent;border:1px solid transparent;color:var(--mut);border-radius:9px;padding:9px 11px;font:inherit;font-size:13px;cursor:pointer;text-align:left;width:100%}
.navb:hover{background:var(--s1);color:var(--ink)}
.navb.act{background:var(--s1);border-color:var(--line);color:var(--ink);font-weight:650}
.navb .ic{width:20px;text-align:center;font-size:14px}
.navb .bd{margin-left:auto;font-size:10px;background:var(--line);color:var(--mut);border-radius:99px;padding:1px 7px}
.navb.act .bd{background:var(--teal);color:#04121a}
.main{flex:1;min-width:0}
.page{display:none}.page.on{display:block}
.ph{margin:0 0 4px;font-size:18px;font-weight:750;letter-spacing:-.01em}
.psub{color:var(--mut);font-size:12.5px;margin:0 0 16px}
.grid{display:grid;gap:12px}.g2{grid-template-columns:1fr 1fr}.g3{grid-template-columns:1fr 1fr 1fr}.g4{grid-template-columns:repeat(4,1fr)}
.card{background:var(--s1);border:1px solid var(--line);border-radius:13px;padding:15px 16px}
.full{grid-column:1/-1}
.ct{font-size:13.5px;font-weight:700;margin:0}
.cc{color:var(--mut);font-size:12px;margin:2px 0 13px}
.big{font-size:30px;font-weight:750;letter-spacing:-.02em;line-height:1}.big small{font-size:16px;color:var(--dim)}
.mut{color:var(--mut)}.dim{color:var(--dim);font-size:12px}
.pill{display:inline-flex;align-items:center;gap:5px;font-size:10.5px;font-weight:700;border-radius:99px;padding:2px 8px}
.p-live{color:var(--good);background:rgba(63,217,139,.12)}.p-need{color:var(--warn);background:rgba(245,177,76,.13)}
.pill .d{width:6px;height:6px;border-radius:50%}
.fn{display:flex;flex-direction:column;gap:6px}.fr{display:flex;align-items:center;gap:10px}
.fbar{height:26px;border-radius:6px;display:flex;align-items:center;padding:0 9px;color:#05131f;font-weight:750;font-size:12px;min-width:28px}
.fr .fl{width:120px;color:var(--mut);font-size:12px;flex-shrink:0}
.bars{display:flex;flex-direction:column;gap:8px}.br{display:flex;align-items:center;gap:10px}
.br .bl{width:110px;font-size:12px;color:var(--mut)}.track{flex:1;height:11px;background:var(--s2);border-radius:99px;overflow:hidden}.track i{display:block;height:100%;border-radius:99px}
.br .bv{width:52px;text-align:right;font-size:11.5px}
.chip{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:12px;padding:6px 0;border-bottom:1px solid var(--line2)}
.chip .nm{display:flex;align-items:center;gap:8px}.chip .d{width:7px;height:7px;border-radius:50%}
.fe{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--line2);font-size:12.5px}
.fe .tm{color:var(--dim);font-size:11px;width:74px;flex-shrink:0}
.empty{color:var(--dim);font-size:12.5px;padding:20px 8px;text-align:center;border:1px dashed var(--line);border-radius:9px}
.ov{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.tile{background:var(--s1);border:1px solid var(--line);border-radius:12px;padding:14px;cursor:pointer;transition:border-color .15s}
.tile:hover{border-color:var(--teal)}
.tile .tl{font-size:12px;color:var(--mut);display:flex;align-items:center;gap:7px}
.tile .tv{font-size:22px;font-weight:750;margin-top:7px}.tile .tx{font-size:11.5px;color:var(--dim);margin-top:3px}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:9px 10px;font-size:12px;border-bottom:1px solid var(--line2);vertical-align:top}
th{color:var(--dim);font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;font-weight:700}
.tbwrap{overflow-x:auto}
.cmd{display:flex;gap:8px;flex-wrap:wrap}.cmd select,.cmd input{flex:1;min-width:130px;background:var(--s2);border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:9px 11px;font:inherit}
.cmd button{background:var(--teal);color:#04121a;font-weight:700;border:none;border-radius:8px;padding:9px 15px;cursor:pointer}
pre{background:var(--s2);border:1px solid var(--line);border-radius:8px;padding:10px;overflow:auto;font-size:11.5px;color:#B9C4E0;max-height:190px;margin-top:8px}
.maplegend{display:flex;gap:16px;flex-wrap:wrap;font-size:11.5px;color:var(--mut);margin-top:12px}
.ctrl{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
.cbtn{background:var(--s1);border:1px solid var(--line);color:var(--ink);border-radius:9px;padding:8px 13px;font:inherit;font-size:12.5px;font-weight:650;cursor:pointer}
.cbtn:hover{border-color:var(--teal)}.cbtn.warn{border-color:var(--warn);color:var(--warn)}.cbtn.on{border-color:var(--good);color:var(--good)}
.attn{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.alert{background:var(--s1);border:1px solid var(--line);border-radius:9px;padding:8px 12px;font-size:12.5px;color:var(--ink);cursor:pointer;display:inline-flex;gap:7px;align-items:center}
.alert:hover{border-color:var(--teal)}
.sbtn{background:var(--good);color:#04140a;border:none;border-radius:7px;padding:5px 11px;font-weight:700;font-size:11.5px;cursor:pointer}
.prog{height:8px;background:var(--s2);border-radius:99px;overflow:hidden;margin:6px 0 10px}.prog i{display:block;height:100%;background:var(--teal);border-radius:99px}
.cgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}
.cform{background:var(--s2);border:1px solid var(--line);border-radius:11px;padding:13px;display:flex;flex-direction:column;gap:7px}
.cflab{font-size:12.5px;font-weight:700}
.cform input{background:#0a0f1b;border:1px solid var(--line);color:var(--ink);border-radius:7px;padding:8px 10px;font:inherit;font-size:12px}
.cform input:focus{outline:none;border-color:var(--teal)}
.cform .sbtn{align-self:flex-start;margin-top:3px}
@media(max-width:860px){.shell{flex-direction:column}.side{width:auto;flex-direction:row;overflow-x:auto;position:static;max-height:none}.navb{white-space:nowrap}.navb .bd{display:none}.g2,.g3,.g4{grid-template-columns:1fr}}
.bpwrap{display:flex;gap:4px;align-items:stretch;overflow-x:auto;padding:8px 0 4px}
.bpcol{flex:1 1 0;min-width:196px;display:flex;flex-direction:column;gap:8px}
.bpcl{font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--dim);font-weight:700;padding:0 2px 3px;display:flex;align-items:center;gap:6px}
.bpcl .n{margin-left:auto;background:var(--line);color:var(--mut);border-radius:99px;padding:1px 7px;font-size:9.5px}
.bpc{background:var(--s2);border:1px solid var(--line);border-radius:11px;padding:10px 11px;transition:border-color .15s}
.bpc.on{border-color:rgba(63,217,139,.5)}.bpc.off{border-color:rgba(245,177,76,.4)}
.bph{display:flex;align-items:center;gap:8px}
.bpi{font-size:18px;width:24px;text-align:center}
.bpn{font-weight:700;font-size:12.5px}
.bpd{width:8px;height:8px;border-radius:50%;margin-left:auto;flex-shrink:0}
.bpt{display:inline-block;font-size:9px;color:var(--dim);background:var(--bg);border:1px solid var(--line);border-radius:5px;padding:1px 6px;margin-top:7px;letter-spacing:.03em}
.bpx{font-size:11px;color:var(--mut);margin-top:6px;line-height:1.4}
.bps{font-size:10px;font-weight:700;margin-top:6px;text-transform:uppercase;letter-spacing:.04em}
.bparrow{display:flex;align-items:center;justify-content:center;color:var(--dim);font-size:16px;flex:0 0 14px}
.bplegend{display:flex;gap:16px;flex-wrap:wrap;font-size:11px;color:var(--mut);margin-top:10px}
@media(max-width:860px){.bpwrap{flex-direction:column}.bparrow{transform:rotate(90deg);align-self:center;flex-basis:auto}}
"""


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# connector diagnostics — the "which wire is down, why, and what breaks" table
# ---------------------------------------------------------------------------
_DIAG = [
    ("claude_api", "Claude AI brain (Anthropic)",
     "no Anthropic API key set",
     "The whole engine can't think — no content, cold emails, or replies get written. This is the brain; wire it first.",
     "ANTHROPIC_API_KEY"),
    ("wordpress_publish", "Publish to website (WordPress)",
     "no WordPress URL + application password set",
     "Articles get written and checked, but can't post to your site on their own — you'd paste them in by hand.",
     "WORDPRESS_URL + WORDPRESS_APP_PASSWORD"),
    ("email_send", "Send email (Gmail / SMTP)",
     "no mail login set",
     "Cold emails and replies are written, but nothing actually sends.",
     "SMTP_HOST=smtp.gmail.com + SMTP_USER + SMTP_PASSWORD"),
    ("email_reply_inbound", "Read + answer replies (IMAP)",
     "no inbox login set",
     "The agent can't see customer replies, so it can't auto-answer them.",
     "IMAP_HOST + IMAP_USER + IMAP_PASSWORD"),
    ("web_search", "Find leads on the web (Tavily)",
     "no search provider key",
     "The lead finder can't search the open web — fewer new leads come in.",
     "SEARCH_PROVIDER=tavily + SEARCH_API_KEY"),
    ("linkedin_leads", "Find leads on LinkedIn (Prospeo)",
     "no Prospeo API key set",
     "No leads flow in — your cold-email pipeline has nobody to email.",
     "PROSPEO_API_KEY + LEAD_COUNTRIES=United States,United Kingdom,Germany,Switzerland,Canada + LEAD_TITLES=Dentist,Doctor,Lawyer,Tax Consultant,Accountant,Marketing Manager,Founder,Owner"),
    ("google_gsc_ga4", "Google Search Console + Analytics",
     "no Google token set",
     "You can't see real rankings, traffic, or which pages convert — SEO runs blind.",
     "GOOGLE_ACCESS_TOKEN + GSC_SITE_URL + GA4_PROPERTY_ID"),
    ("google_sheets", "Google Sheets (your data hub)",
     "no Google service-account key / shared sheet",
     "Results don't mirror to Google, so you can't see them in Sheets.",
     "GOOGLE_SERVICE_ACCOUNT_JSON + GOOGLE_SHEETS_ID"),
    ("google_drive", "Google Drive (content store)",
     "no Google service-account key / shared folder",
     "Finished content isn't saved to your Drive as files.",
     "GOOGLE_SERVICE_ACCOUNT_JSON + GDRIVE_FOLDER_ID"),
    ("social_linkedin", "Post to LinkedIn",
     "no LinkedIn post token",
     "Content is ready but won't post to LinkedIn on its own.",
     "LINKEDIN_POST_TOKEN + LINKEDIN_AUTHOR_URN"),
    ("social_twitter", "Post to X (Twitter)",
     "no X post token",
     "Content won't post to X automatically.",
     "TWITTER_BEARER_TOKEN"),
    ("social_facebook", "Post to Facebook",
     "no Facebook page token",
     "Content won't post to Facebook automatically.",
     "META_PAGE_ID + META_PAGE_TOKEN"),
    ("social_instagram", "Post to Instagram",
     "no Instagram account + token",
     "Content won't post to Instagram automatically.",
     "IG_USER_ID + META_PAGE_TOKEN"),
    ("social_tiktok", "Post to TikTok",
     "no TikTok token",
     "Content won't post to TikTok automatically.",
     "TIKTOK_ACCESS_TOKEN"),
    ("image_gen", "Generate images (OpenAI)",
     "no image provider key",
     "Posts go out as text only — no generated images.",
     "IMAGE_PROVIDER=openai + IMAGE_API_KEY + IMAGE_MODEL=gpt-image-1"),
    ("video_gen", "Generate video",
     "no video provider key",
     "No AI video is produced (the pricey one — use selectively).",
     "VIDEO_PROVIDER + VIDEO_API_KEY + VIDEO_API_URL"),
]


# Plain-language placeholders so the connect boxes read like a form, not code.
_FIELD_HINT = {
    "ANTHROPIC_API_KEY": "Claude API key (sk-ant-…)",
    "WORDPRESS_URL": "Your website address (https://…)", "WORDPRESS_USER": "WordPress username",
    "WORDPRESS_APP_PASSWORD": "WordPress application password", "WP_STATUS": "publish or draft",
    "SMTP_HOST": "Mail server (smtp.gmail.com)", "SMTP_PORT": "Port (587)",
    "SMTP_USER": "Your business email address", "SMTP_PASSWORD": "Email app password (16 chars, no spaces)",
    "SMTP_FROM": "Send-from email address", "SMTP_STARTTLS": "Leave as 1",
    "IMAP_HOST": "Inbox server (imap.gmail.com)", "IMAP_PORT": "Port (993)",
    "IMAP_USER": "Your business email address", "IMAP_PASSWORD": "Email app password (16 chars, no spaces)",
    "IMAP_FOLDER": "Folder (INBOX)",
    "PROSPEO_API_KEY": "Prospeo API key", "LEAD_COUNTRIES": "Target countries (comma-separated)",
    "LEAD_TITLES": "Target job titles (comma-separated)",
    "SEARCH_PROVIDER": "Search provider (tavily)", "SEARCH_API_KEY": "Tavily API key",
    "GOOGLE_SERVICE_ACCOUNT_JSON": "Paste the whole Google key file (the { … } JSON)",
    "GOOGLE_SHEETS_ID": "Google Sheet ID (from its URL)", "GDRIVE_FOLDER_ID": "Google Drive folder ID (from its URL)",
    "GSC_SITE_URL": "Search Console site (sc-domain:yoursite.com)", "GA4_PROPERTY_ID": "Analytics property ID (numbers only)",
    "GOOGLE_ACCESS_TOKEN": "Google access token (optional)",
    "LINKEDIN_POST_TOKEN": "LinkedIn access token", "LINKEDIN_AUTHOR_URN": "Your LinkedIn URN (urn:li:person:…)",
    "TWITTER_BEARER_TOKEN": "X (Twitter) access token",
    "META_PAGE_ID": "Facebook Page ID", "META_PAGE_TOKEN": "Facebook Page access token",
    "IG_USER_ID": "Instagram business account ID", "TIKTOK_ACCESS_TOKEN": "TikTok access token",
    "IMAGE_PROVIDER": "Image provider (openai)", "IMAGE_API_KEY": "OpenAI API key (sk-…)",
    "IMAGE_MODEL": "Image model (gpt-image-1)",
    "VIDEO_PROVIDER": "Video provider (fal)", "VIDEO_API_KEY": "Video API key", "VIDEO_API_URL": "Video endpoint URL",
    "ADS_JSON": "Ad data (JSON)", "BACKLINKS_JSON": "Backlink data (JSON)",
}


# ---------------------------------------------------------------------------
# data shaping
# ---------------------------------------------------------------------------
_STAGES = ["Ideas", "Written", "Checked", "Waiting for you", "Published", "Measured"]
_STAGE_OF = {"created": 0, "site_ready": 0, "competitor_ready": 0, "planned": 0, "sourced": 0,
             "qualified": 0, "segmented": 0, "produced": 1, "drafted": 1, "seo_checked": 2,
             "AWAITING_APPROVAL": 3, "publishing": 4, "published": 4, "sending": 4, "sent": 4,
             "measuring": 4, "tracking": 4, "measured": 5, "tracked": 5, "learned": 5, "optimized": 5}
_FRIENDLY = {"created": "queued a new job", "planned": "planned the content", "produced": "wrote the content",
             "drafted": "drafted the emails", "seo_checked": "optimised it for search",
             "AWAITING_APPROVAL": "is waiting for your approval", "published": "published to your website",
             "sent": "sent the cold emails", "measured": "measured the results",
             "optimized": "finished and learned from it", "failed": "hit an error",
             "halted_budget": "paused — budget cap reached"}


def _pipeline(jobs):
    c = [0] * 6
    for j in jobs:
        i = _STAGE_OF.get(j.get("status", ""))
        if i is not None:
            c[i] += 1
    return c


def _lead_funnel(jobs):
    f = v = q = e = 0
    for j in jobs:
        if j.get("type") != "outreach_campaign":
            continue
        p = j.get("payload", {}) or {}
        f += len(p.get("raw_leads", []) or []) or len(p.get("leads", []) or [])
        v += len(p.get("leads", []) or [])
        q += len((p.get("lead_qualifier", {}) or {}).get("results", []) or [])
        if p.get("send_ref") or p.get("outreach_send"):
            e += 1
    return [("Found", f), ("Verified", v), ("Qualified", q), ("Emailed", e), ("Replied", 0), ("Booked", 0)]


# ---------------------------------------------------------------------------
# chart helpers
# ---------------------------------------------------------------------------
def _donut(pct, color):
    import math
    r = 46
    circ = 2 * math.pi * r
    off = circ * (1 - min(100, max(0, pct)) / 100)
    return (f'<svg width="112" height="112" viewBox="0 0 112 112"><circle cx="56" cy="56" r="{r}" fill="none" stroke="#16223c" stroke-width="13"/>'
            f'<circle cx="56" cy="56" r="{r}" fill="none" stroke="{color}" stroke-width="13" stroke-linecap="round" stroke-dasharray="{circ:.0f}" stroke-dashoffset="{off:.0f}" transform="rotate(-90 56 56)"/>'
            f'<text x="56" y="53" text-anchor="middle" fill="#EDF1FB" font-size="22" font-weight="750">{pct}%</text>'
            f'<text x="56" y="71" text-anchor="middle" fill="#8E9BBE" font-size="10">of budget</text></svg>')


_FN = ["#4C8DFF", "#5A7BE8", "#8B7CFF", "#F5B14C", "#2FE3D2", "#3FD98B"]


def _funnel(rows):
    mx = max((v for _, v in rows), default=0) or 1
    return "<div class='fn'>" + "".join(
        f"<div class='fr'><span class='fl'>{_esc(l)}</span><div class='fbar' style='width:{max(5,round(v/mx*100))}%;background:{_FN[i%len(_FN)]}'>{v}</div></div>"
        for i, (l, v) in enumerate(rows)) + "</div>"


def _bars(rows, color="#4C8DFF", money=False):
    mx = max((v for _, v in rows), default=0) or 1
    out = ["<div class='bars'>"]
    for l, v in rows:
        val = f"${v:.2f}" if money else f"{v}"
        out.append(f"<div class='br'><span class='bl'>{_esc(l)}</span><div class='track'><i style='width:{max(3,round(v/mx*100))}%;background:{color}'></i></div><span class='bv tnum'>{val}</span></div>")
    return "".join(out) + "</div>"


def _empty(msg):
    return f"<div class='empty'>{_esc(msg)}</div>"


def _funnel_skeleton(rows, note):
    """A funnel drawn even before data flows, so the SHAPE is visible; the note
    says what to connect to fill it. rows = [(label, value, width%)]."""
    body = "<div class='fn'>" + "".join(
        f"<div class='fr'><span class='fl'>{_esc(l)}</span>"
        f"<div class='fbar' style='width:{w}%;background:{_FN[i%len(_FN)]};opacity:.4'>{_esc(str(v))}</div></div>"
        for i, (l, v, w) in enumerate(rows)) + "</div>"
    return body + f"<div class='dim' style='margin-top:9px'>{_esc(note)}</div>"


def _by_country(out_jobs):
    """Count real leads per target market (from lead payloads), so segmentation
    fills as leads arrive. Zeroes until then — never faked."""
    markets = ["United States", "United Kingdom", "Germany", "Switzerland", "Canada"]
    counts = {m: 0 for m in markets}
    alias = {"usa": "United States", "united states": "United States", "u.s": "United States",
             "uk": "United Kingdom", "united kingdom": "United Kingdom", "england": "United Kingdom",
             "germany": "Germany", "deutschland": "Germany",
             "switzerland": "Switzerland", "schweiz": "Switzerland",
             "canada": "Canada"}
    for j in out_jobs:
        for l in (j.get("payload", {}) or {}).get("leads", []) or []:
            raw = str(l.get("country") or l.get("location") or "").strip().lower()
            for key, m in alias.items():
                if key in raw:
                    counts[m] += 1
                    break
    return [(m, counts[m]) for m in markets]


def _panel(title, desc, body):
    return f"<div class='card'><p class='ct'>{_esc(title)}</p><p class='cc'>{_esc(desc)}</p>{body}</div>"


def _sparkline(vals, color, h=42, w=220):
    if not vals or max(vals) == 0:
        return (f"<svg width='100%' height='{h}' viewBox='0 0 {w} {h}' preserveAspectRatio='none'>"
                f"<line x1='0' y1='{h-6}' x2='{w}' y2='{h-6}' stroke='#1B2640' stroke-width='1.5'/></svg>")
    mx = max(vals) or 1
    step = w / max(len(vals) - 1, 1)
    pts = " ".join(f"{i*step:.0f},{h-6-(v/mx)*(h-14):.0f}" for i, v in enumerate(vals))
    return (f"<svg width='100%' height='{h}' viewBox='0 0 {w} {h}' preserveAspectRatio='none'>"
            f"<polyline points='0,{h} {pts} {w},{h}' fill='{color}' opacity='0.12'/>"
            f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='2'/></svg>")


def _daybuckets(jobs, pred, days=14, valfn=None):
    from datetime import date, timedelta
    today = date.today()
    idx = {(today - timedelta(days=days - 1 - i)).isoformat(): i for i in range(days)}
    vals = [0.0] * days
    for j in jobs:
        if not pred(j):
            continue
        ca = (j.get("created_at") or "")[:10]
        if ca in idx:
            vals[idx[ca]] += (valfn(j) if valfn else 1)
    return vals


def _outcomes(jobs):
    leads = revenue = customers = 0.0
    for j in jobs:
        oc = (j.get("payload", {}) or {}).get("outcome", {}) or {}
        leads += oc.get("leads", 0)
        revenue += oc.get("revenue", 0.0)
        customers += oc.get("customers", 0)
    return int(leads), round(revenue, 2), int(customers)


# ---------------------------------------------------------------------------
# blueprint — every API / account / plugin as an icon component, laid out as
# the workflow (inputs -> brain -> hub -> outputs). Reads far clearer than the
# wire tangle: each card shows its icon, what KIND of connection it is, one line
# of detail, and its live status.
#   entry = (status_key | None, icon, name, type_badge, detail)
# ---------------------------------------------------------------------------
_BLUEPRINT = [
    ("① Inputs — data comes in", [
        ("linkedin_leads", "🧲", "Prospeo", "REST API · key", "LinkedIn-sourced leads + verified work emails"),
        ("web_search", "🔎", "Tavily", "REST API · key", "Web-search lead backup source"),
        ("google_gsc_ga4", "🔍", "Search Console", "Google API · service acct", "Keyword rankings & search queries"),
        ("google_gsc_ga4", "📈", "Analytics GA4", "Google API · service acct", "Visitors, traffic & conversions"),
    ]),
    ("② Brain + engine · VPS", [
        ("claude_api", "🧠", "Claude", "Anthropic API · key", "Opus + Haiku — writes & decides everything"),
        (None, "⚙️", "Orchestrator", "engine core", "Runs each job step-by-step"),
        (None, "🗄️", "Postgres", "database", "The engine's memory & job store"),
        (None, "🛡️", "Budget guard", "safety rule", "Hard €200/month cap — auto-pauses"),
        (None, "✅", "Approval gate", "safety rule", "Nothing publishes/sends without you"),
        (None, "💧", "Deliverability", "safety rule", "Warm-up cap + bounce suppression"),
    ]),
    ("③ Google Workspace hub", [
        ("email_send", "📧", "Gmail SMTP", "mother@ · app pw", "Sends every email"),
        ("email_reply_inbound", "📥", "Gmail IMAP", "mother@ · app pw", "Reads customer replies"),
        ("google_sheets", "📊", "Sheets", "Google API", "Live data mirror / dashboard store"),
        ("google_drive", "📁", "Drive", "Google API", "Finished content saved as files"),
    ]),
    ("④ Outputs — channels", [
        ("wordpress_publish", "🌐", "WordPress", "REST API · app pw", "Publishes articles to your site"),
        ("email_send", "✉️", "Cold email out", "alias: contact@/marketing@", "Outreach + reply sending"),
        ("social_linkedin", "💼", "LinkedIn", "REST API · token", "Posts updates to your profile/page"),
        ("social_facebook", "📘", "Facebook", "Graph API · token", "Posts to your Page"),
        ("social_instagram", "📸", "Instagram", "Graph API · token", "Posts images"),
        ("social_twitter", "▶️", "X (Twitter)", "API v2 · token", "Posts tweets"),
        ("social_tiktok", "🎵", "TikTok", "Content API · token", "Posts short video"),
        ("image_gen", "🎨", "OpenAI Images", "REST API · key", "Generates images for posts"),
    ]),
]


def _blueprint(st):
    def stat(key):
        if key is None:
            return ("#8B7CFF", "core", "")          # always-on internal part
        return ("#3FD98B", "live", "on") if st.get(key) else ("#F5B14C", "needs key", "off")
    cols = []
    for layer, items in _BLUEPRINT:
        live = sum(1 for k, *_ in items if k and st.get(k))
        keyed = sum(1 for k, *_ in items if k is not None)
        cards = []
        for key, icon, name, typ, detail in items:
            col, lab, cls = stat(key)
            cards.append(
                f"<div class='bpc {cls}'><div class='bph'><span class='bpi'>{icon}</span>"
                f"<span class='bpn'>{_esc(name)}</span><span class='bpd' style='background:{col}'></span></div>"
                f"<div class='bpt'>{_esc(typ)}</div><div class='bpx'>{_esc(detail)}</div>"
                f"<div class='bps' style='color:{col}'>{lab}</div></div>")
        badge = f"<span class='n'>{live}/{keyed} live</span>" if keyed else ""
        cols.append(f"<div class='bpcol'><div class='bpcl'>{_esc(layer)}{badge}</div>{''.join(cards)}</div>")
    legend = ("<div class='bplegend'>"
              "<span><span style='display:inline-block;width:9px;height:9px;border-radius:50%;background:#3FD98B;margin-right:5px'></span>Connected &amp; live</span>"
              "<span><span style='display:inline-block;width:9px;height:9px;border-radius:50%;background:#F5B14C;margin-right:5px'></span>Ready — needs its key</span>"
              "<span><span style='display:inline-block;width:9px;height:9px;border-radius:50%;background:#8B7CFF;margin-right:5px'></span>Always-on engine part</span></div>")
    return ("<div class='bpwrap'>" + "<div class='bparrow'>→</div>".join(cols) + "</div>" + legend)


# ---------------------------------------------------------------------------
# system map (component-level, every labeled connection)
# ---------------------------------------------------------------------------
def _system_map(st):
    def c(k):
        return "#3FD98B" if st.get(k) else "#F5B14C"
    g_on = st.get("google_sheets") or st.get("google_drive")
    P = ['<svg width="100%" viewBox="0 0 1220 560" style="max-width:100%;height:auto">'
         '<defs><marker id="arw" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#5a79aa"/></marker></defs>']

    def box(x, y, w, h, col, t, sub=""):
        s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="#0B111F" stroke="{col}" stroke-width="1.3"/>'
        yt = y + (h / 2 + 4) if not sub else y + h / 2 - 2
        s += f'<text x="{x+w/2}" y="{yt:.0f}" text-anchor="middle" fill="#EDF1FB" font-size="11" font-weight="600">{t}</text>'
        if sub:
            s += f'<text x="{x+w/2}" y="{y+h/2+11:.0f}" text-anchor="middle" fill="#8E9BBE" font-size="9">{sub}</text>'
        return s

    def wire(x1, y1, x2, y2, col="#33507e", dash="", label="", lx=None, ly=None, flow=True):
        mx = (x1 + x2) / 2
        d = f"M{x1} {y1} C {mx} {y1}, {mx} {y2}, {x2} {y2}"
        s = f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.3" {dash} marker-end="url(#arw)" opacity="0.7"/>'
        if flow:
            # the "crystal jar" — data you can actually SEE moving through the wire
            s += (f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2.4" stroke-linecap="round" '
                  f'stroke-dasharray="0.1 13" opacity="0.95">'
                  f'<animate attributeName="stroke-dashoffset" from="26" to="0" dur="1.5s" repeatCount="indefinite"/></path>')
        if label:
            s += f'<text x="{lx or mx:.0f}" y="{(ly or (y1+y2)/2-4):.0f}" text-anchor="middle" fill="#8E9BBE" font-size="9">{label}</text>'
        return s

    for lx, txt in [(95, "SOURCES"), (300, "TRIGGER"), (610, "ENGINE (VPS)"), (940, "GOOGLE HUB"), (1130, "CHANNELS")]:
        P.append(f'<text x="{lx}" y="20" text-anchor="middle" fill="#59668A" font-size="9.5" font-weight="700" letter-spacing="1">{txt}</text>')
    src = [("Web search", c("web_search"), 46), ("Web scraper", c("web_search"), 92),
           ("LinkedIn", c("linkedin_leads"), 138), ("Search Console", c("google_gsc_ga4"), 204),
           ("Analytics (GA4)", c("google_gsc_ga4"), 250)]
    for n, col, y in src:
        P.append(box(20, y, 150, 36, col, n))
    P.append(box(228, 440, 140, 40, "#8B7CFF", "n8n", "cron + webhooks"))
    P.append('<rect x="410" y="36" width="400" height="440" rx="12" fill="#0D1526" stroke="#2FE3D2" stroke-width="1.6"/>')
    P.append('<text x="610" y="58" text-anchor="middle" fill="#2FE3D2" font-size="12.5" font-weight="750">Automation Engine · 24/7</text>')
    P.append(box(434, 74, 352, 30, "#4C8DFF", "Orchestrator", "decides each job's next step"))
    P.append('<rect x="434" y="114" width="352" height="64" rx="7" fill="#0B111F" stroke="#2b3a5c"/>')
    P.append('<text x="444" y="130" fill="#8B7CFF" font-size="9" font-weight="700">CONTENT AGENTS</text>')
    P.append('<text x="444" y="146" fill="#C7D0EA" font-size="9.5">site · competitor · strategist · writer</text>')
    P.append('<text x="444" y="161" fill="#C7D0EA" font-size="9.5">SEO/AEO · quality &amp; legal · publisher</text>')
    P.append('<text x="444" y="174" fill="#8E9BBE" font-size="8.5">→ images + video (phase 2)</text>')
    P.append('<rect x="434" y="190" width="352" height="60" rx="7" fill="#0B111F" stroke="#2b3a5c"/>')
    P.append('<text x="444" y="206" fill="#8B7CFF" font-size="9" font-weight="700">LEAD MACHINE</text>')
    P.append('<text x="444" y="222" fill="#C7D0EA" font-size="9.5">sourcing · verify · qualifier · segmenter</text>')
    P.append('<text x="444" y="237" fill="#C7D0EA" font-size="9.5">outreach writer · reply responder</text>')
    P.append(box(434, 262, 172, 30, "#4C8DFF", "Ads optimizer"))
    P.append(box(614, 262, 172, 30, "#4C8DFF", "Learning agent"))
    P.append(box(434, 302, 172, 30, "#3FD98B", "Approval gate"))
    P.append(box(614, 302, 172, 30, "#3FD98B", "Budget guard $200"))
    P.append(box(434, 342, 172, 36, c("claude_api"), "Claude · the brain", "Opus / Haiku"))
    P.append(box(614, 342, 172, 36, "#2FE3D2", "Postgres", "engine memory"))
    P.append(box(434, 390, 352, 34, "#2FE3D2", "Control dashboard", "this screen"))
    P.append(f'<rect x="890" y="50" width="176" height="150" rx="10" fill="#0D1526" stroke="{"#3FD98B" if g_on else "#F5B14C"}" stroke-width="1.5"/>')
    P.append('<text x="978" y="70" text-anchor="middle" fill="#EDF1FB" font-size="11" font-weight="700">Google Workspace</text>')
    P.append(box(904, 84, 148, 30, c("google_sheets"), "Sheets", "dashboard data"))
    P.append(box(904, 120, 148, 30, c("google_drive"), "Drive", "content JSON"))
    P.append(box(904, 156, 148, 30, c("email_send"), "Gmail", "sending"))
    ch = [("Website", c("wordpress_publish"), 46), ("LinkedIn", c("social_linkedin"), 86),
          ("X / Twitter", c("social_twitter"), 126), ("Facebook", c("social_facebook"), 166),
          ("Instagram", "#F5B14C", 206), ("TikTok", "#F5B14C", 246),
          ("Email out", c("email_send"), 300), ("Replies in", c("email_reply_inbound"), 340)]
    for n, col, y in ch:
        P.append(box(1086, y, 128, 32, col, n))
    for _, _, y in src:
        P.append(wire(170, y + 18, 410, 89, "#33507e"))
    P.append('<text x="295" y="128" text-anchor="middle" fill="#8E9BBE" font-size="9">leads · research · SEO data</text>')
    P.append(wire(368, 460, 410, 230, "#5b4fb0", label="triggers", lx=392, ly=330))
    P.append(wire(810, 120, 890, 120, "#2FE3D2", label="mirror + content", lx=850, ly=108))
    P.append(wire(810, 300, 1086, 62, "#2FE3D2", label="publish", lx=980, ly=150))
    P.append(wire(810, 320, 1086, 182, "#2FE3D2", label="post", lx=980, ly=250))
    P.append(wire(810, 350, 1086, 316, "#2FE3D2", label="send", lx=980, ly=320))
    P.append(wire(1086, 356, 810, 400, "#33507e", dash='stroke-dasharray="4 3"', label="answer replies", lx=980, ly=395))
    P.append("</svg>")
    legend = ('<div class="maplegend"><span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#3FD98B;margin-right:5px"></span>Connected &amp; running</span>'
              '<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#F5B14C;margin-right:5px"></span>Ready — needs its key</span>'
              '<span><span style="color:#5a79aa">→</span> data flows this way</span></div>')
    return "".join(P) + legend


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------
def login_html(error=""):
    err = f'<p style="color:#FF6B93;font-size:13px;margin:0 0 10px">{_esc(error)}</p>' if error else ""
    return ("<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Sign in</title><style>" + CSS +
            "body{display:flex;align-items:center;justify-content:center;min-height:100vh}.box{background:var(--s1);border:1px solid var(--line);border-radius:14px;padding:26px;width:330px;max-width:90vw}"
            "input{width:100%;margin-bottom:12px;background:var(--s2);border:1px solid var(--line);color:var(--ink);border-radius:9px;padding:11px}button{width:100%;background:var(--teal);color:#04121a;font-weight:700;border:none;border-radius:9px;padding:11px;cursor:pointer}</style></head><body>"
            "<form class='box' method='post' action='/login'><h1 style='font-size:17px;margin:0 0 2px'>Business Control Center</h1>"
            "<p style='color:#8E9BBE;font-size:12px;margin:0 0 16px'>Sign in to continue</p>" + err +
            "<input type='password' name='password' placeholder='Password' autofocus><button type='submit'>Sign in</button></form></body></html>")


# ---------------------------------------------------------------------------
# dashboard
# ---------------------------------------------------------------------------
def dashboard_html(*, jobs, st, health, month_spent, month_cap, day_spent, day_cap,
                   taste_skills, has_password=False, paused=False, autonomy=False):
    from datetime import date
    jobs, st, health = jobs or [], st or {}, health or {}
    o_leads, o_rev, o_cust = _outcomes(jobs)
    content_jobs = [j for j in jobs if j.get("type") != "outreach_campaign"]
    out_jobs = [j for j in jobs if j.get("type") == "outreach_campaign"]
    pl = _pipeline(jobs)
    lead_rows = _lead_funnel(jobs)
    published = sum(1 for j in content_jobs if _STAGE_OF.get(j.get("status", "")) in (4, 5))
    leads_found = lead_rows[0][1]
    emails_sent = lead_rows[3][1]
    waiting = sum(1 for j in jobs if j.get("status") == "AWAITING_APPROVAL")
    pct = round(month_spent / month_cap * 100) if month_cap else 0
    bcol = "#3FD98B" if pct < 70 else ("#F5B14C" if pct < 90 else "#FF6B93")
    live_conn = sum(1 for k, name, *_ in _DIAG if st.get(k))
    total_conn = len(_DIAG)
    healthy = health.get("healthy")
    total_cost = sum(float(j.get("cost_so_far_usd", 0)) for j in jobs)
    content_cost = sum(float(j.get("cost_so_far_usd", 0)) for j in content_jobs)

    def grid(*panels):
        return "<div class='grid g2'>" + "".join(panels) + "</div>"

    # ---- 1. CONTENT FACTORY ----
    by_status = {}
    for j in content_jobs:
        by_status[j.get("status", "?")] = by_status.get(j.get("status", "?"), 0) + 1
    import calendar
    this_month = date.today().isoformat()[:7]
    made_month = sum(1 for j in content_jobs if (j.get("created_at") or "")[:7] == this_month)
    dom = date.today().day
    dim = calendar.monthrange(date.today().year, date.today().month)[1]
    proj = round(made_month / max(dom, 1) * dim)
    content_series = _daybuckets(content_jobs, lambda j: True, 14)
    top = [j for j in content_jobs if _STAGE_OF.get(j.get("status", "")) in (4, 5)][:6]
    top_html = "".join(
        f"<div class='fe'><span>{_esc((j.get('payload',{}).get('content_producer',{}) or {}).get('title') or j.get('job_id'))}</span>"
        f"<span class='dim' style='margin-left:auto'>{_esc(j.get('status'))}</span></div>" for j in top)
    p_content = grid(
        _panel("Pipeline — where each piece is", "Idea → written → checked → your approval → live → measured.",
               _funnel(list(zip(_STAGES, pl))) if sum(pl) else _empty("No content jobs yet.")),
        _panel("Content by stage", "How many pieces sit at each stage right now.",
               _bars([(k, v) for k, v in by_status.items()][:6], "#4C8DFF") if by_status else _empty("Nothing in production yet.")),
        _panel("Output & projection", "Target ≈ 60/month (2 blogs a day).",
               (_sparkline(content_series, "#4C8DFF") + f"<div class='dim' style='margin-top:6px'>{made_month} made this month · on pace for <b style='color:var(--ink)'>{proj}</b></div>") if content_jobs else _empty("Fills as pieces are made.")),
        _panel("Published pieces", "What's live on your site.",
               top_html or _empty("Nothing published yet.")))

    # ---- 2. LEAD MACHINE ----
    p_leads = grid(
        _panel("Lead funnel", "Stranger → verified → qualified → emailed → replied → booked.",
               _funnel(lead_rows) if any(v for _, v in lead_rows) else _empty("No leads yet — connect the lead finder.")),
        _panel("Leads by country — your 5 target markets",
               "Segmentation across USA · UK · Germany · Switzerland · Canada.",
               _bars(_by_country(out_jobs), "#2FE3D2") if any(v for _, v in _by_country(out_jobs))
               else _funnel_skeleton([("United States", 0, 100), ("United Kingdom", 0, 82),
                                      ("Germany", 0, 66), ("Switzerland", 0, 50), ("Canada", 0, 40)],
                                     "Fills as Prospeo leads arrive, split by country.")),
        _panel("Leads by source", "Where each lead came from (Prospeo / web).",
               _bars([("Prospeo (LinkedIn)", 0), ("Web search", leads_found)], "#8B7CFF") if leads_found else _empty("No lead sources connected.")),
        _panel("Leads over time · 14 days", "New lead-jobs per day.",
               _sparkline(_daybuckets(out_jobs, lambda j: True, 14), "#8B7CFF") if out_jobs else _empty("Fills as the lead finder runs.")))

    # ---- 3. EMAIL & OUTREACH ----
    _routing = [("📰 Newsletter", "newsletter@"), ("🎯 Marketing", "marketing@"),
                ("💬 Support reply", "customercare@"), ("🙏 Thanks / general", "contact@")]
    route_html = "".join(
        f"<div class='chip'><span class='nm'>{p}</span><span class='dim'>from {a}</span></div>"
        for p, a in _routing)
    p_email = grid(
        _panel("Sent vs replied", "Cold emails out, and how many replied.",
               _bars([("Sent", emails_sent), ("Replied", 0)], "#4C8DFF") if emails_sent else _empty("No emails sent yet.")),
        _panel("Sent by purpose → address", "The loop: your agent sends each email type from the right alias — all from your one inbox.", route_html),
        _panel("Deal conversion — the money moment", "Email → reply → booked consultation → paying customer.",
               _funnel_skeleton([("Emailed", emails_sent, 100), ("Replied", 0, 62),
                                 ("Consultation booked", 0, 38), ("Customer won", o_cust, 20)],
                                "Fills as replies land. Connect Cal.com so booked consultations count here automatically.")),
        _panel("Send volume over time", "Emails sent per day.",
               _sparkline(_daybuckets(out_jobs, lambda j: bool((j.get('payload',{}) or {}).get('send_ref')), 14), "#4C8DFF")
               if emails_sent else _empty("Fills as outreach runs.")))

    # ---- 4. SOCIAL MEDIA ----
    p_social = grid(
        _panel("Posts per channel", "Content pushed to each social channel.", _empty("Connect a social channel to post.")),
        _panel("Engagement", "Likes, comments, shares per channel.", _empty("Shows once posting is on.")),
        _panel("Schedule adherence", "Are you hitting 3 posts/channel/day?", _empty("Target 3/channel/day.")),
        _panel("Content mix", "Story vs image vs video vs link.", _empty("Fills as content posts.")))

    # ---- 5. SEO / AEO / GEO ----
    gsc_on = st.get("google_gsc_ga4")
    mfunnel = (_funnel([("Traffic", 0), ("Interest", 0), ("Location match", 0), ("Authority", 0)]) if gsc_on
               else _funnel_skeleton([("Traffic — visitors", "—", 100), ("Interest — engaged", "—", 70),
                                      ("Location — your 5 markets", "—", 48), ("Authority — backlinks", "—", 30)],
                                     "Connect Search Console + Analytics to fill this with real numbers."))
    assist = "".join(f"<div class='fe'><span class='mut'>{x}</span></div>" for x in [
        "◆ <b>Publish next</b> for your least-covered vertical — rotate dentists → lawyers → tax consultants → Shopify → creators.",
        "◆ <b>Internal links:</b> point each new blog at its matching service page — that's where deals happen.",
        "◆ <b>Backlinks to chase:</b> local directories, niche bodies (dental / legal / tax associations), one guest post a month.",
        "◆ <b>Topic gaps:</b> once Search Console is live this turns data-driven — the keywords you rank #5–15 for are your easy wins.",
    ])
    p_seo = grid(
        _panel("Marketing funnel", "Traffic → interest → location → authority.", mfunnel),
        _panel("Keyword rankings", "Where your pages rank.", _empty("Connect Search Console.")),
        _panel("AI-answer mentions", "How often ChatGPT / Google AI quote you.", _empty("Shows once tracking is on.")),
        _panel("Content assistant — your next move", "What to publish and where to build backlinks.", assist))

    # ---- 6. ADS & GROWTH ----
    p_ads = grid(
        _panel("Spend by campaign", "Where the ad budget goes.", _empty("Feed ad data (ADS_JSON / n8n).")),
        _panel("Cost per result (CPA/ROAS)", "Efficiency per campaign.", _empty("Shows with ad data.")),
        _panel("Budget reallocation", "Move money to what works.", _empty("The ads agent suggests moves here.")),
        _panel("SEO-informed keywords", "Winning keywords to pull into ads.", _empty("Fills from your SEO data.")))

    # ---- 7. BUDGET & COST ----
    lead_cost = total_cost - content_cost
    spend_series = _daybuckets(jobs, lambda j: True, 14, valfn=lambda j: float(j.get("cost_so_far_usd", 0)))
    if o_rev or o_leads or o_cust:
        roi_col = "#3FD98B" if o_rev >= total_cost else "#F5B14C"
        cpl = f"${(total_cost/o_leads):.2f}" if o_leads else "—"
        cpc = f"${(total_cost/o_cust):.2f}" if o_cust else "—"
        roi_body = (f"<div class='big tnum' style='color:{roi_col}'>${o_rev:,.0f}</div>"
                    f"<div class='dim'>earned vs ${total_cost:.2f} spent</div>"
                    "<div class='bars' style='margin-top:10px'>"
                    f"<div class='br'><span class='bl'>Cost / lead</span><div class='track'><i style='width:40%;background:#8B7CFF'></i></div><span class='bv'>{cpl}</span></div>"
                    f"<div class='br'><span class='bl'>Cost / customer</span><div class='track'><i style='width:60%;background:#4C8DFF'></i></div><span class='bv'>{cpc}</span></div></div>")
    else:
        roi_body = _empty("No results yet. Record leads/revenue per job (from your CRM or n8n → POST /jobs/{id}/outcome) to see ROI here.")
    p_budget = grid(
        _panel("This month vs $200 cap", "The engine pauses before it ever goes over.",
               "<div style='display:flex;align-items:center;gap:18px'>" + _donut(pct, bcol) +
               f"<div><div class='dim'>Today</div><div class='big tnum'>${day_spent:.2f}</div><div class='dim'>of ${day_cap:.0f}/day</div></div></div>"),
        _panel("Return on investment (ROI)", "The number that matters: money in vs money out.", roi_body),
        _panel("Cost by activity", "What your AI spend is doing.",
               _bars([("Content", content_cost), ("Leads/email", lead_cost)], "#8B7CFF", money=True) if total_cost else _empty("No spend yet.")),
        _panel("Spend trend · 14 days", f"${total_cost:.2f} so far this month · ${(content_cost/max(len(content_jobs),1)):.3f} per piece.",
               _sparkline(spend_series, "#3FD98B") if total_cost else _empty("Fills day by day.")))

    # ---- 8. AGENTS & HEALTH ----
    outcomes = {"running": 0, "done": 0, "failed": 0}
    for j in jobs:
        s = j.get("status", "")
        if s in ("optimized", "measured", "learned"):
            outcomes["done"] += 1
        elif s in ("failed", "halted_budget", "revision_needed"):
            outcomes["failed"] += 1
        else:
            outcomes["running"] += 1
    hrows = "".join(
        f"<div class='chip'><span class='nm'><span class='d' style='background:{({'ok':'#3FD98B','fail':'#FF6B93'}.get((health.get(k) or {}).get('status'),'#8E9BBE'))}'></span>{lbl}</span><span class='dim'>{_esc((health.get(k) or {}).get('status','—'))}</span></div>"
        for k, lbl in [("anthropic", "Claude API"), ("postgres", "Database (memory)"), ("connectors", "Connectors")])
    errs = "".join(f"<div class='fe'><span class='tm'>{_esc(str(j.get('job_id',''))[:10])}</span><span class='mut'>{_esc(j.get('halt_reason') or j.get('status'))}</span></div>" for j in jobs if j.get("status") in ("failed", "halted_budget"))
    p_agents = grid(
        _panel("Engine health", "Live checks on the core parts.", hrows),
        _panel("Job outcomes", "Running vs done vs failed.",
               _bars([("Running", outcomes["running"]), ("Done", outcomes["done"]), ("Failed", outcomes["failed"])], "#4C8DFF") if jobs else _empty("No jobs yet.")),
        _panel("Automations live", f"{live_conn} of {total_conn} connectors are live.",
               f"<div class='big tnum'>{live_conn}<small>/{total_conn}</small></div><div class='dim'>connected · see System Map to fix the rest</div>"),
        _panel("Recent errors", "Anything that failed or paused.", errs or _empty("No errors — all clean.")))

    # ---- 9. GOOGLE HUB ----
    def ghub(k, name, what):
        on = st.get(k)
        return f"<div class='chip'><span class='nm'><span class='d' style='background:{'#3FD98B' if on else '#F5B14C'}'></span>{name}</span><span class='pill {'p-live' if on else 'p-need'}'>{'live' if on else 'needs key'}</span></div><div class='dim' style='padding:0 0 8px'>{what}</div>"
    p_google = grid(
        _panel("Google Sheets", "Your mother dashboard / data store.", ghub("google_sheets", "Sheets", "Every job, lead and metric mirrors here as rows.")),
        _panel("Google Drive", "Where content is stored as JSON.", ghub("google_drive", "Drive", "Each finished piece saved as a file in your folder.")),
        _panel("Gmail (Workspace)", "How email is sent.", ghub("email_send", "Gmail", "Personalised emails sent through your company mail.")),
        _panel("What's stored", "The data living in Google right now.", _empty("Counts appear once the hub is connected.")))

    # ---- 10. APPROVALS & QUEUE ----
    ap = "".join(
        f"<div class='chip'><span class='nm'>{_esc((j.get('payload',{}).get('content_producer',{}) or {}).get('title') or j.get('job_id'))}</span>"
        f"<button class='sbtn' onclick=\"approve('{_esc(j.get('job_id'))}')\">Approve</button></div>"
        for j in jobs if j.get("status") == "AWAITING_APPROVAL")
    revs = sum(1 for j in jobs if j.get("status") == "revision_needed")
    opts = "".join(f"<option value='{_esc(s)}'>{_esc(s)}</option>" for s in taste_skills)
    p_appr = grid(
        _panel("Waiting for your approval", "Nothing goes live without you.", ap or _empty("Nothing waiting right now.")),
        _panel("Approval turnaround", "How fast you review.", _empty("Tracked once you start approving.")),
        _panel("Sent back for rewrite", "Pieces that needed changes.", f"<div class='big tnum'>{revs}</div><div class='dim'>need a rewrite</div>" if revs else _empty("None — quality is clean.")),
        _panel("Talk to an agent", "Give any agent a direct command.",
               "<div class='cmd'><select id='sk'>" + opts + "</select><input id='inp' placeholder='{\"site_url\":\"https://...\"}'><button onclick='runSkill()'>Run</button></div><pre id='out'>Pick an agent, add input, press Run.</pre>"))

    # ---- 11. LEARNING & RESULTS ----
    p_learn = grid(
        _panel("Winning topics", "What's working, remembered for next time.", _empty("Fills after the first measured cycle.")),
        _panel("Content that converted", "Pieces that brought leads/sales.", _empty("Shows once results are measured.")),
        _panel("Cycle improvements", "How each month gets smarter.", _empty("Compares month over month.")),
        _panel("Playbook", "The rules the agents learned about your brand.", _empty("Grows as the engine learns.")))

    # ---- 12. SYSTEM MAP + DIAGNOSTIC ----
    diag_rows = []
    for k, name, why, effect, fix in _DIAG:
        on = st.get(k)
        if on:
            diag_rows.append(f"<tr><td>{_esc(name)}</td><td><span class='pill p-live'><span class='d' style='background:#3FD98B'></span>Working</span></td><td class='dim'>—</td><td class='dim'>Fully connected.</td></tr>")
        else:
            diag_rows.append(f"<tr><td>{_esc(name)}</td><td><span class='pill p-need'><span class='d' style='background:#F5B14C'></span>Not connected</span></td><td class='mut'>{_esc(why)}</td><td class='mut'>{_esc(effect)}<div class='dim' style='margin-top:3px'>Fix: add {_esc(fix)}</div></td></tr>")
    diag = ("<div class='card full'><p class='ct'>Wiring diagnostic — what's down, why, and what it breaks</p>"
            "<p class='cc'>Every connection in plain English. Amber rows tell you exactly what to add and what you're missing until you do.</p>"
            "<div class='tbwrap'><table><thead><tr><th>Connection (wire)</th><th>Status</th><th>Why it's not working</th><th>What it breaks — and the fix</th></tr></thead><tbody>"
            + "".join(diag_rows) + "</tbody></table></div></div>")
    # Connect form — paste keys in the browser, no SSH. Fields auto-built from
    # each wire's required keys; the wire turns green above once saved.
    conn_rows = []
    for k, name, why, effect, fix in _DIAG:
        if st.get(k):
            keys = ",".join(tok.split("=", 1)[0].strip() for tok in fix.split(" + "))
            conn_rows.append(
                "<div class='cform'><div class='cflab'><span class='dot' style='display:inline-block;width:8px;height:8px;border-radius:50%;background:#3FD98B;margin-right:6px'></span>"
                f"{_esc(name)}</div><span class='pill p-live'>connected</span>"
                f"<button class='sbtn' style='background:transparent;border:1px solid #F5788A;color:#F5788A' "
                f"onclick=\"disconnectWire('{_esc(keys)}')\">Disconnect</button></div>")
            continue
        fields = ""
        for tok in fix.split(" + "):
            tok = tok.strip()
            if "=" in tok:
                kk, dv = tok.split("=", 1)
            else:
                kk, dv = tok, ""
            typ = "password" if any(x in kk.upper() for x in ("PASSWORD", "TOKEN", "KEY", "JSON", "SECRET")) else "text"
            friendly = _FIELD_HINT.get(kk, kk)
            pre = "🔑 " if typ == "password" else ""
            fields += f"<input name='{_esc(kk)}' type='{typ}' placeholder='{pre}{_esc(friendly)}' value='{_esc(dv)}'>"
        conn_rows.append(
            f"<form class='cform' onsubmit='return saveConnect(this)'>"
            f"<div class='cflab'>{_esc(name)}</div>"
            f"<div class='dim' style='margin:-3px 0 5px;line-height:1.45'>{_esc(effect)}</div>"
            f"{fields}"
            f"<button class='sbtn' type='submit'>Connect · turns green in ~15s</button></form>")
    connect_card = ("<div class='card full' style='margin-top:12px'><p class='ct'>🔌 Connect your wires — paste keys, click Connect</p>"
                    "<p class='cc'>No SSH, no rebuild. Saved instantly; the wire turns green above within ~15 seconds. What each one needs (and unlocks) is in the table above.</p>"
                    "<div class='cgrid'>" + "".join(conn_rows) + "</div></div>")
    p_map = ("<div class='card full'><p class='ct'>🗺️ System blueprint — every connection in your machine</p>"
             "<p class='cc'>Each card is one API, account or plugin — its icon, what kind of connection it is, one line of what it does, and whether it's live. Read left → right: inputs → brain → Google hub → outputs.</p>"
             + _blueprint(st) + "</div>"
             "<div class='card full' style='margin-top:12px'><p class='ct'>Live data flow</p>"
             "<p class='cc'>The same machine as a moving flow — data animates along each connected wire.</p>"
             + _system_map(st) + "</div>"
             + diag + connect_card)

    # ---- OVERVIEW (mother) ----
    def tile(nav, icon, label, val, sub, dot):
        return (f"<div class='tile' onclick=\"nav('{nav}')\"><div class='tl'><span class='d' style='width:8px;height:8px;border-radius:50%;background:{dot}'></span>{icon} {label}</div>"
                f"<div class='tv tnum'>{val}</div><div class='tx'>{sub}</div></div>")
    green, amber = "#3FD98B", "#F5B14C"
    setup_missing = [(name, fix) for k, name, why, eff, fix in _DIAG if not st.get(k)]
    setup_done = total_conn - len(setup_missing)
    setup_pct = round(setup_done / total_conn * 100) if total_conn else 0
    setup_list = "".join(
        f"<div class='fe'><span class='mut'>{_esc(name)}</span>"
        f"<span class='dim' style='margin-left:auto'>add {_esc(fix.split(' + ')[0])}</span></div>"
        for name, fix in setup_missing[:6])
    setup_card = ("<div class='card full' style='margin-bottom:12px'><p class='ct'>Setup — connect these to switch everything on</p>"
                  f"<p class='cc'>{setup_done} of {total_conn} connections live.</p>"
                  f"<div class='prog'><i style='width:{setup_pct}%'></i></div>"
                  + (setup_list or "<div class='dim'>All connected 🎉</div>")
                  + "<div class='dim' style='margin-top:8px'>Full details + what each one unlocks on the <b>System Map</b> page.</div></div>")
    avg_day = total_cost / max(date.today().day, 1)
    cost_meter = ("<div class='card full' style='margin-bottom:12px'>"
                  "<p class='ct'>💸 API cost meter — live spend</p>"
                  "<p class='cc'>Every euro the engine spends on Claude, tracked against your cap. (Prospeo + images are small separate fixed costs.)</p>"
                  "<div style='display:flex;gap:26px;flex-wrap:wrap;align-items:flex-end'>"
                  f"<div><div class='dim'>This month</div><div class='big tnum' style='color:{bcol}'>${month_spent:.2f}</div><div class='dim'>of ${month_cap:.0f} cap · {pct}%</div></div>"
                  f"<div><div class='dim'>Today</div><div class='big tnum'>${day_spent:.2f}</div><div class='dim'>of ${day_cap:.0f}/day</div></div>"
                  f"<div><div class='dim'>Avg / day</div><div class='big tnum'>${avg_day:.2f}</div><div class='dim'>this month</div></div>"
                  f"<div style='flex:1;min-width:220px'><div class='dim' style='margin-bottom:4px'>Spend · last 14 days</div>{_sparkline(spend_series, bcol)}</div>"
                  "</div>"
                  f"<div class='prog' style='margin-top:12px'><i style='width:{min(100,pct)}%;background:{bcol}'></i></div></div>")
    overview = (setup_card + cost_meter + "<div class='ov'>"
                + tile("content", "📝", "Content", published, "published this month", green if published else amber)
                + tile("leads", "🧲", "Leads", leads_found, "collected", green if leads_found else amber)
                + tile("email", "✉️", "Email", emails_sent, "sent", green if emails_sent else amber)
                + tile("social", "📣", "Social", "—", "connect a channel", amber)
                + tile("seo", "🔎", "SEO/AEO/GEO", "—", "connect Google", amber)
                + tile("ads", "🎯", "Ads", "—", "feed ad data", amber)
                + tile("budget", "💰", "Budget", f"${month_spent:.0f}/{month_cap:.0f}", f"{pct}% of cap", green if pct < 90 else amber)
                + tile("agents", "❤️", "Agents", f"{live_conn}/{total_conn}", "connectors live", green if live_conn else amber)
                + tile("google", "☁️", "Google hub", "—", "sheets · drive · gmail", green if (st.get('google_sheets') or st.get('google_drive')) else amber)
                + tile("appr", "✅", "Approvals", waiting, "waiting for you", amber if waiting else green)
                + tile("learn", "🧠", "Learning", "—", "improves monthly", green)
                + tile("map", "🗺️", "System map", f"{total_conn-live_conn}", "wires to fix", amber if live_conn < total_conn else green)
                + "</div>")

    # ---- nav + assembly ----
    PAGES = [
        ("overview", "📊", "Overview", "Overview", "A summary of all 12 machines — click any tile to dive in.", overview),
        ("content", "📝", "Content Factory", "Content Factory", "Everything about creating & publishing content.", p_content),
        ("leads", "🧲", "Lead Machine", "Lead Machine", "Finding, scoring and grouping your leads.", p_leads),
        ("email", "✉️", "Email & Outreach", "Email & Outreach", "Cold emails, replies and deliverability.", p_email),
        ("social", "📣", "Social Media", "Social Media", "Posting and engagement across channels.", p_social),
        ("seo", "🔎", "SEO / AEO / GEO", "SEO · AEO · GEO", "Search, AI-answer and geo visibility.", p_seo),
        ("ads", "🎯", "Ads & Growth", "Ads & Growth", "Paid campaigns tuned with your SEO signals.", p_ads),
        ("budget", "💰", "Budget & Cost", "Budget & Cost", "Where the money goes, against your $200 cap.", p_budget),
        ("agents", "❤️", "Agents & Health", "Agents & Health", "Are the agents running, and is anything broken?", p_agents),
        ("google", "☁️", "Google Hub", "Google Hub", "Your Sheets, Drive and Gmail data hub.", p_google),
        ("appr", "✅", "Approvals & Commands", "Approvals & Commands", "Approve work and command any agent.", p_appr),
        ("learn", "🧠", "Learning & Results", "Learning & Results", "What's working and how the engine improves.", p_learn),
        ("map", "🗺️", "System Map & Wiring", "System Map & Wiring", "Every wire, and a plain-English list of what to fix.", p_map),
    ]
    nav = "".join(
        f"<button class='navb{' act' if i==0 else ''}' id='nav-{pid}' onclick=\"nav('{pid}')\"><span class='ic'>{icon}</span>{_esc(short)}"
        + ("" if pid in ("overview",) else "") + "</button>"
        for i, (pid, icon, short, title, sub, body) in enumerate(PAGES))
    pages = "".join(
        f"<section class='page{' on' if i==0 else ''}' id='sec-{pid}'><h2 class='ph'>{_esc(title)}</h2><p class='psub'>{_esc(sub)}</p>{body}</section>"
        for i, (pid, icon, short, title, sub, body) in enumerate(PAGES))

    warn = "" if has_password else "<div style='background:#2a1420;border:1px solid #FF6B93;border-radius:10px;padding:11px 14px;font-size:12.5px;color:#FFC3D4;margin-bottom:12px'>⚠ <b>No password set.</b> This dashboard has no login — set <b>DASHBOARD_PASSWORD</b> in deploy/.env and rebuild to lock it before sharing the link.</div>"
    onboarding = warn + ("" if jobs else "<div style='background:#101d33;border:1px solid #26456f;border-radius:10px;padding:11px 14px;font-size:12.5px;color:var(--mut);margin-bottom:14px'><b style='color:var(--teal)'>Your control center is ready.</b> Numbers fill in as agents run and you connect keys — the <b>System Map</b> page lists exactly what to add.</div>")
    # ---- attention center + control bar (always visible above the pages) ----
    failed = sum(1 for j in jobs if j.get("status") in ("failed", "halted_budget"))
    broken = total_conn - live_conn
    alerts = []
    if paused:
        alerts.append(("#FF6B93", "⏸", "Everything is paused", ""))
    if waiting:
        alerts.append(("#F5B14C", "⚠", f"{waiting} waiting for your approval", "appr"))
    if broken:
        alerts.append(("#F5B14C", "🔌", f"{broken} connection(s) not wired", "map"))
    if pct >= 80:
        alerts.append(("#FF6B93" if pct >= 95 else "#F5B14C", "💰", f"Budget at {pct}% of ${month_cap:.0f}", "budget"))
    if failed:
        alerts.append(("#FF6B93", "✕", f"{failed} job(s) failed or paused", "agents"))
    if not alerts:
        alerts.append(("#3FD98B", "✓", "All clear — nothing needs you right now", ""))
    aparts = []
    for col, ic, msg, nid in alerts:
        oc = f" onclick=\"nav('{nid}')\"" if nid else ""
        aparts.append(f"<button class='alert'{oc}><span style='color:{col}'>{ic}</span> {_esc(msg)}</button>")
    attn_html = "<div class='attn'>" + "".join(aparts) + "</div>"
    pause_btn = ("<button class='cbtn warn' onclick=\"act('/control/resume')\">▶ Resume all</button>" if paused
                 else "<button class='cbtn' onclick=\"act('/control/pause')\">⏸ Pause all</button>")
    auto_btn = ("<button class='cbtn on' onclick=\"act('/control/autonomy?on=false')\">🟢 Autonomy ON</button>" if autonomy
                else "<button class='cbtn' onclick=\"act('/control/autonomy?on=true')\">⚪ Autonomy OFF</button>")
    ctrl_html = ("<div class='ctrl'><button class='cbtn' onclick=\"act('/tick')\">▶ Run now</button>"
                 + pause_btn + auto_btn + "</div>")

    logout = "<a class='logout' href='/logout'>Sign out</a>" if has_password else ""
    script = ("<script>function nav(id){document.querySelectorAll('.page').forEach(p=>p.classList.remove('on'));"
              "var s=document.getElementById('sec-'+id);if(s)s.classList.add('on');"
              "document.querySelectorAll('.navb').forEach(b=>b.classList.remove('act'));"
              "var n=document.getElementById('nav-'+id);if(n)n.classList.add('act');window.scrollTo(0,0);}"
              "async function act(u){try{await fetch(u,{method:'POST'});location.reload();}catch(e){alert('Action failed: '+e);}}"
              "async function saveConnect(f){var o={};for(var i=0;i<f.elements.length;i++){var e=f.elements[i];if(e.name&&e.value)o[e.name]=e.value;}"
              "if(!Object.keys(o).length){alert('Fill in at least one field.');return false;}"
              "try{var r=await fetch('/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)});"
              "var j=await r.json();alert('Saved: '+(j.saved||[]).join(', ')+'. It goes live in ~15s.');location.reload();}"
              "catch(e){alert('Save failed: '+e);}return false;}"
              "async function disconnectWire(keys){if(!confirm('Disconnect and clear this connection? You can re-enter it right after.'))return false;"
              "try{await fetch('/disconnect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keys:keys.split(',')})});"
              "alert('Disconnected — the box is editable again.');location.reload();}"
              "catch(e){alert('Disconnect failed: '+e);}return false;}"
              "async function approve(id){await act('/jobs/'+id+'/approve');}"
              "async function runSkill(){var sk=document.getElementById('sk').value,out=document.getElementById('out'),inp=document.getElementById('inp').value;"
              "out.textContent='Running '+sk+'…';try{var b=JSON.parse(inp||'{}');}catch(e){out.textContent='That input is not valid JSON.';return;}"
              "try{var r=await fetch('/skills/'+sk+'/taste',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({input:b})});"
              "out.textContent=JSON.stringify(await r.json(),null,2);}catch(e){out.textContent='Error: '+e;}}</script>")

    return (
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Business Control Center</title><style>" + CSS + "</style></head><body>"
        "<div class='top'><div class='brand'><div class='logo'>A</div><div><h1>Anthropos — Control Center</h1><small>Your automation, in plain English</small></div></div>"
        "<div style='display:flex;gap:9px;align-items:center'><span class='status'><span class='d' style='background:"
        + ("#3FD98B" if healthy else "#F5B14C") + "'></span>" + ("All systems nominal" if healthy else "Check health")
        + "</span>" + logout + "</div></div>"
        "<div class='shell'><div class='side'>" + nav + "</div><div class='main'>"
        + ctrl_html + attn_html + onboarding + pages + "</div></div>"
        + script + "</body></html>")


if __name__ == "__main__":
    demo = [
        {"job_id": "job_a1", "type": "content_piece", "status": "AWAITING_APPROVAL",
         "payload": {"content_producer": {"title": "24/7 competitor price monitoring"}}, "cost_so_far_usd": 0.04},
        {"job_id": "job_b2", "type": "content_piece", "status": "optimized", "payload": {}, "cost_so_far_usd": 0.11},
        {"job_id": "job_e5", "type": "outreach_campaign", "status": "sent",
         "payload": {"raw_leads": [{}] * 40, "leads": [{}] * 31, "send_ref": "x"}, "cost_so_far_usd": 0.02},
    ]
    html = dashboard_html(jobs=demo, st={"wordpress_publish": True, "google_sheets": False},
                          health={"healthy": True, "anthropic": {"status": "ok"}, "postgres": {"status": "ok"}},
                          month_spent=63, month_cap=200, day_spent=4.2, day_cap=50,
                          taste_skills=["content_producer", "seo_optimizer"])
    for need in ("Overview", "Content Factory", "System Map", "Wiring diagnostic", "Automation Engine",
                 "sec-map", "nav('leads')", "24/7 competitor", "What it breaks", "Not connected"):
        assert need in html, need
    assert html.count("class='page") == 13, html.count("class='page")
    assert "control center is ready" in dashboard_html(jobs=[], st={}, health={"healthy": True},
                                                       month_spent=0, month_cap=200, day_spent=0, day_cap=50, taste_skills=[])
    assert "Sign in" in login_html()
    print("OK — 13-page tabbed dashboard (overview + 12 machines, 48 views) + wiring diagnostic render. No network.")
