"""
content_engine_media_manifest.py
============================================================================
THE PLATFORM CAPABILITY MANIFEST. Machine-readable, authoritative for UI
capability rendering, per the omnichannel spec sections 2-4 and 14.

THE RESEARCH RULE, obeyed: every hard fact in this file is either
VERIFIED against official documentation on 2026-08-09 (source noted), or
marked "UNKNOWN - REQUIRES VERIFICATION". Nothing here is remembered from
training data and presented as current.

Verified on 2026-08-09 from official sources:
- Google Ads API current major version: v25 (breaking changes; release
  notes page current as of 2026-08). Hierarchy: customer > campaign >
  ad_group > ad. Source: developers.google.com/google-ads/api.
- Meta Marketing API current version: v25.0 (announced 2026-02-18 on the
  official developer blog). Hierarchy: ad_account > campaign > ad_set >
  ad. Source: developers.facebook.com.
- LinkedIn Marketing API: monthly YYYYMM versions via Linkedin-Version
  header, each supported a minimum of ONE YEAR then sunset; 202506 and
  202507 are already sunset. Hierarchy: ad_account > campaign_group >
  campaign > creative. Source: learn.microsoft.com/linkedin/marketing.
- TikTok Business API: v1.3, base business-api.tiktok.com/open_api/v1.3,
  OAuth2 bearer. Hierarchy: advertiser > campaign > ad_group > ad.
  Source: business-api.tiktok.com/portal.

CODED VERSION vs CURRENT VERSION is recorded per platform below, because
this codebase's sockets defaulted to versions that have since sunset, and
pretending otherwise is exactly the drift the founder's spec forbids.
============================================================================
"""

from __future__ import annotations

import copy

UNKNOWN = "UNKNOWN - REQUIRES VERIFICATION"

