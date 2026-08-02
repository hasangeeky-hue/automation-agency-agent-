"""
content_engine_site_taxonomy.py
============================================================================
The REAL structure of anthropos-automation.com — so the Content Factory writes
FOR the website (its customer segments + service pillars) instead of producing
generic machine articles. Sourced from the live site's blog taxonomy:

  BY BUSINESS (who): 7 customer segments, each with a /services/ page.
  BY SERVICE  (what): 6 service pillars = the 5 blog "reading paths".

Every piece the factory makes is tagged with ONE segment + ONE pillar, which:
  - focuses the writing on that audience's real situation, and
  - routes the post to the right WordPress category (services / blogs / guides).

Also carries the on-brand IMAGE style so generated blog images match the site
(dark theme, cyan/violet accents) instead of random stock-looking pictures.
============================================================================
"""

from __future__ import annotations

SITE_URL = "https://anthropos-automation.com"

# --- BY BUSINESS: the 7 customer segments (name -> services page + keywords) ---
SEGMENTS = [
    {"key": "regulated", "name": "Regulated Professionals",
     "url": "/services/regulated-professionals/",
     "kw": ["lawyer", "attorney", "legal", "accountant", "tax", "compliance", "regulated", "finance", "advisor"]},
    {"key": "medical", "name": "Medical Professionals",
     "url": "/services/medical-professionals/",
     "kw": ["doctor", "clinic", "dental", "dentist", "medical", "healthcare", "patient", "practice", "therapist"]},
    {"key": "ecommerce", "name": "E-Commerce & Retail",
     "url": "/services/ecommerce-retail/",
     "kw": ["shopify", "ecommerce", "e-commerce", "store", "retail", "cart", "checkout", "product", "order"]},
    {"key": "service", "name": "Service-Based Professionals",
     "url": "/services/service-professionals/",
     "kw": ["salon", "trades", "contractor", "plumber", "cleaning", "booking", "appointment", "local service"]},
    {"key": "freelancers", "name": "Freelancers & Micro-Agencies",
     "url": "/services/freelancers-agencies/",
     "kw": ["freelancer", "agency", "micro-agency", "solo", "consultant", "studio"]},
    {"key": "creators", "name": "Creators & Coaches",
     "url": "/services/creators-coaches/",
     "kw": ["creator", "coach", "course", "audience", "newsletter", "influencer", "content creator"]},
    {"key": "b2b", "name": "B2B Service Providers",
     "url": "/services/b2b-providers/",
     "kw": ["b2b", "saas", "software", "provider", "enterprise", "sales team", "pipeline"]},
]

# --- BY SERVICE: the 6 pillars (= the site's 5 "reading paths" + whole-business) ---
PILLARS = [
    {"key": "get_found", "name": "Get Found", "service": "AEO / GEO",
     "wp": "Get Found", "kw": ["seo", "aeo", "geo", "search", "found", "ranking", "answer engine", "local search", "visibility"]},
    {"key": "convert", "name": "Convert Visitors", "service": "Web Design",
     "wp": "Convert Visitors", "kw": ["web design", "website", "landing", "conversion", "5-second", "ux", "redesign", "page"]},
    {"key": "never_lose_lead", "name": "Never Lose a Lead", "service": "Lead",
     "wp": "Never Lose a Lead", "kw": ["lead", "reply", "follow-up", "nurture", "response", "inquiry", "60-second", "win-back", "crm"]},
    {"key": "campaigns", "name": "Grow with Campaigns", "service": "Marketing / Social",
     "wp": "Grow with Campaigns", "kw": ["campaign", "marketing", "social", "ads", "email marketing", "outreach", "reach", "content marketing"]},
    {"key": "automate", "name": "Automate Everything", "service": "Whole-Business",
     "wp": "Automate Everything", "kw": ["automation", "n8n", "ai agent", "workflow", "dashboard", "integrate", "whole business", "tool sprawl", "system"]},
]

