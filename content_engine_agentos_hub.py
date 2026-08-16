# -*- coding: utf-8 -*-
"""THE FIVE SCREENS HIS FINAL REVISION ADDED.

The revised wireframe grew from 51 screens to 56. Nothing was removed;
five were added, and they belong to three different modules:

    15a  Community Chat Desk        -> 5 Leads & Outreach
    15b  Supply Chain               -> 4 Commerce
    15c  Market Intelligence        -> 4 Commerce
    16a  ERP & Universal Data Hub   -> 6 Web & Data Core
    16b  Data Mutation Ledger       -> 6 Web & Data Core

They live in one module rather than being spliced into three large ones,
because splicing into a return expression is how this project has broken
five files at once before.

WHAT THESE SCREENS SAY, AND WHY THEY DO NOT PRETEND

Every one of them describes a capability the engine does not have yet: no
ERP hub exists, no supply-chain wire is connected, no mutation ledger is
being written. The wireframe is a specification, not a report of running
software, and rendering it as though the work were done would put five
more false greens on his dashboard.

So each screen states three things and nothing else: what it is FOR (his
words), what it would need to become real, and what it can honestly show
today. The staffrail, chart cards and tab strips his file draws on these
screens attach automatically through the kit, so the STRUCTURE is his
even while the numbers are absent.
"""
from __future__ import annotations

from typing import Any, Dict, List

import content_engine_os_kit as K

#: his ids, in his order, per module
SCREENS_15_LEADS = ("15a",)
SCREENS_15_COMMERCE = ("15b", "15c")
SCREENS_16 = ("16a", "16b")
ALL_NEW = SCREENS_15_LEADS + SCREENS_15_COMMERCE + SCREENS_16

#: title and subtitle, from the crumbs of his CORRECTED file. He renamed
#: three of these in the revision (Community Chat Desk became Community
#: Manager, Supply Chain's crumb reads Inventory Controller, ERP and
#: Universal Data Hub became Data Hub), so the crumbs are copied, not
#: remembered. The subnav labels stay his too, and they differ from the
#: crumbs on 15b by his own hand: the subnav says Supply Chain, the
#: screen says Inventory Controller.
TITLES = {
    "15a": ("Community Manager",
            "One chat bot, five channels, wired only to surfaces each "
            "platform really offers."),
    "15b": ("Inventory Controller",
            "Where the units physically are, right now."),
    "15c": ("Market Intelligence",
            "What competitors charge, and what to sell next, per channel."),
    "16a": ("Data Hub",
            "One intake for every system, ERP, web, social, marketplaces, "
            "custom."),
    "16b": ("Mutation Ledger",
            "Who changed what, where, and with whose approval."),
}

#: what each screen needs before it can carry a number. Named, because
#: "no data" is useless and "this key, from this place" is a next step.
NEEDS = {
    "15a": ("a Meta page token with pages_messaging, an Instagram business "
            "account, and a verified WhatsApp Business number"),
    "15b": ("Amazon SP-API credentials for Send-to-Amazon, a TikTok Shop "
            "fulfilment token, and the shop keys the orders collector "
            "already reads"),
    "15c": ("read access to each platform's own reporting API: Amazon "
            "Opportunity Explorer, TikTok Seller Center, Meta Commerce"),
    "16a": ("nothing new: the hub is the place where the keys for every "
            "other system are entered, and the Tool Hub on 13i already "
            "accepts them"),
    "16b": ("nothing new: the ledger records what the engine already does, "
            "so it needs a writer on the mutation paths rather than a key"),
}


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _e(v) -> str:
    return K._e(v)