#: The manifest. Keys are the CANONICAL provider ids this OS already uses.
MANIFEST = {
    "google": {
        "display": "Google Ads",
        "api": {
            "current_version": "v25",
            "current_version_verified": "2026-08-09, official release notes",
            "coded_default_version": "v25",
            "version_env": "GOOGLE_ADS_API_VERSION",
            "base_url": "https://googleads.googleapis.com/{version}",
            "auth": "OAuth2 refresh token + developer token",
            "oauth_scopes": ["https://www.googleapis.com/auth/adwords"],
            "breaking_changes_note": "v25 (2026-07) is a major release "
                                     "with breaking changes; do not mix "
                                     "v21-v24 examples into v25 calls",
            "rate_limits": UNKNOWN,
            "webhooks": "none; polling only (verified: no push API for "
                        "campaign state)",
        },
        "hierarchy": ["customer", "campaign", "ad_group", "ad"],
        "hierarchy_words": {"middle": "ad group", "leaf": "ad"},
        "networks": ["search", "display", "youtube", "performance_max"],
        "youtube_note": "YouTube advertising runs THROUGH this adapter; "
                        "there is deliberately no separate YouTube API "
                        "architecture",
        "supports": {
            "campaign_creation": True, "asset_upload": True,
            "preview": UNKNOWN, "targeting": True, "pause_resume": True,
            "budget_update": True, "negative_keywords": True,
            "offline_conversions": True,
        },
        "objectives_note": "objective is expressed via campaign type + "
                           "bidding strategy, not a single enum",
        "campaign_types": ["SEARCH", "PERFORMANCE_MAX", "DISPLAY",
                           "VIDEO", "DEMAND_GEN"],
        "placements": ["Google Search", "YouTube video placement",
                       "Display network"],
        "asset_specs": {
            "rsa_headline_max_chars": 30, "rsa_description_max_chars": 90,
            "image_formats": ["PNG", "JPEG"], "video": "via YouTube",
            "aspect_ratios": UNKNOWN,
        },
        "status": "LIVE_CAPABLE",
    },
    "meta": {
        "display": "Meta Ads (Facebook + Instagram)",
        "api": {
            "current_version": "v25.0",
            "current_version_verified": "2026-08-09, official developer "
                                        "blog (announced 2026-02-18)",
            "coded_default_version": "v25.0",
            "version_env": "META_API_VERSION",
            "base_url": "https://graph.facebook.com/{version}",
            "auth": "OAuth2 long-lived token (Marketing API access)",
            "oauth_scopes": ["ads_management", "ads_read"],
            "breaking_changes_note": "Graph versions live roughly two "
                                     "years; the previously coded v21.0 "
                                     "(2024-10) is at end of life",
            "rate_limits": UNKNOWN,
            "webhooks": UNKNOWN,
        },
        "hierarchy": ["ad_account", "campaign", "ad_set", "ad"],
        "hierarchy_words": {"middle": "ad set", "leaf": "ad"},
        "networks": ["facebook", "instagram"],
        "supports": {
            "campaign_creation": UNKNOWN, "asset_upload": UNKNOWN,
            "preview": UNKNOWN, "targeting": True, "pause_resume": True,
            "budget_update": True,
        },
        "campaign_types": UNKNOWN,
        "placements": ["Facebook Feed", "Instagram Feed",
                       "Instagram Stories", "Instagram Reels"],
        "asset_specs": {
            "image_formats": ["PNG", "JPEG"],
            "video_formats": ["MP4", "MOV"],
            "aspect_ratios": ["9:16", "1:1", "4:5", "16:9"],
            "specs_detail": UNKNOWN,
        },
        "status": "READ_SOCKET_ONLY",
    },
    "linkedin": {
        "display": "LinkedIn Ads",
        "api": {
            "current_version": "YYYYMM monthly (2026-07 docs current)",
            "current_version_verified": "2026-08-09, learn.microsoft.com; "
                                        "202506 and 202507 already sunset",
            "coded_default_version": "202601",
            "version_env": "LINKEDIN_ADS_API_VERSION",
            "base_url": "https://api.linkedin.com/rest",
            "auth": "OAuth2, Linkedin-Version header REQUIRED",
            "oauth_scopes": ["r_ads", "r_ads_reporting", "rw_ads"],
            "breaking_changes_note": "each YYYYMM version sunsets after a "
                                     "minimum of one year; the previously "
                                     "coded 202409 default is past that "
                                     "window. The Creatives API replaced "
                                     "adCreativesV2.",
            "rate_limits": UNKNOWN,
            "webhooks": UNKNOWN,
        },
        "hierarchy": ["ad_account", "campaign_group", "campaign",
                      "creative"],
        "hierarchy_words": {"middle": "campaign", "leaf": "creative"},
        "hierarchy_note": "LinkedIn's leaf is a CREATIVE under a campaign "
                          "under a CAMPAIGN GROUP; it is not the same "
                          "object as a Google ad and is not renamed into "
                          "one. The canonical mapping stores campaign_group "
                          "in provider_config.",
        "networks": ["linkedin"],
        "supports": {
            "campaign_creation": UNKNOWN, "asset_upload": True,
            "preview": "documented Ad Preview API exists (2026-07 docs)",
            "targeting": True, "pause_resume": UNKNOWN,
            "budget_update": UNKNOWN,
        },
        "campaign_types": UNKNOWN,
        "placements": ["LinkedIn Feed"],
        "asset_specs": {"specs_detail": UNKNOWN},
        "utm_note": "dynamic UTM macros documented per LinkedIn docs; "
                    "macro syntax differs from other platforms",
        "status": "READ_SOCKET_ONLY",
    },
    "tiktok": {
        "display": "TikTok Ads",
        "api": {
            "current_version": "v1.3",
            "current_version_verified": "2026-08-09, "
                                        "business-api.tiktok.com portal",
            "coded_default_version": "v1.3",
            "version_env": "TIKTOK_ADS_API_VERSION",
            "base_url": "https://business-api.tiktok.com/open_api/v1.3",
            "auth": "OAuth2 access token (Access-Token header)",
            "oauth_scopes": [UNKNOWN],
            "breaking_changes_note": "",
            "rate_limits": UNKNOWN,
            "webhooks": UNKNOWN,
        },
        "hierarchy": ["advertiser", "campaign", "ad_group", "ad"],
        "hierarchy_words": {"middle": "ad group", "leaf": "ad"},
        "networks": ["tiktok"],
        "supports": {
            "campaign_creation": "documented (campaign/create in v1.3)",
            "asset_upload": UNKNOWN, "preview": UNKNOWN,
            "targeting": True, "pause_resume": UNKNOWN,
            "budget_update": UNKNOWN,
        },
        "campaign_types": UNKNOWN,
        "placements": ["TikTok Feed"],
        "asset_specs": {
            "aspect_ratios": ["9:16"], "specs_detail": UNKNOWN,
        },
        "status": "READ_SOCKET_ONLY",
    },
}