# ===========================================================================
# THE ONE CONTENT VOCABULARY.
#
# There were FIVE lists of content types across four files, and only "blog"
# appeared in all of them:
#
#   strategist schema enum   blog, social_carousel, reel, email
#   prep image gate          blog, guide, social, post, article, case_study
#   factory.IMAGE_TYPES      blog, guide, social, post, article, case_study
#   KIND_CATEGORY            blog, guide, service, social_carousel, reel, email
#   prep._LENGTH_BY_TYPE     blog, social_carousel, reel, email
#
# The strategist writes the type; the image gate reads it. Their lists shared
# one word, so every piece that was not a blog silently got no hero image -
# no error, no card, nothing. Two word-lists that must agree, with nothing
# making them agree, is a bug waiting for a quiet week. This is the list.
# ===========================================================================
CONTENT_TYPES = ("blog", "guide", "service", "social_carousel", "reel", "email")

# Types that never carry a hero image. Everything else DOES - an opt-out, not
# an opt-in, because a new type added later should get a picture by default
# rather than silently going without one.
NO_IMAGE_TYPES = ("email",)

# What the strategist is allowed to PLAN. A service page is a site page someone
# writes on purpose, not something a campaign schedules, so it is a valid
# content type but not a plannable one. Everything here must be in
# CONTENT_TYPES - verify_vocabulary.py asserts it.
PLANNABLE_TYPES = ("blog", "guide", "social_carousel", "reel", "email")


# Types that never get repurposed into a LinkedIn post. An email already IS
# the message; everything else - including a carousel or a reel script - has a
# LinkedIn version worth writing.
NO_LINKEDIN_TYPES = ("email",)


# Types too short to be worth a live web-research pass. A carousel and a reel
# script are built from a piece that was already researched.
NO_RESEARCH_TYPES = ("social_carousel", "reel")


def wants_research(kind: str) -> bool:
    """Should this piece get a live web-research brief? Unknown types do.

    The hand-written version of this rule said ("blog", "email") under a
    comment reading "long-form only" - which excluded GUIDE, the longest
    thing this engine writes at 2500-3500 words, and included email at 120.
    Exactly backwards, for over a year, because the list and the comment were
    written at different moments and nothing compared them."""
    return str(kind or "blog").strip().lower() not in NO_RESEARCH_TYPES


def wants_linkedin(kind: str) -> bool:
    """Should this piece get a native LinkedIn post? Unknown types do.

    This was hard-coded as ('blog', 'guide') in prep, which is the SIXTH copy
    of a content-type list in this codebase and the second one to silently
    drop work: a social_carousel or a reel - the two things most obviously
    destined for LinkedIn - got no LinkedIn post at all."""
    return str(kind or "blog").strip().lower() not in NO_LINKEDIN_TYPES


def wants_image(kind: str) -> bool:
    """Should this piece get a hero image? Unknown types get one."""
    return str(kind or "blog").strip().lower() not in NO_IMAGE_TYPES


# WordPress top-level sections a piece can be routed to, by its 'kind'.
KIND_CATEGORY = {"blog": "Blog", "guide": "Guides", "service": "Services",
                 "social_carousel": "Blog", "reel": "Blog", "email": "Blog"}

# The theme's own `ao_type` taxonomy — the one the site actually FILTERS on.
# index.php lists posts where ao_type=blog and the guides listing queries
# ao_type=guide, so a post without it is published, live, and invisible on both.
# Only two terms exist in the theme (functions.php seeds 'guide' and 'blog'),
# so anything that is not a guide lands in blog rather than inventing a term.
KIND_AO_TYPE = {"guide": "guide"}
AO_TYPE_DEFAULT = "blog"


def wp_ao_type(kind: str) -> str:
    """The theme's Content Type slug for this piece: 'guide' or 'blog'."""
    return KIND_AO_TYPE.get((kind or "").strip().lower(), AO_TYPE_DEFAULT)

