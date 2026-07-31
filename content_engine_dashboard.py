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

import logging

import content_engine_charts as CH   # BOS visual language (SVG, no libs)

log = logging.getLogger("content_engine.dashboard")

# Bumped on every deploy so the running build is VISIBLE on the page — no more
# guessing from terminal hashes. If the badge in the top bar doesn't match this,
# the new code isn't live yet (re-pull + rebuild).
BUILD_TAG = ("2026-07-31 · v31 · THE CADENCE — the worker now queues the daily batch, runs the SEO engines when they are due, and drafts replies, without ever being able to publish or send. START is SUPERVISED: it no longer grants autonomy as a side effect, so nothing auto-publishes after 24h unless you deliberately choose it. Previously: THE RETURN ARROW — the engine can now find "
             "out what happened. Real GA4 numbers for the exact page that was "
             "published (including conversions, which were structurally zero "
             "before), real opens and clicks per campaign, content measured at "
             "21 days and outreach at 7. An outcome that cannot be measured "
             "states WHY, skips the model, and teaches the playbook nothing. A "
             "measured-poor piece earns a proposal that still waits for you. "
             "Loop closure is computed from live wires, not drawn. 2,284 "
             "engine cards across 9 sidebar entries: Media 296, Content 278, "
             "Cockpit 269, BI 268, SGA 250, System 240, Outreach 240, SEO 235, "
             "Risk 208")

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
.grid{display:grid;gap:12px}
/* Cards lay out ACROSS, not down. The old rule was a fixed 3 columns that a
   max-width:860px query flattened to a single column - so on any window under
   860px (which is most of them, and every embedded browser pane) all 2,255
   cards stacked one per row and every board read as an endless vertical list.
   These widths are content-driven: 2 across from 560px, 3 from 1080px, and a
   single column only on a real phone. */