def manifest(provider=None) -> dict:
    """The manifest, or one platform's slice. Always a deep copy: the
    manifest is authoritative and nobody edits it by accident."""
    if provider is None:
        return copy.deepcopy(MANIFEST)
    p = MANIFEST.get(str(provider or "").lower())
    return copy.deepcopy(p) if p else {}


def capabilities(provider) -> dict:
    """What the spec's GET /platforms/{platform}/capabilities returns.
    The frontend renders ONLY what this says; an unknown is an unknown."""
    m = manifest(provider)
    if not m:
        return {"ok": False,
                "message": f"{provider!r} is not a platform this OS "
                           f"supports. They are: "
                           + ", ".join(sorted(MANIFEST))}
    return {"ok": True, "provider": provider, "display": m["display"],
            "hierarchy": m["hierarchy"],
            "hierarchy_words": m["hierarchy_words"],
            "placements": m.get("placements", []),
            "networks": m.get("networks", []),
            "supports": m.get("supports", {}),
            "campaign_types": m.get("campaign_types"),
            "asset_specs": m.get("asset_specs", {}),
            "api_version": m["api"]["current_version"],
            "coded_version": m["api"]["coded_default_version"],
            "status": m.get("status"),
            "unknowns": sorted(_unknowns(m))}


def _unknowns(node, path="") -> list:
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            out += _unknowns(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += _unknowns(v, f"{path}[{i}]")
    elif node == UNKNOWN:
        out.append(path)
    return out


def version_drift() -> list:
    """Where the coded default trails the verified current version. This
    is the list the founder reads before trusting a live call."""
    out = []
    for pid, m in MANIFEST.items():
        cur, coded = m["api"]["current_version"], \
            m["api"]["coded_default_version"]
        if "YYYYMM" in cur:
            out.append({"provider": pid, "coded": coded, "current": cur,
                        "drift": False,
                        "note": "monthly versioning; the coded default "
                                "must be re-verified every few months"})
        else:
            out.append({"provider": pid, "coded": coded, "current": cur,
                        "drift": coded != cur,
                        "note": m["api"].get("breaking_changes_note", "")})
    return out


def compatibility(creative, provider) -> dict:
    """The creative compatibility verdict, spec section 12:
    SUPPORTED | REQUIRES_TRANSFORMATION | UNSUPPORTED | UNKNOWN.

    Judged ONLY from what is actually known about the asset (stored
    width/height/aspect_ratio) and the platform (manifest asset_specs).
    Where either side is unknown, the verdict says UNKNOWN instead of
    waving the creative through."""
    m = manifest(provider)
    if not m:
        return {"verdict": "UNSUPPORTED",
                "why": f"{provider!r} is not a supported platform"}
    c = creative or {}
    specs = m.get("asset_specs", {})
    ratios = specs.get("aspect_ratios")
    ar = str(c.get("aspect_ratio") or "").strip()
    if not ar and c.get("width") and c.get("height"):
        ar = _ratio(c["width"], c["height"])
    if str(c.get("type") or "").upper() == "TEXT":
        return {"verdict": "SUPPORTED",
                "why": "text creative; no asset dimensions to judge"}
    if not ar:
        return {"verdict": "UNKNOWN",
                "why": "the asset's aspect ratio is not recorded, so "
                       "compatibility cannot be judged honestly. Re-upload "
                       "through the room (dimensions are probed) or set "
                       "aspect_ratio on the creative."}
    if ratios in (None, UNKNOWN):
        return {"verdict": "UNKNOWN",
                "why": f"{m['display']}'s accepted ratios are not verified "
                       f"in the manifest yet ({UNKNOWN})"}
    if ar in ratios:
        return {"verdict": "SUPPORTED",
                "why": f"{ar} is accepted by {m['display']}"}
    return {"verdict": "REQUIRES_TRANSFORMATION", "have": ar,
            "accepted": ratios,
            "why": (f"{ar} is not among {m['display']}'s accepted ratios "
                    f"({', '.join(ratios)}); a variant is needed rather "
                    f"than forcing this asset on")}


def _ratio(w, h) -> str:
    try:
        from math import gcd
        w, h = int(w), int(h)
        g = gcd(w, h) or 1
        rw, rh = w // g, h // g
        # collapse to the nearest advertising ratio when close
        for cand, val in (("9:16", 9 / 16), ("1:1", 1.0), ("4:5", 4 / 5),
                          ("16:9", 16 / 9)):
            if abs((w / h) - val) < 0.02:
                return cand
        return f"{rw}:{rh}"
    except Exception:
        return ""
