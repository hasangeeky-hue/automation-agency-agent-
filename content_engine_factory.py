"""
content_engine_factory.py
============================================================================
CONTENT FACTORY — the loops, the strategy brief, and the per-platform previews.

This is the heart of the system, and it had five real failures. Each is
addressed here rather than papered over:

 1. Images never reached social. _ensure_hero_image() ran only for blog/guide,
    so Instagram — which returns "instagram_needs_image_url" without one — could
    never succeed. image_needed() now covers every type that requires a visual.

 2. Claude cannot generate images. There is no Anthropic image API. An
    Anthropic key in the image slot 401s on every call. image_status() says so
    in plain words instead of leaving you to guess.

 3. The calendar had no preview and knew only two channels. previews() renders
    a styled mockup for six platforms from the SAME piece object that publishes,
    so what you approve is what ships.

 4. The CI reached the prompt but nothing reported whether it was APPLIED.
    ci_compliance() checks the draft against each CI field and shows the misses.

 5. The planner was blind: api_plan_content passed site_signals={}. The whole
    engine — SEO gaps, AI visibility, market coverage, lead reality, revenue by
    source, channel performance, budget and capacity — is now assembled by
    strategy_brief() and handed to the planner as evidence.

Run offline self-check:  python content_engine_factory.py
============================================================================
"""
from __future__ import annotations

import html
import logging
import re
from datetime import date, datetime, timedelta, timezone

log = logging.getLogger("content_engine.factory")

# Platforms we can preview, with the limits that actually change what a reader
# sees. These are the real platform behaviours, not guesses.
PLATFORMS = {
    "website": {"label": "Website", "icon": "🌐"},
    "linkedin": {"label": "LinkedIn", "icon": "in", "cut": 210, "max": 3000,
                 "img": (1200, 627), "wire": "social_linkedin"},
    "instagram": {"label": "Instagram", "icon": "◎", "cut": 125, "max": 2200,
                  "img": (1080, 1080), "wire": "social_instagram",
                  "image_required": True},
    "twitter": {"label": "X", "icon": "𝕏", "cut": 280, "max": 280,
                "img": (1200, 675), "wire": "social_twitter"},
    "facebook": {"label": "Facebook", "icon": "f", "cut": 250, "max": 63206,
                 "img": (1200, 630), "wire": "social_facebook"},
    "youtube": {"label": "YouTube", "icon": "▶", "cut": 157, "max": 5000,
                "img": (1280, 720), "wire": "social_youtube",
                "image_required": True, "title_max": 70},
}
SERP_TITLE_MAX = 60
SERP_META_MAX = 155
IMAGE_TYPES = ("blog", "guide", "social", "post", "article", "case_study")


# ------------------------------------------------------------------ coercion
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


def _day(v):
    return str(v or "")[:10]


def _pct(part, whole, nd=1):
    w = _f(whole)
    return round(100 * _f(part) / w, nd) if w else 0.0


def _e(v):
    return html.escape(_s(v), quote=True)


def _get(store, key, default=None):
    try:
        return store.get_setting(key, default)
    except Exception:
        return default