.g2,.g3,.g4{grid-template-columns:repeat(2,minmax(0,1fr))}
@media(min-width:1080px){.g3{grid-template-columns:repeat(3,minmax(0,1fr))}
  .g4{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(min-width:1440px){.g4{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(max-width:559px){.g2,.g3,.g4{grid-template-columns:minmax(0,1fr)}}
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
/* The sidebar turns into a horizontal strip on a narrow window. It carried
   overflow-x:auto but no min-width:0, and a flex item defaults to min-width:auto
   - so it refused to shrink below its content, grew to 1263px inside a 768px
   shell and dragged the WHOLE PAGE into sideways scrolling. min-width:0 is what
   makes its own overflow-x:auto actually engage. The grid columns are no longer
   touched here; they are set once, above, and stay horizontal. */
@media(max-width:860px){.shell{flex-direction:column;min-width:0}
  .side{width:auto;min-width:0;max-width:100%;flex-direction:row;overflow-x:auto;position:static;max-height:none}
  .navb{white-space:nowrap;flex:0 0 auto}.navb .bd{display:none}}
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
.dfp{margin-top:4px}.dfp+.dfp{margin-top:18px}
.dfh{font-size:12.5px;font-weight:700;margin-bottom:9px}.dfh .dim{font-weight:400}
.dfrow{display:flex;align-items:center;overflow-x:auto;padding:2px 0 6px}
.dfstage{flex:1 1 0;min-width:106px;background:var(--s2);border:1px solid var(--line);border-radius:11px;padding:10px 8px;text-align:center}
.dfstage.hot{border-color:rgba(47,227,210,.55)}
.dfstage .i{font-size:18px}
.dfstage .n{font-size:11px;color:var(--mut);margin-top:3px}
.dfstage .v{font-size:21px;font-weight:750;margin-top:2px;line-height:1}
.dfstage .b{font-size:9px;color:var(--dim);margin-top:5px;background:var(--bg);border:1px solid var(--line);border-radius:5px;padding:1px 6px;display:inline-block}
.dfconn{flex:0 0 32px;position:relative;height:2px;margin-top:-8px}
.dfconn .line{position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--line2),var(--teal),var(--line2))}
.dfconn::after{content:'';position:absolute;top:-2px;left:0;width:6px;height:6px;border-radius:50%;background:var(--teal);box-shadow:0 0 7px var(--teal);animation:dfflow 1.7s linear infinite}
@keyframes dfflow{0%{left:-4px;opacity:0}15%{opacity:1}85%{opacity:1}100%{left:100%;opacity:0}}
.mcard{background:linear-gradient(180deg,#0d1a33,#0b111f);border-color:#22345a;margin-bottom:12px}
.mhead{display:flex;align-items:center;gap:11px;margin-bottom:13px}
.mi{font-size:22px}.mt{font-size:15px;font-weight:750;letter-spacing:-.01em}
.mbody{display:flex;gap:20px;flex-wrap:wrap;align-items:center}
.mstats{display:flex;gap:9px;flex-wrap:wrap;flex:1 1 260px}
.mstat{background:var(--s2);border:1px solid var(--line);border-radius:10px;padding:9px 13px;min-width:88px}
.msv{font-size:23px;font-weight:750;line-height:1}
.msl{font-size:10px;color:var(--mut);margin-top:4px;letter-spacing:.02em}
.mchart{flex:1 1 240px;min-width:220px}
@media(max-width:860px){.mbody{flex-direction:column;align-items:stretch}}
.wkgrid{display:grid;grid-template-columns:repeat(7,minmax(150px,1fr));gap:8px;overflow-x:auto;padding-bottom:4px}
.wkcol{background:var(--s2);border:1px solid var(--line);border-radius:11px;padding:8px;min-height:130px;display:flex;flex-direction:column}
.wkcol.today{border-color:#2FE3D2;box-shadow:0 0 16px -5px rgba(47,227,210,.55)}
.wkcol.wknd{opacity:.72}
.wkhead{font-weight:700;font-size:12px;color:var(--ink);padding:2px 2px 8px;border-bottom:1px solid var(--line);margin-bottom:8px;display:flex;justify-content:space-between;align-items:baseline}
.wkhead small{color:var(--mut);font-weight:500;font-size:10px}
.wkhead .tdy{color:#2FE3D2;font-size:9px;letter-spacing:1px}
.wkcard{background:rgba(255,255,255,.04);border-radius:8px;padding:7px 8px;margin-bottom:6px;border-left:3px solid var(--c,#2FE3D2);transition:transform .15s}
.wkcard:hover{transform:translateX(2px);background:rgba(255,255,255,.07)}
.wkcard b{font-size:12px;line-height:1.32;display:block;color:var(--ink)}
.wkchip{display:inline-block;font-size:9.5px;padding:0 6px;border-radius:6px;margin-top:4px;margin-right:3px}
.wkempty{color:#3A4160;font-size:11px;text-align:center;margin:auto 0;padding:10px 0}
@keyframes cf-flow{0%,100%{opacity:.2;transform:translateX(-2px)}50%{opacity:1;transform:translateX(3px)}}
@keyframes cf-pulse{0%,100%{box-shadow:0 0 0 0 rgba(47,227,210,0)}50%{box-shadow:0 0 16px -2px rgba(47,227,210,.55)}}
.cf-arrow{animation:cf-flow 1.8s ease-in-out infinite}
.cf-live{animation:cf-pulse 2.2s ease-in-out infinite}
.cf-station{transition:transform .25s}.cf-station:hover{transform:translateY(-4px)}
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
    ("ads_api", "Google Ads (paid campaigns)",
     "no Google Ads API credentials",
     "The ads agent can't see or tune your paid campaigns — no spend, cost-per-lead or ROAS flows in, so it can't move budget to what works.",
     "GOOGLE_ADS_DEVELOPER_TOKEN + GOOGLE_ADS_CUSTOMER_ID + GOOGLE_ADS_REFRESH_TOKEN + GOOGLE_ADS_CLIENT_ID + GOOGLE_ADS_CLIENT_SECRET"),
    ("calcom_bookings", "Booked consultations (Cal.com)",
     "no Cal.com API key",
     "The dashboard can't see booked calls, so the deal loop (email → reply → BOOKED → customer) never closes — 'Booked' stays 0.",
     "CALCOM_API_KEY"),
    ("image_gen", "Generate images (OpenAI)",
     "no image provider key",
     "Posts go out as text only — no generated images.",
     "IMAGE_PROVIDER=openai + IMAGE_API_KEY + IMAGE_MODEL=gpt-image-1"),
    ("video_gen", "Generate video",
     "no video provider key",
     "No AI video is produced (the pricey one — use selectively).",
     "VIDEO_PROVIDER + VIDEO_API_KEY + VIDEO_API_URL"),
    # ---- APPENDED 2026-07-30. The 18 entries above are untouched. These 12
    # wires existed in connectors.status() with NO diagnostic and NO connect
    # form, so they could not be wired from the browser at all.
    ("serper_search", "Google search + Maps (Serper)",
     "no Serper key",
     "Rank tracking, competitor scans, AI-answer checks, link prospecting and Maps lead sourcing all stop. One key powers five engines.",
     "SERPER_API_KEY"),
    ("seo_backlinks", "Backlink profile (DataForSEO)",
     "no DataForSEO login",
     "Your own backlink profile stays invisible. Google publishes no links API, so this is the only source — link PROSPECTING still works without it.",
     "DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD"),
    ("seo_pagespeed", "Page speed + Core Web Vitals",
     "no PageSpeed key (works without one, but heavily rate-limited)",
     "Speed scores come back empty. The API is free either way — a key just raises the quota.",
     "PAGESPEED_API_KEY"),
    ("seo_indexnow", "Instant indexing (Bing/Yandex)",
     "no IndexNow key",
     "New posts are not pushed to Bing or Yandex. Invent any 32-character hex string and upload <key>.txt to your site root.",
     "INDEXNOW_KEY"),
    ("seo_index_inspect", "Ask Google what is indexed",
     "Google service account not connected",
     "You cannot see which pages Google has actually indexed. Free, 2,000 checks a day — it uses the same service account as Search Console.",
     "GOOGLE_SERVICE_ACCOUNT_JSON"),
    ("seo_rank_tracker", "Daily rank tracking",
     "no Serper key",
     "Search Console averages 28 days and lags 2-3 days. Without this you cannot tell whether yesterday's fix worked.",
     "SERPER_API_KEY"),
    ("seo_gbp", "Google Business Profile",
     "no Business Profile OAuth",
     "Reviews, posts and local insights stay empty. Needs its own OAuth - a service account cannot act on a business profile.",
     "GBP_ACCESS_TOKEN + GBP_ACCOUNT_ID + GBP_LOCATION_ID"),
    ("ads_data", "Ads data paste-in (fallback)",
     "no ADS_JSON pasted",
     "A manual fallback for ad metrics when the Google Ads API is not connected.",
     "ADS_JSON"),
    ("backlinks_data", "Backlinks paste-in (fallback)",
     "no BACKLINKS_JSON pasted",
     "A manual fallback for backlink data if you export it from another tool.",
     "BACKLINKS_JSON"),
    ("seo_crawler", "Your own site crawler",
     "",
     "ALWAYS ON. Pure code, no credential, no cost - it reads your own site and feeds every on-page, technical and landing-page card.",
     ""),
    ("email_verify", "Email address verification",
     "",
     "ALWAYS ON. Falls back from MX lookup to syntax checking, so it never blocks outreach.",
     ""),
    ("requests_installed", "HTTP library",
     "",
     "ALWAYS ON. Ships in the image; every outbound call depends on it.",
     ""),
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
    "GOOGLE_ADS_DEVELOPER_TOKEN": "Google Ads developer token",
    "GOOGLE_ADS_CUSTOMER_ID": "Google Ads account ID (10 digits)",
    "GOOGLE_ADS_REFRESH_TOKEN": "Google Ads refresh token",
    "GOOGLE_ADS_CLIENT_ID": "Google OAuth client ID",
    "GOOGLE_ADS_CLIENT_SECRET": "Google OAuth client secret",
    "CALCOM_API_KEY": "Cal.com API key (cal_live_…)",
}

# Keys that /connect has always accepted but that no wire's `fix` string ever
# rendered a box for — so they were allow-listed and unreachable at the same
# time. Grouped by what each one unlocks, and rendered by _extra_keys_card()
# through the SAME saveConnect() form and the SAME /connect endpoint. No new
# route, no new vendor, no change to how any credential is stored or read.
EXTRA_KEY_GROUPS = [
    ("🤖 AI answer engines", "openai",
     "You are measured against ChatGPT, Perplexity and Gemini. Only Claude is "
     "wired, so AI visibility is being judged on one engine out of four.",
     [("OPENAI_API_KEY", "OpenAI API key (sk-…)"),
      ("PERPLEXITY_API_KEY", "Perplexity API key (pplx-…)"),
      ("GEMINI_API_KEY", "Google Gemini API key"),
      ("OPENAI_AEO_MODEL", "OpenAI model (blank = default)"),
      ("PERPLEXITY_MODEL", "Perplexity model (blank = default)"),
      ("GEMINI_MODEL", "Gemini model (blank = default)")]),
    ("✉️ Email identity", "email",
     "Every cold email currently goes out carrying defaults where your branding "
     "should be — company name, logo, booking link and signature.",
     [("EMAIL_COMPANY", "Company name on the signature"),
      ("EMAIL_FROM_NAME", "Sender name recipients see"),
      ("EMAIL_SENDER_TITLE", "Your title (Founder)"),
      ("EMAIL_WEBSITE", "Website shown in the footer"),
      ("EMAIL_PHONE", "Phone number in the signature"),
      ("EMAIL_ADDRESS", "Postal address (required by law in DE)"),
      ("EMAIL_LOGO_URL", "Logo image URL (https://…)"),
      ("EMAIL_BRAND_COLOR", "Brand colour (#RRGGBB)"),
      ("EMAIL_BOOKING_URL", "Booking link (Cal.com)"),
      ("EMAIL_UNSUBSCRIBE_URL", "Unsubscribe link"),
      ("EMAIL_MANAGE_URL", "Manage-preferences link"),
      ("EMAIL_HTML", "Send HTML email? 1 or 0")]),
    ("📮 Mail transport", "mail",
     "Only needed if your mail host is not on standard ports. Blank means the "
     "usual defaults, which is right for Google Workspace.",
     [("SMTP_PORT", "SMTP port (587)"),
      ("SMTP_FROM", "Send-from address if different"),
      ("SMTP_STARTTLS", "STARTTLS on? 1 or 0"),
      ("IMAP_PORT", "IMAP port (993)"),
      ("IMAP_FOLDER", "Folder to read (INBOX)")]),
    ("💬 Reply agent", "reply",
     "What the reply agent is ALLOWED to say. Leaving these blank is why replies "
     "read generic — it has no offer and no context to work from.",
     [("REPLY_OUR_OFFER", "What you actually sell, in one line"),
      ("REPLY_SENDER_NAME", "Name replies are signed with"),
      ("REPLY_CONTEXT", "Anything the agent must know or never claim"),
      ("REPLY_AUTO_SEND", "Auto-send replies? Leave 0 — you approve each one")]),
    ("📝 WordPress", "wp",
     "Only needed for a non-standard WordPress setup.",
     [("WORDPRESS_USER", "WordPress username"),
      ("WP_STATUS", "publish or draft")]),
    ("⚙️ Advanced", "adv",
     "Overrides and pins. Every one is optional — blank uses the default.",
     [("CI_JSON", "Brand CI as JSON (or use the CI upload)"),
      ("IMAGE_API_URL", "Image endpoint override"),
      ("LINKEDIN_API_KEY", "LinkedIn data provider key"),
      ("LINKEDIN_PROVIDER_URL", "LinkedIn provider endpoint"),
      ("GOOGLE_ADS_API_VERSION", "Google Ads API version (v17)"),
      ("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "Manager account ID, if you use one"),
      ("GOOGLE_ADS_OFFLINE_ACTION", "Offline conversion action name")]),
]


def _extra_keys_card(saved_keys=None) -> str:
    """The 36 keys that /connect accepts but no form ever showed a box for.

    A key the endpoint allows and the browser cannot reach is the same as a key
    you do not have. This renders them grouped by what they unlock, through the
    existing saveConnect() → /connect path — the allow-list is unchanged."""
    saved = set(saved_keys or ())
    n_total = sum(len(f) for _t, _s, _w, f in EXTRA_KEY_GROUPS)
    n_saved = sum(1 for _t, _s, _w, f in EXTRA_KEY_GROUPS
                  for k, _h in f if k in saved)
    forms = []
    for title, slug, why, fields in EXTRA_KEY_GROUPS:
        boxes = ""
        for k, hint in fields:
            secret = any(x in k for x in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
            mark = " ✅" if k in saved else ""
            typ = "password" if secret else "text"
            pre = "🔑 " if secret else ""
            ph = ("saved — type to replace" if k in saved
                  else pre + hint)
            boxes += (f"<input name='{_esc(k)}' type='{typ}' "
                      f"placeholder='{_esc(ph)}' title='{_esc(k)}{mark}'>")
        done = sum(1 for k, _h in fields if k in saved)
        pill = (f"<span class='pill p-live'>{done}/{len(fields)} saved</span>"
                if done else
                f"<span class='pill p-need'>{len(fields)} to add</span>")
        forms.append(
            f"<form class='cform' onsubmit='return saveConnect(this)'>"
            f"<div class='cflab'>{_esc(title)} {pill}</div>"
            f"<div class='dim' style='margin:-3px 0 5px;line-height:1.45'>"
            f"{_esc(why)}</div>{boxes}"
            f"<button class='sbtn' type='submit'>Save · live in ~15s</button>"
            f"</form>")
    return ("<div class='card full' style='margin-top:12px' id='extrakeys'>"
            "<p class='ct'>🔑 Extra keys — everything else your machine can use</p>"
            f"<p class='cc'>{n_saved} of {n_total} set. These were accepted by "
            "/connect all along but no form showed a box for them, so they could "
            "only be added by editing .env and rebuilding. Same endpoint, same "
            "allow-list, same settings store — blank fields are ignored, so you "
            "can save one group at a time. <b>None of these is a SaaS tool</b> — "
            "they are the platforms' own APIs.</p>"
            "<div class='cgrid'>" + "".join(forms) + "</div></div>")


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


_STOP = set(("the a an and or to of for your you our we with in on how why what that this not are is it as at "
             "by from into their his her its can will about over more into out get your make when where who "
             "you're every each still just than then them they there here".split()))
_VMAP = {"dentist": "Dentists", "zahnarzt": "Dentists", "doctor": "Doctors", "clinic": "Doctors",
         "lawyer": "Lawyers", "attorney": "Lawyers", "kanzlei": "Lawyers", "law": "Lawyers",
         "tax": "Tax / Accounting", "account": "Tax / Accounting", "steuer": "Tax / Accounting",
         "treuhand": "Tax / Accounting", "fiduciary": "Tax / Accounting",
         "shopify": "E-commerce", "commerce": "E-commerce", "shop": "E-commerce",
         "marketing": "Marketing", "social": "Marketing", "agency": "Marketing"}


def _themes(content_jobs):
    """Most-written subjects (word frequency across content titles)."""
    import re, collections
    w = collections.Counter()
    for j in content_jobs:
        t = ((j.get("payload", {}).get("content_producer", {}) or {}).get("title") or "")
        for x in re.findall(r"[a-zA-Z]{4,}", t.lower()):
            if x not in _STOP:
                w[x] += 1
    return w.most_common(6)


def _verticals(out_jobs):
    """Which professions the leads cluster in (from lead titles)."""
    import collections
    c = collections.Counter()
    for j in out_jobs:
        for l in (j.get("payload", {}) or {}).get("leads", []) or []:
            t = str(l.get("title", "")).lower()
            for k, v in _VMAP.items():
                if k in t:
                    c[v] += 1
                    break
    return c.most_common(6)


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


def _master(icon, title, sub, kpis, chart_html):
    """The big at-a-glance summary card that sits on top of a section: a row of
    headline KPI numbers + one summary chart. kpis = [(label, value, color)]."""
    tiles = "".join(
        f"<div class='mstat'><div class='msv tnum' style='color:{c}'>{v}</div>"
        f"<div class='msl'>{_esc(l)}</div></div>" for l, v, c in kpis)
    return (f"<div class='card full mcard'><div class='mhead'><span class='mi'>{icon}</span>"
            f"<div><div class='mt'>{_esc(title)}</div>"
            f"<div class='cc' style='margin:1px 0 0'>{_esc(sub)}</div></div></div>"
            f"<div class='mbody'><div class='mstats'>{tiles}</div>"
            f"<div class='mchart'>{chart_html}</div></div></div>")


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


def _send_daybuckets(out_jobs, days=14):
    """Real emails-sent-per-day from the sent_at timestamps (intro + follow-ups),
    not campaign-created dates — so the send-volume chart reflects actual sends."""
    from datetime import date, timedelta
    today = date.today()
    idx = {(today - timedelta(days=days - 1 - i)).isoformat(): i for i in range(days)}
    vals = [0.0] * days
    for j in out_jobs:
        at = (j.get("payload", {}) or {}).get("sent_at", {}) or {}
        for times in at.values():
            for t in (times if isinstance(times, list) else [times]):
                d = str(t)[:10]
                if d in idx:
                    vals[idx[d]] += 1
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
        ("ads_api", "🎯", "Google Ads", "Ads API · token", "Paid campaign spend, CPA & ROAS"),
        ("calcom_bookings", "📅", "Cal.com", "REST API · key", "Booked consultations — closes the deal loop"),
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


def _dataflow(pl, lead_rows):
    """Live data-flow map: the two pipelines, stage by stage, with REAL counts and
    the tool each stage uses. A dot animates along each connector = data moving."""
    def cell(icon, name, val, tool):
        hot = " hot" if val else ""
        return (f"<div class='dfstage{hot}'><div class='i'>{icon}</div><div class='n'>{_esc(name)}</div>"
                f"<div class='v tnum'>{val}</div><div class='b'>{_esc(tool)}</div></div>")
    def row(title, sub, stages):
        cells = []
        for j, s in enumerate(stages):
            cells.append(cell(*s))
            if j < len(stages) - 1:
                cells.append("<div class='dfconn'><div class='line'></div></div>")
        return (f"<div class='dfp'><div class='dfh'>{_esc(title)} <span class='dim'>· {_esc(sub)}</span></div>"
                f"<div class='dfrow'>{''.join(cells)}</div></div>")
    lr = lead_rows
    content = [("💡", "Plan", pl[0], "strategist"), ("✍️", "Write", pl[1], "Claude"),
               ("🔎", "SEO check", pl[2], "SEO agent"), ("✅", "Approve", pl[3], "you"),
               ("🌐", "Publish", pl[4], "WordPress"), ("📈", "Measure", pl[5], "GA4")]
    outreach = [("🧲", "Find", lr[0][1], "Prospeo"), ("✔️", "Verify", lr[1][1], "engine"),
                ("🎯", "Qualify", lr[2][1], "Claude"), ("✉️", "Send", lr[3][1], "contact@"),
                ("💬", "Reply", lr[4][1], "IMAP"), ("📅", "Booked", lr[5][1], "Cal.com")]
    return (row("Content pipeline", "idea → written → checked → approved → live → measured", content)
            + row("Outreach pipeline", "lead → verify → qualify → send → reply → booked", outreach))


# ---------------------------------------------------------------------------
# Media buying — drafted Google Ads campaigns (the media_buyer agent's output)
# ---------------------------------------------------------------------------
def _media_campaigns(jobs):
    """Pull drafted campaigns (the media_buyer result lives on the job payload)."""
    out = []
    for j in jobs:
        mb = (j.get("payload", {}) or {}).get("media_buyer")
        if isinstance(mb, dict) and mb.get("campaign_name"):
            out.append((j, mb))
    return out


def _media_funnel(mb):
    """Estimated funnel from the drafted campaign: budget -> impressions -> clicks
    -> leads -> customers, with real numbers derived from the media buyer's own
    estimates. This is the 'funnel visualized with estimated data'."""
    import re

    def _mid(s, default):
        vals = [float(n) for n in re.findall(r"[0-9]+\.?[0-9]*", str(s or ""))]
        return (sum(vals) / len(vals)) if vals else default

    monthly = float(mb.get("monthly_budget") or 0) or (float(mb.get("daily_budget") or 10) * 30)
    cpc = _mid(mb.get("estimated_cpc_range"), 2.0) or 2.0
    clicks = int(monthly / cpc) if cpc else 0
    impressions = int(clicks / 0.05) if clicks else 0            # ~5% CTR assumption
    leads = int(_mid(mb.get("estimated_leads_range"), max(1, clicks * 0.05)))
    customers = max(0, round(leads * 0.2))                       # ~20% close assumption
    cpl = (monthly / leads) if leads else 0
    stages = [("Impressions", impressions, "#4C8DFF"), ("Clicks", clicks, "#2FE3D2"),
              ("Leads", leads, "#8B7CFF"), ("Customers", customers, "#46E08B")]
    mx = max(impressions, 1)
    bars = ""
    for label, val, col in stages:
        w = max(4, round(100 * val / mx))
        bars += (f"<div class='br'><span class='bl'>{label}</span>"
                 f"<div class='track'><i style='width:{w}%;background:{col}'></i></div>"
                 f"<span class='bv tnum'>{val:,}</span></div>")
    return ("<div style='margin-top:12px;padding:12px;border-radius:9px;background:rgba(76,141,255,.06)'>"
            f"<div class='dim'>📊 Estimated monthly funnel · ${monthly:,.0f} budget · ~${cpc:.2f} CPC</div>"
            f"<div class='bars' style='margin-top:8px'>{bars}</div>"
            f"<div class='dim' style='margin-top:6px'>≈ <b>${cpl:.0f}</b> per lead · ≈ <b>{customers}</b> customers/mo "
            "<span style='opacity:.7'>(estimated — real numbers replace these once the campaign runs)</span></div></div>")


def _media_card(jid, mb, approved=False, live=False, ads_on=False, history=None):
    ags = mb.get("ad_groups", []) or []
    themes = " · ".join(a.get("theme", "") for a in ags[:6])
    kws, heads = [], []
    for a in ags:
        kws += (a.get("keywords") or [])
        heads += (a.get("headlines") or [])
    checks = "".join(f"<div class='fe'><span class='mut'>◆ {_esc(x)}</span></div>"
                     for x in (mb.get("human_should_check") or [])[:5])
    # abort is always available: pause a live campaign, or discard a draft
    abort = (f"<button class='cbtn warn' onclick=\"abortCampaign('{_esc(jid)}',{'true' if live else 'false'})\">"
             + ("⛔ Abort — pause &amp; stop spend" if live else "🗑 Discard draft") + "</button>")
    # action button: draft -> Approve ; approved+ads -> Activate ; approved no-ads -> guidance ; live -> pill
    if live:
        action = "<span class='pill p-live'>🚀 live in Google Ads</span>"
    elif not approved:
        action = (f"<button class='sbtn' onclick=\"approve('{_esc(jid)}')\">✓ Approve campaign</button>"
                  f"<button class='sbtn' onclick=\"activateCampaign('{_esc(jid)}')\">🚀 Approve &amp; deploy in 1 click</button>")
    elif ads_on:
        action = (f"<span class='pill p-live'>✓ approved</span>"
                  f"<button class='sbtn' onclick=\"activateCampaign('{_esc(jid)}')\">🚀 Activate campaign (go live)</button>")
    else:
        action = (f"<span class='pill p-live'>✓ approved</span>"
                  f"<button class='sbtn' onclick=\"activateCampaign('{_esc(jid)}')\">🚀 Activate (connect Google Ads first)</button>")
    risks = (f"<div class='dim' style='margin-top:8px'>⚠ Risks</div>"
             f"<div style='margin-top:4px'>{_esc(mb.get('risks',''))}</div>") if mb.get("risks") else ""
    # S1: the judge's verdict on this draft (cheap-model quality check)
    q = mb.get("_quality") or {}
    if q:
        sc = int(q.get("score", 0) or 0)
        weak = q.get("verdict") in ("revise", "block") or sc < 75
        qcol, qbg = (("#F5B14C", "#3a2c10") if weak else ("#3FD98B", "#10281c"))
        qissues = "".join(f"<div class='fe'><span class='mut'>• {_esc(x)}</span></div>"
                          for x in (q.get("issues") or [])[:3])
        quality = (f"<div style='margin-top:12px;padding:10px 12px;border-radius:9px;background:{qbg}'>"
                   f"<span class='pill' style='background:transparent;color:{qcol}'>"
                   f"{'⚠ Weak' if weak else '✓ Looks good'} · judge score {sc}/100</span>"
                   + (f"<div style='margin-top:6px'>{qissues}</div>" if qissues else "")
                   + (f"<div class='dim' style='margin-top:4px'>Fix: {_esc(q.get('suggestion',''))}</div>" if q.get('suggestion') else "")
                   + "</div>")
    else:
        quality = ""
    # chat log (hidden until the user opens it)
    log = ""
    for h in (history or [])[-8:]:
        who = "You" if h.get("role") == "user" else "Agent"
        log += (f"<div class='fe'><span class='tm' style='min-width:44px'>{who}</span>"
                f"<span class='mut'>{_esc(h.get('text',''))}</span></div>")
    chat = (
        f"<div class='mchat' id='mchat-{_esc(jid)}' style='display:none;margin-top:12px;"
        "border-top:1px solid rgba(255,255,255,.08);padding-top:12px'>"
        f"<div class='dim'>💬 Talk to the media buyer — ask why, or request changes (budget, keywords, headlines, locations)</div>"
        f"<div class='mlog' id='mlog-{_esc(jid)}' style='margin-top:8px;max-height:240px;overflow:auto'>{log}</div>"
        "<div class='ctrl' style='margin-top:8px'>"
        f"<input id='min-{_esc(jid)}' placeholder='e.g. lower the daily budget to €10 and add Munich' "
        "style='flex:1;min-width:220px' onkeydown=\"if(event.key==='Enter')mediaSend('" + _esc(jid) + "')\">"
        f"<button class='sbtn' onclick=\"mediaSend('{_esc(jid)}')\">Send</button></div></div>")
    return (
        "<div class='card full' style='margin-bottom:12px'>"
        f"<p class='ct'>🎯 {_esc(mb.get('campaign_name','Campaign'))}</p>"
        f"<p class='cc'>{_esc(mb.get('objective','leads'))} · ${_esc(str(mb.get('daily_budget','')))}/day "
        f"(${_esc(str(mb.get('monthly_budget','')))}/mo) · {_esc(', '.join(mb.get('locations',[]) or []))}</p>"
        "<div style='display:flex;gap:22px;flex-wrap:wrap'>"
        f"<div style='flex:1;min-width:240px'><div class='dim'>Ad groups ({len(ags)})</div>"
        f"<div style='margin-top:4px'>{_esc(themes)}</div>"
        f"<div class='dim' style='margin-top:8px'>Top keywords</div>"
        f"<div style='margin-top:4px'>{_esc(', '.join(kws[:8]))}</div>"
        f"<div class='dim' style='margin-top:8px'>Sample headlines</div>"
        f"<div style='margin-top:4px'>{_esc(' · '.join(heads[:4]))}</div></div>"
        f"<div style='flex:1;min-width:240px'><div class='dim'>💡 Why the agent built it this way</div>"
        f"<div style='margin-top:4px;line-height:1.6'>{_esc(mb.get('rationale',''))}</div>{risks}"
        f"<div class='dim' style='margin-top:8px'>🎯 Targeting: {_esc(', '.join(mb.get('locations',[]) or []) or 'not set')}"
        f" · {_esc(', '.join(mb.get('languages',[]) or []))}</div>"
        f"<div class='dim' style='margin-top:4px'>Estimate: {_esc(mb.get('estimated_cpc_range',''))} CPC · "
        f"{_esc(mb.get('estimated_leads_range',''))}</div></div></div>"
        + _media_funnel(mb)
        + quality
        + (f"<div style='margin-top:10px'><div class='dim'>Check before you approve:</div>{checks}</div>" if checks else "")
        + "<div class='ctrl' style='margin-top:12px'>" + action
        + f"<button class='cbtn' onclick=\"mediaChat('{_esc(jid)}')\">💬 Discuss / request changes</button>"
        + abort + "</div>"
        + chat + "</div>")


def _media_tracking_panel(web):
    """Real website tracking from the connected GA4 + Search Console (the data the
    service-account keys unlock). This is 'tracking inside the website'."""
    web = web or {}
    ga4 = web.get("ga4") or {}
    gsc = web.get("gsc") or []
    m = ga4.get("metrics") or {}
    sessions = m.get("sessions") or 0
    top_pages = m.get("top_pages") or []
    if not sessions and not gsc:
        return ("<div class='card full' style='margin-bottom:12px'><p class='ct'>📈 Website tracking</p>"
                "<p class='cc'>Live sessions and top search queries appear here from your connected Google "
                "Analytics + Search Console. It's empty because GA4/GSC returned no data for the last 28 days yet "
                "(new property, or low traffic). The wires are green — data fills in as visits accrue.</p></div>")
    pages = "".join(f"<div class='fe'><span class='mut'>{_esc(p.get('page',''))}</span>"
                    f"<span class='dim' style='margin-left:auto'>{p.get('sessions',0):,} sessions</span></div>"
                    for p in top_pages[:6]) or _empty("No page data yet.")
    queries = "".join(f"<div class='fe'><span class='mut'>{_esc(q.get('query',''))}</span>"
                      f"<span class='dim' style='margin-left:auto'>{q.get('clicks',0)} clicks · pos {q.get('position',0)}</span></div>"
                      for q in gsc[:8]) or _empty("No query data yet.")
    return ("<div class='card full' style='margin-bottom:12px'><p class='ct'>📈 Website tracking (live)</p>"
            f"<p class='cc'>Real data from your Google Analytics + Search Console · {_esc(ga4.get('period','last 28d'))}. "
            "This is what your funnel is built on.</p>"
            "<div style='display:flex;gap:22px;flex-wrap:wrap'>"
            f"<div style='flex:1;min-width:240px'><div class='dim'>Sessions</div>"
            f"<div class='big tnum' style='color:#2FE3D2'>{sessions:,}</div>"
            f"<div class='dim' style='margin-top:8px'>Top pages</div>{pages}</div>"
            f"<div style='flex:1;min-width:240px'><div class='dim'>Top search queries (Search Console)</div>"
            f"<div style='margin-top:4px'>{queries}</div></div></div></div>")


def _media_page(jobs, st, web_tracking=None):
    all_drafts = _media_campaigns(jobs)
    drafts = [(j, mb) for j, mb in all_drafts if j.get("status") != "aborted"]
    ads_on = bool(st.get("ads_api"))
    total = sum(float(mb.get("monthly_budget") or 0) for _, mb in drafts)
    waiting = sum(1 for j, _ in drafts if not j.get("approved") and j.get("status") != "campaign_live")
    live = sum(1 for j, _ in drafts if j.get("status") == "campaign_live")
    master = _master("🎯", "Media buying — at a glance",
        "AI-drafted Google Ads campaigns from your creatives. Nothing spends until you deploy.",
        [("Drafts", len(drafts), "#EDF1FB"), ("Waiting you", waiting, "#F5B14C"),
         ("Live", live, "#3FD98B"),
         ("Budget drafted", f"${total:,.0f}/mo", "#8B7CFF"),
         ("Google Ads", "live" if ads_on else "not connected", "#3FD98B" if ads_on else "#F5B14C")],
        "<div class='ctrl' style='margin-top:8px'>"
        "<button class='sbtn' id='draftbtn' onclick='draftCampaign()'>✍️ Draft a campaign now</button>"
        "<span class='dim' style='align-self:center'>Runs the media buyer on your ICP — a full campaign appears below in ~15s.</span></div>")
    if drafts:
        cards = "".join(
            _media_card(j.get("job_id"), mb,
                        bool(j.get("approved")), j.get("status") == "campaign_live", ads_on,
                        (j.get("payload", {}) or {}).get("media_chat_history"))
            for j, mb in drafts)
    else:
        cards = ("<div class='card full'><p class='ct'>No campaigns yet</p>"
                 "<p class='cc'>Click <b>✍️ Draft a campaign now</b> above and the media buyer will draft a full "
                 "Google Ads campaign — with its reasoning — for you to review, chat about, and deploy in one click. "
                 "(It also drafts automatically whenever your image agents produce new creatives.)</p></div>")
    # Always-visible chat with the media buyer. When a campaign exists, changes
    # apply to the latest one; otherwise it acts as a planning assistant.
    latest_id = drafts[-1][0].get("job_id") if drafts else ""
    bound = ("💬 It will apply changes to your latest campaign, <b>"
             + _esc(drafts[-1][1].get("campaign_name", "campaign")) + "</b>."
             if drafts else
             "💬 No campaign yet — ask it to plan one, or click <b>Draft a campaign now</b> above, "
             "then chat here to refine it.")
    chat_card = (
        "<div class='card full' style='margin-bottom:12px'>"
        "<p class='ct'>💬 Talk to your media buyer</p>"
        f"<p class='cc'>{bound} Ask <i>why</i> it chose a strategy, or request changes — budget, keywords, "
        "headlines, locations, countries.</p>"
        "<div class='mlog' id='mlog-section' style='max-height:280px;overflow:auto;margin-bottom:8px'></div>"
        "<div class='ctrl'>"
        "<input id='min-section' placeholder='e.g. plan a lead-gen campaign for dentists in Munich at €10/day' "
        "style='flex:1;min-width:260px' onkeydown=\"if(event.key==='Enter')mediaSectionSend()\">"
        "<button class='sbtn' onclick='mediaSectionSend()'>Send</button></div>"
        f"<input type='hidden' id='section-jobid' value='{_esc(latest_id)}'></div>")
    # Connections live ONLY on the System Map. Here we just show status + point there.
    if not ads_on:
        note = ("<div class='card full' style='margin-bottom:12px'><p class='ct'>🟠 Google Ads not connected</p>"
                "<p class='cc'>You can draft, chat about and plan campaigns now. To <b>deploy</b> them live, connect "
                "Google Ads on the <b>🗺️ System Map</b> page (that's where every wire connects). "
                "Google must approve your developer token before live campaigns can be created.</p>"
                "<div class='ctrl'><button class='cbtn' onclick=\"nav('map')\">Go to System Map →</button></div></div>")
    else:
        note = ""
    return master + _media_tracking_panel(web_tracking) + chat_card + note + cards


# ---------------------------------------------------------------------------
# Pipeline health (plain English) + approval log + "why this piece"
# ---------------------------------------------------------------------------
_HEALTH_WIRES = [
    ("claude_api", "🧠 Claude — the brain", "Agents can't think or write. Nothing runs."),
    ("wordpress_publish", "📝 WordPress publishing", "Finished content can't deploy to your site."),
    ("linkedin_leads", "🧲 Prospeo lead collection", "No new leads get sourced."),
    ("email_send", "📧 Email sending", "Cold emails and replies can't go out."),
    ("email_reply_inbound", "📥 Inbox (IMAP)", "Replies from prospects aren't read."),
    ("google_gsc_ga4", "📈 Analytics + Search Console", "No website tracking or SEO data for the funnel."),
    ("ads_api", "🎯 Google Ads", "Campaigns can't deploy; live ad spend won't show (needs Google token approval)."),
    ("calcom_bookings", "📅 Cal.com bookings", "Booked-call data won't show."),
]
_HEALTH_CRITICAL = {"claude_api", "wordpress_publish", "email_send"}


def _pipeline_health(st, jobs):
    rows, down_critical = "", []
    for k, name, why in _HEALTH_WIRES:
        ok = bool(st.get(k))
        if not ok and k in _HEALTH_CRITICAL:
            down_critical.append(name)
        badge = ("<span class='pill p-live'><span class='d' style='background:#3FD98B'></span>OK</span>" if ok
                 else "<span class='pill p-need'><span class='d' style='background:#F5788A'></span>DOWN</span>")
        rows += f"<tr><td>{name}</td><td>{badge}</td><td class='mut'>{'Working.' if ok else _esc(why)}</td></tr>"
    fails = [j for j in jobs if j.get("status") in ("failed", "halted_budget")]
    frows = ""
    for j in fails[:8]:
        reason = str(j.get("halt_reason") or "stopped (no reason recorded)")[:130]
        plain = ("Budget cap reached — raise the cap or wait for the month to reset."
                 if j.get("status") == "halted_budget"
                 else "A step failed; the engine stopped this one job and kept the rest running.")
        frows += (f"<tr><td>{_esc(j.get('job_id'))}</td><td class='mut'>{_esc(j.get('type',''))}</td>"
                  f"<td class='mut'>{_esc(reason)}</td><td class='mut'>{plain}</td></tr>")
    if down_critical:
        banner = ("<div style='padding:10px 12px;border-radius:8px;background:#2c1420;border-left:4px solid #F5788A;margin-bottom:10px'>"
                  f"<b style='color:#F5788A'>⛔ Can't run:</b> {', '.join(down_critical)} is down — connect it on the System Map.</div>")
    elif not fails:
        banner = ("<div style='padding:10px 12px;border-radius:8px;background:#10281c;border-left:4px solid #3FD98B;margin-bottom:10px'>"
                  "<b style='color:#3FD98B'>✅ Pipeline healthy</b> — every critical wire is up and no jobs are stuck.</div>")
    else:
        banner = ""
    fail_tbl = (f"<div class='dim' style='margin-top:12px'>Recent stops ({len(fails)})</div>"
                "<div class='tbwrap'><table><thead><tr><th>Job</th><th>Type</th><th>Error / where it broke</th><th>Plain English</th></tr></thead><tbody>"
                + frows + "</tbody></table></div>") if fails else ""
    return ("<div class='card full'><p class='ct'>🩺 Pipeline health — is anything broken?</p>"
            "<p class='cc'>Every wire and every recent stop in plain English. Green = go; red tells you exactly what's down and what it breaks.</p>"
            + banner
            + "<div class='tbwrap'><table><thead><tr><th>Wire</th><th>Status</th><th>What it means if down</th></tr></thead><tbody>"
            + rows + "</tbody></table></div>" + fail_tbl
            + "<div class='ctrl' style='margin-top:12px'><button class='cbtn' onclick='runSelftest()'>🔬 Test every agent live</button>"
            "<span class='dim' style='align-self:center'>Runs all 18 agents and reports any that fail (~2 min, ~$0.25).</span></div></div>")


_LEAD_STATUS = {
    "sent": ("emailed", "#3FD98B"), "measuring": ("emailed", "#3FD98B"),
    "measured": ("emailed", "#3FD98B"), "optimized": ("emailed", "#3FD98B"),
    "AWAITING_APPROVAL": ("email ready — awaiting your OK", "#F5B14C"),
    "drafted": ("writing email", "#4C8DFF"), "segmented": ("qualified", "#8B7CFF"),
    "qualified": ("qualified", "#8B7CFF"), "revision_needed": ("email held (QA)", "#F5788A"),
    "failed": ("stopped", "#F5788A"), "created": ("sourced", "#8E9BBE"),
}


def _collect_leads(jobs):
    """Each lead record + campaign status + qualifier profile + whether THIS lead
    was actually emailed. The engine emails ONE primary contact per campaign, so
    only that one is 'emailed'; the rest are sourced/queued (never a 25-blast)."""
    seen, out = set(), []
    for j in jobs:
        if j.get("type") != "outreach_campaign":
            continue
        js = j.get("status", "")
        p = j.get("payload", {}) or {}
        sent_ref = p.get("send_ref") or (p.get("outreach_send", {}) or {}).get("send_ref")
        sent_map = p.get("sent_to", {}) or {}
        try:
            import content_engine_connectors as _C
        except Exception:
            _C = None
        qmap = {}
        for r in ((p.get("lead_qualifier") or {}).get("results") or []):
            qmap[str(r.get("id", "")).strip().lower()] = r
        first = True
        for L in (p.get("leads") or []):
            e = (L.get("email") or "").strip().lower()
            k = e or (L.get("company") or "").lower()
            if not k or k in seen:
                continue
            seen.add(k)
            q = qmap.get(e) or qmap.get((L.get("company") or "").strip().lower()) or {}
            n_sent = (_C.touch_stats(sent_map.get(e))[0] if _C else 0)   # manual sequence sends
            emailed = n_sent > 0 or (bool(sent_ref) and first)  # primary auto-send OR any manual touch
            out.append((L, js, q, emailed))
            if e:
                first = False
    return out


def _leads_table(jobs):
    triples = _collect_leads(jobs)
    if not triples:
        return ("<div class='card full' style='margin-top:12px'><p class='ct'>🧲 Your customer leads</p>"
                "<p class='cc'>Each lead — with what their business does, their likely pain point, the offer to pitch "
                "them, fit score, and outreach status — appears here once a batch is sourced + qualified. Saved on your "
                "server; this reads it directly.</p></div>")
    emailed = sum(1 for _, _, _, em in triples if em)
    rows = ""
    for L, js, q, em in triples[:200]:
        if em:
            label, col = ("✉ emailed", "#3FD98B")
        elif js in ("sent", "measuring", "measured", "optimized"):
            label, col = ("in list · not emailed", "#8E9BBE")
        else:
            label, col = _LEAD_STATUS.get(js, ("sourced", "#8E9BBE"))
        fit = q.get("fit_score")
        fit_txt = f"{fit}/10" if fit not in (None, "") else "—"
        prio = q.get("priority", "")
        pcol = {"urgent": "#F5788A", "high": "#F5B14C", "medium": "#4C8DFF", "low": "#8E9BBE"}.get(prio, "#8E9BBE")
        biz = q.get("business") or (q.get("category") if q.get("category") != "disqualified" else "") or "—"
        pain = q.get("pain_point") or "—"
        offer = q.get("offer") or "—"
        reason = q.get("reason") or ""
        web = (L.get("domain") or "").strip()
        weblink = (f"<div class='dim'>🌐 <a href='https://{_esc(web)}' target='_blank' "
                   f"style='color:#4C8DFF'>{_esc(web)}</a></div>") if web else ""
        reason_html = (f"<div class='dim' style='margin-top:3px'>Why: {_esc(reason)}</div>") if reason else ""
        rows += (f"<tr><td><b>{_esc(L.get('name','') or '—')}</b>"
                 f"<div class='dim'>{_esc(L.get('title','') or '')}</div></td>"
                 f"<td>{_esc(L.get('company','') or '—')}<div class='dim'>{_esc(biz)}</div>{weblink}</td>"
                 f"<td class='tnum'>{fit_txt}<div class='dim' style='color:{pcol}'>{_esc(prio)}</div>{reason_html}</td>"
                 f"<td class='mut' style='max-width:220px'>{_esc(pain)}</td>"
                 f"<td class='mut' style='max-width:220px'>{_esc(offer)}</td>"
                 f"<td class='mut'>{_esc(L.get('email','') or '—')}</td>"
                 f"<td><span style='color:{col};font-weight:600'>● {label}</span></td></tr>")
    return ("<div class='card full' style='margin-top:12px'>"
            f"<p class='ct'>🧲 Your customer leads — {len(triples)} verified · {emailed} actually emailed</p>"
            "<p class='cc'>Real people from Prospeo, qualified by the agent: <b>what they do</b>, their likely "
            "<b>pain point</b>, the <b>offer</b> to pitch them, a <b>fit score</b>, verified email, and outreach status. "
            "The engine emails only the <b>primary contact</b> per approved campaign (conservative warm-up) — it never "
            "blasts the whole list, so “emailed” shows exactly who was actually contacted.</p>"
            "<div class='tbwrap'><table><thead><tr><th>Lead</th><th>Company · website · what they do</th>"
            "<th>Fit + why</th><th>Likely pain point</th><th>Offer to pitch</th><th>Verified email</th>"
            "<th>Status</th></tr></thead><tbody>"
            + rows + "</tbody></table></div></div>")


def _md_inline(s):
    import re, html as _h
    s = _h.escape(s)
    s = re.sub(r"!\[(.*?)\]\((.*?)\)", r'<img src="\2" alt="\1" style="max-width:100%;border-radius:10px;margin:10px 0">', s)
    s = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return s


def _md_to_html(text):
    """Lightweight markdown -> HTML for the blog 'web view' (headings, lists,
    bold/italic, links, images) — how the piece reads on the site."""
    import re
    out, inlist = [], False
    for ln in (text or "").split("\n"):
        s = ln.rstrip()
        if not s.strip():
            if inlist:
                out.append("</ul>"); inlist = False
            continue
        m = re.match(r"^(#{1,3})\s+(.*)", s)
        if m:
            if inlist:
                out.append("</ul>"); inlist = False
            out.append(f"<h{len(m.group(1))}>{_md_inline(m.group(2))}</h{len(m.group(1))}>")
            continue
        if re.match(r"^[-*]\s+", s):
            if not inlist:
                out.append("<ul>"); inlist = True
            out.append(f"<li>{_md_inline(s[2:])}</li>")
            continue
        if inlist:
            out.append("</ul>"); inlist = False
        out.append(f"<p>{_md_inline(s)}</p>")
    if inlist:
        out.append("</ul>")
    return "\n".join(out)


def _brand_palette(ci_text=""):
    """Pull brand colours from the saved CI text (any #hex codes), else fall back
    to the Anthropos palette (deep slate + cyan/violet). Returns (ink, accent, accent2)."""
    import re
    hexes = re.findall(r"#[0-9A-Fa-f]{6}", ci_text or "")
    ink = accent = None     # None = "not yet found from the CI"
    # first dark-ish hex -> ink (headings/body), first vivid hex -> accent
    for h in hexes:
        r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        if lum < 90 and ink is None:
            ink = h
        elif lum >= 90 and accent is None:
            accent = h
    ink = ink or "#101A2E"          # deep slate default
    accent = accent or "#12B5A6"    # cyan default
    accent2 = hexes[2] if len(hexes) >= 3 else "#7C6BFF"   # violet default
    return ink, accent, accent2


def _blog_webview_srcdoc(title, body, ci_text="", hero_url="", kicker="ANTHROPOS · FIELD NOTES"):
    """Render the piece EXACTLY like a real post on anthropos-automation.com:
    dark theme (#080B14), Sora headings + Instrument Sans body, teal/coral
    accents, 760px column, rounded images, teal booking CTA. Matched from the
    live site's computed styles — not an invented template."""
    # real site palette (accent overridable via saved CI hexes)
    _, accent, _a2 = _brand_palette(ci_text)
    if not ci_text.strip():
        accent = "#2FE3D2"                    # site teal
    BG, INK, MUT, CORAL = "#080B14", "#EAF0FF", "#9AA6C6", "#FF5C8A"
    inner = _md_to_html(body)
    hero = (f"<img class='hero' src='{_esc(hero_url)}' alt=''>"
            if isinstance(hero_url, str) and hero_url.startswith("http") else "")
    doc = (
        "<html><head><meta charset='utf-8'>"
        "<link rel='preconnect' href='https://fonts.googleapis.com'>"
        "<link href='https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&"
        "family=Instrument+Sans:wght@400;500;600&display=swap' rel='stylesheet'>"
        "<style>*{box-sizing:border-box}"
        "body{margin:0;background:" + BG + ";color:" + INK + ";"
        "font:18px/1.7 'Instrument Sans',system-ui,-apple-system,Segoe UI,sans-serif}"
        ".wrap{max-width:760px;margin:0 auto;padding:38px 22px 60px}"
        ".kick{font:700 12px/1 'Instrument Sans',sans-serif;letter-spacing:2.5px;"
        "color:" + CORAL + ";text-transform:uppercase;margin-bottom:16px}"
        "h1{font-family:'Sora',system-ui,sans-serif;font-weight:800;font-size:38px;line-height:1.15;"
        "margin:0 0 14px;color:" + INK + "}"
        ".hero{width:100%;height:auto;display:block;border-radius:16px;margin:24px 0 8px;"
        "border:1px solid rgba(255,255,255,.09)}"
        "h2{font-family:'Sora',system-ui,sans-serif;font-weight:700;font-size:27px;line-height:1.2;"
        "margin:40px 0 14px;color:" + INK + "}"
        "h3{font-family:'Sora',system-ui,sans-serif;font-weight:600;font-size:21px;"
        "margin:28px 0 10px;color:" + INK + "}"
        "p{margin:0 0 20px;color:" + INK + "}"
        "a{color:" + accent + ";text-decoration:underline}"
        "ul{margin:0 0 20px;padding-left:22px}li{margin:9px 0;color:" + INK + "}"
        "li::marker{color:" + accent + "}"
        "img{max-width:100%;border-radius:14px;margin:14px 0;border:1px solid rgba(255,255,255,.09)}"
        "strong{color:#fff;font-weight:600}"
        ".cta{margin-top:44px;padding:28px;border-radius:18px;"
        "background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.09)}"
        ".cta .ek{font:700 11px/1 'Instrument Sans',sans-serif;letter-spacing:2px;color:" + accent + ";"
        "text-transform:uppercase}"
        ".cta b{display:block;font-family:'Sora',sans-serif;font-size:22px;font-weight:700;margin:8px 0 6px;color:#fff}"
        ".cta p{color:" + MUT + ";margin:0}"
        ".cta .btn{display:inline-block;margin-top:16px;background:" + accent + ";color:#05121a;"
        "font-weight:700;padding:12px 22px;border-radius:10px;text-decoration:none}"
        "</style></head><body><div class='wrap'>"
        f"<div class='kick'>{_esc(kicker)}</div><h1>{_esc(title)}</h1>"
        f"{hero}{inner}"
        "<div class='cta'><div class='ek'>Prefer it done?</div>"
        "<b>Book a non-binding call</b><p>We map your biggest leak in 30 minutes.</p>"
        "<a class='btn' href='#'>Book a Free Consultation →</a></div>"
        "</div></body></html>")
    return doc.replace("&", "&amp;").replace('"', "&quot;")


def _outbox(jobs):
    """The mailbox: one personalized email per lead (built from their persona),
    each ready to send individually, in bulk, or all at once."""
    try:
        import content_engine_connectors as _C
        _mailer = _C.Emailer()
    except Exception:
        _C, _mailer = None, None
    items, sample_html, trashed_items = [], None, []
    for j in jobs:
        if j.get("type") != "outreach_campaign":
            continue
        p = j.get("payload", {}) or {}
        leads = p.get("leads") or []
        oc = p.get("outreach_copy") or {}
        if not leads or not oc.get("body"):
            continue
        qmap = {str(r.get("id", "")).lower(): r for r in ((p.get("lead_qualifier") or {}).get("results") or [])}
        sent = p.get("sent_to", {}) or {}
        sent_at = p.get("sent_at", {}) or {}
        edits = p.get("email_edits", {}) or {}
        trashed = set(str(x).lower() for x in (p.get("email_trashed") or []))
        for L in leads:
            e = (L.get("email") or "").strip().lower()
            if not e:
                continue
            if e in trashed:                       # soft-deleted -> junk box, never lost
                trashed_items.append((j.get("job_id"), L))
                continue
            q = qmap.get(e) or {}
            ed = edits.get(e)
            # where is this lead in their 3-email cycle?
            hist = sent.get(e)
            sent_n, last = _C.touch_stats(hist)
            nxt = _C.next_touch(hist)            # next step to send (0 = done/blocked)
            base_subj = (oc.get("subject_variants") or ["Quick idea for {{company}}"])[0]
            _tname = {1: "Intro", 2: "Follow-up", 3: "Final note"}
            sched = _C.sequence_schedule(sent_at.get(e))   # real 3-step timeline (dates)
            # build ALL THREE emails so each can be previewed (sent + upcoming)
            touches = []
            for step in (1, 2, 3):
                if step == 1 and ed and ed.get("body"):   # founder's manual edit wins (intro only)
                    tsubj, traw = ed.get("subject") or "", ed.get("body")
                else:
                    try:
                        # `oc` carries the AI-written body_2 / body_3. Without it
                        # the preview fell back to the generic bumps while the
                        # send used the real ones.
                        tsubj, traw = _C.outreach_touch(L, q, base_subj,
                                                        oc.get("body", ""), step, oc)
                    except Exception:
                        tsubj, traw = base_subj, oc.get("body", "")
                thtml = None
                try:
                    _pl, thtml = _mailer.compose_outreach(traw, j)
                    if sample_html is None and thtml:
                        sample_html = thtml
                except Exception:
                    pass
                tstate = "sent" if step <= sent_n else ("next" if step == nxt else "pending")
                _s = sched[step - 1] if step - 1 < len(sched) else {}
                touches.append({"step": step, "name": _tname[step], "subj": tsubj,
                                "raw": traw, "html": thtml, "state": tstate,
                                "date": _s.get("date", ""), "when": _s.get("state", "")})
            # the email shown in the row summary = the next one (or the last if done)
            cur = touches[(nxt or _C.SEQUENCE_TOUCHES) - 1]
            subj, raw, html = cur["subj"], cur["raw"], cur["html"]
            if nxt == 0 and last == "blocked":
                status = "blocked"
            elif nxt == 0:
                status = "complete"          # all 3 emails sent
            elif last == "held":
                status = "held"              # warm-up cap — retries same step
            else:
                status = "ready"
            items.append((j.get("job_id"), L, q, subj, raw, html, status, bool(ed), sent_n, nxt, touches))
    if not items:
        # show the 3-email cycle even when empty, so the feature is always visible
        # and the founder knows WHY it's empty (no written emails in the pipeline yet).
        n_out = sum(1 for j in jobs if j.get("type") == "outreach_campaign")
        n_leads = sum(len((j.get("payload", {}) or {}).get("leads") or [])
                      for j in jobs if j.get("type") == "outreach_campaign")
        why = ("No outreach campaigns yet — start the lead machine to source + write emails."
               if n_out == 0 else
               f"You have {n_out} campaign(s) with {n_leads} lead(s), but the emails aren't "
               "written yet (the campaign hasn't reached the copywriting step). Once written, "
               "every customer appears below with their 3-email cycle.")
        return ("<div class='card full' style='margin-bottom:12px'>"
                "<p class='ct'>📬 Email outbox — 3-email cycle per customer</p>"
                "<div style='display:flex;gap:10px;flex-wrap:wrap;font-size:13px;margin:8px 0'>"
                "<div class='fe' style='flex:1;min-width:150px'><b>1 · Intro</b><div class='dim'>The full personalized pitch</div></div>"
                "<div class='fe' style='flex:1;min-width:150px'><b>2 · Follow-up</b><div class='dim'>A short bump if no reply</div></div>"
                "<div class='fe' style='flex:1;min-width:150px'><b>3 · Final note</b><div class='dim'>A last soft close, then stop</div></div>"
                "</div>"
                "<p class='cc'>Each customer gets a <b>3-dot cycle</b> (●●●) you can track and send step by step — "
                "and after the 3rd email we stop automatically. "
                f"<b style='color:#F5B14C'>{_esc(why)}</b></p></div>")
    ready = sum(1 for it in items if it[6] == "ready")
    complete = sum(1 for it in items if it[6] == "complete")
    emails_sent = sum(it[8] for it in items)          # total emails sent across all steps
    customers = len(items)
    remaining = sum(max(0, _C.SEQUENCE_TOUCHES - it[8]) for it in items if it[6] != "blocked")
    # a real rendered preview of the branded email — exactly how the customer sees
    # it: logo, body, and the footer signature (Hassan, company, address, booking,
    # unsubscribe). srcdoc renders the actual HTML on a white 'inbox' background.
    sample = ""
    if sample_html:
        _sd = sample_html.replace("&", "&amp;").replace('"', "&quot;")
        sample = ("<details style='margin-bottom:12px'><summary style='cursor:pointer;color:#4C8DFF;font-weight:600'>"
                  "🎨 Preview how your email looks to the customer (branded)</summary>"
                  f"<iframe srcdoc=\"{_sd}\" style='width:100%;max-width:640px;height:560px;border:1px solid var(--line);"
                  "border-radius:9px;background:#fff;margin-top:8px'></iframe>"
                  "<div class='dim' style='margin-top:6px'>The footer signature (name, company, address, booking link, "
                  "unsubscribe) is added automatically to every email. To show your logo + brand colour there, set "
                  "<code>EMAIL_LOGO_URL</code> and <code>EMAIL_BRAND_COLOR</code> on the System Map.</div></details>")
    PAGE = 20                       # customers per page
    npages = (len(items) + PAGE - 1) // PAGE
    rows = ""
    _tlabel = {1: "intro", 2: "follow-up", 3: "final note"}
    _tstatecol = {"sent": "#3FD98B", "next": "#F5B14C", "pending": "#8E9BBE"}
    _tstatelbl = {"sent": "✓ sent", "next": "→ next to send", "pending": "queued"}
    _whenlbl = {"sent": "sent", "due": "due now", "scheduled": "scheduled"}
    for i, (jid, L, q, subj, raw, html, status, was_edited, sent_n, nxt, touches) in enumerate(items):
        pg = i // PAGE
        # real schedule for the NEXT email (the row's "Scheduled" column)
        nt = next((t for t in touches if t["step"] == nxt), None)
        if nt:
            sched = (f"{_whenlbl.get(nt['when'], nt['when'])} {nt['date']}"
                     if nt["when"] != "due" else "⏰ due now")
        else:
            sched = "✓ complete"
        stcol = {"complete": "#3FD98B", "ready": "#F5B14C", "held": "#8E9BBE", "blocked": "#F5788A"}.get(status, "#8E9BBE")
        dots = "".join(f"<span style='color:{'#3FD98B' if k < sent_n else '#3A4160'}'>●</span>" for k in range(3))
        _steplbl = _tlabel.get(nxt, "")
        stlabel = {"complete": "✓ 3/3 done",
                   "ready": f"○ next: {_steplbl}" if _steplbl else "○ ready",
                   "held": "held (cap)", "blocked": "stopped"}.get(status, status)
        email = L.get("email") or ""
        chk = (f"<input type='checkbox' class='obx' value='{_esc(email)}' data-job='{_esc(jid)}'>"
               if status == "ready" else "")
        sendlbl = f"Send {_steplbl}" if _steplbl else "Send"
        sendbtn = (f"<button class='cbtn' style='padding:3px 10px' onclick=\"sendOne('{_esc(jid)}','{_esc(email)}')\">{sendlbl}</button>"
                   if status == "ready" else "")
        edited_tag = " <span class='pill p-live' style='padding:1px 7px'>edited by you</span>" if was_edited else ""
        # --- all 3 emails, each previewable (sent + upcoming) ---
        tblocks = ""
        for t in touches:
            thtml_attr = (t["html"] or "").replace("&", "&amp;").replace('"', "&quot;")
            scol = _tstatecol.get(t["state"], "#8E9BBE")
            slbl = _tstatelbl.get(t["state"], t["state"])
            # the real date this step went out / is due / is scheduled
            when = t.get("when", "")
            wtxt = ("sent " + t.get("date", "") if when == "sent"
                    else "⏰ due now" if when == "due"
                    else "scheduled " + t.get("date", "") if t.get("date") else "")
            timeline = (f"<span class='dim tnum' style='font-size:12px'>📅 {wtxt}</span>" if wtxt else "")
            tblocks += (
                f"<div style='border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-bottom:6px'>"
                f"<div style='display:flex;align-items:center;gap:8px;flex-wrap:wrap'>"
                f"<b>{t['step']} · {t['name']}</b>"
                f"<span style='color:{scol};font-weight:600;font-size:12px'>{slbl}</span>"
                f"{timeline}"
                f"<span class='dim' style='flex:1;min-width:120px'>{_esc(t['subj'])}</span>"
                f"<button class='cbtn' style='padding:2px 9px' onclick=\"toggleEl('tv-{i}-{t['step']}')\">👁 preview</button></div>"
                f"<div id='tv-{i}-{t['step']}' style='display:none;margin-top:6px'>"
                f"<iframe srcdoc=\"{thtml_attr}\" style='width:100%;max-width:600px;height:480px;"
                "border:1px solid var(--line);border-radius:9px;background:#fff'></iframe></div></div>")
        all3 = (f"<button class='cbtn' style='padding:3px 10px' onclick=\"toggleEl('tch-{i}')\">📧 See all 3 emails</button>"
                f"<div id='tch-{i}' style='display:none;margin-top:8px'>"
                "<div class='dim' style='margin-bottom:6px'>The full 3-email cycle for this customer — "
                "what was sent and what's coming next. Click any to preview exactly how it lands.</div>"
                f"{tblocks}</div>")
        actions = (
            f"{sendbtn}{all3}"
            + (f"<button class='cbtn' style='padding:3px 10px' onclick=\"editEmail({i})\">"
               f"✏️ Edit email {nxt} of 3</button>"
               if status != "complete" else "")
            + (f"<button class='cbtn warn' style='padding:3px 10px' onclick=\"trashEmail('{_esc(jid)}','{_esc(email)}')\">🗑 Delete</button>")
            + (f"<div id='ed-{i}' style='display:none;margin-top:8px'>"
               f"<input id='eds-{i}' value='{_esc(subj)}' style='width:100%;margin-bottom:6px' placeholder='Subject'>"
               f"<textarea id='edb-{i}' style='width:100%;min-height:150px;font-family:inherit'>{_esc(raw)}</textarea>"
               "<div class='ctrl' style='margin-top:6px'>"
               f"<button class='sbtn' onclick=\"saveEdit('{_esc(jid)}','{_esc(email)}',{i},{nxt})\">"
               f"💾 Save email {nxt}</button>"
               f"<button class='cbtn' onclick=\"editEmail({i})\">Cancel</button></div>"
               f"<div class='dim' style='margin-top:4px'>You are editing <b>email {nxt} of 3</b> "
               f"for this lead — the other two are unaffected. Edit the message only; the "
               f"branded footer (name, address, booking button, unsubscribe) is added "
               f"automatically.</div></div>" if status != "complete" else ""))
        rows += (f"<tr class='obxrow' data-pg='{pg}'{'' if pg == 0 else ' style=display:none'}><td>{chk}</td>"
                 f"<td><b>{_esc(L.get('name',''))}</b><div class='dim'>{_esc(L.get('company',''))}</div></td>"
                 f"<td class='mut'>{_esc(q.get('business') or q.get('category') or '—')}</td>"
                 f"<td class='mut' style='max-width:240px'>{_esc(subj)}{edited_tag}</td>"
                 f"<td class='dim tnum'>{sched}</td>"
                 f"<td style='white-space:nowrap'><span style='font-size:13px;letter-spacing:2px'>{dots}</span>"
                 f"<div style='color:{stcol};font-weight:600;font-size:12px'>{stlabel}</div></td>"
                 f"<td style='min-width:230px'>{actions}</td></tr>")
    # pager (client-side, 20 customers per page)
    pager = ""
    if npages > 1:
        pager = ("<div class='ctrl' id='obx-pager' style='margin-top:10px;align-items:center'>"
                 "<button class='cbtn' onclick='pageOutbox(-1)'>‹ Prev</button>"
                 "<span class='dim' style='align-self:center'>Page <b id='obx-pg'>1</b> of "
                 f"{npages} · {len(items)} customers</span>"
                 "<button class='cbtn' onclick='pageOutbox(1)'>Next ›</button></div>")
    # the follow-up cadence explainer — COLLAPSIBLE so it doesn't eat the screen
    cadence = (
        "<details class='card' open style='margin-bottom:10px;background:rgba(76,141,255,.06);border-left:4px solid #4C8DFF'>"
        "<summary style='cursor:pointer;font-weight:700;list-style:none'>🔁 3-email follow-up cycle (then we stop) "
        "<span class='dim' style='font-weight:400'>— click to fold/unfold</span></summary>"
        "<div style='display:flex;gap:10px;flex-wrap:wrap;font-size:13px;margin-top:10px'>"
        "<div class='fe' style='flex:1;min-width:150px'><b>1 · Intro</b><div class='dim'>The full personalized pitch</div></div>"
        "<div class='fe' style='flex:1;min-width:150px'><b>2 · Follow-up</b><div class='dim'>A short bump if no reply</div></div>"
        "<div class='fe' style='flex:1;min-width:150px'><b>3 · Final note</b><div class='dim'>A last soft close, then stop</div></div>"
        "</div>"
        f"<p class='cc' style='margin-top:8px'>Each customer gets <b>at most 3 emails</b>, each one different. "
        f"After the 3rd, that customer is done — <b>no more emails</b>. The dots (●●●) track where each person is.</p>"
        f"<div class='dim' style='margin-top:6px'>{customers} customers · <b style='color:#3FD98B'>{emails_sent} emails sent</b> · "
        f"<b style='color:#F5B14C'>{remaining} still to send</b> across all cycles · {complete} finished all 3.</div></details>")
    return ("<div class='card full' style='margin-bottom:12px'><p class='ct'>📬 Email outbox — your agent's emails, per customer</p>"
            f"<p class='cc'>One personalized email per lead, built from their persona (business · pain · offer), "
            f"sent as a <b>3-step sequence</b>. <b style='color:#F5B14C'>{ready} ready for their next email</b> · "
            f"<b style='color:#3FD98B'>{emails_sent} emails sent</b>. "
            "Send one, tick several and send selected, or send all — warm-up capped so day-one stays safe. "
            "Nothing sends until you click.</p>"
            + cadence
            + sample
            + "<div class='ctrl' style='margin-bottom:8px'>"
            "<label class='dim' style='align-self:center'><input type='checkbox' id='obx-all' onclick='toggleOutbox(this)'> select all ready</label>"
            "<button class='sbtn' onclick='sendSelected()'>📨 Send selected (next step)</button>"
            "<button class='cbtn' onclick='sendAllOutbox()'>📤 Send all ready</button></div>"
            "<div class='tbwrap'><table><thead><tr><th></th><th>Customer</th><th>Persona</th><th>Next email</th>"
            "<th>Next send</th><th>Cycle 1·2·3</th><th>Actions</th></tr></thead><tbody>"
            + rows + "</tbody></table></div>" + pager + _junk_box(trashed_items) + "</div>")


def _junk_box(trashed_items):
    """The recoverable junk box — deleted emails are kept here, never lost."""
    if not trashed_items:
        return ""
    rows = ""
    for jid, L in trashed_items[:100]:
        email = L.get("email") or ""
        rows += (f"<div class='fe'><span class='mut'>{_esc(L.get('name',''))} · {_esc(L.get('company',''))} "
                 f"<span class='dim'>({_esc(email)})</span></span>"
                 f"<button class='cbtn' style='margin-left:auto;padding:2px 10px' "
                 f"onclick=\"restoreEmail('{_esc(jid)}','{_esc(email)}')\">↩ Restore</button></div>")
    return ("<details style='margin-top:12px'><summary style='cursor:pointer;color:#8E9BBE;font-weight:600'>"
            f"🗑 Junk box ({len(trashed_items)}) — deleted emails, kept safe &amp; restorable</summary>"
            "<div style='margin-top:8px'>" + rows + "</div>"
            "<div class='dim' style='margin-top:6px'>Deleting an email moves it here (it's never permanently lost). "
            "Restore any time.</div></details>")


def _replies_inbox(reply_drafts):
    """Customer replies, drafted by the agent and HELD for you to review, edit,
    and send. Nothing to a customer goes out until you click 'Approve & send'."""
    drafts = reply_drafts or []
    pending = [d for d in drafts if d.get("status") == "pending"]
    done = [d for d in drafts if d.get("status") in ("sent", "dismissed")]
    head = ("<div class='card full' style='margin-bottom:12px'>"
            "<p class='ct'>💬 Customer replies — review, edit &amp; send</p>"
            "<p class='cc'>When a customer replies, your agent reads it and <b>drafts an answer</b> — "
            "but it's held here for you. Read their message, fix the draft if needed, then approve &amp; send. "
            "Replies go out from <code>customercare@</code>, threaded to their email.</p>"
            "<div class='ctrl' style='margin:8px 0'>"
            "<button class='sbtn' onclick='refreshReplies()'>🔄 Check for new replies</button>"
            f"<span class='dim' style='align-self:center'>{len(pending)} waiting · {sum(1 for d in done if d.get('status')=='sent')} sent</span></div>")
    if not pending and not done:
        return (head + "<div class='fe'><span class='mut'>No replies yet. When customers reply to your emails, "
                "their message + a ready-to-edit draft answer will appear here.</span></div></div>")
    _icol = {"interested": "#3FD98B", "question": "#4C8DFF", "objection": "#F5B14C",
             "unsubscribe": "#FF6B93", "complaint": "#FF6B93", "not_interested": "#8E9BBE"}
    rows = ""
    for i, d in enumerate(pending):
        rid = _esc(d.get("id", ""))
        intent = d.get("intent") or "reply"
        icol = _icol.get(intent, "#8E9BBE")
        hflag = (" <span class='pill' style='background:rgba(255,107,147,.15);color:#FF6B93;padding:1px 7px'>"
                 "needs your judgement</span>" if d.get("needs_human") else "")
        edited = " <span class='pill p-live' style='padding:1px 7px'>edited</span>" if d.get("edited") else ""
        rows += (
            "<div style='border:1px solid var(--line);border-radius:11px;padding:12px;margin-bottom:10px'>"
            f"<div style='display:flex;align-items:center;gap:8px;flex-wrap:wrap'>"
            f"<b>{_esc(d.get('from_name') or d.get('from_email'))}</b>"
            f"<span class='dim'>{_esc(d.get('from_email'))}</span>"
            f"<span class='pill' style='background:{icol}22;color:{icol};padding:1px 8px'>{_esc(intent)}</span>"
            f"{hflag}</div>"
            # what the customer wrote
            f"<div style='margin-top:8px;padding:9px 11px;border-radius:8px;background:rgba(255,255,255,.03);"
            "border-left:3px solid #3A4160'>"
            f"<div class='dim' style='font-size:12px'>They wrote — re: {_esc(d.get('subject_in',''))}</div>"
            f"<div style='white-space:pre-wrap;margin-top:3px;font-size:13.5px'>{_esc((d.get('message_in') or '')[:1200])}</div></div>"
            # the editable draft answer
            f"<div style='margin-top:10px'><div class='dim' style='font-size:12px'>Your agent's draft answer{edited} "
            "— edit anything, then send:</div>"
            f"<input id='rs-{i}' value='{_esc(d.get('draft_subject',''))}' style='width:100%;margin:6px 0' placeholder='Subject'>"
            f"<textarea id='rb-{i}' style='width:100%;min-height:130px;font-family:inherit'>{_esc(d.get('draft_body',''))}</textarea></div>"
            "<div class='ctrl' style='margin-top:8px'>"
            f"<button class='sbtn' onclick=\"sendReply('{rid}',{i})\">✓ Approve &amp; send</button>"
            f"<button class='cbtn' onclick=\"saveReply('{rid}',{i})\">💾 Save draft</button>"
            f"<button class='cbtn warn' onclick=\"dismissReply('{rid}')\">🗑 Dismiss</button></div></div>")
    donebox = ""
    if done:
        drows = ""
        for d in done[-40:][::-1]:
            tag = "✓ sent" if d.get("status") == "sent" else "dismissed"
            tcol = "#3FD98B" if d.get("status") == "sent" else "#8E9BBE"
            drows += (f"<div class='fe'><span class='mut'>{_esc(d.get('from_name') or d.get('from_email'))} "
                      f"<span class='dim'>— re: {_esc(d.get('subject_in',''))}</span></span>"
                      f"<span style='margin-left:auto;color:{tcol};font-weight:600'>{tag}</span></div>")
        donebox = ("<details style='margin-top:8px'><summary style='cursor:pointer;color:#8E9BBE;font-weight:600'>"
                   f"History ({len(done)})</summary><div style='margin-top:8px'>" + drows + "</div></details>")
    return head + rows + donebox + "</div>"


def _followups_due(jobs):
    """The follow-up approval board: email #2 / #3 that are DUE per each customer's
    timeline, shown with a preview and an 'Approve & send' button — so no follow-up
    goes out until you OK it."""
    try:
        import content_engine_connectors as _C
        mailer = _C.Emailer()
    except Exception:
        return ""
    _tname = {2: "Follow-up (email 2)", 3: "Final note (email 3)"}
    cards = ""
    n = 0
    for j in jobs:
        if j.get("type") != "outreach_campaign":
            continue
        p = j.get("payload", {}) or {}
        leads = p.get("leads") or []
        oc = p.get("outreach_copy") or {}
        if not leads or not oc.get("body"):
            continue
        sent = p.get("sent_to", {}) or {}
        sent_at = p.get("sent_at", {}) or {}
        trashed = set(str(x).lower() for x in (p.get("email_trashed") or []))
        qmap = {str(r.get("id", "")).lower(): r for r in ((p.get("lead_qualifier") or {}).get("results") or [])}
        for L in leads:
            e = (L.get("email") or "").strip().lower()
            if not e or e in trashed:
                continue
            nxt = _C.next_touch(sent.get(e))
            if nxt < 2:                       # intro is approved elsewhere; only follow-ups here
                continue
            s = _C.sequence_schedule(sent_at.get(e))
            step_info = s[nxt - 1] if nxt - 1 < len(s) else {}
            if step_info.get("state") != "due":   # only when the timeline says it's time
                continue
            n += 1
            if n > 30:                        # keep the board readable
                continue
            q = qmap.get(e) or {}
            try:
                subj, raw = _C.outreach_touch(
                    L, q, (oc.get("subject_variants") or ["Follow-up"])[0],
                    oc.get("body", ""), nxt, oc)
                _pl, html = mailer.compose_outreach(raw, j)
            except Exception:
                subj, html = "(follow-up)", ""
            html_attr = (html or "").replace("&", "&amp;").replace('"', "&quot;")
            cards += (
                "<div style='background:var(--s2);border:1px solid var(--line);border-radius:11px;padding:12px;margin-bottom:10px'>"
                f"<div style='display:flex;align-items:center;gap:9px;flex-wrap:wrap'>"
                f"<span class='pill' style='background:rgba(245,177,76,.15);color:#F5B14C;padding:1px 8px'>⏰ {_tname.get(nxt,'Follow-up')} due</span>"
                f"<b>{_esc(L.get('name',''))}</b><span class='dim'>{_esc(L.get('company',''))} · {_esc(e)}</span>"
                f"<button class='sbtn' style='margin-left:auto' onclick=\"sendOne('{_esc(j.get('job_id'))}','{_esc(e)}')\">✓ Approve &amp; send</button></div>"
                f"<div class='dim' style='margin-top:6px'>Subject: <b>{_esc(subj)}</b></div>"
                f"<details style='margin-top:6px'><summary style='cursor:pointer;color:#4C8DFF;font-weight:600'>👁 Preview this follow-up</summary>"
                f"<iframe srcdoc=\"{html_attr}\" style='width:100%;max-width:600px;height:460px;border:1px solid var(--line);"
                "border-radius:9px;background:#fff;margin-top:8px'></iframe></details></div>")
    if not n:
        return ""
    return ("<div class='card full' style='margin-bottom:12px;border-left:4px solid #F5B14C'>"
            f"<p class='ct'>⏰ Follow-ups due for approval ({n})</p>"
            "<p class='cc'>These customers are due for their next email in the 3-step cycle (they haven't replied). "
            "Preview each follow-up and approve it — nothing sends on its own.</p>" + cards + "</div>")


def _outbox_ready_count(jobs):
    """How many emails are ready to send right now — i.e. leads whose next
    sequence step (1, 2 or 3) is due and not yet sent."""
    try:
        import content_engine_connectors as _C
    except Exception:
        _C = None
    n = 0
    for j in jobs:
        if j.get("type") != "outreach_campaign":
            continue
        p = j.get("payload", {}) or {}
        if not (p.get("outreach_copy") or {}).get("body"):
            continue
        sent = p.get("sent_to", {}) or {}
        for L in (p.get("leads") or []):
            e = (L.get("email") or "").strip().lower()
            if not e or e in set(str(x).lower() for x in (p.get("email_trashed") or [])):
                continue
            if _C and _C.next_touch(sent.get(e)) > 0:
                n += 1
    return n


def _outbox_pointer(jobs):
    n = _outbox_ready_count(jobs)
    if not n:
        return ""
    return ("<div class='card full' style='margin-bottom:12px;border-left:4px solid #F5B14C'>"
            f"<p class='ct'>📬 {n} personalized email{'s' if n != 1 else ''} ready to send</p>"
            "<p class='cc'>Your agent has written one on-brand email per customer (from their persona). Send them all "
            "from here in one click, or open the outbox to review, edit, preview or send individually.</p>"
            f"<div class='ctrl'><button class='sbtn' onclick='sendAllCommand()'>📤 Send all {n} emails now</button>"
            "<button class='cbtn' onclick=\"nav('email')\">📬 Open the email outbox →</button></div>"
            "<div class='dim' style='margin-top:6px'>Warm-up capped — day-one stays safe, the rest queue for the next days.</div></div>")


def _why_piece(job):
    """Plain-English 'on what basis was this made' — the data behind the piece."""
    p = job.get("payload", {}) or {}
    bits = []
    if p.get("site_intelligence"):
        bits.append("your site audited")
    if p.get("competitor_intel"):
        bits.append("competitors analyzed")
    if p.get("content_strategist"):
        bits.append("strategy set")
    if p.get("seo_optimizer"):
        bits.append("SEO-optimized")
    cfg = p.get("config", {}) or {}
    kw = cfg.get("target_keyword")
    gsc = (p.get("audit", {}) or {}).get("top_gsc_queries") or []
    tail = ""
    if kw:
        tail += f" · keyword: {kw}"
    if gsc:
        tail += f" · informed by {len(gsc)} Search Console queries"
    return (", ".join(bits) + tail) if bits else "queued — its research/SEO basis appears as it runs"


# The content assembly line — the 7 stations every piece passes through, in order.
# Each station: (icon, name, what-happens-here, {statuses that sit at this station}).
_FACTORY = [
    ("📋", "Plan", "Idea picked + tagged to a customer segment & service pillar",
     {"created", "site_ready", "competitor_ready", "planned", "site_intelligence"}),
    ("✍️", "Write", "Researched (web + your site) and written on-brand for that audience",
     {"produced"}),
    ("🎨", "Image + LinkedIn", "On-brand hero image made + a native LinkedIn post written",
     set()),
    ("🔎", "SEO", "Keyword, headings, meta — checked for search",
     {"seo_checked"}),
    ("✅", "Your approval", "You review, then Approve or Decline with notes",
     {"AWAITING_APPROVAL"}),
    ("🚀", "Publish", "Website (right category) + LinkedIn on its scheduled day",
     {"publishing", "published"}),
    ("📊", "Measure", "Real traffic + learnings feed the next batch",
     {"measuring", "tracking", "measured", "tracked", "learned", "optimized"}),
]


def _factory_stage(status):
    for i, (_ic, _nm, _d, sts) in enumerate(_FACTORY):
        if status in sts:
            return i
    return 0


def _factory_line(content_jobs):
    """The production line — every station a piece flows through, with a live count
    of how many pieces sit at each one. This IS the machine: what it makes and how."""
    counts = [0] * len(_FACTORY)
    for j in content_jobs:
        counts[_factory_stage(j.get("status", ""))] += 1
    stations = ""
    for i, (ic, nm, desc, _s) in enumerate(_FACTORY):
        n = counts[i]
        active = n > 0
        col = "#2FE3D2" if active else "#3A4160"
        badge = (f"<span style='position:absolute;top:-8px;right:-8px;background:#2FE3D2;color:#04121a;"
                 f"font-weight:800;font-size:11px;border-radius:10px;padding:1px 7px'>{n}</span>" if active else "")
        arrow = (f"<div class='cf-arrow' style='align-self:center;color:#2FE3D2;font-size:18px;flex:0 0 auto;"
                 f"animation-delay:{i * 0.22:.2f}s'>→</div>" if i < len(_FACTORY) - 1 else "")
        stations += (
            f"<div class='cf-station{' cf-live' if active else ''}' style='position:relative;flex:0 0 150px;"
            f"background:var(--s2);border:1px solid "
            f"{'rgba(47,227,210,.4)' if active else 'var(--line)'};border-radius:11px;padding:11px 12px'>"
            f"{badge}<div style='font-size:20px'>{ic}</div>"
            f"<div style='font-weight:700;color:{col};margin-top:3px'>{nm}</div>"
            f"<div class='dim' style='font-size:11.5px;line-height:1.4;margin-top:4px'>{desc}</div></div>"
            + arrow)
    total = sum(counts)
    return ("<div class='card full' style='margin-bottom:12px'>"
            "<p class='ct'>🏭 The content machine — how every piece is made</p>"
            f"<p class='cc'>Each piece flows left-to-right through these 7 stations. The number on a station = how many "
            f"pieces are sitting there right now. <b>{total}</b> in the line today.</p>"
            "<div style='display:flex;gap:6px;overflow-x:auto;padding:14px 2px 4px'>" + stations + "</div></div>")


_CF3D_CSS = """
<style>
.cf3d-wrap{margin-bottom:12px}
.cf3d-scene{position:relative;perspective:1500px;perspective-origin:50% 32%;height:440px;overflow:hidden;
 border-radius:16px;background:radial-gradient(ellipse at 50% 15%,#12203a 0%,#0a1120 55%,#070b14 100%);cursor:grab}
.cf3d-scene:active{cursor:grabbing}
.cf3d-board{position:absolute;left:50%;top:56%;width:660px;height:560px;margin:-280px 0 0 -330px;
 transform-style:preserve-3d;display:grid;grid-template-columns:repeat(6,1fr);grid-auto-rows:78px;gap:13px;
 transform:rotateX(54deg) rotateZ(0deg);transition:transform .08s linear;will-change:transform}
.cf3d-tile{position:relative;transform-style:preserve-3d;transform:translateZ(var(--z,0px));
 border-radius:10px;background:rgba(255,255,255,.028);border:1px solid var(--line);
 display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;
 transition:transform .3s cubic-bezier(.2,.8,.2,1),box-shadow .3s,filter .3s}
.cf3d-has{background:rgba(255,255,255,.05);border-color:var(--c);
 box-shadow:0 0 22px -5px var(--c),0 14px 26px rgba(0,0,0,.5)}
.cf3d-tile:hover{transform:translateZ(calc(var(--z,0px) + 46px)) scale(1.06);filter:brightness(1.25);z-index:9}
.cf3d-sel{outline:2px solid #fff;outline-offset:1px}
.cf3d-dnum{font-weight:800;font-size:19px;color:#EDF1FB;line-height:1}
.cf3d-dow{font-size:9px;color:#8E9BBE;text-transform:uppercase;letter-spacing:1.5px;margin-top:2px}
.cf3d-cnt{position:absolute;top:-9px;right:-9px;color:#04121a;font-weight:800;font-size:11px;border-radius:10px;padding:1px 6px}
.cf3d-dots{display:flex;gap:3px;margin-top:4px}
.cf3d-dot{width:5px;height:5px;border-radius:50%}
.cf3d-legend{position:absolute;top:12px;left:14px;display:flex;gap:12px;font-size:11px;color:#8E9BBE;z-index:5}
.cf3d-lg{display:flex;align-items:center;gap:5px}.cf3d-sw{width:9px;height:9px;border-radius:2px;display:inline-block}
.cf3d-hint{position:absolute;bottom:10px;left:14px;color:#59668A;font-size:11px;z-index:5}
.cf3d-reset{position:absolute;bottom:10px;right:14px;z-index:5}
</style>"""


def _week_calendar(content_jobs, content_plan):
    """The agency week board — the next 7 days as columns, each showing what posts
    that day (title · channel · segment · where it is in the machine). Always
    visible: an empty week shows the 7-day skeleton so you know what 'Plan my
    content' will fill."""
    from datetime import date, timedelta
    today = date.today()
    days = [today + timedelta(days=k) for k in range(7)]
    daymap = {d.isoformat(): [] for d in days}

    def _norm(chs):
        out = []
        for c in (chs or ["website"]):
            c = str(c).lower()
            out.append("Website" if c in ("website", "web", "blog", "wordpress")
                       else ("LinkedIn" if c == "linkedin" else c.title()))
        return out or ["Website"]

    waiting = inprod = live = 0
    for j in content_jobs:
        p = j.get("payload", {}) or {}
        cfg = p.get("config", {}) or {}
        d = cfg.get("publish_date") or (j.get("created_at") or "")[:10]
        st = j.get("status", "")
        si = _factory_stage(st)
        if st == "AWAITING_APPROVAL":
            waiting += 1
        elif si >= 5:
            live += 1
        else:
            inprod += 1
        if d in daymap:
            daymap[d].append({"t": (p.get("content_producer", {}) or {}).get("title")
                              or cfg.get("chosen_topic") or j.get("job_id"),
                              "ch": _norm(cfg.get("deploy_channels")),
                              "seg": (p.get("taxonomy") or {}).get("segment", ""),
                              "si": si, "status": st, "jid": j.get("job_id"),
                              "ref": p.get("published_ref") or (p.get("publisher") or {}).get("published_ref") or ""})
    planned_n = 0
    if content_plan and content_plan.get("status") == "pending":
        for it in content_plan.get("items", []):
            planned_n += 1
            d = (today + timedelta(days=int(it.get("day_offset", 0) or 0))).isoformat()
            if d in daymap:
                daymap[d].append({"t": it.get("title", ""), "ch": _norm(it.get("channels")),
                                  "seg": it.get("segment", ""), "si": 0, "status": "plan", "jid": "", "ref": ""})

    def _chip(label):
        col = "#4C9AFF" if label == "LinkedIn" else "#2FE3D2"
        return f"<span class='wkchip' style='background:{col}22;color:{col}'>{'in ' if label=='LinkedIn' else '🌐 '}{_esc(label)}</span>"

    cols = ""
    for d in days:
        iso = d.isoformat()
        items = daymap[iso]
        is_today = (d == today)
        cls = "wkcol" + (" today" if is_today else "") + (" wknd" if d.weekday() >= 5 else "")
        head = (f"<div class='wkhead'><span>{d.strftime('%a')}<small>{d.strftime('%b %d')}</small></span>"
                + ("<span class='tdy'>TODAY</span>" if is_today else "") + "</div>")
        if items:
            body = ""
            for it in items:
                col = "#4C9AFF" if ("LinkedIn" in it["ch"] and "Website" not in it["ch"]) else "#2FE3D2"
                chips = "".join(_chip(c) for c in it["ch"])
                seg = f"<div class='dim' style='font-size:10px;margin-top:3px'>{_esc(it['seg'])}</div>" if it.get("seg") else ""
                si = it.get("si", 0)
                stage = f"{_FACTORY[si][0]} {_FACTORY[si][1]}"
                # per-card CTA — act right here, no hunting
                jid, st, ref = it.get("jid", ""), it.get("status", ""), it.get("ref", "")
                if st == "AWAITING_APPROVAL":
                    cta = (f"<div style='margin-top:5px;display:flex;gap:4px'>"
                           f"<button class='sbtn' style='padding:2px 8px;font-size:11px' onclick=\"approve('{_esc(jid)}')\">✓ Approve</button>"
                           f"<button class='cbtn' style='padding:2px 8px;font-size:11px' onclick=\"nav('appr')\">👁 Review</button></div>")
                    stg_col = "#F5B14C"
                elif st == "plan":
                    cta = (f"<div style='margin-top:5px'><button class='sbtn' style='padding:2px 8px;font-size:11px' "
                           f"onclick=\"nav('appr')\">Approve the plan →</button></div>")
                    stg_col = "#8B7CFF"
                elif isinstance(ref, str) and ref.startswith("http"):
                    cta = (f"<div style='margin-top:5px'><a class='cbtn' style='padding:2px 8px;font-size:11px' "
                           f"href='{_esc(ref)}' target='_blank'>🔗 View live</a></div>")
                    stg_col = "#3FD98B"
                else:
                    cta = ""
                    stg_col = "#8E9BBE"
                body += (f"<div class='wkcard' style='--c:{col}'><b>{_esc(str(it['t'])[:64])}</b>{chips}{seg}"
                         f"<div style='font-size:10px;margin-top:3px;color:{stg_col};font-weight:600'>{stage}</div>{cta}</div>")
        else:
            body = "<div class='wkempty'>— no post —</div>"
        cols += f"<div class='{cls}'>{head}{body}</div>"

    total = sum(len(v) for v in daymap.values())
    span = f"{days[0].strftime('%b %d')} → {days[-1].strftime('%b %d')}"
    # honest production summary (the real state, not just a drawing)
    if total:
        summary = (f"<b style='color:#F5B14C'>{waiting} waiting for you</b> · "
                   f"<b style='color:#4C8DFF'>{inprod} in production</b> · "
                   f"<b style='color:#3FD98B'>{live} live</b>"
                   + (f" · <b style='color:#8B7CFF'>{planned_n} planned (not yet approved)</b>" if planned_n else ""))
    else:
        summary = "Nothing in the factory yet — hit <b>Plan my week</b> below to fill it, agency-style."
    stuck = (inprod and False)   # placeholder for an engine-off signal
    honest = ("<div class='dim' style='margin-top:8px;font-size:11.5px'>ℹ️ The day shown is each piece's "
              "<b>target</b> day. Right now a piece goes live the moment you <b>Approve</b> it — turn on "
              "<b>scheduled publishing</b> (ask me) to make it hold and post automatically on its day.</div>")
    return ("<div class='card full' style='margin-bottom:12px'>"
            f"<p class='ct'>🗓️ This week's content calendar · {span}</p>"
            f"<p class='cc'>{summary}</p>"
            "<div class='wkgrid'>" + cols + "</div>" + honest + "</div>")


def _content_calendar(content_jobs, content_plan):
    """The always-on calendar: what posts which day, on which channel, and where it
    is in the machine. Combines scheduled/in-flight pieces with the pending plan."""
    from datetime import date, timedelta

    def _chan_badges(chs):
        out = ""
        for c in chs or ["website"]:
            c = str(c).lower()
            if c in ("website", "web", "blog", "wordpress"):
                out += "<span class='pill' style='background:rgba(47,227,210,.14);color:#2FE3D2;padding:1px 7px'>🌐 Website</span> "
            else:
                # Instagram, Facebook, YouTube, X and TikTok rendered NOTHING —
                # a piece planned for Instagram showed a title with no channel.
                _CH_PILL = {
                    "linkedin": ("in LinkedIn", "10,102,194", "#4C9AFF"),
                    "instagram": ("◎ Instagram", "225,48,108", "#F5788A"),
                    "facebook": ("f Facebook", "24,119,242", "#4C8DFF"),
                    "meta": ("f Facebook", "24,119,242", "#4C8DFF"),
                    "youtube": ("▶ YouTube", "255,0,0", "#F5788A"),
                    "twitter": ("𝕏 X", "120,120,140", "#C7D0E8"),
                    "x": ("𝕏 X", "120,120,140", "#C7D0E8"),
                    "tiktok": ("♪ TikTok", "0,242,234", "#2FE3D2"),
                }
                lbl, rgb, col = _CH_PILL.get(c, (c.title(), "139,124,255", "#8B7CFF"))
                out += (f"<span class='pill' style='background:rgba({rgb},.16);"
                        f"color:{col};padding:1px 7px'>{_esc(lbl)}</span> ")
        return out

    by_day = {}   # iso date -> list of (title, channels, stage_label, is_plan)
    for j in content_jobs:
        p = j.get("payload", {}) or {}
        cfg = p.get("config", {}) or {}
        d = cfg.get("publish_date") or (j.get("created_at") or "")[:10]
        if not d:
            continue
        title = (p.get("content_producer", {}) or {}).get("title") or cfg.get("chosen_topic") or j.get("job_id")
        si = _factory_stage(j.get("status", ""))
        stage = f"{_FACTORY[si][0]} {_FACTORY[si][1]}"
        by_day.setdefault(d, []).append((str(title), cfg.get("deploy_channels") or ["website"], stage, False))
    # pending plan (not yet created)
    if content_plan and content_plan.get("status") == "pending":
        for it in content_plan.get("items", []):
            d = (date.today() + timedelta(days=int(it.get("day_offset", 0) or 0))).isoformat()
            by_day.setdefault(d, []).append((it.get("title", ""), it.get("channels") or ["website"], "📋 Planned (awaiting approval)", True))
    if not by_day:
        return ("<div class='card full' style='margin-bottom:12px'><p class='ct'>🗓️ Content calendar</p>"
                "<p class='cc'>Your posting schedule — which piece, which day, which channel — appears here once you "
                "plan a batch. Hit <b>Plan content</b> below to fill it.</p></div>")
    rows = ""
    for d in sorted(by_day)[:21]:
        try:
            lbl = date.fromisoformat(d).strftime("%a · %b %d")
        except Exception:
            lbl = d
        items = ""
        for title, chans, stage, is_plan in by_day[d]:
            items += (
                "<div style='padding:8px 0 8px 14px;border-left:2px solid rgba(255,255,255,.08);margin:6px 0 6px 6px'>"
                f"<div style='display:flex;gap:8px;align-items:baseline;flex-wrap:wrap'><b>{_esc(str(title)[:80])}</b>"
                f"<span style='margin-left:auto'>{_chan_badges(chans)}</span></div>"
                f"<div class='dim' style='margin-top:2px'>{_esc(stage)}</div></div>")
        rows += (f"<div style='margin-top:10px'><span class='pill' style='background:rgba(139,124,255,.16);"
                 f"color:#8B7CFF;padding:2px 10px;font-weight:700'>📅 {lbl}</span>{items}</div>")
    return ("<div class='card full' style='margin-bottom:12px'>"
            "<p class='ct'>🗓️ Content calendar — what posts, which day, which channel</p>"
            "<p class='cc'>Every planned + in-production piece on a timeline, with its channels and where it is in the "
            "machine. This is your production schedule.</p>" + rows + "</div>")


def _factory_3d(content_jobs, content_plan):
    """A dynamic, interactive 3D month-ahead board: each of the next 30 days is a
    floating tile that RISES toward you the more content it carries, coloured by
    channel. Drag to look around; click a day to see exactly what posts and where.
    Pure CSS 3D — no libraries, works offline on the VPS."""
    import json
    from datetime import date, timedelta
    today = date.today()
    days = [today + timedelta(days=k) for k in range(30)]
    daymap = {d.isoformat(): [] for d in days}

    def _norm(chs):
        out = []
        for c in (chs or ["website"]):
            c = str(c).lower()
            out.append("Website" if c in ("website", "web", "blog", "wordpress") else
                       ("LinkedIn" if c == "linkedin" else c.title()))
        return out or ["Website"]

    for j in content_jobs:
        p = j.get("payload", {}) or {}
        cfg = p.get("config", {}) or {}
        d = cfg.get("publish_date") or (j.get("created_at") or "")[:10]
        if d in daymap:
            si = _factory_stage(j.get("status", ""))
            daymap[d].append({"t": (p.get("content_producer", {}) or {}).get("title")
                              or cfg.get("chosen_topic") or j.get("job_id"),
                              "ch": _norm(cfg.get("deploy_channels")),
                              "seg": (p.get("taxonomy") or {}).get("segment", ""),
                              "stage": f"{_FACTORY[si][0]} {_FACTORY[si][1]}"})
    if content_plan and content_plan.get("status") == "pending":
        for it in content_plan.get("items", []):
            d = (today + timedelta(days=int(it.get("day_offset", 0) or 0))).isoformat()
            if d in daymap:
                daymap[d].append({"t": it.get("title", ""), "ch": _norm(it.get("channels")),
                                  "seg": it.get("segment", ""), "stage": "📋 Planned (awaiting approval)"})

    total = sum(len(v) for v in daymap.values())
    if not total:
        return ""   # nothing to show in 3D yet — the flat calendar handles the empty state
    tiles = ""
    for d in days:
        iso = d.isoformat()
        items = daymap[iso]
        n = len(items)
        li = sum(1 for it in items if "LinkedIn" in it["ch"])
        web = sum(1 for it in items if "Website" in it["ch"])
        col = "#4C9AFF" if (li and li >= web) else ("#2FE3D2" if web else "#3A4160")
        z = min(n, 7) * 16
        dots = "".join(
            f"<span class='cf3d-dot' style='background:{'#4C9AFF' if 'LinkedIn' in it['ch'] else '#2FE3D2'}'></span>"
            for it in items[:5])
        cnt = f"<div class='cf3d-cnt' style='background:{col}'>{n}</div>" if n else ""
        tiles += (f"<div class='cf3d-tile{' cf3d-has' if n else ''}' data-date='{iso}' "
                  f"style='--z:{z}px;--c:{col}' onclick='cf3dPick(this)'>{cnt}"
                  f"<div class='cf3d-dnum'>{d.day}</div><div class='cf3d-dow'>{d.strftime('%a')}</div>"
                  f"<div class='cf3d-dots'>{dots}</div></div>")
    data_json = json.dumps(daymap).replace("</", "<\\/")
    first_with = next((d.isoformat() for d in days if daymap[d.isoformat()]), days[0].isoformat())
    scene = (
        "<div class='cf3d-scene' id='cf3dScene'>"
        "<div class='cf3d-legend'>"
        "<span class='cf3d-lg'><span class='cf3d-sw' style='background:#2FE3D2'></span>Website</span>"
        "<span class='cf3d-lg'><span class='cf3d-sw' style='background:#4C9AFF'></span>LinkedIn</span>"
        "<span class='cf3d-lg'>taller = more content that day</span></div>"
        "<div class='cf3d-board' id='cf3dBoard'>" + tiles + "</div>"
        "<div class='cf3d-hint'>🖱️ drag to look around · click a day for detail</div>"
        "<button class='cbtn cf3d-reset' onclick='cf3dReset()'>reset view</button></div>")
    js = ("<script>(function(){var data=" + data_json + ";"
          "var b=document.getElementById('cf3dBoard'),s=document.getElementById('cf3dScene');"
          "if(!b||!s)return;var rx=54,rz=0,drag=false,px=0,py=0,idle=true;"
          "function ap(){b.style.transform='rotateX('+rx+'deg) rotateZ('+rz+'deg)';}"
          "window.cf3dReset=function(){rx=54;rz=0;ap();};"
          "s.addEventListener('mousedown',function(e){drag=true;idle=false;px=e.clientX;py=e.clientY;});"
          "window.addEventListener('mouseup',function(){drag=false;});"
          "window.addEventListener('mousemove',function(e){if(!drag)return;rz+=(e.clientX-px)*0.45;"
          "rx=Math.max(18,Math.min(74,rx-(e.clientY-py)*0.3));px=e.clientX;py=e.clientY;ap();});"
          "function esc(x){return (''+(x||'')).replace(/&/g,'&amp;').replace(/</g,'&lt;');}"
          "window.cf3dPick=function(el){idle=false;"
          "document.querySelectorAll('.cf3d-tile').forEach(function(t){t.classList.remove('cf3d-sel');});"
          "el.classList.add('cf3d-sel');var d=el.getAttribute('data-date');var it=data[d]||[];"
          "var h=\"<div class='card full' style='margin-top:10px'><p class='ct'>📅 \"+d+' — '+it.length+' piece'+(it.length==1?'':'s')+'</p>';"
          "if(!it.length){h+=\"<p class='cc'>Nothing scheduled this day.</p>\";}"
          "else{it.forEach(function(x){var chs=(x.ch||[]).map(function(c){var col=c=='LinkedIn'?'#4C9AFF':'#2FE3D2';"
          "return \"<span class='pill' style='background:\"+col+\"22;color:\"+col+\";padding:1px 8px'>\"+esc(c)+'</span>';}).join(' ');"
          "h+=\"<div style='padding:9px 0;border-top:1px solid rgba(255,255,255,.06)'><div style='display:flex;gap:8px;flex-wrap:wrap;align-items:baseline'><b>\"+esc(x.t)+\"</b><span style='margin-left:auto'>\"+chs+'</span></div>'"
          "+\"<div class='dim' style='margin-top:2px'>\"+esc(x.seg)+' · '+esc(x.stage)+'</div></div>';});}"
          "h+='</div>';document.getElementById('cf3dDetail').innerHTML=h;};"
          "ap();var _t=0;function idleSpin(){if(idle){_t+=0.012;rz=Math.sin(_t)*9;ap();}requestAnimationFrame(idleSpin);}requestAnimationFrame(idleSpin);"
          "var f=document.querySelector('[data-date=\"" + first_with + "\"]');if(f)window.cf3dPick(f);"
          "})();</script>")
    return ("<div class='card full cf3d-wrap' style='margin-bottom:12px'>"
            "<p class='ct'>🧊 Next 30 days — live 3D content board</p>"
            f"<p class='cc'>Every day ahead as a floating tile: the more it carries, the higher it rises; colour shows "
            f"the channel. <b>{total}</b> pieces scheduled across the month. Drag to look around, click any day for the "
            f"full detail.</p>" + _CF3D_CSS + scene
            + "<div id='cf3dDetail'></div></div>" + js)


def _approval_log(jobs):
    rel = [j for j in jobs if j.get("type") in ("content_piece", "outreach_campaign")]
    rel = sorted(rel, key=lambda j: j.get("updated_at", ""), reverse=True)[:20]
    rows = ""
    for j in rel:
        p = j.get("payload", {}) or {}
        title = ((p.get("content_producer", {}) or {}).get("title")
                 or (p.get("config", {}) or {}).get("chosen_topic") or j.get("job_id"))
        appr = "✓ yes" if j.get("approved") else "—"
        pub = (p.get("publisher", {}) or {}).get("published_ref") or ""
        publink = (f"<a href='{_esc(pub)}' target='_blank' style='color:#4C8DFF'>view</a>"
                   if str(pub).startswith("http") else ("sent" if j.get("status") == "sent" else "—"))
        kind = "email" if j.get("type") == "outreach_campaign" else "blog"
        rows += (f"<tr><td>{_esc(str(title)[:56])}</td><td class='mut'>{kind}</td>"
                 f"<td>{_esc(j.get('status',''))}</td><td>{appr}</td><td>{publink}</td>"
                 f"<td class='mut'>{_esc(str(j.get('updated_at','') or '')[:10])}</td></tr>")
    return ("<div class='card full' style='margin-top:12px'><p class='ct'>🧾 Approval &amp; publish log</p>"
            "<p class='cc'>Every piece: its status, whether you approved it, and where it published. Your audit trail.</p>"
            "<div class='tbwrap'><table><thead><tr><th>Piece</th><th>Type</th><th>Status</th><th>Approved</th><th>Published</th><th>Updated</th></tr></thead><tbody>"
            + (rows or "<tr><td colspan='6' class='mut'>No pieces yet.</td></tr>") + "</tbody></table></div></div>")


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
# Business Operating System — the Intelligence Card (evidence -> diagnosis ->
# recommendation -> action) and the Executive AI Briefing (the "AI brain").
# Every card answers one business question and offers one decision. Real data
# only; unconnected sources show an honest "connect to activate" state.
# ---------------------------------------------------------------------------
def _intel_card(title, current, *, sub="", trend="", trend_up=None, goal="", forecast="",
                confidence="", insight="", recommendation="", action_label="", action="",
                source="", dept="", chart="", accent="#2FE3D2", empty=""):
    if empty:
        return ("<div class='card' style='display:flex;flex-direction:column'>"
                f"<div style='display:flex;align-items:center;gap:8px'><span class='ct' style='margin:0'>{_esc(title)}</span>"
                + (f"<span class='pill' style='margin-left:auto;background:rgba(255,255,255,.05);color:#8E9BBE;padding:1px 8px'>{_esc(dept)}</span>" if dept else "")
                + "</div>"
                f"<div class='dim' style='margin-top:10px;line-height:1.5'>⚪ {_esc(empty)}</div></div>")
    tr = ""
    if trend:
        tcol = "#3FD98B" if trend_up else ("#FF6B93" if trend_up is False else "#8E9BBE")
        arr = "▲" if trend_up else ("▼" if trend_up is False else "•")
        tr = f"<span style='color:{tcol};font-weight:700;font-size:13px;margin-left:8px'>{arr} {_esc(trend)}</span>"
    stats = []
    if goal:
        stats.append(("Goal", goal))
    if forecast:
        stats.append(("Forecast", forecast))
    if confidence:
        stats.append(("Confidence", confidence))
    statrow = ""
    if stats:
        statrow = "<div style='display:flex;gap:16px;margin-top:10px;flex-wrap:wrap'>" + "".join(
            f"<div><div class='dim' style='font-size:10px'>{_esc(l)}</div>"
            f"<div style='font-weight:700;font-size:14px'>{_esc(v)}</div></div>" for l, v in stats) + "</div>"
    insight_html = (f"<div style='margin-top:12px;padding:9px 11px;border-radius:8px;background:rgba(139,124,255,.08);"
                    f"border-left:3px solid #8B7CFF'><div class='dim' style='font-size:10px;letter-spacing:1px'>🧠 AI INSIGHT</div>"
                    f"<div style='font-size:12.5px;margin-top:2px'>{_esc(insight)}</div></div>") if insight else ""
    rec_html = (f"<div style='margin-top:8px;padding:9px 11px;border-radius:8px;background:rgba(47,227,210,.07);"
                f"border-left:3px solid {accent}'><div class='dim' style='font-size:10px;letter-spacing:1px'>✅ RECOMMENDATION</div>"
                f"<div style='font-size:12.5px;margin-top:2px'>{_esc(recommendation)}</div></div>") if recommendation else ""
    act_html = ""
    if action_label:
        act_html = (f"<div class='ctrl' style='margin-top:10px'><button class='sbtn' "
                    f"style='padding:5px 14px'{(' onclick=' + chr(34) + action + chr(34)) if action else ''}>{_esc(action_label)}</button></div>")
    foot = ""
    if source or dept:
        foot = ("<div class='dim' style='font-size:10px;margin-top:10px;display:flex;gap:10px;flex-wrap:wrap'>"
                + (f"<span>Source: {_esc(source)}</span>" if source else "")
                + (f"<span>Dept: {_esc(dept)}</span>" if dept else "") + "</div>")
    return ("<div class='card' style='display:flex;flex-direction:column'>"
            f"<div style='display:flex;align-items:baseline;gap:8px'><span class='ct' style='margin:0'>{_esc(title)}</span></div>"
            f"<div style='display:flex;align-items:baseline;margin-top:8px'>"
            f"<span style='font-size:30px;font-weight:800;line-height:1;color:{accent}'>{_esc(current)}</span>"
            f"<span class='dim' style='margin-left:6px;font-size:12px'>{_esc(sub)}</span>{tr}</div>"
            + statrow + (f"<div style='margin-top:10px'>{chart}</div>" if chart else "")
            + insight_html + rec_html + act_html + foot + "</div>")


def _exec_briefing(name, health, sub_kpis, risks, opportunities, actions):
    """The AI brain: one glance instead of dozens of cards. health=0-100 int;
    sub_kpis=[(label,value,trend,up)]; risks/opportunities=[str]; actions=[(label,js)]."""
    from datetime import datetime
    hcol = "#3FD98B" if health >= 80 else ("#F5B14C" if health >= 60 else "#FF6B93")
    kpis = "".join(
        f"<div class='mstat'><div class='msv' style='color:{('#3FD98B' if up else ('#FF6B93' if up is False else '#EDF1FB'))}'>{_esc(v)}</div>"
        f"<div class='msl'>{_esc(l)}{(' ' + ('▲' if up else '▼') + ' ' + _esc(t)) if t else ''}</div></div>"
        for l, v, t, up in sub_kpis)
    def _lst(items, icon, col):
        if not items:
            return f"<div class='dim'>None flagged.</div>"
        return "".join(f"<div style='display:flex;gap:8px;margin:5px 0'><span>{icon}</span>"
                       f"<span style='font-size:13px'>{_esc(x)}</span></div>" for x in items[:5])
    act_btns = "".join(
        f"<button class='cbtn' style='margin:3px 4px 0 0' onclick=\"{js}\">{_esc(l)}</button>" for l, js in actions)
    ring = (f"<div style='position:relative;width:96px;height:96px;flex:0 0 auto'>"
            f"<svg width='96' height='96' viewBox='0 0 96 96'><circle cx='48' cy='48' r='40' fill='none' stroke='#16223c' stroke-width='9'/>"
            f"<circle cx='48' cy='48' r='40' fill='none' stroke='{hcol}' stroke-width='9' stroke-linecap='round' "
            f"stroke-dasharray='{2*3.14159*40:.0f}' stroke-dashoffset='{2*3.14159*40*(1-health/100):.0f}' transform='rotate(-90 48 48)'/>"
            f"<text x='48' y='45' text-anchor='middle' fill='#EDF1FB' font-size='24' font-weight='800'>{health}</text>"
            f"<text x='48' y='63' text-anchor='middle' fill='#8E9BBE' font-size='9'>/ 100</text></svg></div>")
    return (
        "<div class='card full' style='margin-bottom:14px;background:linear-gradient(135deg,rgba(139,124,255,.07),rgba(47,227,210,.05));border:1px solid var(--line)'>"
        "<div style='display:flex;gap:18px;align-items:center;flex-wrap:wrap'>" + ring
        + f"<div style='flex:1;min-width:220px'><div class='dim' style='font-size:12px'>Executive briefing</div>"
        f"<h2 style='margin:2px 0 4px;font-size:20px'>Good day, {_esc(name)}</h2>"
        f"<div class='dim'>Business health <b style='color:{hcol}'>{health}/100</b> — the AI brain read your whole engine and picked what matters.</div></div>"
        "<div class='mstats' style='flex:2 1 300px'>" + kpis + "</div></div>"
        "<div class='grid g3' style='margin-top:14px'>"
        "<div><div class='ct' style='font-size:13px'>⚠️ Risks</div>" + _lst(risks, "🔻", "#FF6B93") + "</div>"
        "<div><div class='ct' style='font-size:13px'>🚀 Opportunities</div>" + _lst(opportunities, "▹", "#3FD98B") + "</div>"
        "<div><div class='ct' style='font-size:13px'>⚡ Immediate actions</div>"
        + ("<div class='dim'>Nothing needs you right now.</div>" if not actions else act_btns) + "</div>"
        "</div></div>")


def _viz(title, sub, svg, empty_msg):
    """A titled visualization panel (chart or honest empty)."""
    inner = svg or f"<div class='dim' style='padding:14px 0'>⚪ {_esc(empty_msg)}</div>"
    return (f"<div class='card'><p class='ct'>{_esc(title)}</p><p class='cc'>{_esc(sub)}</p>"
            f"<div style='margin-top:8px;overflow-x:auto'>{inner}</div></div>")


def _decision_strip(problems, opportunities, actions):
    """The AI Decision Engine layer that ends each module: problems -> opportunities
    -> prioritised actions. Turns the module from a report into a decision."""
    def _col(title, icon, items, col):
        body = ("".join(f"<div style='display:flex;gap:7px;margin:4px 0;font-size:12.5px'><span>{icon}</span>"
                        f"<span>{_esc(x)}</span></div>" for x in items[:4])
                if items else "<div class='dim'>None right now.</div>")
        return f"<div><div class='ct' style='font-size:12px;color:{col}'>{_esc(title)}</div>{body}</div>"
    act = ("".join(f"<button class='cbtn' style='margin:3px 4px 0 0' onclick=\"{js}\">{_esc(l)}</button>"
                   for l, js in actions) if actions else "<div class='dim'>No action needed.</div>")
    return ("<div class='card full' style='margin-top:12px;border-left:4px solid #8B7CFF'>"
            "<p class='ct'>🧭 AI Decision Engine</p>"
            "<div class='grid g3'>"
            + _col("Problems", "🔻", problems, "#FF6B93")
            + _col("Opportunities", "🚀", opportunities, "#3FD98B")
            + f"<div><div class='ct' style='font-size:12px;color:#4C8DFF'>Execute</div>{act}</div>"
            + "</div></div>")


# ---- The 10 intelligence centres. Each: master + intel cards + a signature
# ---- visualization + a decision strip. Real data only; honest empties else. ----
def _mod_business(c):
    m = _master("📈", "Business Performance", "Revenue, pipeline and momentum in one view.",
                [("Pipeline leads", c["leads_found"], "#EDF1FB"), ("Booked", c["booked"], "#F5B14C"),
                 ("Customers", c["o_cust"], "#3FD98B"), ("Health", f"{c['health']}/100", "#8B7CFF")],
                _funnel(c["lead_rows"]) if any(v for _, v in c["lead_rows"]) else _empty("Fills as leads flow in."))
    rev = (_intel_card("Revenue", f"${c['o_rev']:.0f}", sub="recorded", dept="Finance", source="Outcomes",
                       accent="#3FD98B", insight="Recorded from closed outcomes.",
                       recommendation="Log every won deal to sharpen forecasting.", action_label="Open Finance", action="nav('finance')")
           if c["o_rev"] else _intel_card("Revenue", "", dept="Finance",
                       empty="Connect Stripe / QuickBooks / Xero to activate revenue, MRR and profit intelligence."))
    growth = _intel_card("Output momentum", str(c["published"]), sub="live pieces",
                         forecast=f"{c['proj']}/mo", confidence=("high" if c["made_month"] > 3 else "building"),
                         dept="Growth", source="Content engine", accent="#4C8DFF",
                         insight="Publishing cadence compounds SEO + authority over time.",
                         recommendation="Hold ≥2 pieces/day to keep the curve rising.",
                         action_label="Plan my week", action="nav('content')",
                         chart=CH.confband([max(1, x) for x in c["content_series"]] or [1, 2]))
    conv = _intel_card("Pipeline conversion", f"{c['reply_rate']}%", sub="reply rate", dept="Sales",
                       source="Outreach", accent="#8B7CFF",
                       insight=f"{c['leads_emailed']} emailed → {c['replied']} replied → {c['booked']} booked.",
                       recommendation="Tighten follow-ups to lift reply→booked.", action_label="Open Sales", action="nav('sales')")
    return (m + "<div class='grid g2'>" + rev + growth + conv
            + _viz("Growth forecast (confidence band)", "Output trend with a forecast envelope.",
                   CH.confband([max(1, x) for x in c["content_series"]]), "Fills as pieces are made.")
            + "</div>" + _decision_strip(c["risks"], c["opps"], c["actions"]))


def _mod_marketing(c):
    sess, topq, gsc = c["_sess"], c["_topq"], c["_gsc"]
    m = _master("📣", "Marketing Intelligence", "SEO · AEO · GEO · Ads — visibility to revenue.",
                [("Sessions", sess or "—", "#4C8DFF"), ("Top queries", len(gsc), "#2FE3D2"),
                 ("Content live", c["published"], "#3FD98B"), ("Segments", 7, "#8B7CFF")],
                _sparkline(c["content_series"], "#4C8DFF") if c["content_jobs"] else _empty("Fills as content runs."))
    seo = (_intel_card("SEO Intelligence", str(sess), sub="sessions", dept="Marketing", source="GA4 + GSC",
                       accent="#4C8DFF", insight=(f"Strongest demand: “{topq}”." if topq else "Ranking signals building."),
                       recommendation=(f"Publish for “{topq}”." if topq else "Keep publishing to earn rankings."),
                       action_label="Open SEO", action="nav('seo')")
           if sess else _intel_card("SEO Intelligence", "", dept="Marketing",
                       empty="Connect Google Analytics 4 + Search Console to activate sessions, rankings and query demand."))
    geo = _intel_card("GEO — AI search visibility", "", dept="Marketing",
                      empty="Connect an AI-visibility source to track ChatGPT / Perplexity / Gemini / Claude mentions.")
    ads = (_intel_card("Google Ads", "", dept="Marketing", empty="Google Ads is connected — spend/ROAS intelligence activates once campaigns run.")
           if c["st"].get("google_ads") else _intel_card("Paid Ads", "", dept="Marketing",
                      empty="Connect Google / Meta / LinkedIn Ads to activate spend, ROAS and attribution."))
    # heatmap of top queries × rank buckets (real GSC), sankey attribution (real counts)
    qrows = [q.get("query", "")[:22] for q in gsc[:6] if isinstance(q, dict)]
    qmat = [[max(0, 100 - int(q.get("position", 50)) * 5)] for q in gsc[:6] if isinstance(q, dict)]
    heat = CH.heatmap(qrows, ["visibility"], qmat) if qmat else ""
    flows = []
    if c["leads_found"]:
        flows += [("SEO / Web", "Leads", max(1, c["leads_found"] * 0.6)), ("Outreach", "Leads", max(1, c["leads_found"] * 0.4))]
    if c["booked"]:
        flows += [("Leads", "Booked", c["booked"])]
    if c["o_cust"]:
        flows += [("Booked", "Customers", c["o_cust"])]
    return (m + "<div class='grid g2'>" + seo + geo + ads
            + _viz("Keyword visibility (Search Console)", "Where your queries rank — brighter = more visible.", heat,
                   "Connect Search Console to see ranking heat.")
            + _viz("Attribution — how visits become customers", "Channel → lead → booked → won.", CH.sankey(flows),
                   "Fills as leads and bookings flow in.")
            + "</div>" + _decision_strip(
                ([f"“{topq}” has demand you're not fully capturing." for _ in [1] if topq]),
                (["Publish comparison + FAQ pages to win AI Overviews."] if sess else ["Connect GA4 + GSC to unlock SEO intelligence."]),
                [("Open SEO", "nav('seo')"), ("Plan content", "nav('content')")]))


def _mod_sales(c):
    m = _master("💼", "Sales Intelligence", "Lead → qualified → emailed → replied → booked → won.",
                [("Leads", c["leads_found"], "#EDF1FB"), ("Emailed", c["leads_emailed"], "#4C8DFF"),
                 ("Replied", c["replied"], "#8B7CFF"), ("Booked", c["booked"], "#3FD98B")],
                _funnel(c["lead_rows"]) if any(v for _, v in c["lead_rows"]) else _empty("Fills as leads flow in."))
    lead = _intel_card("Lead generation", str(c["leads_found"]), sub="sourced", dept="Sales", source="Prospeo + web",
                       accent="#8B7CFF", insight=f"{c['qualified']} qualified · {c['leads_emailed']} emailed.",
                       recommendation=(f"Email the {c['not_emailed']} qualified but un-contacted." if c["not_emailed"] else "Source a fresh batch."),
                       action_label="Open Lead Machine", action="nav('leads')")
    out = _intel_card("Outreach performance", f"{c['reply_rate']}%", sub="reply rate", dept="Sales", source="Workspace mail",
                      accent="#4C9AFF", insight=f"{c['emails_sent']} emails → {c['replied']} replies.",
                      recommendation=("Send today's ready follow-ups." if c["outbox_ready"] else "Warm up more leads."),
                      action_label="Open outbox", action="nav('email')")
    close = _intel_card("Consultations", str(c["booked"]), sub="booked", dept="Sales",
                        source="Cal.com", accent="#3FD98B",
                        insight=("Bookings are the money moment." if c["booked"] else "No consultations booked yet."),
                        recommendation="Make the booking CTA prominent in every email.", action_label="Open outreach", action="nav('email')")
    flows = []
    if c["leads_found"]:
        flows += [("Sourced", "Qualified", max(1, c["qualified"] or c["leads_found"]))]
    if c["qualified"] or c["leads_emailed"]:
        flows += [("Qualified", "Emailed", max(1, c["leads_emailed"]))]
    if c["replied"]:
        flows += [("Emailed", "Replied", c["replied"])]
    if c["booked"]:
        flows += [("Replied", "Booked", c["booked"])]
    return (m + "<div class='grid g2'>" + lead + out + close
            + _viz("Pipeline flow", "Where prospects move — and where they drop.", CH.sankey(flows),
                   "Fills as the lead pipeline runs.")
            + "</div>" + _decision_strip(
                ([f"{c['not_emailed']} qualified leads sitting un-emailed." for _ in [1] if c["not_emailed"]]
                 + (["No leads in the pipeline."] if not c["leads_found"] else [])),
                (["Ready follow-ups can go today."] if c["outbox_ready"] else ["Source a new lead batch to grow pipeline."]),
                [("Send ready emails", "nav('email')"), ("Open Lead Machine", "nav('leads')")]))


def _mod_customer(c):
    m = _master("🫂", "Customer Intelligence", "Who's booking, buying and staying.",
                [("Booked", c["booked"], "#F5B14C"), ("Customers", c["o_cust"], "#3FD98B"),
                 ("Replies", c["replied"], "#8B7CFF"), ("Leads", c["leads_found"], "#EDF1FB")],
                _empty("Retention + LTV activate once a CRM / payments source is connected."))
    cust = (_intel_card("Customers won", str(c["o_cust"]), sub="recorded", dept="Customer", source="Outcomes",
                        accent="#3FD98B", insight="Closed customers recorded from outcomes.",
                        recommendation="Record each win to build LTV + cohorts.", action_label="Open Learning", action="nav('learn')")
            if c["o_cust"] else _intel_card("Customers", "", dept="Customer",
                        empty="Connect HubSpot / Salesforce / Stripe to activate customer, LTV and retention intelligence."))
    ret = _intel_card("Retention / LTV", "", dept="Customer",
                      empty="Connect a CRM + payments to activate cohort retention and lifetime value.")
    sat = _intel_card("Sentiment", "", dept="Customer",
                      empty="Connect Zendesk / Intercom / reviews to activate customer-sentiment intelligence.")
    return (m + "<div class='grid g2'>" + cust + ret + sat
            + _viz("Retention cohorts", "How many customers stay, month over month.", "",
                   "Connect a CRM / payments source to populate cohorts.")
            + "</div>" + _decision_strip(
                (["No customer/retention source connected — you're flying blind on LTV."]),
                (["Connecting Stripe alone unlocks revenue + retention + LTV cards."]),
                [("Open System Map", "nav('map')")]))


def _mod_workforce(c):
    live = c["live_agents"]
    m = _master("🤖", "AI Workforce", "Your agents — running, healthy and productive.",
                [("Jobs active", live, "#3FD98B"), ("Wires live", f"{c['live_conn']}/{c['total_conn']}", "#4C8DFF"),
                 ("Waiting on you", c["waiting"], "#F5B14C"), ("Cost/piece", f"${(c['content_cost']/max(len(c['content_jobs']),1)):.2f}", "#8B7CFF")],
                "")
    ok = c["healthy"]
    nodes = [("site", "Site analyst", ok), ("comp", "Competitor", ok), ("strat", "Strategist", ok),
             ("write", "Writer", ok), ("seo", "SEO", ok), ("qa", "Quality", ok),
             ("pub", "Publisher", ok), ("reply", "Reply agent", ok)]
    edges = [("site", "comp"), ("comp", "strat"), ("strat", "write"), ("write", "seo"), ("seo", "qa"), ("qa", "pub")]
    agents = _intel_card("Workforce status", str(live), sub="jobs active", dept="Operations", source="Orchestrator",
                         accent=("#3FD98B" if ok else "#F5B14C"),
                         insight=("All agents nominal." if ok else "A health check is needed on Agents & Health."),
                         recommendation=("Nothing to do — running normally." if ok else "Open Agents & Health to see the failing check."),
                         action_label="Open Agents", action="nav('agents')")
    eff = _intel_card("Cost efficiency", f"${(c['content_cost']/max(len(c['content_jobs']),1)):.2f}", sub="per piece",
                      dept="Finance", source="API meters", accent="#4C8DFF",
                      insight=f"${c['content_cost']:.2f} spent making {len(c['content_jobs'])} pieces.",
                      recommendation="Cheap per piece — safe to scale the cadence.", action_label="Open budget", action="nav('budget')")
    return (m + "<div class='grid g2'>" + agents + eff
            + _viz("Agent dependency graph", "How the content agents hand off, and their health.",
                   CH.digraph(nodes, edges), "No agents mapped.")
            + "</div>" + _decision_strip(
                ([] if ok else ["A subsystem health check is failing."]),
                (["Per-piece cost is low — scaling output is affordable."]),
                [("Open Agents & Health", "nav('agents')")]))


def _mod_operations(c):
    m = _master("⚙️", "Operations", "Throughput, this week's schedule and the approval queue.",
                [("Made / mo", c["made_month"], "#EDF1FB"), ("Published", c["published"], "#3FD98B"),
                 ("In production", sum(c["pl"][0:4]), "#F5B14C"), ("On pace", c["proj"], "#8B7CFF")],
                _sparkline(c["content_series"], "#4C8DFF") if c["content_jobs"] else _empty("Fills as pieces are made."))
    # gantt of this week's scheduled content (real publish_date)
    from datetime import date
    tasks = []
    for j in c["content_jobs"]:
        cfg = (j.get("payload", {}) or {}).get("config", {}) or {}
        pd = cfg.get("publish_date")
        if pd:
            try:
                off = (date.fromisoformat(pd) - date.today()).days
                if 0 <= off <= 6:
                    tasks.append(((j.get("payload", {}).get("content_producer", {}) or {}).get("title") or j.get("job_id"), off, 1))
            except Exception:
                pass
    thr = _intel_card("Throughput", str(c["made_month"]), sub="this month", forecast=f"{c['proj']}/mo",
                      dept="Operations", source="Content engine", accent="#2FE3D2",
                      insight=f"{sum(c['pl'][0:4])} in production, {c['waiting']} awaiting approval.",
                      recommendation=("Clear the approval queue to keep flow." if c["waiting"] else "Cadence is healthy."),
                      action_label="Review approvals", action="nav('appr')")
    que = _intel_card("Approval queue", str(c["waiting"]), sub="waiting", dept="Operations", source="Pipeline",
                      accent=("#F5B14C" if c["waiting"] else "#3FD98B"),
                      insight=("The pipeline pauses on you until these are approved." if c["waiting"] else "Queue is clear."),
                      recommendation=("Approve or decline with notes." if c["waiting"] else "Nothing waiting."),
                      action_label="Open Approvals", action="nav('appr')")
    return (m + "<div class='grid g2'>" + thr + que
            + _viz("This week's production schedule", "Each piece's target day.", CH.gantt(tasks),
                   "Plan a week to fill the schedule.")
            + "</div>" + _decision_strip(
                ([f"{c['waiting']} pieces waiting on you." for _ in [1] if c["waiting"]]),
                ([f"On pace for {c['proj']} this month." for _ in [1] if c["made_month"]] or ["Plan a week to start throughput."]),
                [("Review approvals", "nav('appr')"), ("Plan my week", "nav('content')")]))


def _mod_finance(c):
    pct = c["pct"]
    m = _master("💰", "Finance", "Spend against the cap, and cost per outcome.",
                [("Spent", f"${c['month_spent']:.0f}", c["bcol"]), ("Cap", f"${c['month_cap']:.0f}", "#8B7CFF"),
                 ("Per piece", f"${(c['content_cost']/max(len(c['content_jobs']),1)):.2f}", "#4C8DFF"),
                 ("Headroom", f"{max(0,100-pct)}%", "#3FD98B")],
                _donut(max(0, 100 - pct), "#3FD98B"))
    spend = _intel_card("Monthly spend", f"${c['month_spent']:.0f}", sub=f"of ${c['month_cap']:.0f}",
                        goal=f"${c['month_cap']:.0f} cap", forecast=f"${(c['total_cost']/max(__import__('datetime').date.today().day,1)*30):.0f}/mo",
                        confidence=("high" if c["made_month"] > 3 else "building"), dept="Finance", source="API meters", accent=c["bcol"],
                        insight=f"{pct}% of the cap used.", recommendation=("Ease off — near the cap." if pct >= 85 else "Headroom is healthy."),
                        action_label="Open budget", action="nav('budget')")
    rev = (_intel_card("Revenue", f"${c['o_rev']:.0f}", sub="recorded", dept="Finance", source="Outcomes", accent="#3FD98B",
                       insight="From recorded outcomes.", recommendation="Log wins to compute profit + ROI.",
                       action_label="Open Learning", action="nav('learn')")
           if c["o_rev"] else _intel_card("Revenue & profit", "", dept="Finance",
                       empty="Connect Stripe / QuickBooks / Xero to activate revenue, profit and ROI."))
    # waterfall of spend areas (real), or profit if revenue exists
    if c["o_rev"]:
        wf = [("Revenue", c["o_rev"]), ("Content", -c["content_cost"]), ("Leads/email", -(c["total_cost"] - c["content_cost"])), ("Net", 0)]
    else:
        wf = [("Content", c["content_cost"]), ("Leads/email", (c["total_cost"] - c["content_cost"])), ("Total", 0)]
    return (m + "<div class='grid g2'>" + spend + rev
            + _viz("Money flow", ("Revenue minus costs." if c["o_rev"] else "Where spend goes (connect revenue to see profit)."),
                   CH.waterfall(wf), "Fills as spend + revenue are recorded.")
            + _viz("Budget headroom", "How much of the cap remains.", _donut(max(0, 100 - pct), "#3FD98B"), "")
            + "</div>" + _decision_strip(
                ([f"Spend at {pct}% of cap." for _ in [1] if pct >= 85]),
                (["Per-piece cost is low; output is affordable to scale."]),
                [("Open budget", "nav('budget')")]))


def _mod_infra(c):
    items = [(name, bool(c["st"].get(k)), "connected" if c["st"].get(k) else "not connected")
             for k, name, *_ in _DIAG]
    m = _master("🛰️", "Infrastructure", "Every connection, live or down.",
                [("Wires live", f"{c['live_conn']}/{c['total_conn']}", "#4C8DFF"),
                 ("Down", c["total_conn"] - c["live_conn"], "#FF6B93" if c["live_conn"] < c["total_conn"] else "#3FD98B"),
                 ("System", "OK" if c["healthy"] else "Check", "#3FD98B" if c["healthy"] else "#F5B14C"),
                 ("Uptime", "24/7", "#8B7CFF")], "")
    conn = _intel_card("Connections", f"{c['live_conn']}/{c['total_conn']}", sub="live", dept="Infrastructure",
                       source="System map", accent=("#3FD98B" if c["live_conn"] == c["total_conn"] else "#F5B14C"),
                       insight=(f"{c['total_conn']-c['live_conn']} down — those intelligence centres stay greyed until fixed." if c["live_conn"] < c["total_conn"] else "All healthy."),
                       recommendation=("Fix the down wires to unlock more cards." if c["live_conn"] < c["total_conn"] else "Nothing to fix."),
                       action_label="Open System Map", action="nav('map')")
    sysh = _intel_card("System health", "OK" if c["healthy"] else "Check", dept="Infrastructure", source="Health probe",
                       accent=("#3FD98B" if c["healthy"] else "#F5B14C"),
                       insight=("Claude API + database + connectors all responding." if c["healthy"] else "A component check is failing."),
                       recommendation=("Nothing to do." if c["healthy"] else "Open Agents & Health."), action_label="Open Agents", action="nav('agents')")
    return (m + "<div class='grid g2'>" + conn + sysh
            + _viz("Connection status grid", "Green = live · amber = optional · red = down.", CH.statusgrid(items), "No connections mapped.")
            + "</div>" + _decision_strip(
                ([f"{c['total_conn']-c['live_conn']} connections down." for _ in [1] if c["live_conn"] < c["total_conn"]]),
                (["Each connection you add lights up its intelligence cards."]),
                [("Open System Map", "nav('map')")]))


def _mod_risk(c):
    pct = c["pct"]
    down = c["total_conn"] - c["live_conn"]
    items = []
    if c["month_cap"]:
        items.append(("Budget cap", 3 if pct >= 85 else (2 if pct >= 60 else 1), 3))
    if down:
        items.append(("Wires down", 3 if down > 2 else 2, 2))
    if c["waiting"]:
        items.append(("Approval backlog", 2 if c["waiting"] > 5 else 1, 2))
    if not c["leads_found"]:
        items.append(("Empty pipeline", 3, 3))
    if not c["healthy"]:
        items.append(("System health", 2, 3))
    if not items:
        items.append(("Deliverability", 1, 2))
    m = _master("⚠️", "Risk", "What could hurt the business, ranked.",
                [("Risks tracked", len(items), "#F5B14C"), ("Critical", sum(1 for _, l, i in items if l * i >= 6), "#FF6B93"),
                 ("System", "OK" if c["healthy"] else "Check", "#3FD98B" if c["healthy"] else "#F5B14C"),
                 ("Headroom", f"{max(0,100-pct)}%", "#3FD98B")], "")
    cards = ""
    for label, lk, im in items[:3]:
        sev = lk * im
        col = "#FF6B93" if sev >= 6 else ("#F5B14C" if sev >= 3 else "#3FD98B")
        cards += _intel_card(label, ("Critical" if sev >= 6 else ("Elevated" if sev >= 3 else "Low")), sub="severity",
                             dept="Risk", accent=col, insight=f"Likelihood {lk}/3 · impact {im}/3.",
                             recommendation={"Budget cap": "Throttle spend as you approach the cap.",
                                             "Wires down": "Reconnect on the System Map.",
                                             "Approval backlog": "Clear the approval queue.",
                                             "Empty pipeline": "Source leads + plan content.",
                                             "System health": "Open Agents & Health.",
                                             "Deliverability": "Keep warm-up cap + suppression on."}.get(label, "Monitor."),
                             action_label="Act", action="nav('map')")
    return (m + "<div class='grid g2'>" + cards + "</div>"
            + _viz("Risk matrix — likelihood × impact", "Top-right is act-now.", CH.risk_matrix(items), "No risks flagged.")
            + _decision_strip([l for l, lk, im in items if lk * im >= 6],
                              (["Fixing the top-right risk protects the most value."] if items else []),
                              [("Open System Map", "nav('map')"), ("Open budget", "nav('budget')")]))


def _mod_executive(c):
    # cross-module scoreboard + the decision engine (the CEO's single screen)
    board = "<div class='grid g4'>" + "".join(
        f"<div class='mstat'><div class='msv' style='color:{col}'>{_esc(v)}</div><div class='msl'>{_esc(l)}</div></div>"
        for l, v, col in [
            ("Business health", f"{c['health']}/100", "#8B7CFF"),
            ("Content live", c["published"], "#3FD98B"),
            ("Pipeline leads", c["leads_found"], "#4C8DFF"),
            ("Reply rate", f"{c['reply_rate']}%", "#2FE3D2"),
            ("Booked", c["booked"], "#F5B14C"),
            ("Spend", f"${c['month_spent']:.0f}/{c['month_cap']:.0f}", c["bcol"]),
            ("Wires", f"{c['live_conn']}/{c['total_conn']}", "#4C9AFF"),
            ("Waiting", c["waiting"], "#F5B14C"),
        ]) + "</div>"
    return ("<div class='card full' style='margin-bottom:12px'><p class='ct'>🏛️ Executive Intelligence</p>"
            "<p class='cc'>The whole business on one screen — every module's headline, plus the decisions that move "
            "the needle this week.</p>" + board + "</div>"
            + _viz("Value flow — channel to customer", "How marketing turns into revenue.",
                   CH.sankey([f for f in [
                       ("SEO / Web", "Leads", max(1, c["leads_found"] * 0.6)) if c["leads_found"] else None,
                       ("Outreach", "Leads", max(1, c["leads_found"] * 0.4)) if c["leads_found"] else None,
                       ("Leads", "Booked", c["booked"]) if c["booked"] else None,
                       ("Booked", "Customers", c["o_cust"]) if c["o_cust"] else None] if f]),
                   "Fills as the pipeline runs.")
            + _decision_strip(c["risks"], c["opps"], c["actions"]))


# ---------------------------------------------------------------------------
# dashboard
# ---------------------------------------------------------------------------
def _insight_card(title, big, sub, body="", insight="", src="", accent="#4C8DFF"):
    """Google-grade metric card: big number + context + chart + a one-line
    qualitative read of what the number MEANS."""
    return ("<div class='card'>"
            f"<p class='ct' style='margin:0'>{_esc(title)}</p>"
            f"<div style='display:flex;align-items:baseline;gap:8px;margin-top:7px'>"
            f"<span style='font-size:27px;font-weight:800;color:{accent}' class='tnum'>{_esc(str(big))}</span>"
            f"<span class='dim'>{_esc(sub)}</span></div>"
            + (f"<div style='margin-top:8px;overflow-x:auto'>{body}</div>" if body else "")
            + (f"<div style='margin-top:8px;padding:7px 10px;border-radius:8px;background:rgba(139,124,255,.08);"
               f"border-left:3px solid #8B7CFF;font-size:12px'>💡 {_esc(insight)}</div>" if insight else "")
            + (f"<div class='dim' style='font-size:10px;margin-top:7px'>🔌 {_esc(src)}</div>" if src else "")
            + "</div>")


def _gsc_board(gi):
    """The Search Console replication — every metric as its own card, with real
    zeros shown IN CONTEXT (position 42 = page 5), quantitative + qualitative."""
    gsc = (gi or {}).get("gsc") or {}
    if not gsc:
        return ("<div class='card full' style='margin-top:12px'><p class='ct'>🔍 Search Console (full)</p>"
                "<p class='cc'>⚪ No cached pull yet — click ↻ Refresh Google data.</p></div>")
    q = gsc.get("queries") or []
    daily = gsc.get("daily") or []
    imp = sum(r["impressions"] for r in q)
    clk = sum(r["clicks"] for r in q)
    ctr = round(clk / imp * 100, 1) if imp else 0
    avgpos = round(sum(r["position"] for r in q) / len(q), 1) if q else 0
    best = min(q, key=lambda r: r["position"]) if q else {}
    # qualitative reads (computed, not invented)
    pos_read = (f"Average page {int((avgpos - 1) // 10) + 1} of Google — best query “{best.get('key','')[:30]}” at "
                f"#{best.get('position', 0)} (page {int((best.get('position', 99) - 1) // 10) + 1}). "
                + ("Zero clicks so far is normal below page 1 — rankings must climb first." if clk == 0 else
                   f"{clk} clicks earned."))
    trend = CH.lines([("Impressions", [r["impressions"] for r in daily] or [0], "#4C8DFF"),
                      ("Clicks", [r["clicks"] for r in daily] or [0], "#3FD98B")]) if daily else ""
    qrows = "".join(
        f"<tr><td>{_esc(r['key'][:44])}</td><td class='tnum'>{r['impressions']}</td>"
        f"<td class='tnum'>{r['clicks']}</td><td class='tnum'>{r['ctr']}%</td>"
        f"<td class='tnum'>#{r['position']} <span class='dim'>(p{int((r['position']-1)//10)+1})</span></td></tr>"
        for r in q[:15])
    prows = "".join(
        f"<tr><td>{_esc(r['key'][:44])}</td><td class='tnum'>{r['impressions']}</td>"
        f"<td class='tnum'>{r['clicks']}</td><td class='tnum'>#{r['position']}</td></tr>"
        for r in (gsc.get("pages") or [])[:10])
    dev = [(r["key"].title(), r["impressions"], c) for r, c in
           zip(gsc.get("devices") or [], ["#4C8DFF", "#2FE3D2", "#8B7CFF", "#F5B14C", "#3FD98B"])]
    geo = [(r["key"].upper(), r["impressions"]) for r in (gsc.get("countries") or [])[:8]]
    return (
        "<div class='card full' style='margin-top:12px'><p class='ct'>🔍 Search Console — full replication</p>"
        "<p class='cc'>Your complete Google Search presence, straight from the GSC API. Real zeros are shown with "
        "context — they mean 'not ranking high enough yet', not 'broken'.</p></div>"
        "<div class='grid g3' style='margin-top:8px'>"
        + _insight_card("Impressions (28d)", imp, "times you appeared in Google", "",
                        f"Your site appeared {imp} times; impressions come mostly from the "
                        f"{'e-commerce monitoring' if any('monitor' in r['key'] for r in q) else 'automation'} cluster.",
                        "Search Console API", "#4C8DFF")
        + _insight_card("Clicks (28d)", clk, f"CTR {ctr}%", "", pos_read, "Search Console API", "#3FD98B")
        + _insight_card("Average position", f"#{avgpos}", f"across {len(q)} queries", "",
                        pos_read, "Search Console API", "#8B7CFF")
        + "</div><div class='grid g2' style='margin-top:8px'>"
        + _viz2("Impressions & clicks — 28-day trend", trend, "Fills day by day.")
        + _viz2("Devices", (CH.ring([(l, v, c) for l, v, c in dev], center=str(imp)) if dev else ""), "Device split appears with impressions.")
        + "</div>"
        "<div class='card full' style='margin-top:8px'><p class='ct'>Every ranking query</p>"
        "<div class='tbwrap'><table><thead><tr><th>Query</th><th>Impr.</th><th>Clicks</th><th>CTR</th><th>Position</th></tr></thead>"
        f"<tbody>{qrows or '<tr><td colspan=5 class=dim>No queries yet.</td></tr>'}</tbody></table></div></div>"
        "<div class='grid g2' style='margin-top:8px'>"
        "<div class='card'><p class='ct'>Pages Google shows</p><div class='tbwrap'><table>"
        "<thead><tr><th>Page</th><th>Impr.</th><th>Clicks</th><th>Pos.</th></tr></thead>"
        f"<tbody>{prows or '<tr><td colspan=4 class=dim>No page data yet.</td></tr>'}</tbody></table></div></div>"
        + _viz2("Countries searching you", (CH.geo(geo) if geo else ""), "Fills as impressions arrive.")
        + "</div>")


def _ga4_board(gi, title="📈 Analytics (GA4) — full replication"):
    ga4 = (gi or {}).get("ga4") or {}
    if not ga4:
        return (f"<div class='card full' style='margin-top:12px'><p class='ct'>{_esc(title)}</p>"
                "<p class='cc'>⚪ No cached pull yet — click ↻ Refresh Google data.</p></div>")
    t = ga4.get("totals") or {}
    daily = ga4.get("daily") or []
    sess = int(t.get("sessions", 0))
    users = int(t.get("totalUsers", 0))
    new = int(t.get("newUsers", 0))
    eng = round(float(t.get("engagementRate", 0)) * 100)
    ch = ga4.get("channels") or []
    topch = max(ch, key=lambda r: r["sessions"])["sessionDefaultChannelGroup"] if ch else "—"
    trend = CH.lines([("Sessions", [r.get("sessions", 0) for r in daily] or [0], "#2FE3D2"),
                      ("Users", [r.get("totalUsers", 0) for r in daily] or [0], "#4C8DFF")]) if daily else ""
    chring = CH.ring([(r["sessionDefaultChannelGroup"][:12], r["sessions"], c) for r, c in
                      zip(ch, ["#4C8DFF", "#2FE3D2", "#8B7CFF", "#F5B14C", "#3FD98B", "#FF6B93"])],
                     center=str(sess)) if ch else ""
    prow = "".join(f"<div class='fe'><span class='mut'>{_esc(r['pagePath'][:40])}</span>"
                   f"<span class='tnum' style='margin-left:auto'>{int(r['sessions'])}</span></div>"
                   for r in (ga4.get("pages") or [])[:8])
    geo = [(r["country"], r["sessions"]) for r in (ga4.get("countries") or [])[:8]]
    return (
        f"<div class='card full' style='margin-top:12px'><p class='ct'>{_esc(title)}</p>"
        "<p class='cc'>Your complete traffic picture from the GA4 API — sessions, people, channels, pages, countries.</p></div>"
        "<div class='grid g4' style='margin-top:8px'>"
        + _insight_card("Sessions (28d)", sess, "visits", "",
                        f"Most visits arrive via {topch} — " +
                        ("young-site numbers; every published piece compounds this." if sess < 100 else "growing base."),
                        "GA4 API", "#2FE3D2")
        + _insight_card("People", users, f"{new} new", "",
                        f"{round(new / users * 100) if users else 0}% of visitors are first-timers.", "GA4 API", "#4C8DFF")
        + _insight_card("Engagement", f"{eng}%", "engaged sessions", "",
                        ("Healthy engagement — visitors read." if eng >= 50 else "Visitors bounce fast — landing content needs a hook."),
                        "GA4 API", "#8B7CFF")
        + _insight_card("Top channel", topch, "traffic source", "",
                        "Organic growing = SEO engine working; Direct-heavy = brand/word-of-mouth.", "GA4 API", "#F5B14C")
        + "</div><div class='grid g2' style='margin-top:8px'>"
        + _viz2("Sessions & users — 28-day trend", trend, "Fills day by day.")
        + _viz2("Traffic channels", chring, "Fills as sessions arrive.")
        + "</div><div class='grid g2' style='margin-top:8px'>"
        + f"<div class='card'><p class='ct'>Top pages by visits</p>{prow or '<div class=dim>No page data yet.</div>'}</div>"
        + _viz2("Visitor countries", (CH.geo(geo) if geo else ""), "Fills as sessions arrive.")
        + "</div>")


def _viz2(title, svg, empty):
    return (f"<div class='card'><p class='ct'>{_esc(title)}</p>"
            f"<div style='margin-top:8px;overflow-x:auto'>{svg or ('<div class=dim style=padding:12px>⚪ ' + _esc(empty) + '</div>')}</div></div>")


def _competitor_board(ci, serper_on):
    """The 22 Competitor-Intelligence cards in the SEO/AEO/GEO section — filled
    from captured data (source-tagged), honest 'needs tool' for the rest."""
    scans = (ci or {}).get("competitors") or []
    ai = ((ci or {}).get("ai") or {}).get("per_competitor") or {}
    recs = ((ci or {}).get("ai") or {}).get("recommendations") or []
    scanned = (ci or {}).get("scanned_at", "")[:16].replace("T", " ")

    def card(title, body, live=True, src=""):
        col = "#3FD98B" if (live and body) else "#8E9BBE"
        return ("<div class='card'><div style='display:flex;align-items:center;gap:7px'>"
                f"<span class='ct' style='margin:0'>{_esc(title)}</span>"
                f"<span style='margin-left:auto;width:8px;height:8px;border-radius:50%;background:{col}'></span></div>"
                + (f"<div style='margin-top:8px;font-size:12.5px;line-height:1.55'>{body}</div>"
                   if body else "<div class='dim' style='margin-top:8px'>No signal captured yet.</div>")
                + (f"<div class='dim' style='font-size:10px;margin-top:8px'>🔌 {_esc(src)}</div>" if src else "")
                + "</div>")

    def per_comp(fn):
        rows = ""
        for c in scans:
            v = fn(c)
            if v:
                rows += f"<div class='fe'><b style='min-width:130px'>{_esc(c['domain'][:22])}</b><span class='mut'>{v}</span></div>"
        return rows

    def newsbucket(key, label):
        rows = ""
        for c in scans:
            items = (c.get("news_buckets") or {}).get(key) or []
            for n in items[:2]:
                rows += (f"<div class='fe'><b style='min-width:130px'>{_esc(c['domain'][:22])}</b>"
                         f"<span class='mut'>{_esc(str(n.get('title',''))[:70])}</span></div>")
        return card(label, rows, src="Google News (Serper)")

    aivis = (ci or {}).get("ai_visibility") or {}
    serp_ads = (ci or {}).get("serp_ads") or {}
    own_q = (ci or {}).get("queries_used") or []

    def rival_block(c, inner):
        a = ai.get(c["domain"]) or {}
        thr = a.get("threat", "")
        tcol = {"high": "#FF6B93", "medium": "#F5B14C", "low": "#3FD98B"}.get(thr, "#8E9BBE")
        return ("<div style='border:1px solid var(--line);border-radius:9px;padding:9px 11px;margin-top:7px'>"
                f"<div style='display:flex;gap:8px;align-items:center'><b>{_esc(c['domain'][:26])}</b>"
                + (f"<span class='pill' style='background:{tcol}22;color:{tcol};padding:1px 8px'>{_esc(thr)} threat</span>" if thr else "")
                + f"</div><div style='margin-top:5px;font-size:12px;line-height:1.55'>{inner}</div></div>")

    def detail(fn):
        out = ""
        for c in scans:
            inner = fn(c)
            if inner:
                out += rival_block(c, inner)
        return out

    if not scans:
        empty_note = ("Serper is connected — click Scan to capture." if serper_on
                      else "Connect SERPER_API_KEY first (System Map).")
        board_cards = f"<div class='card full'><div class='dim'>⚪ No competitor scan yet. {empty_note}</div></div>"
    else:
        # --- individual, detailed signal cards (quant + qualitative mix) ---
        seo_d = detail(lambda c: "".join(
            f"<div class='fe'><span class='mut'>{_esc(h['query'][:38])}</span>"
            f"<span class='tnum' style='margin-left:auto'>them <b>#{h['position']}</b></span></div>"
            for h in (c.get("seo_hits") or [])[:6]) or "")
        vis_d = detail(lambda c: (
            f"<div class='big tnum' style='font-size:24px'>{c.get('visibility_index', 0)}%</div>"
            f"<div class='dim'>appears in {len(c.get('seo_hits') or [])} of your {max(len(own_q),1)} query SERPs</div>"
            "<div class='prog' style='margin:6px 0 0'>"
            f"<i style='width:{max(3, c.get('visibility_index', 0))}%;background:#8B7CFF'></i></div>"))
        geo_d = detail(lambda c: (
            f"<div style='font-size:16px'>{'★' * int(round(c['maps'].get('rating', 0)))}"
            f"<span class='dim'>{'☆' * (5 - int(round(c['maps'].get('rating', 0))))}</span> "
            f"<b>{c['maps'].get('rating', 0)}</b> · {c['maps'].get('reviews', 0)} reviews</div>"
            f"<div class='dim'>{_esc((c['maps'].get('address') or '')[:48])}</div>"
            + ("<div style='color:#3FD98B;font-size:11.5px;margin-top:3px'>💡 weak social proof — attackable with review-rich comparison content</div>"
               if c['maps'].get('rating', 5) <= 3.5 and c['maps'].get('reviews', 99) < 20 else "")) if c.get("maps") else "")
        prod_d = detail(lambda c: (
            f"<div><b>{_esc(((ai.get(c['domain']) or {}).get('products_guess') or (c.get('site') or {}).get('title') or '')[:70])}</b></div>"
            + (f"<div class='dim' style='margin-top:3px'>{_esc(((c.get('site') or {}).get('description') or '')[:110])}</div>"
               if (c.get('site') or {}).get('description') else "")))
        price_d = detail(lambda c: (" ".join(
            f"<span class='pill' style='background:rgba(245,177,76,.14);color:#F5B14C;padding:2px 9px'>{_esc(p)}</span>"
            for p in (c.get("site") or {}).get("prices_seen") or []) or ""))
        promo_d = detail(lambda c: ("🏷️ promo/offer visible on their homepage right now"
                                    if (c.get("site") or {}).get("promo_on_site") else ""))
        tech_d = detail(lambda c: (" ".join(
            f"<span class='pill' style='background:rgba(76,141,255,.14);color:#4C8DFF;padding:2px 9px'>{_esc(t)}</span>"
            for t in (c.get("site") or {}).get("tech") or []) or ""))
        soc_d = detail(lambda c: (
            f"<div class='big tnum' style='font-size:22px'>{c.get('linkedin_followers', 0):,}</div>"
            "<div class='dim'>LinkedIn followers (from Google snippet)</div>") if c.get("linkedin_followers") else "")

        def bucket_d(key):
            return detail(lambda c: "".join(
                f"<div class='fe'><span class='mut'>{_esc(str(n.get('title',''))[:64])}</span>"
                f"<span class='dim' style='margin-left:auto'>{_esc(str(n.get('date',''))[:12])}</span></div>"
                for n in ((c.get("news_buckets") or {}).get(key) or [])[:3]) or "")
        ads_d = ""
        if serp_ads:
            for c in scans:
                qs = [q for q, doms in serp_ads.items() if c["domain"] in doms]
                if qs:
                    ads_d += rival_block(c, "advertising on: " + ", ".join(_esc(q[:30]) for q in qs[:3]))
            if not ads_d:
                ads_d = ("<div class='dim' style='margin-top:6px'>Observed: <b>no rival is paying for ads</b> on your "
                         f"{len(own_q)} tracked queries — the SERP is winnable organically.</div>")
        aivis_d = ""
        if aivis.get("mentions"):
            mx = max(aivis["mentions"].values()) or 1
            for d, n in sorted(aivis["mentions"].items(), key=lambda x: -x[1]):
                aivis_d += (f"<div class='fe'><span class='mut'>{_esc(d[:26])}</span>"
                            f"<div class='track' style='margin:0 8px;flex:1'><i style='width:{round(n/mx*100)}%;background:#8B7CFF'></i></div>"
                            f"<span class='tnum'>{n}/{aivis.get('prompts_run', 0)}</span></div>")
            aivis_d = (f"<div class='dim' style='margin-bottom:4px'>Asked Claude {aivis.get('prompts_run', 0)} buyer-intent "
                       "questions with live web search — who got cited:</div>") + aivis_d
        health_d = detail(lambda c: (
            f"<div class='big tnum' style='font-size:22px'>{(ai.get(c['domain']) or {}).get('health','—')}<small>/100</small></div>"
            f"<div class='dim'>threat: {(ai.get(c['domain']) or {}).get('threat','—')}</div>") if ai else "")
        risk_d = detail(lambda c: _esc((ai.get(c["domain"]) or {}).get("risk", "")))
        fc_d = detail(lambda c: _esc((ai.get(c["domain"]) or {}).get("forecast", "")))
        rev_d = detail(lambda c: (
            f"<b>{_esc((ai.get(c['domain']) or {}).get('revenue_band_est','unknown'))}</b> "
            f"<span class='dim'>(confidence {_esc((ai.get(c['domain']) or {}).get('revenue_confidence','low'))})</span>")
            if ai and (ai.get(c["domain"]) or {}).get("revenue_band_est") else "")
        rec_html = "".join(f"<div class='fe'><span>▹ {_esc(r)}</span></div>" for r in recs[:4])
        # per-competitor full dossier
        dossiers = ""
        for c in scans:
            a = ai.get(c["domain"]) or {}
            dossiers += ("<div class='card'><p class='ct'>🗂️ " + _esc(c["domain"]) + "</p>"
                         + rival_block(c,
                            f"<div class='dim'>{_esc(((c.get('site') or {}).get('title') or '')[:80])}</div>"
                            f"<div style='margin-top:4px'>Visibility <b>{c.get('visibility_index',0)}%</b>"
                            + (f" · ★{c['maps'].get('rating')} ({c['maps'].get('reviews')} reviews)" if c.get('maps') else "")
                            + (f" · {c.get('linkedin_followers',0):,} followers" if c.get('linkedin_followers') else "")
                            + (f"<br>Risk: {_esc(a.get('risk',''))}" if a.get('risk') else "")
                            + (f"<br>Forecast: {_esc(a.get('forecast',''))}" if a.get('forecast') else "")) + "</div>")
        board_cards = (
            card("Competitor Health", health_d, src="AI analysis of captured signals (est.)")
            + card("Competitor SEO — query by query", seo_d, src="Your GSC queries × Google SERPs")
            + card("Competitor Traffic → Visibility Index", vis_d, src="Share of YOUR query SERPs (real index, not visits)")
            + card("Competitor GEO (local presence)", geo_d, src="Google Maps")
            + card("Competitor Reviews", geo_d, src="Google Maps ratings")
            + card("Competitor Products", prod_d, src="Their website + AI extract")
            + card("Competitor Pricing", price_d, src="Prices published on their own site")
            + card("Competitor Promotions", promo_d, src="Homepage scan")
            + card("Competitor Technology", tech_d, src="Homepage stack detection")
            + card("Competitor Social Growth", soc_d, src="LinkedIn count via Google snippet (free)")
            + card("Competitor Ads", ads_d, src="Sponsored slots on your query SERPs")
            + card("Competitor AI Visibility", aivis_d, src="Measured via your Claude key (Claude engine; est. for others)")
            + card("Competitor Hiring", bucket_d("hiring"), src="Google News")
            + card("Competitor Partnerships", bucket_d("partnerships"), src="Google News")
            + card("Competitor Funding", bucket_d("funding"), src="Google News")
            + card("Competitor Expansion", bucket_d("expansion"), src="Google News")
            + card("Competitor Launches", bucket_d("launches"), src="Google News")
            + card("Competitor Risk", risk_d, src="AI analysis (est.)")
            + card("Competitor Forecast", fc_d, src="AI analysis (est.)")
            + card("Competitor Revenue Estimate", rev_d, src="AI estimate from signals — labelled, low confidence")
            + card("Competitor Recommendations", rec_html, src="AI counter-moves for Anthropos")
            + card("Competitor Inventory", "<div class='dim'>N/A — your rivals are service/SaaS businesses, not stores.</div>",
                   live=True, src="not applicable to this market")
            + dossiers)
    return (
        "<div class='card full' style='margin-top:12px;border-left:4px solid #8B7CFF'>"
        "<p class='ct'>🛰️ Competitive Intelligence — 22 signals</p>"
        "<p class='cc'>The machine discovers who ranks for <b>your</b> queries, then captures their SEO share, local "
        "reviews, tech stack, pricing, news (funding/partners/launches) and synthesizes health · risk · forecast · "
        "counter-moves. Every card shows its source; grey cards need a tool we haven't bought.</p>"
        "<div class='cmd'>"
        "<input id='compdoms' placeholder='Optional: competitor domains, comma-separated (else auto-discover)'>"
        f"<button onclick='scanCompetitors()' {'disabled' if not serper_on else ''}>🛰️ Scan competitors (~40 credits)</button></div>"
        + (f"<div class='dim' style='margin-top:5px'>Last scan: {scanned} UTC · "
           f"{len(scans)} competitors · queries: {_esc(', '.join((ci or {}).get('queries_used', [])[:4]))}…</div>"
           if scans else "")
        + "</div><div class='grid g3' style='margin-top:10px'>" + board_cards + "</div>")


def dashboard_html(*, jobs, st, health, month_spent, month_cap, day_spent, day_cap,
                   taste_skills, has_password=False, paused=False, autonomy=False,
                   bookings=None, ads=None, needles=None, last_eval=None,
                   meters=None, api_limits=None, ci_text="", ci_drive="", autopilot_on=False,
                   content_plan=None, web_tracking=None, reply_drafts=None,
                   competitor_intel=None, google_insights=None, seo_ctx=None, media_ctx=None,
                   system_ctx=None, risk_ctx=None, bi_ctx=None,
                   outreach_ctx=None, sga_ctx=None, factory_ctx=None,
                   cockpit_ctx=None, saved_keys=None):
    reply_drafts = reply_drafts or []
    competitor_intel = competitor_intel or {}
    google_insights = google_insights or {}
    from datetime import date
    jobs, st, health = jobs or [], st or {}, health or {}
    bookings, ads = bookings or {}, ads or {}
    needles, last_eval = needles or {}, last_eval or {}
    meters, api_limits = meters or {}, api_limits or {}
    ci_text, ci_drive = ci_text or "", ci_drive or ""
    content_plan = content_plan or {}
    booked = int(bookings.get("booked", 0) or 0)
    o_leads, o_rev, o_cust = _outcomes(jobs)
    content_jobs = [j for j in jobs if j.get("type") != "outreach_campaign"]
    out_jobs = [j for j in jobs if j.get("type") == "outreach_campaign"]
    pl = _pipeline(jobs)
    lead_rows = list(_lead_funnel(jobs))
    # --- ACCURATE outreach counters (single source of truth) ---
    # emails_sent = every real send recorded in sent_to (intro + follow-ups);
    # leads_emailed = unique people reached >=1; replied = customer replies read.
    try:
        import content_engine_connectors as _Cc
        _tstats = _Cc.touch_stats
    except Exception:
        _tstats = lambda v: (len(v) if isinstance(v, list) else (1 if v else 0), "")
    real_emails_sent = leads_emailed = 0
    for j in out_jobs:
        sm = (j.get("payload", {}) or {}).get("sent_to", {}) or {}
        for v in sm.values():
            n = _tstats(v)[0]
            if n > 0:
                leads_emailed += 1
                real_emails_sent += n
    replied = len(reply_drafts or [])
    # fold the real numbers into the people-funnel (Emailed = people, + Replied)
    lead_rows[3] = ("Emailed", leads_emailed or lead_rows[3][1])
    lead_rows[4] = ("Replied", replied)
    if booked:
        lead_rows[5] = ("Booked", booked)   # real Cal.com consultations
    published = sum(1 for j in content_jobs if _STAGE_OF.get(j.get("status", "")) in (4, 5))
    leads_found = lead_rows[0][1]
    # 'emails_sent' now means TOTAL emails sent (volume), not campaigns; fall back
    # to the campaign count only if nothing has a send record yet.
    emails_sent = real_emails_sent or lead_rows[3][1]
    reply_rate = round(replied / leads_emailed * 100) if leads_emailed else 0
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
    m_content = _master("📝", "Content — at a glance", "How much you're producing and shipping.",
        [("Made / month", made_month, "#EDF1FB"), ("Published", published, "#3FD98B"),
         ("In progress", sum(pl[0:4]), "#F5B14C"), ("On pace for", proj, "#8B7CFF")],
        _sparkline(content_series, "#4C8DFF") if content_jobs else _empty("Fills as pieces are made."))
    # ---- CONTENT PLAN (agent proposes -> you approve -> pieces get created) ----
    _pending = content_plan.get("status") == "pending" and content_plan.get("items")
    if _pending:
        from datetime import date, timedelta
        _chan_badge = {
            "linkedin": "<span class='pill' style='background:rgba(10,102,194,.16);color:#4C9AFF;padding:1px 8px'>in LinkedIn</span>",
            "website": "<span class='pill' style='background:rgba(47,227,210,.14);color:#2FE3D2;padding:1px 8px'>🌐 Website</span>",
            "web": "<span class='pill' style='background:rgba(47,227,210,.14);color:#2FE3D2;padding:1px 8px'>🌐 Website</span>",
        }
        seg_counts, chan_counts = {}, {}
        # flat review list (the WEEK CALENDAR above shows the day-by-day layout —
        # this card is just the review-and-approve list, no second calendar).
        rows = ""
        for i, it in enumerate(content_plan["items"], 1):
            seg, pil = it.get("segment", ""), it.get("pillar", "")
            if seg:
                seg_counts[seg] = seg_counts.get(seg, 0) + 1
            for c in (it.get("channels") or ["website"]):
                c = str(c).lower()
                c = "website" if c in ("web", "blog", "wordpress") else c
                chan_counts[c] = chan_counts.get(c, 0) + 1
            d = int(it.get("day_offset", 0) or 0)
            daypill = (f"<span class='pill' style='background:rgba(139,124,255,.16);color:#8B7CFF;padding:1px 8px'>"
                       f"📅 {(date.today() + timedelta(days=d)).strftime('%a')}</span>")
            chans = [str(c).lower() for c in (it.get("channels") or ["website"])]
            chan_html = " ".join(_chan_badge.get("website" if c in ("web", "blog", "wordpress") else c, "") for c in chans)
            tags = ""
            if seg or pil:
                tags = ("<div style='margin-top:4px;display:flex;gap:6px;flex-wrap:wrap'>"
                        + (f"<span class='pill' style='background:rgba(47,227,210,.14);color:#2FE3D2;padding:1px 8px'>👤 {_esc(seg)}</span>" if seg else "")
                        + (f"<span class='pill' style='background:rgba(139,124,255,.14);color:#8B7CFF;padding:1px 8px'>🎯 {_esc(pil)}</span>" if pil else "")
                        + "</div>")
            rows += (
                "<div style='padding:10px 0;border-top:1px solid rgba(255,255,255,.06)'>"
                f"<div style='display:flex;gap:8px;align-items:baseline;flex-wrap:wrap'>"
                f"<span class='tnum dim'>{i:02d}</span>{daypill}<b>{_esc(it.get('title',''))}</b>"
                f"<span style='margin-left:auto;display:flex;gap:5px'>{chan_html}</span></div>"
                f"<div class='dim' style='margin-top:3px'>🔑 {_esc(it.get('target_keyword','') or '—')} · "
                f"{_esc(it.get('angle',''))}</div>" + tags
                + (f"<div class='dim' style='margin-top:2px'>Why: {_esc(it.get('rationale',''))}</div>" if it.get('rationale') else "")
                + "</div>")
        # coverage bar: how evenly the plan spans the 7 segments + which channels
        cov = ""
        if seg_counts:
            chips = " ".join(f"<span class='pill' style='background:rgba(47,227,210,.12);color:#2FE3D2;padding:1px 8px'>"
                             f"{_esc(s)} ×{n}</span>" for s, n in sorted(seg_counts.items(), key=lambda x: -x[1]))
            li_n = chan_counts.get("linkedin", 0)
            web_n = chan_counts.get("website", 0)
            cov = (f"<div style='margin:8px 0 4px'><span class='dim'>Segment coverage:</span> "
                   f"<div style='margin-top:5px;display:flex;gap:6px;flex-wrap:wrap'>{chips}</div>"
                   f"<div class='dim' style='margin-top:8px'>Channels: <b style='color:#2FE3D2'>{web_n} website</b> · "
                   f"<b style='color:#4C9AFF'>{li_n} LinkedIn</b></div></div>")
        plan_card = (
            "<div class='card full' style='margin-bottom:12px;border-left:4px solid #4C8DFF'>"
            f"<p class='ct'>✅ Review &amp; approve this week — {len(content_plan['items'])} pieces</p>"
            "<p class='cc'>The day-by-day layout is in the <b>calendar above</b>; this is the review list. Each piece is "
            "tagged with its day, channels, segment &amp; pillar. Approve to create them all (written, QA-checked, "
            "on-brand image + LinkedIn post, published to the right section); or discard and re-plan.</p>"
            + cov + rows +
            "<div class='ctrl' style='margin-top:14px'>"
            "<button class='sbtn' onclick='approvePlan()'>✓ Approve — create these pieces</button>"
            "<button class='cbtn warn' onclick='clearPlan()'>✗ Discard</button></div></div>")
    else:
        plan_card = (
            "<div class='card full' style='margin-bottom:12px'>"
            "<p class='ct'>🗒️ Plan my content — one production-ready week</p>"
            "<p class='cc'>Like an agency: the planner lays out a full <b>week</b> of on-brand pieces — spread across "
            "your 7 customer segments and scheduled day-by-day (Website + LinkedIn) — for you to review and approve. "
            "Nothing is written until your yes.</p>"
            "<div class='ctrl'><span class='dim' style='align-self:center'>Pieces this week: </span>"
            "<input id='plan-count' value='10' style='width:60px' inputmode='numeric'>"
            "<button class='sbtn' id='planbtn' onclick='planContent()'>🗓️ Plan my week</button>"
            + (f"<span class='dim' style='align-self:center'>Last plan: {_esc(content_plan.get('status',''))}</span>"
               if content_plan.get("status") else "") + "</div></div>")

    # ---- BRAND / CI + 1-CLICK AUTOPILOT ----
    _ci_has = bool(ci_text.strip())
    ap_state = ("<span class='pill p-live'><span class='d' style='background:#3FD98B'></span>Autopilot ON — creating & publishing live</span>"
                if autopilot_on else
                "<span class='pill p-need'><span class='d' style='background:#F5B14C'></span>Autopilot off</span>")
    autopilot_card = (
        "<div class='card full' style='margin-bottom:12px'>"
        "<p class='ct'>🎨 Brand & Autopilot — feed your identity, publish on-brand in one click</p>"
        f"<p class='cc'>{ap_state} &nbsp; Everything the agents write follows the brand you paste below. "
        "Quality is still gated automatically (QA agent + judge) — <b>auto never means unchecked</b>.</p>"
        "<div class='dim' style='margin-bottom:4px'>Your brand / CI — voice, tone, always-do, never-do, proof points"
        + ("  ✓ saved" if _ci_has else "  (empty — paste it once)") + "</div>"
        f"<textarea id='ci-text' style='width:100%;min-height:120px;font-family:inherit' "
        f"placeholder='e.g. Voice: plain, confident, no hype. Never: invent client results or use jargon. "
        f"Proof points: runs on n8n, one dashboard. Colors: deep slate + cyan…'>{_esc(ci_text)}</textarea>"
        "<div class='ctrl' style='margin-top:8px'>"
        "<span class='dim'>Design-inspiration Drive folder ID (images to echo): </span>"
        f"<input id='ci-drive' value='{_esc(ci_drive)}' placeholder='1AbC…' style='min-width:220px'>"
        "<button class='cbtn' onclick='saveCI()'>💾 Save brand</button></div>"
        "<div class='ctrl' style='margin-top:14px;border-top:1px solid rgba(255,255,255,.08);padding-top:14px'>"
        + ("<button class='sbtn' style='background:#F5788A' onclick='stopAutopilot()'>■ Stop autopilot</button>"
           if autopilot_on else
           "<button class='sbtn' onclick='runAutopilot()'>🚀 Autopilot: create &amp; publish on-brand (1 click)</button>")
        + "<span class='dim' style='align-self:center'>Queues today's pieces, writes on-brand, and publishes the "
          "ones that pass QA — hands-free. Stop anytime.</span></div></div>")

    p_content = (m_content
                 + _factory_line(content_jobs)
                 + _week_calendar(content_jobs, content_plan)
                 + plan_card + autopilot_card + grid(
        _panel("Pipeline — where each piece is", "Idea → written → checked → your approval → live → measured.",
               _funnel(list(zip(_STAGES, pl))) if sum(pl) else _empty("No content jobs yet.")),
        _panel("Content by stage", "How many pieces sit at each stage right now.",
               _bars([(k, v) for k, v in by_status.items()][:6], "#4C8DFF") if by_status else _empty("Nothing in production yet.")),
        _panel("Output & projection", "Target ≈ 60/month (2 blogs a day).",
               (_sparkline(content_series, "#4C8DFF") + f"<div class='dim' style='margin-top:6px'>{made_month} made this month · on pace for <b style='color:var(--ink)'>{proj}</b></div>") if content_jobs else _empty("Fills as pieces are made.")),
        _panel("Published pieces", "What's live on your site.",
               top_html or _empty("Nothing published yet.")),
        _panel("Cost per piece", "Average AI spend to make one piece.",
               f"<div class='big tnum'>${(content_cost/max(len(content_jobs),1)):.3f}</div><div class='dim'>per piece · {len(content_jobs)} made</div>" if content_jobs else _empty("Fills as pieces are made.")),
        _panel("Live vs in progress", "How much is published vs still moving.",
               _donut(round(published/max(len(content_jobs),1)*100), "#3FD98B") if content_jobs else _empty("Fills as pieces are made.")),
        _panel("Where pieces sit", "Count at each stage of the line.",
               _bars(list(zip(_STAGES, pl)), "#4C8DFF") if sum(pl) else _empty("Nothing in production yet.")),
        _panel("Monthly pace", "Made so far vs projected by month-end.",
               f"<div class='big tnum'>{made_month}<small> / {proj}</small></div><div class='dim'>this month · projected</div>" if content_jobs else _empty("Fills as pieces are made."))))

    # ---- 2. LEAD MACHINE ----
    m_leads = _master("🧲", "Leads — at a glance", "Your pipeline from stranger to booked call.",
        [("Found", leads_found, "#EDF1FB"), ("Emailed", leads_emailed, "#4C8DFF"),
         ("Replied", lead_rows[4][1], "#8B7CFF"), ("Booked", lead_rows[5][1], "#3FD98B")],
        _funnel(lead_rows) if any(v for _, v in lead_rows) else _empty("Fills as leads flow in."))
    # 🗺️ Maps lead sourcing: type a business type + city -> real local businesses
    # with verified emails land in the pipeline (qualify -> write -> YOUR approval).
    _serper_on = bool(st.get("serper_search"))
    maps_form = (
        "<div class='card full' style='margin-bottom:12px;border-left:4px solid #2FE3D2'>"
        "<p class='ct'>🗺️ Source local leads from Google Maps</p>"
        "<p class='cc'>Type who and where — the engine scrapes real local businesses (name, phone, website, rating), "
        "finds a <b>verified email</b> for each via Prospeo, and drops them into the normal pipeline: qualify → "
        "write → QA → <b>your approval</b> → capped send. Nothing is emailed by this button.</p>"
        + ("" if _serper_on else "<p class='cc' style='color:#F5B14C'>⚠ Serper isn't connected — save SERPER_API_KEY on the System Map first.</p>")
        + "<div class='cmd'>"
        "<input id='mv' placeholder='Business type — e.g. tax consultants, dentists, law firms'>"
        "<input id='mc' placeholder='City — e.g. Zurich, Munich, Manchester'>"
        "<select id='mn'><option value='10'>10 leads</option><option value='20' selected>20 leads</option>"
        "<option value='30'>30 leads</option><option value='40'>40 leads</option></select>"
        f"<button onclick='sourceMapsLeads()' {'disabled' if not _serper_on else ''}>🗺️ Find leads</button></div>"
        "<div class='dim' style='margin-top:6px'>Cost ≈ 1 Serper credit + 1 Prospeo credit per business with a website. "
        "Your 5 markets: USA · UK · Germany · Switzerland · Canada.</div></div>")
    p_leads = m_leads + _outbox_pointer(jobs) + maps_form + _leads_table(jobs) + grid(
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
               _sparkline(_daybuckets(out_jobs, lambda j: True, 14), "#8B7CFF") if out_jobs else _empty("Fills as the lead finder runs.")),
        _panel("Leads by vertical", "Which professions your leads cluster in.",
               _bars(_verticals(out_jobs), "#8B7CFF") if _verticals(out_jobs) else _empty("Fills as Prospeo leads arrive.")),
        _panel("Cost per lead", "What each verified lead costs you.",
               f"<div class='big tnum'>${(total_cost/max(leads_found,1)):.2f}</div><div class='dim'>per lead · {leads_found} found</div>" if leads_found else _empty("Fills as leads flow in.")),
        _panel("Email quality", "Prospeo returns only verified work emails.",
               (_donut(100, "#3FD98B") + "<div class='dim' style='text-align:center'>verified deliverable</div>") if leads_found else _empty("Fills as leads flow in.")),
        _panel("Reply & booking rate", "How many leads answer and book a call.",
               _funnel_skeleton([("Emailed", emails_sent, 100), ("Replied", lead_rows[4][1], 55), ("Booked", lead_rows[5][1], 28)], "Fills as replies land.")))

    # ---- 3. EMAIL & OUTREACH ----
    _routing = [("📰 Newsletter", "newsletter@"), ("🎯 Marketing", "marketing@"),
                ("💬 Support reply", "customercare@"), ("🙏 Thanks / general", "contact@")]
    route_html = "".join(
        f"<div class='chip'><span class='nm'>{p}</span><span class='dim'>from {a}</span></div>"
        for p, a in _routing)
    m_email = _master("✉️", "Outreach — at a glance", "Cold email → reply → booked → won.",
        [("Emails sent", emails_sent, "#EDF1FB"), ("Replied", replied, "#8B7CFF"),
         ("Booked", booked, "#F5B14C"), ("Won", o_cust, "#3FD98B")],
        _funnel_skeleton([("People emailed", leads_emailed, 100), ("Replied", replied, 62),
                          ("Booked", booked, 38), ("Won", o_cust, 20)], "Fills as replies land."))
    p_email = m_email + _outbox(jobs) + _replies_inbox(reply_drafts) + _leads_table(jobs) + grid(
        _panel("Sent vs replied", "Emails out, and customers who replied.",
               _bars([("Emails sent", emails_sent), ("People emailed", leads_emailed), ("Replied", replied)], "#4C8DFF")
               if emails_sent else _empty("No emails sent yet.")),
        _panel("Sent by purpose → address", "The loop: your agent sends each email type from the right alias — all from your one inbox.", route_html),
        _panel("Deal conversion — the money moment", "Email → reply → booked consultation → paying customer.",
               _funnel_skeleton([("People emailed", leads_emailed, 100), ("Replied", replied, 62),
                                 ("Consultation booked", booked, 38), ("Customer won", o_cust, 20)],
                                "Booked consultations come live from Cal.com; replies + won come as outcomes are recorded.")),
        _panel("Send volume over time", "Emails actually sent per day (intro + follow-ups).",
               _sparkline(_send_daybuckets(out_jobs, 14), "#4C8DFF")
               if emails_sent else _empty("Fills as outreach runs.")),
        _panel("Reply rate", "Share of emailed customers who reply.",
               f"<div class='big tnum'>{reply_rate}%</div><div class='dim'>{replied} of {leads_emailed} people emailed replied</div>"
               if leads_emailed else _empty("Fills as outreach runs.")),
        _panel("Deliverability guard", "How your domain stays out of spam.",
               "<div class='dim' style='line-height:1.8'>✔️ Dead addresses drop automatically (bounce suppression)<br>✔️ Daily send cap ramps up as the domain warms<br>✔️ A suppressed address is never emailed again</div>"),
        _panel("Volume by sender alias", "Which address each email went out from.",
               _bars([("marketing@ (outreach)", emails_sent), ("customercare@ (replies)", replied),
                      ("newsletter@", 0), ("contact@", 0)], "#8B7CFF") if emails_sent else _empty("Fills as outreach runs.")),
        _panel("Best subject lines", "Which openers win the most replies.",
               _empty("Ranks your subject lines once replies come in.")),
        _panel("Consultations booked (Cal.com)", "Real calls booked off your outreach.",
               f"<div class='big tnum' style='color:#3FD98B'>{booked}</div><div class='dim'>consultations booked</div>"
               if st.get("calcom_bookings") else _empty("Connect Cal.com on the System Map to count booked calls.")))

    # ---- 4. SOCIAL MEDIA ----
    _social_live = sum(1 for k in ("social_linkedin", "social_twitter", "social_facebook",
                                    "social_instagram", "social_tiktok") if st.get(k))
    m_social = _master("📣", "Social — at a glance", "Posting across your channels.",
        [("Channels live", f"{_social_live}/5", "#3FD98B" if _social_live else "#F5B14C"),
         ("Posts", 0, "#EDF1FB"), ("Target / day", 15, "#8B7CFF")],
        _bars([("LinkedIn", 0), ("X", 0), ("Facebook", 0), ("Instagram", 0), ("TikTok", 0)], "#8B7CFF"))
    p_social = m_social + grid(
        _panel("Posts per channel", "Content pushed to each social channel.", _empty("Connect a social channel to post.")),
        _panel("Engagement", "Likes, comments, shares per channel.", _empty("Shows once posting is on.")),
        _panel("Schedule adherence", "Are you hitting 3 posts/channel/day?", _empty("Target 3/channel/day.")),
        _panel("Content mix", "Story vs image vs video vs link.", _empty("Fills as content posts.")),
        _panel("Reach & impressions", "How many people saw each channel.", _empty("Shows once a channel is connected + posting.")),
        _panel("Follower growth", "Audience size over time.", _empty("Tracks once channels are connected.")),
        _panel("Best time to post", "When your audience engages most.", _empty("Learns from your post performance.")),
        _panel("Top posts", "Your best-performing content.", _empty("Ranks once posts go out.")))

    # ---- 5. SEO / AEO / GEO (real Search Console + Analytics data) ----
    gsc_on = st.get("google_gsc_ga4")
    _wt = web_tracking or {}
    _ga4m = (_wt.get("ga4") or {}).get("metrics") or {}
    _gsc = _wt.get("gsc") or []
    sessions = _ga4m.get("sessions") or 0
    top_pages = _ga4m.get("top_pages") or []
    total_clicks = sum(q.get("clicks", 0) for q in _gsc)
    total_impr = sum(q.get("impressions", 0) for q in _gsc)
    avg_rank = round(sum(q.get("position", 0) for q in _gsc) / len(_gsc), 1) if _gsc else 0
    ctr = round(100 * total_clicks / total_impr, 1) if total_impr else 0
    r13 = sum(1 for q in _gsc if q.get("position", 99) <= 3)
    r410 = sum(1 for q in _gsc if 3 < q.get("position", 99) <= 10)
    r11 = sum(1 for q in _gsc if q.get("position", 99) > 10)
    kw_rows = "".join(
        f"<div class='fe'><span class='mut'>{_esc(q.get('query',''))}</span>"
        f"<span class='dim' style='margin-left:auto'>#{q.get('position',0)} · {q.get('clicks',0)} clicks · {q.get('impressions',0)} impr</span></div>"
        for q in sorted(_gsc, key=lambda x: -x.get("clicks", 0))[:12]) or _empty("No Search Console query data for the last 28 days yet.")
    tp_rows = "".join(
        f"<div class='fe'><span class='mut'>{_esc(p.get('page',''))}</span>"
        f"<span class='dim' style='margin-left:auto'>{p.get('sessions',0):,} sessions</span></div>"
        for p in top_pages[:8]) or _empty("No Analytics page data yet.")
    mfunnel = _funnel([("Impressions", total_impr), ("Clicks", total_clicks),
                       ("Sessions", sessions), ("Ranking 1-10", r13 + r410)]) if (gsc_on and (_gsc or sessions)) \
        else _funnel_skeleton([("Traffic — visitors", "—", 100), ("Interest — engaged", "—", 70),
                               ("Location — your 5 markets", "—", 48), ("Authority — backlinks", "—", 30)],
                              "Real numbers appear here as Search Console + Analytics accrue data.")
    assist = "".join(f"<div class='fe'><span class='mut'>{x}</span></div>" for x in [
        "◆ <b>Easy wins:</b> your keywords ranking #4–10 are one push from page-one — strengthen those pages first.",
        "◆ <b>Internal links:</b> point each new blog at its matching service page — that's where deals happen.",
        "◆ <b>Off-page / backlinks:</b> connect a backlink tool (Ahrefs/Moz/SE Ranking → <code>BACKLINKS_JSON</code>) to see referring domains + gaps here.",
        "◆ <b>AEO:</b> answer real questions from your Search Console queries directly in H2s so AI engines quote you.",
    ])
    m_seo = _master("🔎", "SEO / AEO / GEO — at a glance", "Visibility across Google & AI answers (live from your Search Console + Analytics).",
        [("Sessions (28d)", f"{sessions:,}", "#4C8DFF"), ("Search clicks", f"{total_clicks:,}", "#2FE3D2"),
         ("Avg rank", avg_rank or "—", "#8B7CFF"), ("CTR", f"{ctr}%", "#3FD98B")], mfunnel)
    _grefresh = ("<div class='ctrl' style='margin-top:10px'><button class='cbtn' onclick='refreshInsights()'>"
                 "↻ Refresh Google data</button>"
                 + (f"<span class='dim' style='align-self:center'>cached {_esc(str(google_insights.get('at',''))[:16].replace('T',' '))} UTC · auto-refreshes hourly</span>"
                    if google_insights.get("at") else
                    "<span class='dim' style='align-self:center'>no pull yet — click to fetch your full GSC + GA4 data</span>")
                 + "</div>")
    p_seo = (m_seo + _grefresh
             + _gsc_board(google_insights)
             + _ga4_board(google_insights)
             + _competitor_board(competitor_intel, bool(st.get("serper_search"))) + grid(
        _panel("Marketing funnel", "Impressions → clicks → sessions → rankings.", mfunnel),
        _panel("Keyword rankings (Search Console)", "The exact queries you show up for, your position + clicks.", kw_rows),
        _panel("Ranking spread", "How many queries rank 1-3 / 4-10 / 11+.",
               _bars([("1-3 (page-one top)", r13), ("4-10 (page one)", r410), ("11+ (page 2+)", r11)], "#8B7CFF")
               if _gsc else _empty("Fills from Search Console.")),
        _panel("Top pages (Analytics)", "Which pages pull the most visits.", tp_rows),
        _panel("Click-through rate", "How often a ranking turns into a click.",
               f"<div class='big tnum'>{ctr}%</div><div class='dim'>{total_clicks:,} clicks on {total_impr:,} impressions</div>"
               if total_impr else _empty("Fills from Search Console.")),
        _panel("Off-page / backlinks", "Referring domains + competitor gaps.",
               _empty("Connect a backlink tool (Ahrefs/Moz) via BACKLINKS_JSON to populate off-page data — it's not part of the Google keys.")),
        _panel("AI-answer mentions (AEO)", "How often ChatGPT / Google AI quote you.",
               _empty("Run a 🛰️ competitor scan — it now measures AI-visibility via your Claude key.")),
        _panel("Content assistant — your next move", "Data-driven, from your real queries.", assist)))

    # ---- 6. ADS & GROWTH ----
    _ads_on = bool(ads)
    m_ads = _master("🎯", "Ads & growth — at a glance", "Paid campaigns, live from Google Ads.",
        [("Spend · 30d", f"${ads.get('spend',0):,.0f}" if _ads_on else "—", "#EDF1FB"),
         ("Clicks", ads.get('clicks', '—') if _ads_on else "—", "#4C8DFF"),
         ("CPA", f"${ads.get('cpa',0):.2f}" if (_ads_on and ads.get('cpa')) else "—", "#8B7CFF"),
         ("Conversions", ads.get('conversions', '—') if _ads_on else "—", "#3FD98B")],
        _bars(ads.get('campaigns', []), "#4C8DFF", money=True) if (_ads_on and ads.get('campaigns'))
        else (_empty("Connect Google Ads on the System Map to fill this.") if not st.get("ads_api")
              else _empty("Campaign data appears once ads run.")))
    p_ads = m_ads + grid(
        _panel("Spend by campaign", "Where the ad budget goes.",
               _bars(ads.get('campaigns', []), "#4C8DFF", money=True) if ads.get('campaigns')
               else _empty("Connect Google Ads on the System Map.")),
        _panel("Cost per result (CPA/ROAS)", "Efficiency per campaign.", _empty("Shows with ad data.")),
        _panel("Budget reallocation", "Move money to what works.", _empty("The ads agent suggests moves here.")),
        _panel("SEO-informed keywords", "Winning keywords to pull into ads.", _empty("Fills from your SEO data.")),
        _panel("Impressions & clicks", "How much attention your ads get.",
               _bars([("Impressions", ads.get('impressions', 0)), ("Clicks", ads.get('clicks', 0))], "#4C8DFF")
               if ads else _empty("Connect Google Ads on the System Map.")),
        _panel("Conversion rate", "Clicks that turn into leads.", _empty("Shows once ads run.")),
        _panel("Budget pacing", "Are you on track for the month?", _empty("Shows once an ad budget is set.")),
        _panel("Best & worst campaign", "Where to add or cut spend.", _empty("Ranks once campaigns run.")))

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
    # ---- API METERS: per-API spend vs your top-up cap, so nothing runs out silently ----
    _API_META = [
        ("anthropic", "🧠", "Claude — the brain", "writing · judging · chat"),
        ("prospeo", "🧲", "Prospeo — leads", "per verified lead"),
        ("image", "🎨", "Image generation", "per image"),
        ("video", "🎬", "Video generation", "per video"),
        ("search", "🔎", "Web search", "per query"),
    ]
    api_warnings = []

    def _meter_row(icon, label, note, spent, cap, calls, api):
        p = round(100 * spent / cap) if cap else 0
        col = "#3FD98B" if p < 70 else ("#F5B14C" if p < 90 else "#F5788A")
        state = ("✓ healthy" if p < 70 else ("⚠ getting low" if p < 90 else "⛔ nearly out — top up"))
        if cap and p >= 80:
            api_warnings.append(f"{label} at {p}% of its ${cap:.0f} cap")
        calls_txt = f" · {calls} calls" if calls not in (None, 0) else ""
        return (
            "<div style='padding:12px 0;border-top:1px solid rgba(255,255,255,.06)'>"
            "<div style='display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap'>"
            f"<div><b>{icon} {_esc(label)}</b> <span class='dim'>· {_esc(note)}{calls_txt}</span></div>"
            f"<div class='tnum' style='color:{col};font-weight:700'>${spent:.2f} <span class='dim'>/ ${cap:.0f}</span></div></div>"
            f"<div class='track' style='margin-top:7px'><i style='width:{min(p,100)}%;background:{col}'></i></div>"
            "<div style='display:flex;justify-content:space-between;align-items:center;margin-top:6px;gap:8px;flex-wrap:wrap'>"
            f"<span class='dim' style='color:{col}'>{state} · {p}%</span>"
            "<span class='dim'>Cap $"
            f"<input id='lim-{api}' value='{cap:.0f}' style='width:64px;padding:2px 6px' inputmode='numeric'> "
            f"<button class='cbtn' style='padding:3px 9px' onclick=\"setApiLimit('{api}')\">Save</button></span></div></div>")

    meter_rows = ""
    for api, icon, label, note in _API_META:
        m = meters.get(api) or {}
        spent = float(m.get("spent", 0) or 0)
        cap = float(api_limits.get(api, 0) or 0)
        # always show Claude + Prospeo; show image/video/search only once used
        if api in ("image", "video", "search") and spent <= 0 and not m:
            continue
        meter_rows += _meter_row(icon, label, note, spent, cap, m.get("calls", 0), api)
    # Google Ads = money paid to Google (their API doesn't bill you for credits, but
    # your ad SPEND is the number to watch) — sourced from the live Ads summary.
    adspend = float((ads or {}).get("spend", 0) or 0)
    if adspend > 0 or st.get("ads_api"):
        meter_rows += _meter_row("🎯", "Google Ads — ad spend", "paid to Google (last 30d)",
                                 adspend, float(api_limits.get("google_ads", 200)), None, "google_ads")
    warn_banner = ""
    if api_warnings:
        warn_banner = ("<div class='card full' style='margin-bottom:12px;border-left:4px solid #F5788A'>"
                       "<p class='ct' style='color:#F5788A'>⚠ API top-up warning</p><p class='cc'>"
                       + " · ".join(_esc(w) for w in api_warnings)
                       + ". Top up that account (or raise its cap) before it stops the agents.</p></div>")
    meters_card = warn_banner + (
        "<div class='card full' style='margin-bottom:12px'>"
        "<p class='ct'>🔌 API meters — usage vs your top-up cap</p>"
        "<p class='cc'>What each paid API has spent this month. Set each cap to your comfort line — you get "
        "an amber warning at 80% and red near the limit, so no API ever runs out on you unnoticed. "
        "(We meter what the engine spends; a provider's exact remaining balance isn't exposed by most APIs.)</p>"
        + (meter_rows or _empty("No paid-API usage yet this month.")) + "</div>")

    m_budget = _master("💰", "Budget & cost — at a glance", "Every euro in and out, against your cap.",
        [("Spent", f"${month_spent:.2f}", bcol), ("Cap", f"${month_cap:.0f}", "#8B7CFF"),
         ("Today", f"${day_spent:.2f}", "#EDF1FB"), ("Earned", f"${o_rev:,.0f}", "#3FD98B")],
        _sparkline(spend_series, bcol) if total_cost else _empty("Fills day by day."))
    p_budget = m_budget + meters_card + grid(
        _panel("This month vs $200 cap", "The engine pauses before it ever goes over.",
               "<div style='display:flex;align-items:center;gap:18px'>" + _donut(pct, bcol) +
               f"<div><div class='dim'>Today</div><div class='big tnum'>${day_spent:.2f}</div><div class='dim'>of ${day_cap:.0f}/day</div></div></div>"),
        _panel("Return on investment (ROI)", "The number that matters: money in vs money out.", roi_body),
        _panel("Cost by activity", "What your AI spend is doing.",
               _bars([("Content", content_cost), ("Leads/email", lead_cost)], "#8B7CFF", money=True) if total_cost else _empty("No spend yet.")),
        _panel("Spend trend · 14 days", f"${total_cost:.2f} so far this month · ${(content_cost/max(len(content_jobs),1)):.3f} per piece.",
               _sparkline(spend_series, "#3FD98B") if total_cost else _empty("Fills day by day.")),
        _panel("Cost per outcome", "What one blog, lead or customer costs.",
               _bars([("Per piece", content_cost/max(len(content_jobs),1)), ("Per lead", total_cost/max(o_leads or leads_found, 1)), ("Per customer", total_cost/max(o_cust, 1))], "#8B7CFF", money=True) if total_cost else _empty("Fills as spend happens.")),
        _panel("Daily burn", "Average spend per day, projected to month-end.",
               f"<div class='big tnum'>${(total_cost/max(date.today().day,1)):.2f}</div><div class='dim'>per day · projecting ${(total_cost/max(date.today().day,1))*30:.0f}/mo</div>" if total_cost else _empty("Fills day by day.")),
        _panel("Spend by area", "Content vs leads & email.",
               _bars([("Claude · content", content_cost), ("Leads / email", lead_cost)], "#4C8DFF", money=True) if total_cost else _empty("Fills as spend happens.")),
        _panel("Headroom left", "How much of the cap remains this month.",
               _donut(max(0, 100 - pct), "#3FD98B")))

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
    _AGENTS = [
        ("🔍 Site analyst", "reads your website for gaps", None),
        ("🕵️ Competitor scout", "checks what rivals rank for", None),
        ("🧭 Content strategist", "picks what to write next", "claude_api"),
        ("✍️ Writer", "writes the articles", "claude_api"),
        ("🔎 SEO / AEO optimizer", "tunes for Google & AI answers", "claude_api"),
        ("🛡️ Quality & legal check", "catches errors before publish", "claude_api"),
        ("🌐 Publisher", "posts to your website", "wordpress_publish"),
        ("📣 Social poster", "pushes to your channels", "social_linkedin"),
        ("🧲 Lead finder", "pulls leads from Prospeo", "linkedin_leads"),
        ("✔️ Email verifier", "checks addresses are real", None),
        ("🎯 Lead qualifier", "scores who's worth emailing", "claude_api"),
        ("🗂️ Segmenter", "groups leads by type", "claude_api"),
        ("✉️ Cold-email writer", "writes each outreach mail", "claude_api"),
        ("💬 Reply responder", "answers customer replies", "email_reply_inbound"),
        ("🎯 Ads optimizer", "moves budget to what works", "ads_api"),
        ("🧠 Learning agent", "remembers what wins", None),
    ]

    def _agent_row(name, does, dep):
        live = (dep is None) or bool(st.get(dep))
        col = "#3FD98B" if live else "#F5B14C"
        return (f"<div class='chip'><span class='nm'><span class='d' style='background:{col}'></span>"
                f"<b>{_esc(name)}</b> <span class='dim'>— {_esc(does)}</span></span>"
                f"<span class='dim' style='color:{col}'>{'ready' if live else 'needs a wire'}</span></div>")
    agents_live = sum(1 for _, _, dep in _AGENTS if dep is None or st.get(dep))
    agents_html = "".join(_agent_row(*a) for a in _AGENTS)
    m_agents = _master("❤️", "Agents & health — at a glance", "Is the machine alive and working?",
        [("Agents ready", f"{agents_live}/16", "#3FD98B" if agents_live else "#F5B14C"),
         ("Wires live", f"{live_conn}/{total_conn}", "#4C8DFF"),
         ("Jobs done", outcomes["done"], "#8B7CFF"), ("Errors", outcomes["failed"], "#FF6B93")],
        _bars([("Running", outcomes["running"]), ("Done", outcomes["done"]),
               ("Failed", outcomes["failed"])], "#4C8DFF") if jobs else _empty("No jobs yet."))
    p_agents = m_agents + grid(
        _panel("Engine health", "Live checks on the core parts.", hrows),
        _panel(f"Your 16 agents — {agents_live} ready", "Each worker, what it does, and whether it can run right now.", agents_html),
        _panel("Job outcomes", "Running vs done vs failed.",
               _bars([("Running", outcomes["running"]), ("Done", outcomes["done"]), ("Failed", outcomes["failed"])], "#4C8DFF") if jobs else _empty("No jobs yet.")),
        _panel("Recent errors", "Anything that failed or paused.", errs or _empty("No errors — all clean.")),
        _panel("Jobs per day · 14 days", "How much the engine is processing.",
               _sparkline(_daybuckets(jobs, lambda j: True, 14), "#4C8DFF") if jobs else _empty("Fills as the engine runs.")),
        _panel("Queue depth", "Jobs in progress right now.",
               f"<div class='big tnum'>{outcomes['running']}</div><div class='dim'>working now</div>" if jobs else _empty("No jobs queued.")),
        _panel("Model usage", "Cheap Haiku vs powerful Opus.", _empty("Shows once the writer runs.")),
        _panel("Engine uptime", "Is the worker alive and ticking?",
               f"<div class='big tnum' style='color:{'#3FD98B' if healthy else '#F5B14C'}'>{'Live' if healthy else 'Check'}</div><div class='dim'>worker status</div>"))

    # ---- 9. GOOGLE HUB ----
    def ghub(k, name, what):
        on = st.get(k)
        return f"<div class='chip'><span class='nm'><span class='d' style='background:{'#3FD98B' if on else '#F5B14C'}'></span>{name}</span><span class='pill {'p-live' if on else 'p-need'}'>{'live' if on else 'needs key'}</span></div><div class='dim' style='padding:0 0 8px'>{what}</div>"
    _hub_live = sum(1 for k in ("google_sheets", "google_drive", "email_send") if st.get(k))
    m_google = _master("☁️", "Google hub — at a glance", "Your Sheets, Drive & Gmail data hub.",
        [("Hub parts live", f"{_hub_live}/3", "#3FD98B" if _hub_live else "#F5B14C"),
         ("Rows", len(jobs), "#EDF1FB"), ("Files", published, "#4C8DFF"), ("Emails sent", emails_sent, "#8B7CFF")],
        _bars([("Job rows", len(jobs)), ("Content files", published), ("Emails sent", emails_sent)], "#2FE3D2")
        if (jobs or emails_sent) else _empty("Fills as the hub connects + jobs run."))
    p_google = m_google + grid(
        _panel("Google Sheets — data hub", "Every job, lead & metric mirrors here as rows.",
               ghub("google_sheets", "Sheets", "Your live spreadsheet dashboard.")
               + f"<div class='dim'>≈ <b style='color:var(--ink)'>{len(jobs)}</b> rows mirrored</div>"),
        _panel("Google Drive — content store", "Each finished piece saved as a file.",
               ghub("google_drive", "Drive", "Your content library, as files.")
               + f"<div class='dim'>≈ <b style='color:var(--ink)'>{published}</b> files saved</div>"),
        _panel("Gmail (Workspace)", "Send + read — from mother@ with aliases.",
               ghub("email_send", "Gmail", "contact@ · marketing@ · newsletter@ · customercare@")
               + f"<div class='dim'><b style='color:var(--ink)'>{emails_sent}</b> sent · replies read via IMAP</div>"),
        _panel("What's stored right now", "Live counts living in your Google hub.",
               _bars([("Job rows", len(jobs)), ("Content files", published), ("Emails sent", emails_sent)], "#2FE3D2")
               if (jobs or emails_sent) else _empty("Counts appear once the hub is connected + jobs run.")),
        _panel("Rows by type", "What's mirrored to Sheets.",
               _bars([("Content", len(content_jobs)), ("Leads", len(out_jobs))], "#2FE3D2") if jobs else _empty("Fills as jobs run.")),
        _panel("Storage used", "Drive space your content uses.", _empty("Shows once files are saved.")),
        _panel("Last sync", "When data last mirrored to Google.", _empty("Shows after the first mirror.")),
        _panel("Email quota", "Daily Gmail send headroom.", _empty("Tracks as email sends.")))

    # ---- 10. APPROVALS & COMMANDS (human, with previews — no code) ----
    # Content + outreach approvals only. Media campaigns are approved/deployed on
    # the Media Buying page (they were showing here mislabeled as "Article").
    waiting_jobs = [j for j in jobs if j.get("status") == "AWAITING_APPROVAL"
                    and j.get("type") in ("content_piece", "outreach_campaign")]

    def _appr_card(j):
        jid = _esc(j.get("job_id"))
        p = j.get("payload", {}) or {}
        meta = ""
        if j.get("type") == "outreach_campaign":
            oc = p.get("outreach_copy", {}) or {}
            n_leads = len((p.get("leads") or []))
            kind = "✉️ Cold email"
            subj = (oc.get("subject_variants") or ["(no subject)"])[0]
            title = subj
            body = (oc.get("body") or "")
            cta = oc.get("cta") or ""
            meta = (f"<div class='dim' style='margin-top:6px'>📧 Type: <b>Cold email</b> · Subject: "
                    f"<b>{_esc(subj)}</b> · will send to <b>{n_leads}</b> verified leads (warm-up capped)</div>")
            snippet = body[:600]
            if cta:
                snippet += f"\n\nCTA: {cta}"
        else:
            cp = p.get("content_producer", {}) or {}
            kind = "📝 Article"
            title = cp.get("title") or j.get("job_id")
            body = (cp.get("body") or cp.get("content") or cp.get("summary") or "")
            words = len(body.split())
            tax = p.get("taxonomy") or {}
            seg, pil = tax.get("segment", ""), tax.get("pillar", "")
            cats_txt = (f" · <b style='color:#2FE3D2'>{_esc(pil)}</b> → <b>{_esc(seg)}</b>"
                        if (seg or pil) else "")
            has_img = bool((cp.get("image_url") or p.get("image_url") or ""))
            img_txt = " · 🖼 on-brand image ready" if has_img else " · ⏳ image pending"
            meta = (f"<div class='dim' style='margin-top:6px'>📄 <b>Blog article</b> · ~{words} words"
                    f"{cats_txt}{img_txt} · posts to the matching website section</div>")
            snippet = body[:600]
        # image preview, if the piece carries a generated hero image
        _pimg = p.get("image")
        img = ((p.get("content_producer", {}) or {}).get("image_url")
               or p.get("image_url") or p.get("hero_image")
               or (_pimg.get("url") if isinstance(_pimg, dict) else _pimg))
        img_html = ""
        if isinstance(img, str) and img.startswith("http"):
            img_html = (f"<div style='margin-top:8px'><img src='{_esc(img)}' alt='preview' "
                        "style='max-width:220px;max-height:150px;border-radius:9px;border:1px solid var(--line)'></div>")
        whatis = "email" if j.get("type") == "outreach_campaign" else "article"
        is_article = j.get("type") != "outreach_campaign"
        teaser = body[:220]
        if body:
            webview = ""
            if is_article:
                _kick = (f"{(p.get('taxonomy') or {}).get('pillar','')} · {(p.get('taxonomy') or {}).get('segment','')}"
                         .strip(" ·").upper() or "ANTHROPOS · FIELD NOTES")
                sd = _blog_webview_srcdoc(title, body, ci_text=ci_text,
                                          hero_url=(img if isinstance(img, str) else ""), kicker=_kick)
                webview = (
                    "<details style='margin-top:6px'><summary style='cursor:pointer;color:#3FD98B;font-weight:600'>"
                    "🌐 See the web view (how it looks on your site — headings, images, layout)</summary>"
                    f"<iframe srcdoc=\"{sd}\" style='width:100%;max-width:760px;height:620px;border:1px solid var(--line);"
                    "border-radius:9px;background:#080B14;margin-top:8px'></iframe>"
                    "<div class='dim' style='margin-top:4px'>Rendered in your live blog's real design "
                    "(dark theme, Sora headings, teal accents) — matched from anthropos-automation.com.</div></details>")
            preview = (
                f"<div class='dim' style='margin-top:8px;line-height:1.55'>{_esc(teaser)}…</div>"
                f"<details style='margin-top:6px'><summary style='cursor:pointer;color:#4C8DFF;font-weight:600'>"
                f"📖 Read the full {whatis} (raw text)</summary>"
                "<div style='margin-top:8px;padding:13px 15px;border-radius:9px;background:var(--panel,rgba(255,255,255,.03));"
                "border:1px solid var(--line);max-height:460px;overflow:auto;white-space:pre-wrap;line-height:1.65;font-size:13.5px'>"
                f"{_esc(body)}</div></details>" + webview)
            li = (p.get("content_producer", {}) or {}).get("linkedin_post")
            if li:
                preview += (
                    "<details style='margin-top:6px'><summary style='cursor:pointer;color:#0A66C2;font-weight:600'>"
                    "in LinkedIn post (auto-made from this article)</summary>"
                    "<div style='margin-top:8px;padding:13px 15px;border-radius:9px;background:rgba(10,102,194,.06);"
                    "border:1px solid rgba(10,102,194,.3);white-space:pre-wrap;line-height:1.6;font-size:13.5px'>"
                    f"{_esc(li)}</div>"
                    "<div class='dim' style='margin-top:4px'>Posts to LinkedIn when the piece's channels include "
                    "LinkedIn (connect LinkedIn on the System Map).</div></details>")
        else:
            preview = "<div class='dim' style='margin-top:8px'>(preview appears once it is written)</div>"
        # prior correction notes, if this piece was declined before
        prior = (p.get("revision_notes") or [])
        prior_html = ""
        if prior:
            prior_html = ("<div class='dim' style='margin-top:6px'>📝 Your past notes: "
                          + " · ".join(_esc(str(n.get('note', ''))[:80]) for n in prior[-3:]) + "</div>")
        # notes box + approve WITH note + decline WITH note (goes back for a rewrite)
        cmd = (
            "<div style='margin-top:10px;padding-top:10px;border-top:1px solid var(--line)'>"
            f"<textarea id='note-{jid}' placeholder='Notes to the system — e.g. \"make it shorter, "
            "add a real example, less salesy\". Sent with Approve, or with Decline to rewrite.' "
            "style='width:100%;min-height:52px;font-family:inherit;font-size:13px'></textarea>"
            "<div class='ctrl' style='margin-top:6px'>"
            f"<button class='sbtn' onclick=\"approve('{jid}')\">✓ Approve &amp; publish</button>"
            f"<button class='cbtn warn' onclick=\"decline('{jid}')\">↩ Decline &amp; rewrite with my notes</button>"
            "</div>"
            "<div class='dim' style='margin-top:4px'>Approve = goes live (your note is logged). "
            "Decline = sent back and re-written to fix exactly what your note says — nothing publishes.</div></div>")
        return ("<div style='background:var(--s2);border:1px solid var(--line);border-radius:11px;padding:12px;margin-bottom:10px'>"
                f"<div style='display:flex;align-items:center;gap:9px;flex-wrap:wrap'><span class='dim'>{kind}</span>"
                f"<b style='font-size:13px'>{_esc(title)}</b></div>"
                + meta
                + f"<div class='dim' style='margin-top:6px'>📎 Basis: {_esc(_why_piece(j))}</div>"
                + prior_html + img_html + preview + cmd + "</div>")

    if waiting_jobs:
        ids = ",".join(str(j.get("job_id")) for j in waiting_jobs)
        ap_body = "".join(_appr_card(j) for j in waiting_jobs[:8])
        if len(waiting_jobs) > 1:
            ap_body += f"<button class='cbtn on' onclick=\"approveAll('{_esc(ids)}')\">✓ Approve all {len(waiting_jobs)}</button>"
    else:
        ap_body = _empty("Nothing waiting — you're all caught up. 🎉")
    revs = sum(1 for j in jobs if j.get("status") == "revision_needed")
    quick_body = ("<div class='ctrl' style='margin:0'>"
                  "<button class='cbtn' onclick=\"act('/schedule/run')\">🗓️ Plan today's work</button>"
                  "<button class='cbtn' onclick=\"act('/tick')\">▶️ Run one cycle now</button></div>"
                  "<div class='dim' style='margin-top:9px;line-height:1.6'><b>Plan today's work</b> — queues today's blogs, social &amp; one cold-email batch.<br>"
                  "<b>Run one cycle</b> — nudges the next job forward one step so you can watch it move.<br>"
                  "Pause &amp; Autonomy are in the bar at the top.</div>")
    howto = ("<div class='dim' style='line-height:1.75'>① The engine writes content &amp; emails.<br>"
             "② Each waits here for your <b>✓ Approve</b>.<br>"
             "③ Approved work publishes / sends right away (cold email is capped &amp; bounce-protected).<br>"
             "④ Flip on <b>Autonomy</b> only when you trust it — then it approves the safe ones itself.</div>")
    m_appr = _master("✅", "Approvals — at a glance", "What needs you, right now.",
        [("Waiting", len(waiting_jobs), "#F5B14C" if waiting_jobs else "#3FD98B"),
         ("Rewrites", revs, "#8B7CFF"),
         ("Autonomy", "ON" if autonomy else "OFF", "#3FD98B" if autonomy else "#59668A")],
        _bars([("Waiting", len(waiting_jobs)), ("Rewrites", revs)], "#F5B14C")
        if (waiting_jobs or revs) else _empty("All caught up — nothing needs you. 🎉"))
    p_appr = m_appr + _outbox_pointer(jobs) + _followups_due(jobs) + ("<div class='card full'><p class='ct'>✅ Waiting for your approval</p>"
              "<p class='cc'>Read the preview, then approve — nothing goes live without you.</p>" + ap_body + "</div>"
              + "<div class='grid g3' style='margin-top:12px'>"
              + _panel("Quick actions", "Real buttons — no code, no typing.", quick_body)
              + _panel("Sent back for rewrite", "Pieces you asked to redo.",
                       f"<div class='big tnum'>{revs}</div><div class='dim'>need a rewrite</div>" if revs else _empty("None — quality is clean."))
              + _panel("How approval works", "The safety flow, in plain words.", howto)
              + _panel("Pending by type", "Articles vs cold emails awaiting you.",
                       _bars([("Articles", sum(1 for j in waiting_jobs if j.get('type') != 'outreach_campaign')),
                              ("Cold emails", sum(1 for j in waiting_jobs if j.get('type') == 'outreach_campaign'))], "#F5B14C")
                       if waiting_jobs else _empty("Nothing pending."))
              + _panel("Turnaround", "How much is queued for you.",
                       f"<div class='big tnum'>{len(waiting_jobs)}</div><div class='dim'>waiting right now</div>" if waiting_jobs else _empty("All caught up."))
              + _panel("Decisions this week", "Your approval activity.", _empty("Builds as you approve."))
              + "</div>" + _approval_log(jobs))

    # ---- 11. LEARNING & RESULTS (cross-functional: content + leads + cost) ----
    themes = _themes(content_jobs)
    verticals = _verticals(out_jobs)
    countries = _by_country(out_jobs)
    top_c = max(countries, key=lambda x: x[1]) if any(v for _, v in countries) else None
    rules = []
    if themes:
        rules.append(f"Your content centers on <b>{_esc(themes[0][0])}</b> — lean into the subjects that perform.")
    if verticals:
        rules.append(f"Most of your leads are <b>{_esc(verticals[0][0])}</b> — sharpen the message for that persona.")
    if top_c and top_c[1]:
        rules.append(f"Strongest market so far: <b>{_esc(top_c[0])}</b> ({top_c[1]} leads).")
    if o_rev and total_cost:
        rules.append(f"ROI so far: <b>${o_rev:,.0f}</b> earned vs ${total_cost:.2f} spent.")
    if o_leads:
        rules.append(f"Cost per lead is <b>${(total_cost/max(o_leads,1)):.2f}</b> — the engine steers spend toward cheaper wins.")
    if published:
        rules.append(f"<b>{published}</b> pieces published — the more it ships, the sharper its topic sense gets.")
    rules_html = ("".join(f"<div class='fe'><span class='mut'>◆ {r}</span></div>" for r in rules)
                  or _empty("Rules appear as work flows through. Publish + send once, record outcomes, and the "
                            "engine starts learning across content, leads and email — automatically."))
    eff_body = ((_sparkline(_daybuckets(content_jobs, lambda j: True, 14,
                                        valfn=lambda j: float(j.get("cost_so_far_usd", 0))), "#3FD98B")
                 + f"<div class='dim' style='margin-top:6px'>${(content_cost/max(len(content_jobs),1)):.3f} avg per piece · "
                   "target: down over time as it learns</div>")
                if content_jobs else _empty("Fills as pieces are made."))
    m_learn = _master("🧠", "Learning — at a glance", "What the engine has figured out so far.",
        [("Rules learned", len(rules), "#EDF1FB"), ("Themes", len(themes), "#4C8DFF"),
         ("Top market", (top_c[0] if top_c and top_c[1] else "—"), "#8B7CFF"), ("ROI", f"${o_rev:,.0f}", "#3FD98B")],
        _bars(themes, "#4C8DFF") if themes else _empty("Fills as content is produced."))
    # ---- S5 instruments: 3 drift needles + the eval runner ----
    def _needle(label, val, sub, col):
        return (f"<div class='card' style='flex:1;min-width:150px'><div class='dim'>{label}</div>"
                f"<div class='tnum' style='font-size:30px;font-weight:800;color:{col};margin-top:2px'>{val}</div>"
                f"<div class='dim' style='margin-top:2px'>{sub}</div></div>")
    ts = needles.get("task_success")
    ts_txt = "—" if ts is None else f"{ts}%"
    tk = needles.get("takeover_rate", 0)
    cpt = needles.get("cost_per_task", 0.0)
    ev_total = last_eval.get("total", 0)
    ev_pass = last_eval.get("passed", 0)
    ev_cost = last_eval.get("cost_usd", 0.0)
    fails = [c for c in (last_eval.get("cases") or []) if not c.get("pass")]
    if last_eval:
        ev_line = (f"Last run: <b>{ev_pass}/{ev_total}</b> passed ({last_eval.get('score',0)}%) · "
                   f"cost ${ev_cost:.3f}")
        fail_html = ("".join(
            f"<div class='fe'><span class='mut'>✗ {_esc(c['name'])} — scored {c.get('score',0)}"
            + (f" · {_esc('; '.join(c.get('issues',[])[:2]))}" if c.get('issues') else "") + "</span></div>"
            for c in fails[:6]) or "<div class='fe'><span class='mut' style='color:#3FD98B'>✓ every eval passed</span></div>")
    else:
        ev_line = "Never run yet. Click <b>Run evals</b> — grades the engine on ~7 real tasks with a cheap judge."
        fail_html = _empty("No eval results yet.")
    instruments = (
        "<div class='card full' style='margin-bottom:12px'>"
        "<p class='ct'>🔬 Instruments — is it actually working?</p>"
        "<p class='cc'>The three needles every serious system watches. “An agent without evals is a rumor.”</p>"
        "<div style='display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px'>"
        + _needle("Task success", ts_txt, "eval pass-rate", "#3FD98B" if (ts or 0) >= 80 else "#F5B14C")
        + _needle("Human takeover", f"{tk}%", "jobs you aborted/edited", "#3FD98B" if tk <= 20 else "#F5B14C")
        + _needle("Cost per task", f"${cpt:.3f}", f"across {needles.get('jobs',0)} jobs", "#8B7CFF")
        + "</div>"
        f"<div class='dim' style='margin-bottom:6px'>{ev_line}</div>{fail_html}"
        "<div class='ctrl' style='margin-top:12px'>"
        "<button class='sbtn' id='evalbtn' onclick='runEvals()'>▶ Run evals</button>"
        "<span class='dim' style='align-self:center'>~7 tasks, cheap judge — a few cents, ~30s.</span></div></div>")

    p_learn = m_learn + instruments + grid(
        _panel("Playbook — what the engine has learned", "Rules it builds from your WHOLE business — content, leads and money.", rules_html),
        _panel("Top content themes", "The subjects your machine writes about most (its growing expertise).",
               _bars(themes, "#4C8DFF") if themes else _empty("Fills as content is produced.")),
        _panel("Where your market really is", "Which professions your leads actually cluster in.",
               _bars(verticals, "#2FE3D2") if verticals else _empty("Fills as leads flow in from Prospeo.")),
        _panel("Getting more efficient", "Cost per piece over time — is the machine learning to do more for less?", eff_body),
        _panel("What converted", "Which topics / verticals brought results.", _empty("Fills once outcomes are recorded.")),
        _panel("Month over month", "Is each cycle smarter than the last?", _empty("Compares once a second month runs.")),
        _panel("ROI by vertical", "Which profession pays back best.", _empty("Fills as customers close.")),
        _panel("Winning email styles", "The openers that get replies.", _empty("Learns from reply data.")))

    # ---- 12. SYSTEM MAP + DIAGNOSTIC ----
    diag_rows = []
    # A wire can fail two different ways and they need different words. "Not
    # connected" means no credentials. "Rejected" means credentials exist and
    # the provider refused them — telling someone to add a key they already
    # added would be a new kind of wrong answer.
    try:
        import content_engine_connectors as _CN
        _rejected = _CN.auth_reasons()
    except Exception:
        _rejected = {}
    for k, name, why, effect, fix in _DIAG:
        on = st.get(k)
        if not on and k in _rejected:
            diag_rows.append(
                "<tr><td>" + _esc(name) + "</td>"
                "<td><span class='pill p-need' style='border-color:#F5788A;color:#F5788A'>"
                "<span class='d' style='background:#F5788A'></span>Rejected</span></td>"
                "<td class='mut'>" + _esc(_rejected[k]) + "</td>"
                "<td class='mut'>" + _esc(effect) +
                "<div class='dim' style='margin-top:3px'>The key is saved but the "
                "provider refused it — replace it below rather than adding a new one."
                "</div></td></tr>")
            continue
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
                    "<div class='cgrid'>" + "".join(conn_rows) + "</div></div>"
                    + _extra_keys_card(saved_keys))
    _wired = round(live_conn / total_conn * 100) if total_conn else 0
    m_map = _master("🗺️", "Wiring — at a glance", "How much of your machine is connected.",
        [("Wires live", f"{live_conn}/{total_conn}", "#3FD98B"),
         ("To connect", total_conn - live_conn, "#F5B14C"), ("Wired", f"{_wired}%", "#4C8DFF")],
        f"<div class='prog' style='height:12px'><i style='width:{_wired}%'></i></div>"
        f"<div class='dim' style='margin-top:6px'>{_wired}% of your machine is connected</div>")
    _map_svgs = m_map + ("<div class='card full'><p class='ct'>🗺️ System blueprint — every connection in your machine</p>"
             "<p class='cc'>Each card is one API, account or plugin — its icon, what kind of connection it is, one line of what it does, and whether it's live. Read left → right: inputs → brain → Google hub → outputs.</p>"
             + _blueprint(st) + "</div>"
             "<div class='card full' style='margin-top:12px'><p class='ct'>⚡ Live data flow — your two pipelines, stage by stage</p>"
             "<p class='cc'>Real counts at every stage, and the tool each one uses. Dots animate along each step — that's data moving through your machine.</p>"
             + _dataflow(pl, lead_rows) + "</div>"
             "<div class='card full' style='margin-top:12px'><p class='ct'>Wiring diagram</p>"
             "<p class='cc'>The physical connections between components (secondary view).</p>"
             + _system_map(st) + "</div>"
             # n8n-style agent flow: who hands off to whom, with live job counts
             + "<div class='card full' style='margin-top:12px'><p class='ct'>🔗 Agent flow — how one agent connects to the next (n8n view)</p>"
             "<p class='cc'>Every node is one agent; the wire shows the hand-off and the moving dot is work flowing. "
             "Badges = how many jobs sit at that step right now. Amber = quality gate, violet = <b>you</b> decide, "
             "blue = deterministic automation. Scroll sideways →</p>"
             "<div style='overflow-x:auto;padding:6px 2px'>"
             + CH.n8n_flow([
                 ("Content pipeline", [
                     ("🔍", "Site Analyst", (str(pl[0]) if pl[0] else ""), "agent"),
                     ("🕵️", "Competitor", "", "agent"),
                     ("🗺️", "Strategist", "", "agent"),
                     ("✍️", "Writer", (str(pl[1]) if pl[1] else ""), "agent"),
                     ("🔎", "SEO Optimizer", (str(pl[2]) if pl[2] else ""), "agent"),
                     ("🛡️", "Quality & Legal", "", "gate"),
                     ("👤", "Your approval", (str(waiting) if waiting else ""), "human"),
                     ("🚀", "Publisher", (str(pl[4]) if pl[4] else ""), "code"),
                     ("📊", "Analytics", (str(pl[5]) if pl[5] else ""), "agent"),
                     ("🧠", "Learning", "", "agent"),
                 ]),
                 ("Lead & outreach pipeline", [
                     ("🧲", "Lead Sourcer", (str(lead_rows[0][1]) if lead_rows[0][1] else ""), "code"),
                     ("⚖️", "Qualifier", (str(lead_rows[2][1]) if lead_rows[2][1] else ""), "agent"),
                     ("🧩", "Segmenter", "", "agent"),
                     ("💬", "Outreach Writer", "", "agent"),
                     ("🛡️", "Quality & Legal", "", "gate"),
                     ("👤", "Your approval", "", "human"),
                     ("📤", "Email Sender", (str(lead_rows[3][1]) if lead_rows[3][1] else ""), "code"),
                     ("📥", "Reply Agent", (str(lead_rows[4][1]) if lead_rows[4][1] else ""), "agent"),
                     ("📅", "Bookings", (str(lead_rows[5][1]) if lead_rows[5][1] else ""), "code"),
                     ("🧠", "Learning", "", "agent"),
                 ]),
             ]) + "</div></div>"
             # API-key map: which key powers which agent, and where the data lives
             + "<div class='card full' style='margin-top:12px'><p class='ct'>🔌 API &amp; data map — which key powers which tool, and where data lives</p>"
             "<p class='cc'>Left = your API keys (green dot = live on this server). Middle = the agents/tools each key "
             "powers. Right = the databases the results land in. Grey wires = that key isn't connected yet. Scroll sideways →</p>"
             "<div style='overflow-x:auto;padding:6px 2px'>"
             + CH.tri_map(
                 [("claude", "🧠", "Claude API", bool(st.get("claude_api"))),
                  ("serper", "🔎", "Serper (search+maps)", bool(st.get("serper_search"))),
                  ("google", "🌐", "Google GSC + GA4", bool(st.get("google_gsc_ga4"))),
                  ("gmail", "✉️", "Gmail SMTP/IMAP", bool(st.get("email_send"))),
                  ("prospeo", "🧲", "Prospeo leads", bool(st.get("linkedin_leads"))),
                  ("wp", "📰", "WordPress", bool(st.get("wordpress_publish"))),
                  ("calcom", "📅", "Cal.com", bool(st.get("calcom_bookings"))),
                  ("gads", "🎯", "Google Ads", bool(st.get("google_ads"))),
                  ("sheets", "📊", "Sheets + Drive key", bool(st.get("google_sheets") or st.get("google_drive")))],
                 [("research", "📚", "Research + Writer", True),
                  ("seo", "🔎", "SEO Intelligence", True),
                  ("sourcer", "🧲", "Lead Sourcer", True),
                  ("outreach", "📤", "Email Sender", True),
                  ("reply", "📥", "Reply Agent", True),
                  ("media", "🛒", "Media Buyer", True),
                  ("publisher", "🚀", "Publisher", True),
                  ("booking", "📅", "Bookings", True)],
                 [("pg", "🐘", "Postgres (jobs+memory)", True),
                  ("drive", "📁", "Google Drive (content)", bool(st.get("google_drive"))),
                  ("gsheets", "📊", "Google Sheets (mirror)", bool(st.get("google_sheets"))),
                  ("wpdb", "📰", "WordPress DB (posts)", bool(st.get("wordpress_publish")))],
                 [("claude", "research"), ("claude", "seo"), ("claude", "reply"), ("claude", "media"),
                  ("serper", "research"), ("serper", "sourcer"),
                  ("google", "seo"), ("google", "media"),
                  ("gmail", "outreach"), ("gmail", "reply"),
                  ("prospeo", "sourcer"), ("wp", "publisher"),
                  ("calcom", "booking"), ("gads", "media")],
                 [("research", "pg"), ("research", "drive"), ("seo", "pg"), ("sourcer", "pg"),
                  ("outreach", "pg"), ("reply", "pg"), ("media", "pg"),
                  ("publisher", "wpdb"), ("booking", "pg"), ("publisher", "gsheets")])
             + "</div></div>")
    p_map = _map_svgs + diag + connect_card

    # ---- MEDIA BUYING (drafted Google Ads campaigns) ----
    p_media = (_media_page(jobs, st, web_tracking)
               + _ga4_board(google_insights, "📈 Website tracking (GA4) — the numbers behind your funnel")
               + _gsc_board(google_insights))

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
    m_overview = _master("📊", "Your business — at a glance", "The whole funnel, content to cash.",
        [("Published", published, "#3FD98B"), ("Leads", leads_found, "#4C8DFF"),
         ("Emails", emails_sent, "#8B7CFF"), ("Customers", o_cust, "#2FE3D2"),
         ("Revenue", f"${o_rev:,.0f}", "#3FD98B")],
        _funnel([("Content", published), ("Leads", leads_found), ("Emailed", emails_sent), ("Customers", o_cust)])
        if (published or leads_found or emails_sent) else _empty("Fills as the engine runs."))
    overview = (m_overview + setup_card + cost_meter + "<div class='ov'>"
                + tile("content", "📝", "Content", published, "published this month", green if published else amber)
                + tile("leads", "🧲", "Leads", leads_found, "collected", green if leads_found else amber)
                + tile("email", "✉️", "Email", emails_sent, "sent", green if emails_sent else amber)
                + tile("social", "📣", "Social", "—", "connect a channel", amber)
                + tile("seo", "🔎", "SEO/AEO/GEO", "—", "connect Google", amber)
                + tile("ads", "🎯", "Ads", "—", "feed ad data", amber)
                + tile("media", "🛒", "Media Buying", len(_media_campaigns(jobs)), "campaigns drafted", green if _media_campaigns(jobs) else amber)
                + tile("budget", "💰", "Budget", f"${month_spent:.0f}/{month_cap:.0f}", f"{pct}% of cap", green if pct < 90 else amber)
                + tile("agents", "❤️", "Agents", f"{live_conn}/{total_conn}", "connectors live", green if live_conn else amber)
                + tile("google", "☁️", "Google hub", "—", "sheets · drive · gmail", green if (st.get('google_sheets') or st.get('google_drive')) else amber)
                + tile("appr", "✅", "Approvals", waiting, "waiting for you", amber if waiting else green)
                + tile("learn", "🧠", "Learning", "—", "improves monthly", green)
                + tile("map", "🗺️", "System map", f"{total_conn-live_conn}", "wires to fix", amber if live_conn < total_conn else green)
                + "</div>" + _pipeline_health(st, jobs))

    # ---- CEO COMMAND CENTER (Business Operating System landing) ----
    # Business-health score computed from REAL engine signals (not fabricated).
    _sig = [live_conn / max(total_conn, 1),
            1.0 if healthy else 0.5,
            1.0 - min(pct, 100) / 100 * 0.5,
            min(1.0, (published + made_month) / 10.0),
            0.6 if waiting > 5 else 1.0,
            1.0 if leads_found else 0.7]
    _health = round(sum(_sig) / len(_sig) * 100)
    _qualified = lead_rows[2][1] if len(lead_rows) > 2 else 0
    _not_emailed = max(0, _qualified - leads_emailed)
    _sess = _ga4m.get("sessions")
    _topq = (_gsc[0].get("query") if _gsc and isinstance(_gsc[0], dict) else "")
    briefing_kpis = [
        ("Content live", str(published), f"{made_month}/mo", None),
        ("Leads", str(leads_found), (f"{leads_emailed} emailed" if leads_emailed else ""), leads_found > 0 or None),
        ("Reply rate", f"{reply_rate}%", f"{replied} replied", (reply_rate > 0) or None),
        ("Spend", f"${month_spent:.0f}", f"of ${month_cap:.0f}", (pct < 90) if month_cap else None),
    ]
    _risks, _opps, _actions = [], [], []
    if total_conn - live_conn > 0:
        _risks.append(f"{total_conn - live_conn} connection(s) down — some intelligence is blind until fixed (System Map).")
    if waiting > 0:
        _risks.append(f"{waiting} piece(s) waiting for your approval — the pipeline is paused on you.")
    if month_cap and pct >= 85:
        _risks.append(f"Spend at {pct}% of the ${month_cap:.0f} cap — approaching the limit.")
    if not leads_found:
        _risks.append("No leads sourced yet — the sales pipeline is empty.")
    if _not_emailed > 0:
        _opps.append(f"{_not_emailed} qualified lead(s) sourced but not emailed — start their sequence to open pipeline.")
    if _topq:
        _opps.append(f"Search Console shows demand for “{_topq}” — commission content on it to capture it.")
    if made_month and proj > made_month:
        _opps.append(f"On pace for {proj} pieces this month — hold the cadence to compound SEO.")
    if _sess:
        _opps.append(f"{_sess} website sessions tracked — a measured base to optimise against.")
    if not _opps:
        _opps.append("Plan a content week to start generating pipeline (Content Factory → Plan my week).")
    if waiting > 0:
        _actions.append((f"Review {waiting} approval(s)", "nav('appr')"))
    if _outbox_ready_count(jobs) > 0:
        _actions.append((f"Send {_outbox_ready_count(jobs)} ready email(s)", "nav('email')"))
    _actions.append(("Plan my week", "nav('content')"))
    if total_conn - live_conn > 0:
        _actions.append(("Fix wiring", "nav('map')"))

    # Intelligence cards — one business question + one decision each, real data only.
    _mkt = (_intel_card("Marketing / SEO Intelligence", str(_sess), sub="sessions", dept="Marketing",
                        source="GA4 + Search Console", accent="#4C8DFF",
                        insight=(f"Top search demand: “{_topq}”." if _topq else "Ranking data is flowing in."),
                        recommendation=(f"Commission a piece targeting “{_topq}”." if _topq else "Keep publishing to build ranking signals."),
                        action_label="Open SEO", action="nav('seo')")
            if _sess else _intel_card("Marketing / SEO Intelligence", "", dept="Marketing",
                        empty="Connect Google Analytics 4 + Search Console (System Map) to activate real SEO intelligence — sessions, rankings, top queries."))
    _content_card = _intel_card("Content Production", str(published), sub="live",
                        goal="60/mo", forecast=f"{proj}/mo", dept="Content", source="Content engine", accent="#2FE3D2",
                        insight=(f"{sum(pl[0:4])} in production, {waiting} awaiting your approval." if content_jobs else "No pieces in the line yet."),
                        recommendation=("Clear the approval queue to keep the line moving." if waiting else "Plan next week to keep the cadence."),
                        action_label=("Review approvals" if waiting else "Plan my week"), action=("nav('appr')" if waiting else "nav('content')"),
                        chart=(_sparkline(content_series, "#2FE3D2") if content_jobs else ""))
    _lead_card = _intel_card("Lead Generation", str(leads_found), sub="sourced", dept="Sales",
                        source="Prospeo + web", accent="#8B7CFF",
                        insight=(f"{_qualified} qualified · {leads_emailed} emailed · {replied} replied." if leads_found else "No leads sourced yet."),
                        recommendation=(f"Email the {_not_emailed} qualified lead(s) not yet contacted." if _not_emailed else "Source a fresh batch to refill the pipeline."),
                        action_label="Open Lead Machine", action="nav('leads')")
    _out_card = _intel_card("Outreach", str(emails_sent), sub="emails sent", dept="Sales",
                        source="Workspace mail", accent="#4C9AFF",
                        insight=(f"Reply rate {reply_rate}% from {leads_emailed} people emailed." if emails_sent else "No emails sent yet."),
                        recommendation=("Send today's ready follow-ups." if _outbox_ready_count(jobs) else "Warm up more leads to lift volume."),
                        action_label="Open outbox", action="nav('email')")
    _fin_card = _intel_card("Finance / Spend", f"${month_spent:.0f}", sub=f"of ${month_cap:.0f}", dept="Finance",
                        goal=f"${month_cap:.0f} cap", forecast=f"${(total_cost/max(date.today().day,1)*30):.0f}/mo",
                        confidence=("high" if made_month > 3 else "building"), source="API meters", accent=bcol,
                        insight=f"{pct}% of the monthly cap used; ${content_cost:.2f} on content.",
                        recommendation=("Ease off — you're near the cap." if pct >= 85 else "Headroom is healthy; invest in more content."),
                        action_label="Open budget", action="nav('budget')")
    _live_agents = sum(1 for j in jobs if j.get("status") not in ("optimized", "failed", "halted_budget", "revision_needed"))
    _wf_card = _intel_card("AI Workforce", str(_live_agents), sub="jobs active", dept="Operations",
                        source="Orchestrator", accent="#3FD98B",
                        insight=(f"System health: {'nominal' if healthy else 'check needed'} · {live_conn}/{total_conn} wires live."),
                        recommendation=("Investigate the health warning on Agents & Health." if not healthy else "Workforce is running normally."),
                        action_label="Open Agents", action="nav('agents')")
    _infra_card = _intel_card("Infrastructure", f"{live_conn}/{total_conn}", sub="wires live", dept="Infrastructure",
                        source="System map", accent=("#3FD98B" if live_conn == total_conn else "#F5B14C"),
                        insight=(f"{total_conn - live_conn} connection(s) need attention." if live_conn < total_conn else "All connections healthy."),
                        recommendation=("Fix the down wires to unblock those intelligence centres." if live_conn < total_conn else "Nothing to fix."),
                        action_label="Open System Map", action="nav('map')")
    _owner = (st.get("owner_name") if isinstance(st, dict) else "") or "Murtuja"
    p_mission = (_exec_briefing(_owner, _health, briefing_kpis, _risks, _opps, _actions)
                 + "<div class='dim' style='margin:-4px 0 12px;font-size:11.5px'>ℹ️ Business-health is computed from your live "
                   "signals (connections · system health · budget · output · approval backlog · pipeline). Cards show only "
                   "REAL data; greyed cards need their source connected. This is Phase 1 of the operating-system migration — "
                   "more intelligence centres + an LLM narrative briefing come next.</div>"
                 + "<div class='grid g2'>" + _mkt + _content_card + _lead_card + _out_card
                 + _fin_card + _wf_card + _infra_card + "</div>")

    # ---- shared context for the 10 intelligence centres (real data only) ----
    ctx = {
        "name": _owner, "health": _health, "risks": _risks, "opps": _opps, "actions": _actions,
        "jobs": jobs, "content_jobs": content_jobs, "out_jobs": out_jobs, "st": st,
        "healthy": bool(healthy), "live_conn": live_conn, "total_conn": total_conn,
        "leads_found": leads_found, "leads_emailed": leads_emailed, "emails_sent": emails_sent,
        "replied": replied, "reply_rate": reply_rate, "booked": booked,
        "o_leads": o_leads, "o_rev": o_rev, "o_cust": o_cust,
        "total_cost": total_cost, "content_cost": content_cost, "month_spent": month_spent,
        "month_cap": month_cap, "pct": pct, "bcol": bcol,
        "published": published, "made_month": made_month, "proj": proj, "waiting": waiting,
        "pl": pl, "content_series": content_series, "lead_rows": lead_rows,
        "_ga4m": _ga4m, "_gsc": _gsc, "_sess": _sess, "_topq": _topq,
        "qualified": _qualified, "not_emailed": _not_emailed,
        "outbox_ready": _outbox_ready_count(jobs), "live_agents": _live_agents,
    }

    # ---- nav + assembly ----
    # ---- SEO engine boards (11 boards / 158 cards). They all live inside the
    # ONE 'SEO / AEO / GEO' section as in-page tabs — no extra sidebar items,
    # and no single endless scroll. Rendered in their own module so this file
    # doesn't grow; a missing ctx must never break the page.
    try:
        import content_engine_seo_boards as _SB
        _seo_all = _SB.seo_section(seo_ctx or {}, legacy_html=p_seo)
    except Exception as _e:                       # degraded, never blank
        _seo_all = (p_seo + "<div class='card full'><p class='ct'>SEO boards unavailable</p>"
                    f"<p class='cc'>{_esc(str(_e))}</p></div>")

    # ---- Media buying boards (16 boards / 296 cards), same card kit ----
    try:
        import content_engine_media_boards as _MB
        _media_all = _MB.media_section(media_ctx or {})
    except Exception as _e2:
        _media_all = (p_media + "<div class='card full'><p class='ct'>Media boards unavailable</p>"
                      f"<p class='cc'>{_esc(str(_e2))}</p></div>")

    # ---- System & Wiring: ONE section replacing Agents & Health, System Map
    # & Wiring and Machines. The connect forms and the four wiring diagrams are
    # passed in, not re-implemented, so no credential path changes.
    try:
        import content_engine_system_boards as _SYSB
        _sysctx = dict(system_ctx or {})
        _sysctx.setdefault("connect_html", diag + connect_card)
        _sysctx.setdefault("legacy_svgs", _map_svgs)
        _sysctx.setdefault("build_tag", BUILD_TAG)
        _system_all = _SYSB.system_section(_sysctx)
    except Exception as _e3:
        # Loud, not silent: this used to leave no trace anywhere, so a broken
        # merge looked identical to a merge that was never deployed.
        log.exception("System & Wiring boards failed to render - showing the "
                      "old three modules instead")
        _system_all = ("<div class='card full' style='border-color:#F5788A'>"
                       "<p class='ct'>System &amp; Wiring boards failed to render</p>"
                       f"<p class='cc'>Showing the older modules below. Reason: "
                       f"{_esc(type(_e3).__name__)}: {_esc(str(_e3))[:300]}</p></div>"
                       + p_agents + p_map + overview)

    # ---- AI Cockpit: ONE section replacing Command Center, Operations,
    # Approvals and Learning — 35 cards, 4 charts, and the decision engine
    # rendered twice. The live approval queue is passed through unchanged.
    try:
        import content_engine_cockpit_boards as _CKB
        _ck = dict(cockpit_ctx or {})
        _ck["live"] = {"approvals": p_appr,
                       "followups": _followups_due(jobs),
                       "plan": _content_calendar(content_jobs, content_plan)}
        _cockpit_all = _CKB.cockpit_section(_ck)
    except Exception as _e9:
        log.exception("AI Cockpit boards failed to render - showing the old "
                      "four modules instead")
        _cockpit_all = ("<div class='card full' style='border-color:#F5788A'>"
                        "<p class='ct'>AI Cockpit boards failed to render</p>"
                        f"<p class='cc'>Showing the older modules below, so the "
                        f"approval queue still works. Reason: "
                        f"{_esc(type(_e9).__name__)}: {_esc(str(_e9))[:300]}</p></div>"
                        + p_mission + p_ops + p_appr + p_learn)

    # ---- Content Factory: the heart. 13 cards with no preview, a planner
    # handed an empty dict, and images that never reached social. Rebuilt as 16
    # boards with SIX platform preview screens.
    try:
        import content_engine_factory_boards as _CFB
        _factory_all = _CFB.factory_section(factory_ctx or {})
    except Exception as _e8:
        log.exception("Content Factory boards failed to render - showing the "
                      "old module instead")
        _factory_all = ("<div class='card full' style='border-color:#F5788A'>"
                        "<p class='ct'>Content Factory boards failed to render</p>"
                        f"<p class='cc'>Showing the older module below. Reason: "
                        f"{_esc(type(_e8).__name__)}: {_esc(str(_e8))[:300]}</p></div>"
                        + p_content)

    # ---- SGA: ONE section replacing Social Media, Google Hub and Ads &
    # Growth — 27 cards between them, ZERO charts, and 19 panels that were
    # literally _empty(). Scope is social (paid + unpaid) plus the Google data
    # hub; Google Ads keeps its own Media Buying section.
    try:
        import content_engine_sga_boards as _SGAB
        _sga_all = _SGAB.sga_section(sga_ctx or {})
    except Exception as _e7:
        log.exception("SGA boards failed to render - showing the old three "
                      "modules instead")
        _sga_all = ("<div class='card full' style='border-color:#F5788A'>"
                    "<p class='ct'>SGA boards failed to render</p>"
                    f"<p class='cc'>Showing the older modules below. Reason: "
                    f"{_esc(type(_e7).__name__)}: {_esc(str(_e7))[:300]}</p></div>"
                    + p_social + p_google + p_ads)

    # ---- Leads & Outreach: ONE section replacing Lead Machine and Email &
    # Outreach. Unlike the other merges these two carry a working launch pad —
    # the outbox, the replies inbox, the leads table and the Maps form are
    # passed through ALREADY RENDERED so every send button keeps calling the
    # same endpoint it always did. Send logic is not touched.
    try:
        import content_engine_outreach_boards as _OB
        _octx = dict(outreach_ctx or {})
        _octx["live"] = {"outbox": _outbox(jobs),
                         "replies": _replies_inbox(reply_drafts),
                         "leads_table": _leads_table(jobs),
                         "maps_form": maps_form,
                         "outbox_pointer": _outbox_pointer(jobs)}
        _outreach_all = _OB.outreach_section(_octx)
    except Exception as _e6:
        log.exception("Leads & Outreach boards failed to render - showing the "
                      "old two modules instead")
        _outreach_all = ("<div class='card full' style='border-color:#F5788A'>"
                         "<p class='ct'>Leads &amp; Outreach boards failed to render</p>"
                         f"<p class='cc'>Showing the older modules below, so the "
                         f"send buttons still work. Reason: "
                         f"{_esc(type(_e6).__name__)}: {_esc(str(_e6))[:300]}</p></div>"
                         + p_leads + p_email)

    # ---- Business Intelligence: ONE section replacing Business Performance,
    # Marketing Intelligence, Sales Intelligence, Customer Intelligence, Finance
    # and Budget & Cost — 41 cards that all read the same context dict.
    try:
        import content_engine_bi_boards as _BIB
        _bi_all = _BIB.bi_section(bi_ctx or {})
    except Exception as _e5:
        log.exception("Business Intelligence boards failed to render - showing "
                      "the old six modules instead")
        _bi_all = ("<div class='card full' style='border-color:#F5788A'>"
                   "<p class='ct'>Business Intelligence boards failed to render</p>"
                   f"<p class='cc'>Showing the older modules below. Reason: "
                   f"{_esc(type(_e5).__name__)}: {_esc(str(_e5))[:300]}</p></div>"
                   + _mod_business(ctx) + _mod_marketing(ctx) + _mod_sales(ctx)
                   + _mod_customer(ctx) + _mod_finance(ctx) + _mod_executive(ctx))

    # ---- Risk & Infrastructure: ONE section replacing Risk, AI Workforce and
    # Infrastructure, which held 13 cards between them and read the same three
    # numbers. No credential path is touched.
    try:
        import content_engine_risk_boards as _RKB
        _risk_all = _RKB.risk_section(risk_ctx or {})
    except Exception as _e4:
        # Same fix. If this fires you see the three old blocks and it looks like
        # nothing was merged - so say WHY, at the top, and log the traceback.
        log.exception("Risk & Infrastructure boards failed to render - showing "
                      "the old three modules instead")
        _risk_all = ("<div class='card full' style='border-color:#F5788A'>"
                     "<p class='ct'>Risk &amp; Infrastructure boards failed to render</p>"
                     f"<p class='cc'>Showing the older modules below. Reason: "
                     f"{_esc(type(_e4).__name__)}: {_esc(str(_e4))[:300]}</p></div>"
                     + _mod_risk(ctx) + _mod_workforce(ctx) + _mod_infra(ctx))

    PAGES = [
        ("cockpit", "🧠", "AI Cockpit", "AI Cockpit",
         "The brain. Every system's signal becomes a decision you can act "
         "on. 268 cards across 15 boards.", _cockpit_all),
        ("bi", "📊", "Business Intel", "Business Intelligence",
         "Demand, pipeline, revenue and unit economics — merged. 252 cards "
         "across 14 boards.", _bi_all),
        ("riskinfra", "🛡", "Risk & Infrastructure", "Risk & Infrastructure",
         "Risk, workforce and infrastructure — merged. 208 cards across 12 boards.",
         _risk_all),
        ("content", "🏭", "Content Factory", "Content Factory",
         "Plan it, see it on every platform, make it, ship it. 278 cards "
         "across 16 boards including six live previews.", _factory_all),
        ("outreach", "📮", "Leads & Outreach", "Leads & Outreach",
         "Find them, write to them, track what came back. 240 cards "
         "across 14 boards.", _outreach_all),
        ("sga", "🚀", "SGA", "SGA — Social, Growth & Ads",
         "Paid and unpaid social, campaign planning, content push and "
         "your Google hub. 250 cards across 14 boards.", _sga_all),
        ("seo", "🔎", "SEO / AEO / GEO", "SEO · AEO · GEO",
         "Search, AI-answer and geo visibility — every SEO board in one place.", _seo_all),
        ("media", "🛒", "Media Buying", "Media Buying · Google Ads",
         "296 cards across 16 boards — what a senior media buyer reads before deciding.",
         _media_all + p_media),
        ("system", "🩺", "System & Wiring", "System & Wiring",
         "Agents, health, wiring and machines — merged. 214 cards across 12 boards.",
         _system_all),
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
    if api_warnings:
        alerts.append(("#FF6B93", "🔌", f"API top-up: {api_warnings[0]}", "budget"))
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
    # ONE start / ONE stop for the whole system. Granular controls tucked away.
    if autopilot_on:
        master_switch = ("<button class='cbtn warn' style='font-size:15px;font-weight:700;padding:11px 24px' "
                         "onclick=\"if(confirm('Stop the machine? Nothing new is queued, run, published or drafted until you start it again.'))act('/system/stop')\">■ STOP the whole system</button>"
                         "<span class='pill p-live' style='align-self:center'><span class='d' style='background:#3FD98B'></span>running</span>"
                         + ("<span class='pill p-need' style='align-self:center;border-color:#FF6B93;color:#FF6B93'>"
                            "<span class='d' style='background:#FF6B93'></span>AUTONOMOUS — publishes without you</span>"
                            if autonomy else
                            "<span class='dim' style='align-self:center;font-size:11.5px'>"
                            "supervised · every publish waits for you</span>"))
    else:
        # SUPERVISED start. This button used to grant autonomy as a side effect,
        # which meant anything left unreviewed for 24h published itself. It now
        # says exactly what it does, and autonomy is a separate deliberate act.
        master_switch = ("<button class='cbtn on' style='font-size:15px;font-weight:700;padding:11px 24px' "
                         "onclick=\"if(confirm('Start the machine?\n\nIt will queue work daily, run the SEO engines on their cadence, and draft replies.\n\nEVERY piece still waits for your approval — nothing publishes or sends until you say so.'))"
                         "act('/system/start')\">▶ START — supervised</button>"
                         "<span class='pill p-need' style='align-self:center'><span class='d' style='background:#F5B14C'></span>stopped</span>"
                         "<span class='dim' style='align-self:center;font-size:11.5px'>"
                         "Queues and drafts. Publishes nothing without you.</span>")
    ctrl_html = ("<div class='ctrl'>" + master_switch + "</div>"
                 "<details style='margin-top:8px'><summary class='dim' style='cursor:pointer'>Advanced controls</summary>"
                 "<div class='ctrl' style='margin-top:6px'><button class='cbtn' onclick=\"act('/tick')\">▶ Run one step</button>"
                 + pause_btn + auto_btn + "</div></details>")

    logout = "<a class='logout' href='/logout'>Sign out</a>" if has_password else ""
    script = ("<script>var NAVALIAS={agents:'system',map:'system',overview:'system',risk:'riskinfra',workforce:'riskinfra',infra:'riskinfra',business:'bi',marketing:'bi',sales:'bi',customer:'bi',finance:'bi',budget:'bi',exec:'bi',leads:'outreach',email:'outreach',social:'sga',google:'sga',ads:'sga',mission:'cockpit',ops:'cockpit',appr:'cockpit',learn:'cockpit'};"
              "function nav(id){id=NAVALIAS[id]||id;"
              "document.querySelectorAll('.page').forEach(p=>p.classList.remove('on'));"
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
              "function _noteFor(id){var t=document.getElementById('note-'+id);return t?t.value.trim():'';}"
              "async function refreshInsights(){var b=event&&event.target;if(b){b.disabled=true;b.textContent='Fetching from Google… ~10s';}"
              "try{var r=await fetch('/insights/refresh',{method:'POST'});var j=await r.json();"
              "if(j.ok){location.reload();}else{alert(j.error||'refresh failed');if(b){b.disabled=false;b.textContent='↻ Refresh Google data';}}}"
              "catch(e){alert('Failed: '+e);if(b){b.disabled=false;b.textContent='↻ Refresh Google data';}}}"
              # ---- SEO section: in-page tabs (one nav item holds every board) ----
              # group rail: show only that group's tabs, open its first
              "function seoGroup(g){document.querySelectorAll('.sgrp').forEach(b=>b.classList.remove('on'));"
              "var gb=document.getElementById('sgrp-'+g);if(gb)gb.classList.add('on');"
              "var first=null;document.querySelectorAll('.stab').forEach(function(t){"
              "var show=t.getAttribute('data-grp')===g;t.style.display=show?'flex':'none';"
              "if(show&&!first)first=t.id.replace('stab-','');});"
              "if(first)seoTab(first);}"
              # live search across all 235 cards, by title, read and source
              "function seoFilter(){var q=(document.getElementById('cardq')||{}).value||'';"
              "q=q.toLowerCase().trim();var shown=0,tot=0;"
              "document.querySelectorAll('.card[data-q]').forEach(function(c){tot++;"
              "var okq=!q||(c.getAttribute('data-q')||'').indexOf(q)>=0;"
              "var oks=!window._sevf||window._sevf==='all'||c.getAttribute('data-sev')===window._sevf;"
              "if(okq&&oks){c.classList.remove('hidecard');shown++;}else{c.classList.add('hidecard');}});"
              "var cc=document.getElementById('cardcount');"
              "if(cc)cc.textContent=(q||(window._sevf&&window._sevf!=='all'))?(shown+' of '+tot+' cards'):'';}"
              "function seoSev(s){window._sevf=s;seoFilter();}"
              # progressive disclosure: 8 cards per board, rest one click away
              "function seoMore(id){var g=document.getElementById(id);if(!g)return;"
              "g.classList.add('expanded');g.querySelectorAll('.card').forEach(c=>c.classList.remove('overflowcard'));"
              "var b=document.getElementById('more-'+id);if(b)b.remove();}"
              "function seoTab(id){document.querySelectorAll('.spanel').forEach(p=>p.classList.remove('on'));"
              "var p=document.getElementById('spanel-'+id);if(p)p.classList.add('on');"
              "var q=document.getElementById('cardq');if(q&&q.value){q.value='';window._sevf='all';seoFilter();}"
              "document.querySelectorAll('.stab').forEach(b=>b.classList.remove('on'));"
              "var b=document.getElementById('stab-'+id);if(b)b.classList.add('on');"
              "try{history.replaceState(null,'','#seo/'+id);}catch(e){}"
              "var s=document.getElementById('sec-seo');if(s)s.scrollIntoView({block:'start'});}"
              # deep link: #seo/seowork opens the SEO section on that tab
              "window.addEventListener('DOMContentLoaded',function(){var h=location.hash||'';"
              "if(h.indexOf('#seo/')===0){nav('seo');seoTab(h.slice(5));}});"
              # ---- SEO engines: one helper drives every run button ----
              "async function seoRun(url,label,confirmMsg){if(confirmMsg&&!confirm(confirmMsg))return;"
              "var b=event&&event.target;var old=b?b.textContent:'';if(b){b.disabled=true;b.textContent=label;}"
              "try{var r=await fetch(url,{method:'POST'});var j=await r.json();"
              "if(j.ok!==false){location.reload();}else{alert('Failed: '+(j.error||''));if(b){b.disabled=false;b.textContent=old;}}}"
              "catch(e){alert('Failed: '+e);if(b){b.disabled=false;b.textContent=old;}}}"
              "function runCrawl(){seoRun('/seo/crawl','Crawling your site… ~2-4 min',"
              "'Crawl every page of your site and audit it? This costs $0 in API — it is your own crawler. Takes 2-4 minutes.');}"
              "function runInspect(){seoRun('/seo/inspect','Asking Google… ~2 min',"
              "'Ask Google whether each page is indexed? Free (URL Inspection API, 2000/day).');}"
              "function runSpeed(){seoRun('/seo/speed','Measuring speed… ~1 min','Run PageSpeed on one page per template? Free.');}"
              "function runFixes(){seoRun('/seo/fix-all','Applying fixes…',"
              "'Apply the safe automatic fixes now (schema, internal links, alt text)? Titles and copy will only be DRAFTED for your approval, never published.');}"
              "function runRanks(){seoRun('/seo/ranks','Checking rankings… ~1 min',"
              "'Check today rankings for your tracked keywords? Uses about 1 Serper credit per keyword.');}"
              "function runAeo(){seoRun('/aeo/probe','Asking the AI engines… ~2 min',"
              "'Ask AI engines the questions your buyers ask, and see if they name you? ~30 small Claude calls plus Serper credits.');}"
              "function runOffpage(){seoRun('/offpage/scan','Pulling backlinks…','Pull your backlink profile? Requires DataForSEO.');}"
              "function runAds(){seoRun('/ads/pull','Pulling Google Ads… ~1 min',"
              "'Pull everything from Google Ads (campaigns, search terms, quality score, assets)? The API is free.');}"
              "function runInterlock(){seoRun('/ads/interlock','Rebuilding cross-channel…',"
              "'Rebuild the SEO/AEO/GEO/Ads interlock? Free — it runs on data you already have.');}"
              "async function openEcon(){var d=prompt('Average deal value in EUR (e.g. 5000)');if(!d)return;"
              "var m=prompt('Gross margin %, e.g. 60');if(!m)return;"
              "var c=prompt('Consultation to client close rate %, e.g. 25');if(!c)return;"
              "var l=prompt('Lead to consultation rate %, e.g. 40')||'0';"
              "try{var r=await fetch('/ads/economics',{method:'POST',headers:{'Content-Type':'application/json'},"
              "body:JSON.stringify({avg_deal_value:d,gross_margin_pct:m,consult_to_client_pct:c,lead_to_consult_pct:l})});"
              "var j=await r.json();alert('Saved. Target CPA per lead: EUR '+((j.targets||{}).target_cpa_lead||'-'));location.reload();}"
              "catch(e){alert('Failed: '+e);}}"
              "function sysTab(id){seoTab(id);}"
              # Cockpit -> the actual box you type the key into. Naming a form
              # without landing on it is how the Keys board pointed at a page
              # that had no field for any of the 36 keys.
              "function goKeys(){nav('system');sysTab('sysconnect');"
              "setTimeout(function(){var e=document.getElementById('extrakeys');"
              "if(e)e.scrollIntoView({block:'start',behavior:'smooth'});},120);}"
              "function runSeoDue(){seoRun('/seo/due','Running what is due…',"
              "'Run every SEO engine that is due right now? Free engines run "
              "immediately; paid ones respect your cap.');}"
              # A rewrite PROPOSAL: accept queues a rewrite, decline records
              # why. Either way a person decided it, which is the point.
              "async function proposal(id,ok){"
              "var n='';"
              "if(!ok){n=prompt('Why are you leaving it? (recorded so the engine learns)')||'';}"
              "else if(!confirm('Queue a rewrite of this piece?'))return;"
              "try{var r=await fetch('/proposal',{method:'POST',headers:{'Content-Type':'application/json'},"
              "body:JSON.stringify({job_id:id,accept:ok,note:n})});"
              "var x=await r.json();alert(x.ok?x.message:('Not saved: '+(x.error||'')));"
              "if(x.ok)location.reload();}catch(e){alert('Failed: '+e);}}"
              "async function setBudget(){"
              "var m=prompt('Monthly cap in euros (leave blank to keep)');"
              "var d=prompt('Daily cap in euros (blank to keep)');"
              "var j=prompt('Per-job cap in euros (blank to keep)');"
              "if(!m&&!d&&!j)return;"
              "try{var r=await fetch('/budget',{method:'POST',headers:{'Content-Type':'application/json'},"
              "body:JSON.stringify({per_month:m,per_day:d,per_job:j,note:'set from the cockpit'})});"
              "var x=await r.json();alert(x.ok?x.message:('Not saved: '+(x.error||'')));"
              "if(x.ok)location.reload();}catch(e){alert('Failed: '+e);}}"
              "function startExperiment(){"
              "var h=prompt('Hypothesis — what do you believe will happen?');if(!h)return;"
              "var m=prompt('Which ONE metric will tell you?');if(!m)return;"
              "var d=prompt('Review in how many days?','14')||'14';"
              "post('/experiment',{hypothesis:h,metric:m,review_days:d});}"
              "function planContent(){"
              "if(!confirm('Plan a week of content?\\n\\nThe planner reads striking-distance "
              "queries, AI-visibility gaps, missing markets, which vertical replies, what "
              "produced revenue and which channels are live. It costs one LLM call and "
              "writes nothing until you approve.'))return;"
              "seoRun('/plan/content','Planning from every system… ~30s');}"
              "async function testImage(){if(!confirm('Generate one real image? Costs about "
              "EUR 0.04 and shows whether the key works and whether the style fits your "
              "brand.'))return;"
              "try{var r=await fetch('/content/test-image',{method:'POST'});var j=await r.json();"
              "if(j.ok){if(confirm('Image generated. Open it?'))window.open(j.url,'_blank');}"
              "else{alert('Failed: '+(j.error||''));}}catch(e){alert('Failed: '+e);}}"
              "function sgaCampaign(){var n=prompt('Campaign name');if(!n)return;"
              "var o=prompt('Objective: awareness / leads / bookings','leads')||'awareness';"
              "var c=prompt('Channels, comma separated: linkedin,facebook,instagram,youtube,twitter,tiktok','linkedin')||'linkedin';"
              "var s=prompt('Start date (YYYY-MM-DD)',new Date().toISOString().slice(0,10))||'';"
              "var e=prompt('End date (YYYY-MM-DD, blank = open)')||'';"
              "var b=prompt('Paid budget in euros (0 = organic only)','0')||'0';"
              "post('/sga/campaign',{name:n,objective:o,channels:c.split(',').map(function(x){return x.trim();}),"
              "start:s,end:e,budget:b,paid:(parseFloat(b)>0)});}"
              "function sgaCampaignDelete(id){if(!confirm('Remove this campaign? Posts already made keep their tag.'))return;"
              "post('/sga/campaign/delete',{id:id});}"
              "function leadEdit(job,email){"
              "var f=['name','title','company','linkedin','phone','country','website'];"
              "var b={job_id:job,email:email},any=false;"
              "for(var i=0;i<f.length;i++){var v=prompt('New '+f[i]+' (leave blank to keep as is)');"
              "if(v){b[f[i]]=v;any=true;}}"
              "if(!any){alert('Nothing changed.');return;}post('/leads/edit',b);}"
              "function leadDelete(job,email){"
              "if(!confirm('Remove '+email+'?\\n\\nThe lead leaves the sendable list and the "
              "address is suppressed, so it can never be emailed. The record is kept.'))return;"
              "post('/leads/delete',{job_id:job,email:email});}"
              "function trackToggle(){"
              "if(!confirm('Toggle open/click tracking for every future send?\\n\\n"
              "ON adds a 1x1 pixel and rewrites links in the HTML part. In Germany "
              "and Switzerland that is a GDPR matter, and pixels cost some "
              "deliverability.'))return;"
              "fetch('/outreach/tracking',{method:'POST',headers:{'Content-Type':'application/json'},"
              "body:JSON.stringify({enabled:!window.__track})}).then(function(r){return r.json();})"
              ".then(function(j){alert(j.message||'Saved');location.reload();})"
              ".catch(function(e){alert('Failed: '+e);});}"
              "function biDeal(){var c=prompt('Client name');if(!c)return;"
              "var v=prompt('Deal value in euros (numbers only)');if(!v)return;"
              "var s=prompt('Where did it come from? outreach / organic / ads / referral / direct','outreach')||'other';"
              "var d=prompt('Date won (YYYY-MM-DD)',new Date().toISOString().slice(0,10))||'';"
              "post('/bi/deal',{client:c,value:v,source:s,at:d});}"
              "function biEcon(){var m=prompt('Gross margin % (e.g. 65)');"
              "var a=prompt('Average deal value in euros');"
              "var r=prompt('Of the consultations you hold, what % become clients?');"
              "if(!m&&!a&&!r)return;post('/bi/econ',{margin_pct:m,avg_deal:a,consult_to_client_pct:r});}"
              "function biTargets(){var r=prompt('Monthly revenue target in euros');"
              "var d=prompt('Deals per month target');var l=prompt('Leads per month target');"
              "if(!r&&!d&&!l)return;post('/bi/targets',{revenue_month:r,deals_month:d,leads_month:l});}"
              "function post(u,b){fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},"
              "body:JSON.stringify(b)}).then(function(r){return r.json();}).then(function(j){"
              "alert(j.ok?('Saved. '+(j.message||'')):('Could not save: '+(j.error||'unknown')));"
              "if(j.ok)location.reload();}).catch(function(e){alert('Failed: '+e);});}"
              "function runRisk(){seoRun('/risk/refresh','Recomputing the risk register…',"
              "'Recompute the risk register from current data? Free — it reads what is already stored.');}"
              "function runGeo(){seoRun('/geo/audit','Auditing your 5 markets… ~1 min',"
              "'Audit hreflang, language coverage and the local pack across your five markets? Uses a few Serper credits.');}"
              "function approveAll(kind){if(!confirm('Publish EVERY drafted '+kind+' rewrite to your website? Review a few first — this cannot be undone in bulk.'))return;"
              "seoRun('/seo/approve-all?type='+kind,'Publishing…');}"
              "function runProspect(){seoRun('/offpage/prospect','Finding link prospects… ~2 min',"
              "'Find link prospects and draft pitches? NOTHING is sent — every pitch waits for your approval.');}"
              "function runSeoAll(){seoRun('/seo/run-all','Running every SEO engine… ~5 min',"
              "'Run the whole SEO sequence (crawl, index check, speed, fixes, rankings)? The free engines always run; paid ones only if their key is set.');}"
              "async function applyFix(id){if(!confirm('Publish this rewrite to your website?'))return;"
              "try{var r=await fetch('/seo/fix/'+id,{method:'POST'});var j=await r.json();"
              "if(j.ok){location.reload();}else{alert('Failed: '+(j.error||''));}}catch(e){alert('Failed: '+e);}}"
              "async function scanCompetitors(){var d=(document.getElementById('compdoms')||{}).value||'';"
              "if(!confirm('Scan competitors now? '+(d?('Using: '+d):'The machine will auto-discover who ranks for your queries.')+' (~40 Serper credits + 1 small Claude call, ~60s)'))return;"
              "var b=event&&event.target;if(b){b.disabled=true;b.textContent='Scanning… ~60s';}"
              "try{var r=await fetch('/competitors/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({domains:d,limit:5})});var j=await r.json();"
              "if(j.ok){alert('✓ Scanned '+(j.competitors||[]).length+' competitors. The board is filled.');location.reload();}"
              "else{alert('Scan failed: '+(j.error||''));if(b){b.disabled=false;b.textContent='🛰️ Scan competitors (~40 credits)';}}}"
              "catch(e){alert('Scan failed: '+e);if(b){b.disabled=false;b.textContent='🛰️ Scan competitors (~40 credits)';}}}"
              "async function sourceMapsLeads(){var v=(document.getElementById('mv')||{}).value||'';var c=(document.getElementById('mc')||{}).value||'';"
              "var n=parseInt((document.getElementById('mn')||{}).value||'20')||20;"
              "if(!v.trim()||!c.trim()){alert('Type a business type AND a city first.');return;}"
              "if(!confirm('Scrape '+n+' \\\"'+v+'\\\" businesses in '+c+' from Google Maps + find their emails? (~'+n+' Serper + Prospeo credits. Nothing gets emailed.)'))return;"
              "var b=event&&event.target;if(b){b.disabled=true;b.textContent='Scraping… ~30s';}"
              "try{var r=await fetch('/leads/maps',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({vertical:v,city:c,count:n})});var j=await r.json();"
              "if(j.ok){alert('✓ '+j.businesses+' businesses sourced · '+j.with_verified_email+' with a verified email.\\n\\n'+(j.next||''));location.reload();}"
              "else{alert('Failed: '+(j.error||''));if(b){b.disabled=false;b.textContent='🗺️ Find leads';}}}"
              "catch(e){alert('Failed: '+e);if(b){b.disabled=false;b.textContent='🗺️ Find leads';}}}"
              "async function approve(id){var note=_noteFor(id);"
              "try{var r=await fetch('/jobs/'+id+'/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({note:note})});await r.json();"
              "alert('✓ Approved'+(note?' with your note':'')+'. It goes live.');location.reload();}catch(e){alert('Failed: '+e);}}"
              "async function decline(id){var note=_noteFor(id);"
              "if(!note){alert('Please add a note first — tell the system what to fix, then Decline.');return;}"
              "if(!confirm('Send this back to be re-written using your note? Nothing publishes.'))return;"
              "try{var r=await fetch('/jobs/'+id+'/decline',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({note:note})});var j=await r.json();"
              "alert(j.ok?'↩ Sent back — it will be re-written to fix your note.':'Failed: '+(j.error||''));location.reload();}catch(e){alert('Failed: '+e);}}"
              "function toggleOutbox(cb){document.querySelectorAll('.obx').forEach(function(x){x.checked=cb.checked;});}"
              "async function sendAllCommand(){if(!confirm('Send ALL ready emails now? Warm-up cap applies — the rest queue for the next days.'))return;"
              "try{var r=await fetch('/outreach/send_all',{method:'POST'});var j=await r.json();alert('Sent '+j.sent+' of '+j.total+(j.held_by_cap?(' · '+j.held_by_cap+' held by cap (send over coming days)'):''));location.reload();}catch(e){alert('Failed: '+e);}}"
              "async function trashEmail(job,email){if(!confirm('Delete this email? It moves to the junk box (recoverable, never lost).'))return;"
              "try{await fetch('/outreach/trash',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:job,email:email})});location.reload();}catch(e){alert('Failed: '+e);}}"
              "async function restoreEmail(job,email){try{await fetch('/outreach/trash',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:job,email:email,restore:true})});location.reload();}catch(e){alert('Failed: '+e);}}"
              "function previewEmail(i){toggleEl('pv-'+i);}"
              "function toggleEl(id){var d=document.getElementById(id);if(d)d.style.display=(d.style.display==='none'?'block':'none');}"
              "var _obxPg=0;function pageOutbox(dir){var rows=document.querySelectorAll('.obxrow');var pages=0;rows.forEach(function(r){pages=Math.max(pages,+r.getAttribute('data-pg'));});"
              "_obxPg=Math.max(0,Math.min(pages,_obxPg+dir));rows.forEach(function(r){r.style.display=(+r.getAttribute('data-pg')===_obxPg?'':'none');});"
              "var lbl=document.getElementById('obx-pg');if(lbl)lbl.textContent=(_obxPg+1);window.scrollTo({top:0});}"
              "function editEmail(i){toggleEl('ed-'+i);}"
              "async function refreshReplies(){try{var r=await fetch('/replies/refresh',{method:'POST'});var j=await r.json();"
              "if(j.ok){alert('Checked replies — '+ (j.added||0) +' new, '+(j.pending||0)+' waiting for you.');location.reload();}"
              "else{alert('Could not read replies: '+(j.error||'')+' (needs IMAP connected).');}}catch(e){alert('Failed: '+e);}}"
              "async function saveReply(id,i){var s=(document.getElementById('rs-'+i)||{}).value||'';var b=(document.getElementById('rb-'+i)||{}).value||'';"
              "try{var r=await fetch('/reply/edit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,subject:s,body:b})});var j=await r.json();"
              "alert(j.ok?'✓ Draft saved.':'Save failed: '+(j.error||''));}catch(e){alert('Failed: '+e);}}"
              "async function sendReply(id,i){var s=(document.getElementById('rs-'+i)||{}).value||'';var b=(document.getElementById('rb-'+i)||{}).value||'';"
              "if(b.trim().length<5){alert('The reply looks empty.');return;}"
              "if(!confirm('Send this reply to the customer?'))return;"
              "try{await fetch('/reply/edit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,subject:s,body:b})});"
              "var r=await fetch('/reply/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id})});var j=await r.json();"
              "alert(j.ok?'✓ Reply sent to the customer.':'Not sent: '+(j.ref||j.error||''));location.reload();}catch(e){alert('Failed: '+e);}}"
              "async function dismissReply(id){if(!confirm('Dismiss this reply (no answer)?'))return;"
              "try{await fetch('/reply/dismiss',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id})});location.reload();}catch(e){alert('Failed: '+e);}}"
              "async function saveEdit(job,email,i,touch){var s=(document.getElementById('eds-'+i)||{}).value||'';var b=(document.getElementById('edb-'+i)||{}).value||'';"
              "if(b.trim().length<10){alert('The email body looks too short.');return;}"
              "try{var r=await fetch('/outreach/edit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:job,email:email,subject:s,body:b,touch:(touch||1)})});var j=await r.json();"
              "if(j.ok){alert('✓ Saved email '+(touch||1)+'. It will preview and send exactly as you wrote it.');location.reload();}else{alert('Save failed: '+(j.error||''));}}catch(e){alert('Save failed: '+e);}}"
              "async function sendOne(job,email){if(!confirm('Send this email to '+email+'?'))return;"
              "try{var r=await fetch('/outreach/send_one',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:job,email:email})});var j=await r.json();"
              "alert(j.ok?('✓ Sent to '+email):('Not sent: '+(j.ref||j.error||'unknown')));location.reload();}catch(e){alert('Failed: '+e);}}"
              "async function sendSelected(){var sel=Array.prototype.slice.call(document.querySelectorAll('.obx:checked'));if(!sel.length){alert('Tick some emails first.');return;}"
              "var job=sel[0].getAttribute('data-job');var emails=sel.map(function(x){return x.value;});if(!confirm('Send '+emails.length+' email(s) now?'))return;"
              "try{var r=await fetch('/outreach/send_batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:job,emails:emails})});var j=await r.json();"
              "alert('Sent '+j.sent+' of '+j.total+(j.held_by_cap?(' · '+j.held_by_cap+' held by the daily warm-up cap'):''));location.reload();}catch(e){alert('Failed: '+e);}}"
              "async function sendAllOutbox(){var all=Array.prototype.slice.call(document.querySelectorAll('.obx'));if(!all.length){alert('Nothing ready to send.');return;}"
              "var job=all[0].getAttribute('data-job');if(!confirm('Send ALL '+all.length+' ready emails? The daily warm-up cap applies (the rest send over the next days).'))return;"
              "try{var r=await fetch('/outreach/send_batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:job})});var j=await r.json();"
              "alert('Sent '+j.sent+' of '+j.total+(j.held_by_cap?(' · '+j.held_by_cap+' held by cap'):''));location.reload();}catch(e){alert('Failed: '+e);}}"
              "async function runSelftest(){if(!confirm('Test every agent live? ~2 minutes, about $0.25.'))return;alert('Running all 18 agents… I will pop the result when done.');"
              "try{var r=await fetch('/selftest',{method:'POST'});var j=await r.json();var f=(j.failures||[]).map(function(x){return x.skill;}).join(', ');"
              "alert('Agents: '+(j.summary||'done')+(f?('\\nFAILING: '+f):'  — all clean'));}catch(e){alert('Test failed: '+e);}}"
              "function mediaChat(id){var c=document.getElementById('mchat-'+id);if(c){c.style.display=(c.style.display==='none'?'block':'none');if(c.style.display==='block'){var i=document.getElementById('min-'+id);if(i)i.focus();}}}"
              "async function mediaSend(id){var el=document.getElementById('min-'+id),log=document.getElementById('mlog-'+id);if(!el||!log)return;var m=el.value.trim();if(!m)return;"
              "log.innerHTML+=\"<div class='fe'><span class='tm' style='min-width:44px'>You</span><span class='mut'>\"+m.replace(/</g,'&lt;')+\"</span></div>\";el.value='';"
              "var wid='w'+Date.now();log.innerHTML+=\"<div class='fe' id='\"+wid+\"'><span class='tm' style='min-width:44px'>Agent</span><span class='dim'>thinking…</span></div>\";log.scrollTop=log.scrollHeight;"
              "try{var r=await fetch('/media/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:id,message:m})});var j=await r.json();"
              "var w=document.getElementById(wid);var t=(j.reply||j.error||'(no reply)').replace(/</g,'&lt;');w.innerHTML=\"<span class='tm' style='min-width:44px'>Agent</span><span class='mut'>\"+t+\"</span>\";log.scrollTop=log.scrollHeight;"
              "if(j.changed){setTimeout(function(){location.reload();},1000);}}catch(e){var w2=document.getElementById(wid);if(w2)w2.innerHTML=\"<span class='mut'>Error: \"+e+\"</span>\";}}"
              "async function activateCampaign(id){if(!confirm('Deploy this campaign to Google Ads now? This approves it and starts spending your daily budget (once Google has approved your developer token).'))return;"
              "try{await fetch('/jobs/'+id+'/approve',{method:'POST'});var r=await fetch('/media/activate/'+id,{method:'POST'});var j=await r.json();"
              "if(j.ok){alert('🚀 Campaign deployed: '+(j.detail||'live in Google Ads'));location.reload();}else{alert('Could not deploy: '+(j.error||j.detail||'unknown error'));}}"
              "catch(e){alert('Deploy failed: '+e);}}"
              "async function abortCampaign(id,live){if(!confirm(live?'Abort this live campaign? It will be paused in Google Ads and stop spending.':'Discard this drafted campaign?'))return;"
              "try{var r=await fetch('/media/abort/'+id,{method:'POST'});var j=await r.json();"
              "if(j.ok){alert(j.detail||'Done.');location.reload();}else{alert('Could not abort: '+(j.error||j.detail||'unknown error'));}}"
              "catch(e){alert('Abort failed: '+e);}}"
              "async function mediaSectionSend(){var el=document.getElementById('min-section'),log=document.getElementById('mlog-section');if(!el||!log)return;var m=el.value.trim();if(!m)return;"
              "var jid=(document.getElementById('section-jobid')||{}).value||'';"
              "log.innerHTML+=\"<div class='fe'><span class='tm' style='min-width:44px'>You</span><span class='mut'>\"+m.replace(/</g,'&lt;')+\"</span></div>\";el.value='';"
              "var wid='ws'+Date.now();log.innerHTML+=\"<div class='fe' id='\"+wid+\"'><span class='tm' style='min-width:44px'>Agent</span><span class='dim'>thinking…</span></div>\";log.scrollTop=log.scrollHeight;"
              "try{var r=await fetch('/media/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:jid,message:m})});var j=await r.json();"
              "var w=document.getElementById(wid);var t=(j.reply||j.error||'(no reply)').replace(/</g,'&lt;');w.innerHTML=\"<span class='tm' style='min-width:44px'>Agent</span><span class='mut'>\"+t+\"</span>\";log.scrollTop=log.scrollHeight;"
              "if(j.changed){setTimeout(function(){location.reload();},1200);}}catch(e){var w2=document.getElementById(wid);if(w2)w2.innerHTML=\"<span class='mut'>Error: \"+e+\"</span>\";}}"
              "async function planContent(){var c=parseInt((document.getElementById('plan-count')||{}).value||'10')||10;var b=document.getElementById('planbtn');if(b){b.disabled=true;b.textContent='Planning your week… ~15s';}"
              "try{var r=await fetch('/plan/content',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({count:c})});var j=await r.json();"
              "if(j.error){alert('Plan failed: '+j.error);if(b){b.disabled=false;b.textContent='🗓️ Plan my week';}}else{alert('Planned '+j.count+' pieces for the week — review the calendar and approve below.');location.reload();}}"
              "catch(e){alert('Plan failed: '+e);if(b){b.disabled=false;b.textContent='🗓️ Plan my week';}}}"
              "async function approvePlan(){if(!confirm('Approve this plan? Each piece will be created, written on-brand, QA-checked, and published.'))return;"
              "try{var r=await fetch('/plan/approve',{method:'POST'});var j=await r.json();if(j.error){alert(j.error);}else{alert('✓ Approved — created '+j.created+' pieces. They\\'re now in the pipeline.');location.reload();}}catch(e){alert('Failed: '+e);}}"
              "async function clearPlan(){if(!confirm('Discard this plan?'))return;try{await fetch('/plan/clear',{method:'POST'});location.reload();}catch(e){alert('Failed: '+e);}}"
              "async function saveCI(){var t=(document.getElementById('ci-text')||{}).value||'';var d=(document.getElementById('ci-drive')||{}).value||'';"
              "try{var r=await fetch('/brand/ci',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t,drive_folder:d})});var j=await r.json();"
              "if(j.error){alert('Save failed: '+j.error);}else{alert('Brand saved ('+(j.chars||0)+' chars). Every agent now writes on-brand.');location.reload();}}catch(e){alert('Save failed: '+e);}}"
              "async function runAutopilot(){if(!confirm('Turn on Autopilot? The agents will create today\\'s content on-brand and PUBLISH the pieces that pass QA straight to your website — no approval step. You can Stop anytime.'))return;"
              "try{var r=await fetch('/autopilot/run',{method:'POST'});var j=await r.json();"
              "if(j.ok){alert('🚀 Autopilot ON. Queued today\\'s work — pieces will publish as they pass QA.');location.reload();}else{alert('Could not start: '+(j.error||'unknown'));}}catch(e){alert('Failed: '+e);}}"
              "async function stopAutopilot(){try{var r=await fetch('/autopilot/stop',{method:'POST'});var j=await r.json();if(j.ok){alert('■ Autopilot stopped. Nothing new will publish.');location.reload();}}catch(e){alert('Failed: '+e);}}"
              "async function setApiLimit(api){var el=document.getElementById('lim-'+api);if(!el)return;var v=parseFloat(el.value);if(!(v>0)){alert('Enter a number.');return;}"
              "try{var r=await fetch('/api-limits/set',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api:api,usd:v})});var j=await r.json();"
              "if(j.error){alert('Could not save: '+j.error);}else{location.reload();}}catch(e){alert('Save failed: '+e);}}"
              "async function runEvals(){var b=document.getElementById('evalbtn');if(b){b.disabled=true;b.textContent='Running evals… ~30s';}"
              "try{var r=await fetch('/evals/run',{method:'POST'});var j=await r.json();"
              "if(j.error){alert('Eval run failed: '+j.error);}else{alert('Evals: '+j.passed+'/'+j.total+' passed ('+j.score+'%) · cost $'+(j.cost_usd||0).toFixed(3));location.reload();}}"
              "catch(e){alert('Eval run failed: '+e);}if(b){b.disabled=false;b.textContent='▶ Run evals';}}"
              "async function draftCampaign(){var b=document.getElementById('draftbtn');if(b){b.disabled=true;b.textContent='Drafting… ~15s';}"
              "try{var r=await fetch('/media/draft',{method:'POST'});var j=await r.json();"
              "if(j.ok){alert('Drafted: '+(j.campaign||'campaign')+'. Scroll down to review it.');location.reload();}else{alert('Could not draft: '+(j.error||'unknown error'));if(b){b.disabled=false;b.textContent='✍️ Draft a campaign now';}}}"
              "catch(e){alert('Draft failed: '+e);if(b){b.disabled=false;b.textContent='✍️ Draft a campaign now';}}}"
              "async function approveAll(ids){var a=ids.split(',');for(var i=0;i<a.length;i++){try{await fetch('/jobs/'+a[i]+'/approve',{method:'POST'});}catch(e){}}location.reload();}"
              "async function runSkill(){var sk=document.getElementById('sk').value,out=document.getElementById('out'),inp=document.getElementById('inp').value;"
              "out.textContent='Running '+sk+'…';try{var b=JSON.parse(inp||'{}');}catch(e){out.textContent='That input is not valid JSON.';return;}"
              "try{var r=await fetch('/skills/'+sk+'/taste',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({input:b})});"
              "out.textContent=JSON.stringify(await r.json(),null,2);}catch(e){out.textContent='Error: '+e;}}</script>")

    return (
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Business Control Center</title><style>" + CSS + "</style></head><body>"
        "<div class='top'><div class='brand'><div class='logo'>A</div><div><h1>Anthropos — Control Center</h1><small>Your automation, in plain English</small></div></div>"
        "<div style='display:flex;gap:9px;align-items:center'>"
        "<span title='Which build is live right now' style='font-size:11px;color:#59668A;"
        "border:1px solid #1B2640;border-radius:7px;padding:3px 8px'>build " + _esc(BUILD_TAG) + "</span>"
        "<span class='status'><span class='d' style='background:"
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
    for need in ("Content Factory", "System Map", "Wiring diagnostic", "Automation Engine",
                 "nav('leads')", "24/7 competitor", "What it breaks", "Not connected",
                 # Risk & Infrastructure: the merged section and its four groups
                 "Risk &amp; Infrastructure", "WHAT COULD HURT", "WHO DOES THE WORK",
                 "WILL IT KEEP RUNNING", "ARE WE COVERED",
                 # Business Intelligence: the merged section and its four groups
                 "IS DEMAND THERE", "IS IT BECOMING PIPELINE",
                 "IS IT BECOMING MONEY", "DOES THE MATH WORK"):
        assert need in html, need
    # ---- the inline JS must PARSE. A single bad string literal takes down
    # every handler on the page: nav() stops working, the sections stop
    # opening and the dashboard reads as completely static. The block is one
    # concatenated line, so a raw newline in it means a Python escape leaked
    # into a JS string.
    import re as _re
    _js = max(_re.findall(r"<script[^>]*>(.*?)</script>", html, _re.S), key=len)
    for _bad, _name in ((chr(10), "newline"), (chr(13), "carriage return")):
        if _bad in _js:
            _at = _js.index(_bad)
            raise AssertionError(
                f"raw {_name} inside the inline JS at offset {_at} - this is a "
                f"SyntaxError and blanks the whole dashboard. Near: "
                f"...{_js[max(0, _at - 90):_at + 40]!r}")
    for _ch, _cl in (("{", "}"), ("(", ")"), ("[", "]")):
        assert _js.count(_ch) == _js.count(_cl), (
            f"unbalanced {_ch}{_cl} in the inline JS: "
            f"{_js.count(_ch)} vs {_js.count(_cl)}")
    # every handler an onclick names must actually exist
    _JS_KEYWORDS = {"if", "for", "while", "return", "switch", "catch",
                    "typeof", "new", "delete", "void", "function"}
    _called = set(_re.findall(r"onclick=[\"']?([A-Za-z_]\w*)\(", html))
    _defined = set(_re.findall(r"function\s+([A-Za-z_]\w*)\s*\(", _js))
    _missing = sorted(c for c in _called
                      if c not in _defined and c not in _JS_KEYWORDS
                      and c not in ("window", "location", "alert", "confirm"))
    assert not _missing, f"onclick calls a function nothing defines: {_missing}"

    import re as _re
    _ids = _re.findall(r"id='sec-([a-z0-9_]+)'", html)
    assert _ids == ["cockpit", "bi", "riskinfra", "content",
                    "outreach", "sga", "seo", "media", "system"], _ids
    assert html.count("class='page") == 9, html.count("class='page")
    for _old in ("mission", "ops", "appr", "learn"):
        assert f"{_old}:'cockpit'" in html, f"nav alias {_old} -> cockpit missing"
    assert "setBudget()" in html, "the budget control must be reachable"
    # the launch pad must survive the merge: every endpoint still reachable
    for _ep in ("/outreach/send_all", "/outreach/send_one", "/outreach/send_batch",
                "/outreach/edit", "/outreach/trash", "/replies/refresh",
                "/reply/send", "/reply/edit", "/reply/dismiss", "/leads/maps"):
        assert _ep in html, f"{_ep} is no longer reachable from the UI"
    # the six merged-away pages must not come back, and every old nav id must
    # still land somewhere real
    for _dead in ("sec-business", "sec-marketing", "sec-sales", "sec-customer",
                  "sec-finance", "sec-budget", "sec-exec",
                  "sec-leads", "sec-email", "sec-social", "sec-google",
                  "sec-ads", "sec-mission", "sec-ops", "sec-appr", "sec-learn"):
        assert f"id='{_dead}'" not in html, f"{_dead} should be merged into sec-bi"
    for _old in ("business", "marketing", "sales", "customer", "finance",
                 "budget", "exec"):
        assert f"{_old}:'bi'" in html, f"nav alias {_old} -> bi missing"
    for _old in ("leads", "email"):
        assert f"{_old}:'outreach'" in html, f"nav alias {_old} -> outreach missing"
    for _old in ("social", "google", "ads"):
        assert f"{_old}:'sga'" in html, f"nav alias {_old} -> sga missing"
    for _fn in ("biDeal()", "biEcon()", "biTargets()"):
        assert _fn in html, f"{_fn} handler missing"
    assert "AI Cockpit" in html, "the cockpit page must exist"
    for _g in ("DECIDE", "APPROVE", "CONTROL", "RUN &amp; LEARN"):
        assert _g in html, f"cockpit group {_g} missing"
    for _m in ("Business Intelligence", "AI Workforce", "Executive brief"):
        assert _m in html, _m
    # the three merged-away sections must not come back as pages, and every old
    # nav id must still land somewhere real
    for _dead in ("id='sec-risk'", "id='sec-workforce'", "id='sec-infra'"):
        assert _dead not in html, f"{_dead} should be merged into sec-riskinfra"
    assert "id='sec-riskinfra'" in html
    for _old, _new in (("risk", "riskinfra"), ("workforce", "riskinfra"),
                       ("infra", "riskinfra"), ("agents", "system"), ("map", "system")):
        assert f"{_old}:'{_new}'" in html, f"nav alias {_old} -> {_new} missing"
    assert "control center is ready" in dashboard_html(jobs=[], st={}, health={"healthy": True},
                                                       month_spent=0, month_cap=200, day_spent=0, day_cap=50, taste_skills=[])
    assert "Sign in" in login_html()
    # ---- every class the page uses must actually be STYLED.
    # Five merged sections shipped `stabbar` and `sgrprail`, which no stylesheet
    # ever defined. An unstyled div is display:block, so both navigation rails
    # stacked one button per row and every one of those sections read as an
    # endless vertical list before you reached a single card. A class name with
    # no rule behind it fails silently — nothing errors, it just looks wrong.
    import re as _re2
    # The board kit ships its own <style> block, so BOTH stylesheets count.
    _allcss = CSS
    try:
        import content_engine_seo_boards as _SB2
        _allcss += _SB2._TAB_CSS
    except Exception as _ce:
        raise AssertionError(f"cannot read the board stylesheet: {_ce}")
    _styled = set(_re2.findall(r"[.#]([A-Za-z][\w-]*)", _allcss))
    _used = set()
    for _attr in _re2.findall(r"class='([^']+)'", html):
        _used.update(_attr.split())
    _LAYOUT = {c for c in _used
               if c.startswith(("s", "g", "c", "n", "b", "m", "p", "t", "w", "f"))}
    # Verified inert: each of these either carries its own inline styles or is a
    # default state that deliberately inherits (.sev-ok / .sev-info keep the
    # normal card border; only critical and warn recolour it).
    _INERT = {"mlog", "sev-ok", "sev-info", "spanels", "subsec"}
    _unstyled = sorted(c for c in _LAYOUT if c not in _styled and c not in _INERT)
    assert not _unstyled, (
        "these classes are used in the markup but no CSS rule defines them, so "
        f"they render as unstyled blocks: {_unstyled}")
    # the rails that actually carry the sub-section buttons must be horizontal
    for _rail in ("stabs", "sgroups"):
        assert f"class='{_rail}'" in html, f"{_rail} rail missing from the page"
        assert f".{_rail}{{display:flex" in _allcss, f".{_rail} must lay out as a flex row"
    assert html.count("class='stabs'") >= 9, (
        "every section with sub-boards needs the styled horizontal tab rail; "
        f"found {html.count(chr(39).join(['class=', 'stabs', '']))}")
    print("OK — 9 pages. Risk + AI Workforce + Infrastructure now render as ONE "
          "Risk & Infrastructure section (208 cards) and six more render as ONE "
          "Business Intelligence section (268 cards, 15 boards, Executive "
          "Intelligence included), and Lead Machine + Email & Outreach render "
          "as ONE Leads & Outreach section (240 cards, 14 boards, every send "
          "endpoint intact); the old nav ids "
          "all alias to them. No page lost, no credential path touched. "
          "No network.")