def _state(sid: str, ctx: Dict[str, Any]) -> str:
    """What this screen can honestly show right now.

    Each branch reads something the engine really has. Where it has
    nothing, it says so in the same words the rest of the OS uses, so a
    reader never has to wonder whether an empty screen is broken."""
    ctx = _d(ctx)
    if sid == "15a":
        # The social wires exist; conversation surfaces do not.
        try:
            import content_engine_social_desk as SD
            st = SD.channel_state(None) or {}
            ready = [c for c, v in st.items() if _d(v).get("verified")]
        except Exception:                                 # noqa: BLE001
            ready = []
        return ("<p class='ox-sub'>The Distributor can POST to %d verified "
                "channel(s). Reading conversations is a different permission "
                "on the same platforms, and this engine holds none of it "
                "yet, so no comment or DM has ever been read.</p>"
                % len(ready))
    if sid == "15b":
        try:
            import content_engine_orders as OR
            c = OR.context(None)
            n = len(_l(c.get("orders")))
        except Exception:                                 # noqa: BLE001
            n = 0
        return ("<p class='ox-sub'>%d order(s) are stored. Supply chain is "
                "the other half of that number: where the stock came from "
                "and when it lands. No fulfilment wire is connected, so "
                "inbound is NOT MEASURED rather than zero.</p>" % n)
    if sid == "15c":
        return ("<p class='ox-sub'>Nothing is pulled yet. This screen reads "
                "each platform's own reports rather than re-deriving them, "
                "which is the honest way to show a marketplace number: the "
                "seller console is the source of truth and this would quote "
                "it, not compete with it.</p>")
    if sid == "16a":
        # The registry is real, so this can count something true.
        try:
            import content_engine_connectors as C
            st = _d(C.status())
            live = sum(1 for v in st.values() if _d(v).get("ok"))
            tot = len(st)
        except Exception:                                 # noqa: BLE001
            live, tot = 0, 0
        return ("<p class='ox-sub'>%d of %d wire(s) are live on this box. "
                "The hub is the one intake for the rest: one form, one "
                "normaliser, one distribution to every agent, instead of a "
                "new connector written per system.</p>" % (live, tot))
    # 16b
    return ("<p class='ox-sub'>No mutation has been recorded, because "
            "nothing writes this ledger yet. Every gated write in the engine "
            "already knows its own approver and reason (a price change, a "
            "post, a publish), so the ledger needs a writer on those paths, "
            "not a new source of truth.</p>")


def _screen(sid: str, ctx: Dict[str, Any]) -> str:
    title, sub = TITLES[sid]
    # NO EMPLOYEE, SO NO staffed_by. His rule: a desk with no employee
    # shows no numbers, and a badge next to a name nobody holds would be
    # the first number it invented. The badge states the state instead.
    body = (K.bp("<div class='ox-sh'>" + K.badge("architected",
                 "the wireframe draws this screen; no lane owns it yet")
                 + "</div>"
                 + "<h4>What this desk is for</h4>"
                 + _state(sid, ctx)
                 + "<h4>What it needs before it carries a number</h4>"
                   "<p class='ox-sub'>" + _e(NEEDS[sid]) + "</p>"
                 + K.planned(title, NEEDS[sid]))
            )
    # staffrail, chart cards and tab strips attach by id inside screen()
    return K.screen(sid, title, sub, body)


def screens(ctx: Dict[str, Any], which) -> str:
    """Render a set of the new screens, in his order."""
    return "".join(_screen(s, ctx) for s in which)


def leads_extra(ctx) -> str:
    return screens(ctx, SCREENS_15_LEADS)


def commerce_extra(ctx) -> str:
    return screens(ctx, SCREENS_15_COMMERCE)


def core_extra(ctx) -> str:
    return screens(ctx, SCREENS_16)


def check(ctx=None) -> Dict[str, Any]:
    """Refuse to ship a screen that claims work nobody did."""
    problems: List[str] = []
    ctx = _d(ctx)
    html = screens(ctx, ALL_NEW)

    for s in ALL_NEW:
        if ("id='os-%s'" % s) not in html:
            problems.append("%s does not render" % s)
        if s not in TITLES or s not in NEEDS:
            problems.append("%s has no title or no stated need" % s)

    # EVERY ONE OF THESE IS ARCHITECTED. Saying otherwise would put five
    # new false greens on his dashboard, which is the whole failure class
    # this OS exists to refuse.
    if html.count("ox-b-architected") != len(ALL_NEW):
        problems.append("a new screen claims a badge it has not earned")
    if "PLANNED" not in html.upper():
        problems.append("a planned screen does not say it is planned")

    # His rule, checked here too because these strings are new.
    if "—" in html:
        problems.append("an em-dash reached the new screens")

    return {"ok": not problems, "problems": problems,
            "screens": len(ALL_NEW), "chars": len(html)}


if __name__ == "__main__":
    r = check()
    print("new screens:", r["screens"], "| chars:", r["chars"])
    for p in r["problems"]:
        print("  FAIL", p)
    print("hub self-check:", "OK" if r["ok"] else "FAILED")
    raise SystemExit(0 if r["ok"] else 1)