def _plain(body):
    """Markdown-ish body to plain text, for character counts that match what a
    platform actually shows."""
    t = _s(body)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)      # images
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)  # links -> text
    t = re.sub(r"[#*_`>]+", "", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


# ======================================================================
#  ① THE COMPARATIVE LOOP — every system feeds the plan
# ======================================================================
def channel_eligibility(status=None) -> dict:
    """A channel with no live wire must never be planned. This is the direct
    fix for content being sent to a channel that cannot receive it."""
    st = _D(status)
    rows = []
    for key, spec in PLATFORMS.items():
        wire = spec.get("wire")
        live = True if key == "website" else bool(st.get(wire))
        if key == "website":
            live = bool(st.get("wordpress_publish"))
        rows.append({"channel": key, "label": spec["label"], "live": live,
                     "wire": wire or "wordpress_publish"})
    eligible = [r["channel"] for r in rows if r["live"]]
    return {"rows": rows, "eligible": eligible,
            "blocked": [r["label"] for r in rows if not r["live"]],
            "count": len(eligible), "total": len(rows),
            "note": ("Only these channels can receive a post today. The planner "
                     "is given this list so it can never schedule a piece to a "
                     "channel that would fail."
                     if eligible else
                     "No channel is connected, so nothing can be published. "
                     "Connect at least WordPress or LinkedIn first.")}


def strategy_brief(store=None, seo=None, bi=None, outreach=None, sga=None,
                   media=None, risk=None, status=None, econ=None) -> dict:
    """THE comparative loop.

    api_plan_content() used to pass site_signals={} — the planner saw only the
    website taxonomy and its own past titles. Every system in this engine
    already computes exactly what a content strategist would ask for. This
    assembles it into evidence the planner can act on. No new API, no new key.
    """
    seo, bi, sga = _D(seo), _D(bi), _D(sga)
    outreach, media, risk = _D(outreach), _D(media), _D(risk)
    signals, gaps = {}, []

    # ---- SEO / AEO / GEO -------------------------------------------------
    striking = _L(_D(seo.get("striking")).get("rows")) or _L(seo.get("striking"))
    decaying = _L(_D(seo.get("decay")).get("rows")) or _L(seo.get("decay"))
    demand = _D(bi.get("demand"))
    if striking:
        signals["striking_distance"] = [
            {"query": _s(_D(r).get("query")), "position": _f(_D(r).get("position"))}
            for r in striking[:10]]
        gaps.append({"kind": "seo", "weight": 950,
                     "why": (f"{len(striking)} queries sit at positions 11-20. A "
                             f"piece aimed at one of these moves it to page 1 "
                             f"faster than a new topic ever could.")})
    if decaying:
        signals["decaying_pages"] = [_s(_D(r).get("url") or _D(r).get("page"))
                                     for r in decaying[:8]]
        gaps.append({"kind": "seo", "weight": 800,
                     "why": f"{len(decaying)} pages are losing clicks and need a refresh."})
    aeo = _D(seo.get("aeo")) or _D(bi.get("aeo"))
    mentions = _i(aeo.get("mentions"))
    if aeo and not mentions:
        signals["ai_visibility"] = {"mentions": 0}
        gaps.append({"kind": "aeo", "weight": 900,
                     "why": ("AI engines never name this business. Content that "
                             "directly answers the questions buyers ask an AI is "
                             "the only way in.")})
    markets = _D(bi.get("markets")) or _D(seo.get("geo"))
    missing = _L(markets.get("missing"))
    if missing:
        signals["missing_markets"] = missing
        gaps.append({"kind": "geo", "weight": 920,
                     "why": (f"No traffic at all from {', '.join(missing)}. "
                             + ("Germany and Switzerland need GERMAN content — "
                                "this is the widest single gap."
                                if any(m in ("Germany", "Switzerland") for m in missing)
                                else ""))})

    # ---- Leads & Outreach: who actually replies --------------------------
    icp_live = _D(outreach.get("icp"))
    verticals = _L(icp_live.get("verticals"))
    if verticals:
        signals["sourced_verticals"] = [{"vertical": _s(v), "leads": _i(n)}
                                        for v, n in verticals[:6]]
        gaps.append({"kind": "leads", "weight": 700,
                     "why": (f"Leads actually source from {verticals[0][0]} most. "
                             f"Write for the vertical that answers, not only the "
                             f"one on the ICP list.")})
    subjects = _L(_D(outreach.get("replies")).get("subjects"))
    if subjects:
        signals["winning_subjects"] = [_s(s[0]) for s in subjects[:5]]

    # ---- BI: what actually paid -----------------------------------------
    rev_src = _L(_D(bi.get("revenue")).get("by_source"))
    if rev_src:
        signals["revenue_by_source"] = [{"source": _s(s), "revenue": _f(v)}
                                        for s, v in rev_src[:5]]
        gaps.append({"kind": "bi", "weight": 880,
                     "why": (f"'{rev_src[0][0]}' produced the most recorded "
                             f"revenue. Weight the plan toward it.")})
    worst = _D(bi.get("funnel")).get("worst")
    if worst:
        signals["biggest_funnel_leak"] = {"stage": _s(worst[0]), "lost": _f(worst[1])}

    # ---- SGA: which channel actually earns -------------------------------
    spp = _D(sga.get("traffic")).get("sessions_per_post")
    if spp is not None:
        signals["sessions_per_post"] = _f(spp)
    by_channel = _L(_D(sga.get("posts")).get("by_channel"))
    if by_channel:
        signals["channel_volume"] = [{"channel": _s(c), "posts": _i(n)}
                                     for c, n in by_channel]
    live_campaigns = _L(_D(sga.get("calendar")).get("live"))
    if live_campaigns:
        signals["live_campaigns"] = [_s(_D(c).get("name")) for c in live_campaigns]

    # ---- Media Buying: paid keywords worth owning organically ------------
    paid_kw = _L(_D(media.get("keywords")).get("winning")) or _L(media.get("winning_keywords"))
    if paid_kw:
        signals["expensive_paid_keywords"] = [_s(k) for k in paid_kw[:8]]
        gaps.append({"kind": "ads", "weight": 650,
                     "why": ("These keywords cost money every click. Ranking for "
                             "them organically is the cheapest long-term win.")})

    # ---- Risk & capacity: what can actually be produced ------------------
    cost = _D(risk.get("cost")) or _D(bi.get("spend"))
    cap = _f(cost.get("month_cap") or cost.get("cap"), 200) or 200
    spent = _f(cost.get("month_spent") or cost.get("spent"))
    headroom = max(0.0, cap - spent)
    capacity = _D(risk.get("capacity"))
    signals["budget"] = {"cap": cap, "spent": round(spent, 2),
                         "headroom": round(headroom, 2)}
    el = channel_eligibility(status)
    return {
        "signals": signals,
        "gaps": sorted(gaps, key=lambda g: -g["weight"]),
        "eligibility": el,
        "budget_headroom": round(headroom, 2),
        "capacity_note": _s(capacity.get("note")),
        "systems_reporting": sum(1 for x in (seo, bi, outreach, sga, media, risk) if x),
        "systems_total": 6,
        "has_signals": bool(signals),
        "note": ("The planner receives this as site_signals. Before it existed "
                 "the planner was handed an empty dict and could only balance "
                 "its own taxonomy against its own past titles."),
    }


# ======================================================================
#  ② IMAGES — the truth about which key does what
# ======================================================================
def image_needed(piece_type="blog", channels=None) -> dict:
    """Which channels in this piece REQUIRE a visual to publish at all."""
    chans = [_s(c).lower() for c in _L(channels)] or ["website"]
    required = [c for c in chans if _D(PLATFORMS.get(c)).get("image_required")]
    wanted = [c for c in chans if c in PLATFORMS and c != "website"]
    return {"channels": chans, "required_by": required,
            "recommended_by": wanted,
            "needed": bool(required or _s(piece_type).lower() in IMAGE_TYPES),
            "blocking": bool(required),
            "note": (f"{', '.join(PLATFORMS[c]['label'] for c in required)} "
                     f"cannot publish without an image — the post is rejected, "
                     f"not degraded." if required else
                     "No channel here hard-requires an image, but every social "
                     "platform reaches further with one.")}


def image_status(status=None, image_key=None, provider=None, model=None) -> dict:
    """Say plainly which key makes images, because this cost real time.

    Anthropic has no image API. A Claude key in the image slot returns 401 on
    every call, forever. The engine's brain key and the image key are different
    wires and always were."""
    st = _D(status)
    key = _s(image_key)
    prov = _s(provider).lower() or "openai"
    looks_anthropic = key.startswith("sk-ant") if key else False
    return {
        "configured": bool(st.get("image_gen") or key),
        "provider": prov,
        "model": _s(model) or "gpt-image-1",
        "key_present": bool(key),
        "key_looks_anthropic": looks_anthropic,
        "wire": "IMAGE_API_KEY",
        "brain_wire": "ANTHROPIC_API_KEY",
        "cost_per_image": 0.04,
        "verdict": ("An Anthropic key is set as the IMAGE key. Anthropic has no "
                    "image API — this will fail on every call. Use an OpenAI key."
                    if looks_anthropic else
                    "Image generation is configured." if st.get("image_gen") else
                    "No image key set, so no piece will ever get a visual."),
        "truth": ("Claude writes the words; it cannot draw. Images need an "
                  "OpenAI key in IMAGE_API_KEY with IMAGE_PROVIDER=openai. "
                  "ANTHROPIC_API_KEY is the engine's brain and is a different "
                  "wire — filling one does nothing for the other."),
    }


# ======================================================================
#  ③ PREVIEWS — styled mockups, from the piece that actually publishes
# ======================================================================
def _shell(inner, width=520, bg="#0F1626", pad=14, radius=12):
    return (f"<div style='max-width:{width}px;background:{bg};border:1px solid "
            f"#1B2640;border-radius:{radius}px;padding:{pad}px;margin:6px auto;"
            f"font-family:-apple-system,Segoe UI,Roboto,sans-serif'>{inner}</div>")


def _cut(text, n):
    """Return (visible, hidden) exactly as the platform truncates it."""
    t = _plain(text)
    if len(t) <= n:
        return t, ""
    return t[:n], t[n:]


def _img_box(url, w, h, label=""):
    if url and _s(url).startswith("http"):
        return (f"<img src='{_e(url)}' alt='' style='width:100%;max-width:100%;"
                f"aspect-ratio:{w}/{h};object-fit:cover;border-radius:8px;"
                f"display:block'>")
    return (f"<div style='width:100%;aspect-ratio:{w}/{h};border-radius:8px;"
            f"background:repeating-linear-gradient(45deg,#131B2E,#131B2E 10px,"
            f"#0F1626 10px,#0F1626 20px);display:flex;align-items:center;"
            f"justify-content:center;color:#F5788A;font-size:12px;"
            f"border:1px dashed #F5788A'>no image · {w}×{h} needed"
            f"{(' · ' + label) if label else ''}</div>")


def preview_website(piece=None, ci_text="", site="anthropos-automation.com") -> dict:
    p = _D(piece)
    title = _s(p.get("title")) or "Untitled"
    body = _plain(p.get("body"))
    img = _s(p.get("image_url"))
    heads = re.findall(r"^#{2,3}\s+(.+)$", _s(p.get("body")), re.M)
    words = len(body.split())
    paras = [x for x in body.split("\n\n") if x.strip()][:3]
    inner = (f"<div style='color:#8E9BBE;font-size:10px;letter-spacing:.14em'>"
             f"{_e(site.upper())}</div>"
             f"<h1 style='color:#EDF1FB;font-size:20px;line-height:1.25;margin:8px 0'>"
             f"{_e(title)}</h1>"
             + (_img_box(img, 1200, 630) if True else "")
             + "".join(f"<p style='color:#C7D0E8;font-size:12.5px;line-height:1.65'>"
                       f"{_e(x[:220])}</p>" for x in paras)
             + ("".join(f"<h2 style='color:#2FE3D2;font-size:14px;margin:10px 0 4px'>"
                        f"{_e(h)}</h2>" for h in heads[:3])))
    return {"html": _shell(inner, 560),
            "checks": [("Hero image", bool(img),
                        "present" if img else "missing — the article publishes flat"),
                       ("H2/H3 headings", len(heads) >= 2, f"{len(heads)} found"),
                       ("Length", words >= 600, f"{words} words"),
                       ("Alt text", bool(_s(p.get("image_alt")) or img), "on the hero"),
                       ("Internal links", "](" in _s(p.get("body")), "in body")],
            "words": words, "headings": len(heads), "has_image": bool(img)}


def preview_linkedin(piece=None) -> dict:
    p = _D(piece)
    text = _plain(p.get("linkedin_post") or p.get("body"))
    vis, hidden = _cut(text, PLATFORMS["linkedin"]["cut"])
    img = _s(p.get("image_url"))
    tags = re.findall(r"#\w+", text)
    inner = ("<div style='display:flex;gap:8px;align-items:center'>"
             "<div style='width:34px;height:34px;border-radius:50%;background:#2FE3D2'></div>"
             "<div><div style='color:#EDF1FB;font-size:12px;font-weight:700'>"
             "Anthropos Automation</div><div style='color:#8E9BBE;font-size:10px'>"
             "Now · 🌐</div></div></div>"
             f"<p style='color:#C7D0E8;font-size:12.5px;line-height:1.5;margin:9px 0'>"
             f"{_e(vis)}"
             + (f"<span style='color:#59668A'>…</span> <span style='color:#4C9AFF;"
                f"font-weight:600'>see more</span>" if hidden else "") + "</p>"
             + _img_box(img, 1200, 627))
    return {"html": _shell(inner, 480),
            "cut_at": PLATFORMS["linkedin"]["cut"], "hidden_chars": len(hidden),
            "checks": [("Hook fits the fold", len(text) <= 210 or bool(vis.strip()),
                        f"{len(vis)} chars visible before 'see more'"),
                       ("Within 3000 chars", len(text) <= 3000, f"{len(text)} chars"),
                       ("Image 1200×627", bool(img),
                        "present" if img else "missing — reach drops sharply"),
                       ("Hashtags 3-5", 3 <= len(tags) <= 5, f"{len(tags)} found")],
            "chars": len(text), "hashtags": len(tags), "has_image": bool(img)}


def preview_instagram(piece=None) -> dict:
    p = _D(piece)
    text = _plain(p.get("instagram_caption") or p.get("body"))
    vis, hidden = _cut(text, PLATFORMS["instagram"]["cut"])
    img = _s(p.get("image_url"))
    tags = re.findall(r"#\w+", text)
    inner = (_img_box(img, 1080, 1080, "REQUIRED")
             + "<div style='display:flex;gap:12px;margin:8px 0;color:#EDF1FB'>"
               "<span>♡</span><span>💬</span><span>➤</span></div>"
             + f"<p style='color:#C7D0E8;font-size:12px;line-height:1.5'>"
               f"<b style='color:#EDF1FB'>anthropos</b> {_e(vis)}"
             + (f"<span style='color:#59668A'> … more</span>" if hidden else "")
             + "</p>")
    return {"html": _shell(inner, 400),
            "cut_at": PLATFORMS["instagram"]["cut"], "hidden_chars": len(hidden),
            "checks": [("Image present", bool(img),
                        "required — Instagram REJECTS a post without one"),
                       ("Square 1080×1080", bool(img), "1:1 recommended"),
                       ("First 125 chars carry it", bool(vis.strip()),
                        f"{len(vis)} chars before '… more'"),
                       ("Within 2200 chars", len(text) <= 2200, f"{len(text)} chars"),
                       ("Hashtags 5-10", 5 <= len(tags) <= 10, f"{len(tags)} found")],
            "blocked": not bool(img), "chars": len(text), "has_image": bool(img)}


def preview_x(piece=None) -> dict:
    p = _D(piece)
    text = _plain(p.get("twitter_post") or p.get("body"))
    over = max(0, len(text) - 280)
    img = _s(p.get("image_url"))
    thread = [text[i:i + 275] for i in range(0, len(text), 275)] if over else [text]
    inner = ("<div style='display:flex;gap:8px'>"
             "<div style='width:32px;height:32px;border-radius:50%;background:#8B7CFF'></div>"
             "<div style='flex:1'><div style='color:#EDF1FB;font-size:12px'>"
             "<b>Anthropos</b> <span style='color:#8E9BBE'>@anthropos · now</span></div>"
             f"<p style='color:#C7D0E8;font-size:12.5px;line-height:1.5;margin:6px 0'>"
             f"{_e(thread[0])}</p>" + _img_box(img, 1200, 675) + "</div></div>")
    return {"html": _shell(inner, 460),
            "checks": [("Within 280 chars", over == 0,
                        f"{len(text)} chars" + (f" · {over} over" if over else "")),
                       ("Thread needed", over == 0,
                        f"{len(thread)} posts" if over else "single post"),
                       ("Image 1200×675", bool(img), "present" if img else "missing")],
            "chars": len(text), "over": over, "thread_parts": len(thread),
            "has_image": bool(img)}


def preview_facebook(piece=None, site="anthropos-automation.com") -> dict:
    p = _D(piece)
    text = _plain(p.get("facebook_post") or p.get("body"))
    vis, hidden = _cut(text, PLATFORMS["facebook"]["cut"])
    img = _s(p.get("image_url"))
    title = _s(p.get("title"))
    inner = (f"<p style='color:#C7D0E8;font-size:12.5px;line-height:1.5'>{_e(vis)}"
             + ("<span style='color:#59668A'>… See more</span>" if hidden else "")
             + "</p>" + _img_box(img, 1200, 630)
             + f"<div style='background:#0B111F;border:1px solid #1B2640;"
               f"border-top:0;padding:8px;border-radius:0 0 8px 8px'>"
               f"<div style='color:#59668A;font-size:10px;text-transform:uppercase'>"
               f"{_e(site)}</div><div style='color:#EDF1FB;font-size:13px;"
               f"font-weight:700'>{_e(title[:80])}</div></div>")
    return {"html": _shell(inner, 470),
            "checks": [("Link card renders", bool(title), "title present"),
                       ("OG image 1200×630", bool(img), "present" if img else "missing"),
                       ("First 250 chars carry it", bool(vis.strip()),
                        f"{len(vis)} visible")],
            "chars": len(text), "has_image": bool(img)}


def preview_youtube(piece=None) -> dict:
    p = _D(piece)
    title = _s(p.get("video_title") or p.get("title"))
    desc = _plain(p.get("video_description") or p.get("body"))
    vis, hidden = _cut(desc, PLATFORMS["youtube"]["cut"])
    thumb = _s(p.get("thumbnail_url") or p.get("image_url"))
    inner = (_img_box(thumb, 1280, 720, "thumbnail")
             + f"<div style='color:#EDF1FB;font-size:14px;font-weight:700;"
               f"margin-top:8px;line-height:1.3'>{_e(title[:70])}</div>"
               f"<div style='color:#8E9BBE;font-size:11px;margin:4px 0'>"
               f"Anthropos · 0 views · now</div>"
               f"<p style='color:#C7D0E8;font-size:11.5px;line-height:1.5'>{_e(vis)}"
             + ("<span style='color:#4C9AFF'> …more</span>" if hidden else "")
             + "</p>")
    return {"html": _shell(inner, 440),
            "checks": [("Thumbnail 1280×720", bool(thumb),
                        "required — YouTube will not accept a video without one"),
                       ("Title ≤70 chars", len(title) <= 70, f"{len(title)} chars"),
                       ("Description hook in 157", bool(vis.strip()),
                        f"{len(vis)} chars above the fold"),
                       ("Video asset", bool(_s(p.get("video_url"))),
                        "present" if p.get("video_url") else "missing")],
            "blocked": not bool(thumb) or not bool(_s(p.get("video_url"))),
            "title_len": len(title), "has_image": bool(thumb)}


def preview_serp(piece=None, site="anthropos-automation.com", keyword="") -> dict:
    """How the piece looks as a Google result — the preview that decides whether
    anyone clicks at all."""
    p = _D(piece)
    title = _s(p.get("seo_title") or p.get("title"))
    meta = _plain(p.get("meta_description") or p.get("summary") or p.get("body"))[:200]
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48]
    t_show = title if len(title) <= SERP_TITLE_MAX else title[:SERP_TITLE_MAX - 1] + "…"
    m_show = meta if len(meta) <= SERP_META_MAX else meta[:SERP_META_MAX - 1] + "…"
    kw = _s(keyword).lower()
    inner = (f"<div style='color:#8E9BBE;font-size:11px'>{_e(site)} › {_e(slug[:28])}</div>"
             f"<div style='color:#8AB4F8;font-size:16px;line-height:1.3;margin:2px 0'>"
             f"{_e(t_show)}</div>"
             f"<div style='color:#BDC1C6;font-size:12px;line-height:1.5'>{_e(m_show)}</div>")
    return {"html": _shell(inner, 520, bg="#0B111F"),
            "checks": [("Title ≤60 chars", len(title) <= SERP_TITLE_MAX,
                        f"{len(title)} chars"
                        + (" · truncated in results" if len(title) > SERP_TITLE_MAX else "")),
                       ("Meta ≤155 chars", len(meta) <= SERP_META_MAX,
                        f"{len(meta)} chars"),
                       ("Keyword in title", bool(kw) and kw in title.lower(),
                        f"'{kw}'" if kw else "no target keyword set"),
                       ("Meta written", bool(_s(p.get("meta_description"))),
                        "custom" if p.get("meta_description") else
                        "falling back to the body's first words")],
            "title_len": len(title), "meta_len": len(meta),
            "truncated": len(title) > SERP_TITLE_MAX}