# On-brand image style — matched to the live site (dark navy, cyan/violet, modern).
IMAGE_STYLE = (
    "Modern minimal editorial tech illustration, 16:9 hero. Deep navy #080B14 background, "
    "cyan #2FE3D2 and violet #7C6BFF accents, subtle abstract automation motifs "
    "(connected nodes, flowing lines, a clean dashboard), premium and calm, lots of negative "
    "space, soft glow. No text, no words, no logos, no watermarks, no human faces."
)

_SEG_BY_KEY = {s["key"]: s for s in SEGMENTS}
_PIL_BY_KEY = {p["key"]: p for p in PILLARS}
SEGMENT_NAMES = [s["name"] for s in SEGMENTS]
PILLAR_NAMES = [p["name"] for p in PILLARS]


def _score(text: str, kws) -> int:
    t = (text or "").lower()
    return sum(1 for k in kws if k in t)


def classify(title: str = "", keyword: str = "", hint: str = "") -> dict:
    """Best-effort map a piece to ONE segment + ONE pillar using its title/keyword.
    Deterministic fallback so a piece is ALWAYS tagged (default: broadest pillar)."""
    text = " ".join([title or "", keyword or "", hint or ""])
    seg = max(SEGMENTS, key=lambda s: _score(text, s["kw"]))
    if _score(text, seg["kw"]) == 0:
        seg = _SEG_BY_KEY["b2b"]                 # neutral default audience
    pil = max(PILLARS, key=lambda p: _score(text, p["kw"]))
    if _score(text, pil["kw"]) == 0:
        pil = _PIL_BY_KEY["automate"]            # the site's flagship pillar
    return {"segment": seg["name"], "segment_key": seg["key"], "segment_url": seg["url"],
            "pillar": pil["name"], "pillar_key": pil["key"], "service": pil["service"],
            "pillar_wp": pil["wp"]}


def resolve(segment: str = "", pillar: str = "", title: str = "", keyword: str = "") -> dict:
    """Resolve an explicit segment/pillar (as chosen by the strategist) to the full
    taxonomy record; fall back to classify() for anything missing or unrecognised."""
    seg = next((s for s in SEGMENTS if s["name"].lower() == (segment or "").lower()
                or s["key"] == (segment or "").lower()), None)
    pil = next((p for p in PILLARS if p["name"].lower() == (pillar or "").lower()
                or p["key"] == (pillar or "").lower() or p["service"].lower() == (pillar or "").lower()), None)
    if seg and pil:
        return {"segment": seg["name"], "segment_key": seg["key"], "segment_url": seg["url"],
                "pillar": pil["name"], "pillar_key": pil["key"], "service": pil["service"],
                "pillar_wp": pil["wp"]}
    return classify(title, keyword, hint=f"{segment} {pillar}")


def wp_categories(kind: str, segment: str = "", pillar: str = "",
                  title: str = "", keyword: str = "") -> list:
    """The WordPress category NAMES this piece should post under: the section
    (Blog/Guides/Services), its service pillar, and its audience segment — so it
    lands in the right place on the site, not randomly."""
    tax = resolve(segment, pillar, title, keyword)
    cats = [KIND_CATEGORY.get((kind or "blog").lower(), "Blog"),
            tax["pillar_wp"], tax["segment"]]
    out, seen = [], set()
    for c in cats:                        # de-dupe, keep order
        if c and c not in seen:
            seen.add(c); out.append(c)
    return out


def image_prompt(title: str, ci_text: str = "") -> str:
    """On-brand hero-image generation prompt for a blog title."""
    subject = (title or "business automation").strip().rstrip(".")
    extra = ""
    if ci_text and ci_text.strip():
        extra = " Follow the brand kit's colour direction where it differs."
    return f"Editorial hero image representing: {subject}. {IMAGE_STYLE}{extra}"
