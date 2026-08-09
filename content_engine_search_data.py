# -*- coding: utf-8 -*-
"""Search OS: the data architecture, the CMS adapters and reporting.

Spec 75-78 and 85-86.

This module holds the parts of the Search OS that are NOT screens: what
an entity is, how two records are decided to be the same thing, how long
anything is kept, what each CMS can actually be asked to do, and what a
report is allowed to contain.

The rule that runs through all of it: a system that merges two records is
making a claim, and a system that changes a live site is taking an
action. Both are stated out loud here rather than happening quietly
inside a helper.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 75. THE CANONICAL MODEL
# ---------------------------------------------------------------------------
#: Every entity this OS stores, the field that identifies it, and what it
#: is. ONE list. Adding a table without adding it here is how a store
#: grows an orphan nobody retains, backs up or deletes.
ENTITIES: Tuple[Tuple[str, str, str], ...] = (
    ("page", "url_id",
     "one crawlable URL on the site we own"),
    ("keyword", "keyword_id",
     "one query string in one market, normalised"),
    ("ranking", "url_id+keyword_id+pulled_at",
     "where one page sat for one keyword at one moment"),
    ("issue", "issue_id",
     "one defect found on one page by one check"),
    ("initiative", "initiative_id",
     "one intended change, from proposed to classified"),
    ("run", "run_id",
     "one agent execution, with its budget and what it spent"),
    ("backlink", "link_id",
     "one link from one external URL to one of ours"),
    ("prompt", "prompt_id",
     "one question asked of one AI provider"),
    ("observation", "prompt_id+provider+observed_at",
     "one answer an AI provider actually gave"),
    ("fact", "fact_id",
     "one metric row from one source for one grain and date"),
    ("report", "report_id",
     "one assembled document, with the sources it drew on"),
    ("credential", "credential_ref",
     "a REFERENCE to a secret held elsewhere, never the secret"),
)

#: Spec 75. The credential rule, stated where the model is defined so it
#: cannot be missed: business tables hold a reference, never a token.
CREDENTIAL_RULE = (
    "Business tables store credential_ref, never a token, key or refresh "
    "string. A token in an ordinary table survives every backup, export "
    "and support dump that table ever appears in."
)


def entity(name: str) -> Optional[Dict[str, str]]:
    """Look one entity up. Unknown names return None, never a guess."""
    for n, key, what in ENTITIES:
        if n == name:
            return {"entity": n, "key": key, "what": what}
    return None


# ---------------------------------------------------------------------------
# 76. IDENTITY: when are two records the same thing?
# ---------------------------------------------------------------------------
#: Query parameters that carry no page content and are safe to drop. This
#: list is deliberately short and explicit. Stripping a parameter that
#: DOES change the page silently merges two different pages into one row,
#: and every metric on that row is then wrong in a way nobody can see.
TRACKING_PARAMS = ("utm_source", "utm_medium", "utm_campaign", "utm_term",
                   "utm_content", "utm_id", "gclid", "gbraid", "wbraid",
                   "fbclid", "msclkid", "mc_cid", "mc_eid", "_ga",
                   "ref", "referrer")

#: Parameters that DO change what a visitor sees, listed so the intent is
#: recorded rather than left to the absence of a rule.
CONTENT_PARAMS = ("page", "p", "q", "s", "search", "id", "product",
                  "variant", "category", "lang", "sort", "filter")

_SCHEME = re.compile(r"^(https?)://", re.I)


def normalize_url(url: Any) -> Dict[str, Any]:
    """One URL, reduced to its identity, with every change listed.

    Returns the normalised form AND what was done to get there, because
    a normaliser that works silently is impossible to argue with when
    two pages turn out to have merged.
    """
    raw = str(url or "").strip()
    if not raw:
        return {"url": None, "changed": [],
                "why": "empty input is not a URL"}
    out, changed = raw, []

    frag = out.find("#")
    if frag >= 0:
        out, _ = out[:frag], changed.append(
            "dropped the #fragment: it never reaches the server")

    m = _SCHEME.match(out)
    scheme = (m.group(1).lower() if m else None)
    if m:
        rest = out[m.end():]
    else:
        rest, scheme = out, None
        changed.append("no scheme given; treated as a path")

    if rest.lower().startswith("www."):
        pass  # host case is handled below; www is NOT stripped, see note

    slash = rest.find("/")
    host, path = (rest[:slash], rest[slash:]) if slash >= 0 else (rest, "/")
    if host != host.lower():
        changed.append("lowercased the host: hostnames are case-insensitive")
        host = host.lower()

    qs = ""
    if "?" in path:
        path, qs = path.split("?", 1)

    kept, dropped = [], []
    for part in [x for x in qs.split("&") if x]:
        key = part.split("=", 1)[0].lower()
        if key in TRACKING_PARAMS:
            dropped.append(key)
        else:
            kept.append(part)
    if dropped:
        changed.append("dropped tracking parameter(s) "
                       + ", ".join(sorted(set(dropped)))
                       + ": they do not change the page")
    kept.sort()
    if len(kept) > 1:
        changed.append("sorted the remaining parameters so the same page "
                       "written two ways gives one identity")

    if path != "/" and path.endswith("/"):
        changed.append("dropped the trailing slash")
        path = path[:-1]
    if not path:
        path = "/"

    norm = ((scheme + "://") if scheme else "") + host + path \
        + (("?" + "&".join(kept)) if kept else "")
    return {
        "url": norm, "host": host, "path": path,
        "params_kept": kept, "params_dropped": sorted(set(dropped)),
        "changed": changed,
        # The three things this function deliberately DOES NOT do.
        "not_done": [
            "http and https are kept apart. They are the same page only "
            "if a redirect says so, and that is a crawl finding, not a "
            "string rule.",
            "www and the bare host are kept apart, for the same reason.",
            "content parameters such as " + ", ".join(CONTENT_PARAMS[:4])
            + " are kept. Dropping one silently merges two different "
            "pages and every metric on the merged row is then wrong.",
        ],
    }


def url_identity(url: Any) -> Optional[str]:
    """The dedup key for a page."""
    return normalize_url(url).get("url")


def normalize_keyword(kw: Any, market: Any = None) -> Dict[str, Any]:
    """One query string, reduced to its identity.

    Market is part of the key. The same words in two countries are two
    different keywords with different volumes, different competitors and
    different intent, and merging them produces an average nobody can
    act on.
    """
    raw = str(kw or "").strip()
    if not raw:
        return {"keyword": None, "why": "empty input is not a keyword"}
    changed = []
    out = raw.lower()
    if out != raw:
        changed.append("lowercased: search is not case-sensitive")
    if "  " in out or out != out.strip():
        changed.append("collapsed whitespace")
    out = " ".join(out.split())
    mk = str(market or "").strip().lower() or None
    return {"keyword": out, "market": mk, "changed": changed,
            "key": (out + "|" + mk) if mk else out,
            "not_done": [
                "no stemming and no plural folding. 'tattoo needle' and "
                "'tattoo needles' rank differently and have different "
                "volumes; folding them invents a keyword that nobody "
                "types.",
                ("no market given, so this key is global and will "
                 "collide with the same words in another country")
                if not mk else
                "market is part of the key, because the same words in "
                "two countries are two keywords.",
            ]}


def keyword_identity(kw: Any, market: Any = None) -> Optional[str]:
    """The dedup key for a keyword."""
    return normalize_keyword(kw, market).get("key")


# ---------------------------------------------------------------------------
# 77. RETENTION
# ---------------------------------------------------------------------------
#: Days to keep, per entity, with the reason. A retention policy with no
#: reason gets raised every year and settled by whoever speaks loudest.
RETENTION: Tuple[Tuple[str, Optional[int], str], ...] = (
    ("fact", 800,
     "just over two years, so a year-on-year comparison always has a "
     "full prior year to compare against"),
    ("ranking", 800, "same reason: seasonality needs two cycles"),
    ("observation", 400,
     "AI answers change fast; a year is enough to show a trend and "
     "beyond that the providers themselves have changed"),
    ("issue", 180,
     "a defect older than six months is either fixed or is not a defect"),
    ("initiative", None,
     "kept forever. The record of what we changed and what it did is "
     "the only thing that makes the next decision better than a guess"),
    ("run", 90,
     "operational detail; the initiative keeps the outcome"),
    ("report", None,
     "kept forever. A report someone acted on must remain readable"),
    ("credential", None,
     "the reference is kept; the secret was never here to expire"),
    # These four were caught by retention_plan() itself on the day this
    # module was written: they existed in ENTITIES with no policy, which
    # is exactly the accidental growth the board flags in red. The
    # detector stays; the gap does not.
    ("page", None,
     "kept forever. A URL we have ever crawled is the spine every "
     "ranking, issue and fact hangs off; deleting one orphans all of "
     "them"),
    ("keyword", None,
     "kept forever, same reason: rankings reference it"),
    ("backlink", 800,
     "two years, matching facts, so a lost-link claim can always be "
     "checked against the pull that first saw it"),
    ("prompt", None,
     "kept forever. Observations reference it, and a prompt we stopped "
     "asking is still the question its old answers answered"),
)


def retention_plan() -> List[Dict[str, Any]]:
    """The whole policy, and any entity that has no policy at all."""
    known = dict((n, (d, why)) for n, d, why in RETENTION)
    out = []
    for name, key, what in ENTITIES:
        if name in known:
            days, why = known[name]
            out.append({"entity": name, "days": days, "why": why,
                        "state": "KEPT FOREVER" if days is None
                        else "EXPIRES"})
        else:
            out.append({"entity": name, "days": None,
                        "state": "NO POLICY",
                        "why": ("nothing decides when this is deleted, "
                                "so it grows forever by accident rather "
                                "than on purpose")})
    return out


# ---------------------------------------------------------------------------
# 78. CMS ADAPTERS
# ---------------------------------------------------------------------------
#: What each CMS can actually be asked to do. A capability absent from
#: this table is UNSUPPORTED and says so; it never silently no-ops, which
#: is the failure that makes an operator think a fix landed.
CMS: Dict[str, Dict[str, Any]] = {
    "wordpress": {
        "label": "WordPress",
        "auth": "application password or REST token, held by reference",
        "can": ("read_post", "update_title", "update_meta_description",
                "update_body", "update_slug", "create_redirect",
                "update_schema", "upload_media", "create_post"),
        "cannot": ("edit_robots_txt", "edit_server_headers"),
        "notes": ("robots.txt and headers are served by the host, not "
                  "the CMS, so this adapter cannot touch them and does "
                  "not pretend to."),
    },
    "webflow": {
        "label": "Webflow",
        "auth": "site API token, held by reference",
        "can": ("read_post", "update_title", "update_meta_description",
                "update_body", "update_slug", "publish_site"),
        "cannot": ("create_redirect", "update_schema", "edit_robots_txt"),
        "notes": ("redirects and custom schema live in site settings, "
                  "which the CMS API does not expose; those come back "
                  "as work orders for a human."),
    },
    "shopify": {
        "label": "Shopify",
        "auth": "admin API access token, held by reference",
        "can": ("read_post", "update_title", "update_meta_description",
                "update_body", "create_redirect", "update_schema"),
        "cannot": ("update_slug", "edit_robots_txt"),
        "notes": ("changing a product handle breaks its URL and every "
                  "link to it, so this adapter refuses rather than "
                  "offering it as a one-click fix."),
    },
    "manual": {
        "label": "No CMS connected",
        "auth": "none",
        "can": (),
        "cannot": ("everything",),
        "notes": ("every change becomes a work order with the exact "
                  "before and after, for a person to apply. This is a "
                  "supported mode, not a broken one."),
    },
}


class UnsupportedCapability(Exception):
    """Raised when a CMS is asked for something it cannot do."""


def cms_capability(platform: Any, capability: Any) -> Dict[str, Any]:
    """Can this CMS do this? Unknown platform is not a silent no."""
    p = str(platform or "").lower()
    spec = CMS.get(p)
    if spec is None:
        return {"supported": False, "state": "UNKNOWN PLATFORM",
                "why": ("'" + str(platform) + "' is not an adapter this "
                        "OS has. It is not assumed to be incapable; it "
                        "is unknown, which is a different problem.")}
    c = str(capability or "")
    if c in spec["can"]:
        return {"supported": True, "state": "SUPPORTED",
                "why": spec["label"] + " exposes this through its API"}
    return {"supported": False, "state": "UNSUPPORTED",
            "why": (spec["label"] + " cannot do this: " + spec["notes"])}


def apply_change(platform: Any, capability: Any, target: Any,
                 before: Any = None, after: Any = None,
                 approved_by: Any = None, dry_run: bool = True
                 ) -> Dict[str, Any]:
    """Change one thing on a live site, or explain why it did not.

    THREE GATES, in this order, and none of them can be skipped:
      1. the CMS must be able to do it
      2. the change must actually change something
      3. a named person must have approved it

    dry_run defaults to True. A function that writes to a live website
    by default is one typo away from a bad afternoon.
    """
    cap = cms_capability(platform, capability)
    if not cap["supported"]:
        return {"state": cap["state"], "applied": False,
                "why": cap["why"]}
    if before is not None and before == after:
        return {"state": "NO CHANGE", "applied": False,
                "why": ("before and after are identical. Writing this "
                        "would produce a revision, a cache purge and a "
                        "log entry for nothing.")}
    if after in (None, ""):
        return {"state": "REFUSED", "applied": False,
                "why": ("the new value is empty. Clearing a title or a "
                        "description is a change a human asks for "
                        "explicitly, never one a fix engine makes.")}
    if dry_run:
        return {"state": "DRY RUN", "applied": False,
                "diff": {"before": before, "after": after},
                "why": ("this is what would be written. Nothing was "
                        "sent; pass dry_run=False with an approval to "
                        "apply it.")}
    if not approved_by:
        return {"state": "NEEDS APPROVAL", "applied": False,
                "diff": {"before": before, "after": after},
                "why": ("a live change needs a named approver. 'The "
                        "agent decided' is not a name.")}
    return {"state": "APPLIED", "applied": True,
            "target": target, "capability": capability,
            "approved_by": str(approved_by),
            "diff": {"before": before, "after": after},
            "why": ("written to " + CMS[str(platform).lower()]["label"]
                    + ", approved by " + str(approved_by))}


# ---------------------------------------------------------------------------
# 85-86. REPORTING
# ---------------------------------------------------------------------------
#: What a report may contain. Anything outside this list is not a
#: section, it is someone pasting a screenshot into a document.
REPORT_SECTIONS = ("summary", "search_performance", "rankings",
                   "technical_health", "content", "backlinks",
                   "ai_visibility", "initiatives", "next_actions")

#: Spec 86. Cadences. There is no "real time" report: a report is a
#: statement about a period, and a period that has not ended cannot be
#: reported on without a caveat that swallows the report.
CADENCE = ("weekly", "monthly", "quarterly", "on_request")


def build_report(sections: Iterable[Any] = (), window: Any = None,
                 sources: Iterable[Any] = ()) -> Dict[str, Any]:
    """Assemble a report, refusing anything it cannot stand behind.

    Two refusals matter here. A figure with no named source is dropped,
    not printed, because a report is the artefact that outlives the
    dashboard and gets forwarded to people who cannot check it. And a
    stale source is stamped on the report rather than quietly used.
    """
    src = {str((s or {}).get("name")): (s or {}) for s in (sources or ())}
    kept, dropped, unsourced = [], [], []
    for s in (sections or ()):
        d = s if isinstance(s, dict) else {"section": s}
        name = str(d.get("section") or "")
        if name not in REPORT_SECTIONS:
            dropped.append({"section": name,
                            "why": ("not a report section. The list is "
                                    "closed so a report cannot grow a "
                                    "panel nobody defined.")})
            continue
        figures = list(d.get("figures") or ())
        good = [f for f in figures if (f or {}).get("source")]
        bad = [f for f in figures if not (f or {}).get("source")]
        if bad:
            unsourced.extend(
                {"section": name, "figure": (f or {}).get("label"),
                 "why": ("dropped: a report is forwarded to people who "
                         "cannot check it, so an unsourced number in "
                         "one is worse than a missing number.")}
                for f in bad)
        if not good:
            dropped.append({"section": name,
                            "why": ("every figure in it was unsourced, "
                                    "so the section would have been an "
                                    "empty heading.")})
            continue
        kept.append({"section": name, "figures": good})
    stale = [n for n, s in src.items()
             if str(s.get("state") or "").upper() in ("STALE", "ERROR")]
    return {
        "window": window,
        "sections": kept,
        "dropped": dropped,
        "unsourced": unsourced,
        "sources": sorted(src),
        "caveat": (None if not stale else
                   ("Built while " + ", ".join(sorted(stale))
                    + " was not current. Figures drawn from it describe "
                    "the last pull, not the window on this report.")),
        "state": ("EMPTY" if not kept else
                  "QUALIFIED" if stale else "CLEAN"),
    }


def schedule_report(cadence: Any, recipients: Iterable[Any] = (),
                    approved_by: Any = None) -> Dict[str, Any]:
    """A recurring report is a recurring outbound send, so it is gated."""
    c = str(cadence or "").lower()
    if c not in CADENCE:
        return {"state": "REFUSED",
                "why": ("'" + str(cadence) + "' is not a cadence. "
                        + "Choices are " + ", ".join(CADENCE) + ".")}
    rec = [str(x) for x in (recipients or ()) if str(x or "").strip()]
    if not rec:
        return {"state": "REFUSED",
                "why": "a schedule with no recipient sends into nothing"}
    if not approved_by:
        return {"state": "NEEDS APPROVAL", "cadence": c,
                "recipients": rec,
                "why": ("this would email " + str(len(rec)) + " "
                        "recipient(s) on a repeating basis without "
                        "anyone reading it first. A standing rule that "
                        "sends outbound mail needs a named owner.")}
    return {"state": "SCHEDULED", "cadence": c, "recipients": rec,
            "approved_by": str(approved_by),
            "why": ("approved by " + str(approved_by) + "; every send "
                    "is still logged and can be stopped.")}