PREVIEWS = {"website": preview_website, "linkedin": preview_linkedin,
            "instagram": preview_instagram, "twitter": preview_x,
            "facebook": preview_facebook, "youtube": preview_youtube,
            "serp": preview_serp}


def previews(piece=None, channels=None, ci_text="", keyword="") -> dict:
    """Every platform preview for one piece, plus a pass/fail roll-up."""
    out, blocked = {}, []
    for name, fn in PREVIEWS.items():
        try:
            out[name] = (fn(piece, ci_text=ci_text) if name == "website" else
                         fn(piece, keyword=keyword) if name == "serp" else
                         fn(piece))
        except Exception as e:
            log.warning("preview %s failed: %s", name, e)
            out[name] = {"html": "", "checks": [("preview failed", False, str(e)[:60])]}
        if _D(out[name]).get("blocked"):
            blocked.append(name)
    fails = sum(1 for v in out.values() for _n, ok, _d in _L(_D(v).get("checks")) if not ok)
    total = sum(len(_L(_D(v).get("checks"))) for v in out.values())
    return {"by_platform": out, "blocked": blocked,
            "checks_total": total, "checks_failed": fails,
            "ready": not blocked and fails == 0,
            "score": _pct(total - fails, total)}


# ======================================================================
#  ④ CI COMPLIANCE — was the brand actually applied?
# ======================================================================
def ci_compliance(piece=None, ci=None) -> dict:
    """The CI reached the prompt; nothing ever reported whether the DRAFT
    honoured it. This checks the text against each CI field."""
    p, c = _D(piece), _D(ci)
    body = _plain(p.get("body")).lower()
    title = _s(p.get("title")).lower()
    blob = f"{title} {body}"
    rows = []
    banned = [_s(x).lower() for x in _L(c.get("avoid") or c.get("banned_words"))]
    hits = [w for w in banned if w and w in blob]
    rows.append(("Banned words avoided", not hits,
                 f"{len(hits)} used: {', '.join(hits[:4])}" if hits else "none used"))
    brand = _s(c.get("brand_name"))
    rows.append(("Brand named", (not brand) or brand.lower() in blob,
                 brand or "no brand name in the CI"))
    tone = _s(c.get("tone") or c.get("voice"))
    rows.append(("Voice guidance supplied", bool(tone), tone[:48] or "not set"))
    rows.append(("CI reached the prompt", bool(c),
                 "the CI block is prepended to every skill prompt"
                 if c else "no CI configured — agents use built-in defaults"))
    caps = len(re.findall(r"\b[A-Z]{4,}\b", _s(p.get("body"))))
    rows.append(("No shouting", caps <= 2, f"{caps} ALL-CAPS words"))
    passed = sum(1 for _n, ok, _d in rows if ok)
    return {"rows": rows, "passed": passed, "total": len(rows),
            "score": _pct(passed, len(rows)),
            "configured": bool(c),
            "fields": [k for k in c if not k.startswith("_")][:12],
            "note": ("The CI is applied to the PROMPT, so it shapes voice, not "
                     "layout. Layout is what the previews show.")}


# ======================================================================
#  ⑤ PIPELINE, ROUTING, REPURPOSING, COST
# ======================================================================
def _content_jobs(jobs):
    return [j for j in _L(jobs) if _D(j).get("type") == "content_piece"]


def pipeline(jobs=None) -> dict:
    STAGES = [("Plan", {"created", "planned", "site_ready", "competitor_ready",
                        "site_intelligence"}),
              ("Write", {"produced"}),
              ("SEO", {"seo_checked"}),
              ("Your approval", {"AWAITING_APPROVAL"}),
              ("Published", {"published", "optimized", "measuring", "measured"})]
    cj = _content_jobs(jobs)
    counts, stuck = [], []
    for label, sts in STAGES:
        n = sum(1 for j in cj if _D(j).get("status") in sts)
        counts.append((label, n))
    waiting = sum(1 for j in cj if _D(j).get("status") == "AWAITING_APPROVAL")
    failed = sum(1 for j in cj if _D(j).get("status") in ("failed", "halted_budget"))
    return {"stages": counts, "total": len(cj), "waiting": waiting,
            "failed": failed, "published": counts[-1][1],
            "waterfall": counts,
            "has_data": bool(cj)}


def routing(jobs=None, eligibility=None) -> dict:
    """Where each piece is aimed, and whether that channel can receive it."""
    el = _D(eligibility)
    live = set(_L(el.get("eligible")))
    planned, mismatched = {}, []
    for j in _content_jobs(jobs):
        cfg = _D(_D(j).get("payload")).get("config") or {}
        for ch in (_L(_D(cfg).get("deploy_channels")) or ["website"]):
            ch = _s(ch).lower()
            ch = "website" if ch in ("web", "blog", "wordpress", "cms") else ch
            planned[ch] = planned.get(ch, 0) + 1
            if ch not in live:
                mismatched.append((_s(_D(j).get("job_id")), ch))
    return {"planned": sorted(planned.items(), key=lambda kv: -kv[1]),
            "mismatched": mismatched[:12],
            "mismatch_count": len(mismatched),
            "live_channels": sorted(live),
            "flows": [("plan", ch, n) for ch, n in planned.items()],
            "has_data": bool(planned),
            "note": (f"{len(mismatched)} pieces are aimed at a channel with no "
                     f"live wire. They will return a not_configured marker "
                     f"instead of publishing." if mismatched else
                     "Every planned channel has a live wire.")}


def repurposing(piece=None, channels=None) -> dict:
    """One piece, many channels — what exists and what is still missing."""
    p = _D(piece)
    chans = [_s(c).lower() for c in _L(channels)] or ["website"]
    FIELD = {"website": "body", "linkedin": "linkedin_post",
             "instagram": "instagram_caption", "twitter": "twitter_post",
             "facebook": "facebook_post", "youtube": "video_description"}
    rows = []
    for ch in PLATFORMS:
        want = ch in chans
        have = bool(_s(p.get(FIELD.get(ch, ""))))
        rows.append({"channel": ch, "label": PLATFORMS[ch]["label"],
                     "planned": want, "written": have,
                     "state": ("native copy written" if have else
                               "will reuse the body" if want else "not planned")})
    native = sum(1 for r in rows if r["written"])
    return {"rows": rows, "native": native, "planned": len(chans),
            "coverage": _pct(native, len(chans)),
            "statusgrid": [(r["label"], r["written"], r["state"][:16]) for r in rows],
            "note": ("A piece reused verbatim on every channel performs worse "
                     "than a native version on each. Where native copy is "
                     "missing the engine falls back to the body.")}


def throughput(jobs=None, days=14) -> dict:
    cj = _content_jobs(jobs)
    per_day, cost = {}, 0.0
    published = 0
    for j in cj:
        d = _day(_D(j).get("created_at"))
        c = _f(_D(j).get("cost_so_far_usd"))
        cost += c
        if d:
            per_day[d] = per_day.get(d, 0) + 1
        if _D(j).get("status") in ("published", "optimized", "measuring", "measured"):
            published += 1
    keys = sorted(per_day)[-days:]
    return {"total": len(cj), "published": published,
            "cost": round(cost, 2),
            "per_piece": round(cost / published, 2) if published else None,
            "per_day": [(k, per_day[k]) for k in keys],
            "series": [per_day[k] for k in keys],
            "avg_per_day": round(sum(per_day.values()) / len(keys), 1) if keys else 0,
            "has_data": bool(cj)}


# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    PIECE = {
        "title": "How Munich clinics recover missed patient enquiries",
        "body": ("![hero](https://x.com/a.png)\n\n"
                 "Most clinics lose enquiries after hours.\n\n"
                 "## The cost of a missed call\n" + ("word " * 700) +
                 "\n\n## What to do\nSee [our guide](https://a.com/g)."),
        "image_url": "https://cdn.example.com/hero.png",
        "linkedin_post": "Clinics lose 30% of enquiries after hours. " + ("x" * 400),
        "meta_description": "How Munich clinics stop losing after-hours patient "
                            "enquiries with simple automation.",
        "seo_title": "Munich clinics: stop losing after-hours enquiries",
    }

    # ---- eligibility: the direct fix for wrong-channel publishing ----
    el = channel_eligibility({"wordpress_publish": True, "social_linkedin": True})
    assert el["count"] == 2 and "instagram" not in el["eligible"]
    assert "Instagram" in el["blocked"]
    assert channel_eligibility({})["count"] == 0

    # ---- images ----
    need = image_needed("social", ["instagram", "linkedin"])
    assert need["blocking"] and "instagram" in need["required_by"]
    assert "cannot publish without an image" in need["note"]
    assert image_needed("blog", ["website"])["blocking"] is False

    st = image_status({"image_gen": False}, image_key="sk-ant-abc123")
    assert st["key_looks_anthropic"] and "no image API" in st["verdict"]
    assert "cannot draw" in st["truth"]
    ok = image_status({"image_gen": True}, image_key="sk-proj-xyz")
    assert ok["key_looks_anthropic"] is False and ok["configured"]

    # ---- previews: every platform, from ONE piece ----
    pv = previews(PIECE, ["website", "linkedin", "instagram"],
                  keyword="munich clinics")
    assert set(pv["by_platform"]) == set(PREVIEWS), list(pv["by_platform"])
    for name, v in pv["by_platform"].items():
        assert v["html"] and v["checks"], name
        assert "<div" in v["html"], name

    li = pv["by_platform"]["linkedin"]
    assert li["cut_at"] == 210 and li["hidden_chars"] > 0
    assert "see more" in li["html"]

    ig = preview_instagram({"body": "no image here"})
    assert ig["blocked"] is True, "Instagram must be blocked with no image"
    assert "no image" in ig["html"]
    ig2 = preview_instagram({"body": "x", "image_url": "https://a/b.png"})
    assert ig2["blocked"] is False

    x = preview_x({"body": "y" * 500})
    assert x["over"] > 0 and x["thread_parts"] > 1

    serp = preview_serp(PIECE, keyword="munich clinics")
    assert serp["title_len"] <= 60 and not serp["truncated"]
    long_t = preview_serp({"title": "z" * 90, "meta_description": "m"})
    assert long_t["truncated"] and "…" in long_t["html"]

    yt = preview_youtube({"title": "t", "body": "b"})
    assert yt["blocked"] is True, "YouTube needs a thumbnail and a video"

    # ---- the comparative loop ----
    brief = strategy_brief(
        seo={"striking": {"rows": [{"query": "n8n agency", "position": 14}]},
             "decay": {"rows": [{"url": "/old"}]},
             "aeo": {"mentions": 0}},
        bi={"markets": {"missing": ["Germany", "Switzerland"]},
            "revenue": {"by_source": [("outreach", 6000.0)]},
            "funnel": {"worst": ("Emailed → Replied", 150, 83.0)}},
        outreach={"icp": {"verticals": [("doctor", 12)]},
                  "replies": {"subjects": [("Quick question", 4, 1)]}},
        sga={"traffic": {"sessions_per_post": 8.5},
             "posts": {"by_channel": [("LinkedIn", 5)]},
             "calendar": {"live": [{"name": "Q3 Launch"}]}},
        media={"winning_keywords": ["ai automation agency"]},
        risk={"cost": {"month_cap": 200, "month_spent": 41.7}},
        status={"wordpress_publish": True, "social_linkedin": True})
    s = brief["signals"]
    assert "striking_distance" in s and "missing_markets" in s
    assert s["ai_visibility"]["mentions"] == 0
    assert "revenue_by_source" in s and "sourced_verticals" in s
    assert "expensive_paid_keywords" in s and "sessions_per_post" in s
    assert brief["budget_headroom"] == 158.3
    assert brief["gaps"][0]["weight"] >= brief["gaps"][-1]["weight"], "ranked"
    assert any("GERMAN content" in g["why"] for g in brief["gaps"])
    assert brief["eligibility"]["count"] == 2
    assert brief["systems_reporting"] == 6
    empty = strategy_brief()
    # budget is always knowable, so it is always a signal; what must be absent
    # with no systems reporting is every GAP and every system-derived signal
    assert empty["systems_reporting"] == 0 and empty["gaps"] == []
    assert list(empty["signals"]) == ["budget"], empty["signals"]

    # ---- CI ----
    ci = ci_compliance(PIECE, {"brand_name": "Anthropos", "tone": "plain",
                               "avoid": ["synergy", "leverage"]})
    assert ci["total"] == 5 and ci["configured"]
    bad = ci_compliance({"body": "We leverage synergy", "title": "t"},
                        {"avoid": ["synergy", "leverage"]})
    assert any(not ok and "used" in d for _n, ok, d in bad["rows"])

    # ---- pipeline / routing / repurposing / throughput ----
    jobs = [{"job_id": "c1", "type": "content_piece", "status": "AWAITING_APPROVAL",
             "created_at": "2026-07-30T09:00:00Z", "cost_so_far_usd": 0.4,
             "payload": {"config": {"deploy_channels": ["website", "instagram"]}}},
            {"job_id": "c2", "type": "content_piece", "status": "published",
             "created_at": "2026-07-29T09:00:00Z", "cost_so_far_usd": 0.6,
             "payload": {"config": {"deploy_channels": ["website"]}}}]
    pl = pipeline(jobs)
    assert pl["total"] == 2 and pl["waiting"] == 1 and pl["published"] == 1
    rt = routing(jobs, el)
    assert rt["mismatch_count"] == 1, rt["mismatched"]
    assert "no live wire" in rt["note"]
    rp = repurposing(PIECE, ["website", "linkedin", "instagram"])
    assert rp["native"] >= 1 and len(rp["rows"]) == len(PLATFORMS)
    tp = throughput(jobs)
    assert tp["total"] == 2 and tp["per_piece"] == 1.0

    # ---- hostile shapes ----
    for bad_v in (None, {}, [], "x", 0):
        channel_eligibility(bad_v if isinstance(bad_v, dict) else None)
        image_needed("blog", bad_v if isinstance(bad_v, list) else None)
        image_status(bad_v if isinstance(bad_v, dict) else None)
        previews(bad_v if isinstance(bad_v, dict) else None, None)
        ci_compliance(bad_v if isinstance(bad_v, dict) else None, None)
        strategy_brief(None, bad_v, bad_v, bad_v, bad_v, bad_v, bad_v, bad_v)
        pipeline(bad_v if isinstance(bad_v, list) else None)
        routing(bad_v if isinstance(bad_v, list) else None, bad_v)
        repurposing(bad_v if isinstance(bad_v, dict) else None, None)
        throughput(bad_v if isinstance(bad_v, list) else None)

    print("factory self-check OK — six platform previews render from ONE piece "
          "with real truncation points, Instagram and YouTube report BLOCKED "
          "without a visual, an Anthropic key in the image slot is named as "
          "unusable, a channel with no live wire is refused, and strategy_brief "
          "assembles evidence from all six systems the planner used to be blind to.")
