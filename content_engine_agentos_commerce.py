# -*- coding: utf-8 -*-
"""AGENT OS: turn 11 (Commerce) and turn 10 (Product Publisher).

  11a Manager's Command Center      11f Lifecycle Analyst's desk
  11b Inventory Controller's desk   11g Hand-off to Marketing
  11c Pricing Analyst's desk        11h Data/Tools + Control Room
  11d Merchandiser's desk           11i Sales Channels
  11e Promotions Manager's desk
  10a Product description editor + per-platform launch

TURN 10 HAS ONE SCREEN, NOT FOUR
  Counted from the handoff file: the t10 block contains exactly one
  screen id. Earlier sessions said the OS was 54 screens on the
  assumption that t10 ran 10a to 10d. The real total is 51.

FIVE DESKS, ONE EMPLOYEE
  11b, 11c, 11d, 11e and 11f are all commerce.analyst. This is the
  clearest case of the whole build: the wireframe draws an Inventory
  Controller, a Pricing Analyst, a Merchandiser, a Promotions Manager and
  a Lifecycle Analyst, and splitting one lane across five workers would
  mean nobody owns commerce and five playbooks each learn a fifth of the
  truth. Every one of the five screens says whose desk it is.

STAGE 1, AND THE SCREENS SAY SO
  The Commerce Analyst is an inspector (4.3 stage 1). It reads the
  catalogue and reports. It does not set a price, and the desks that
  would do that (11c, 11e) say what stage 2 will add rather than showing
  a control that does nothing.
"""
from __future__ import annotations

from typing import Any, Dict, List

import content_engine_os_kit as K

_e, _l, _d = K._e, K._l, K._d

#: his subnav for this module: the label, and the screen
#: it opens. Anchors, exactly as his own markup uses.
SUBNAV_COMMERCE = [('Command Center', '11a'), ('Inventory', '11b'), ('Pricing', '11c'), ('Merchandiser', '11d'), ('Promotions', '11e'), ('Lifecycle', '11f'), ('Hand-off', '11g'), ('Data & Control', '11h'), ('Sales Channels', '11i'), ('Product Publisher', '10a')]

AGENT = "commerce.analyst"

try:
    from content_engine_pricing import MAX_MOVE_PCT as _MAX_MOVE
except Exception:                                         # noqa: BLE001
    _MAX_MOVE = 25.0

#: every commerce desk is worked by the same employee
SHARED_DESKS = ("11b", "11c", "11d", "11e", "11f")

#: Stage 2 is BUILT. These screens used to explain a control that did not
#: exist yet. Describing a shipped lane as future work is the same drift
#: as describing a missing one as present, so the text moves with the code.
STAGE_2 = {}


def _price_table(ctx) -> str:
    """Open price proposals, each with the numbers it was computed from
    and its own approve control. PINK: one at a time, never a batch."""
    # THE PINK RULE IS STANDING, not conditional on there being rows.
    # It first lived only in the populated branch, so an empty queue
    # silently stopped saying how these are approved. A rule stated only
    # when it happens to apply is a rule the reader never learns.
    pink_rule = ("<p class='ox-sub'><span class='ox-pink'>pink</span> Every "
                 "one of these changes what a customer pays. They are "
                 "approved one at a time, never in a batch, and the name of "
                 "whoever approves is recorded against the change.</p>")
    props = _l(_d(ctx).get("price_proposals"))
    if not props:
        return ("<p class='ox-nodata'>no price proposals: either the "
                "catalogue could not be read, or nothing is priced under "
                "target</p>" + pink_rule)
    rows = []
    for p in props:
        pd = _d(p)
        pv = _d(pd.get("preview"))
        if pv.get("margin_known"):
            margin = ("%s%% to %s%% (%+g pts)"
                      % (pv.get("margin_before_pct"),
                         pv.get("margin_after_pct"),
                         pv.get("margin_delta_pct") or 0))
        else:
            margin = ("<span class='ox-nodata'>%s</span>"
                      % _e(pv.get("margin_note")))
        rows.append(
            "<tr id='ospx-" + _e(pd.get("id")) + "'>"
            "<td class='ox-wire'>" + _e(pd.get("sku") or pd.get("product_id"))
            + "</td><td>" + _e(pd.get("title"))[:40]
            + "</td><td>" + _e(pd.get("why"))
            + "</td><td>" + "%s to %s" % (pd.get("price"), pd.get("new_price"))
            + "</td><td>" + margin
            + "</td><td>"
            "<button type='button' class='ox-btn ox-btn-p' "
            'onclick="osPriceApprove(&#39;' + _e(pd.get("id")) + '&#39;)">'
            "Approve</button>"
            "<button type='button' class='ox-btn' "
            'onclick="osPriceDecline(&#39;' + _e(pd.get("id")) + '&#39;)">'
            "Decline</button></td></tr>")
    return ("<div class='ox-tw'><table class='ox-t'><thead><tr><th>SKU</th>"
            "<th>Product</th><th>Why</th><th>Price</th><th>Margin</th>"
            "<th>Decision</th></tr></thead><tbody>" + "".join(rows)
            + "</tbody></table></div>"
            "<p class='ox-sub'><span class='ox-pink'>pink</span> Every one "
            "of these changes what a customer pays. They are approved one "
            "at a time, never in a batch, and the name of whoever approves "
            "is recorded against the change.</p>"
            + K.source_chip("/commerce/prices"))

#: channels the wireframe draws that have no wire in this engine
PLANNED_CHANNELS = [
    ("Amazon FBA and FBM", "Amazon SP-API credentials"),
    ("Shopware 6", "a Shopware 6 API key; still [PLANNED] in the design"),
    ("TikTok Shop", "TikTok Shop credentials"),
    ("Facebook and Instagram Shop", "a Meta commerce credential"),
]


def _card(ctx) -> Dict[str, Any]:
    for c in _l(_d(ctx).get("cards")):
        if _d(c).get("id") == AGENT:
            return _d(c)
    return {}


def _commerce(ctx) -> Dict[str, Any]:
    return _d(_d(ctx).get("commerce"))


def _findings(ctx, kind: str = "") -> List[dict]:
    fs = [_d(f) for f in _l(_commerce(ctx).get("findings"))]
    return [f for f in fs if not kind or f.get("kind") == kind]


def _no_read(ctx) -> str:
    """One honest panel for every desk when the catalogue could not be
    read. It names the cause instead of drawing an empty grid that looks
    like a shop with no products."""
    c = _commerce(ctx)
    if c.get("ok"):
        return ""
    return K.bp("<span class='ox-lbl'>No catalogue</span>"
                "<p class='ox-sub'>%s</p>"
                "<p class='ox-need'>Until a shop is connected this desk has "
                "nothing to read. It shows no numbers rather than zeros, "
                "because an empty shop and an unread shop are different "
                "facts.</p>"
                % _e(c.get("why") or "the catalogue could not be read"),
                cls="ox-plan")


def _shared(sid: str) -> str:
    if sid not in SHARED_DESKS:
        return ""
    others = ", ".join(s for s in SHARED_DESKS if s != sid)
    extra = ""
    if sid in STAGE_2:
        extra = ("<p class='ox-sub'>Stage 2 adds %s. It is not here yet, so "
                 "there is no control on this screen that pretends to do "
                 "it.</p>" % _e(STAGE_2[sid]))
    return K.bp("<span class='ox-lbl'>One worker, five desks</span>"
                "<p class='ox-sub'>This desk and %s are all worked by "
                "<b>commerce.analyst</b>. Five boards, one lane owner, one "
                "playbook. Splitting them would mean nobody owns "
                "commerce.</p>%s" % (_e(others), extra))


def _desk(ctx, sid, title, sub, *, extra: str = "", quick=None,
          note: str = "") -> str:
    card = _card(ctx)
    if not card:
        return K.screen(sid, title, sub,
                        "<p class='ox-nodata'>commerce.analyst is not on the "
                        "roster</p>", staffed_by="nobody",
                        badge_kind="notstaffed")
    blocks = [K.agent_card(card), _shared(sid)]
    nr = _no_read(ctx)
    if nr:
        blocks.append(nr)
    if extra:
        blocks.append(extra)
    return K.screen(
        sid, title, sub, K.grid(*[b for b in blocks if b], cols="two")
        + K.cmdchat(AGENT, _e(card.get("name")), quick=quick or [],
                    context_note=note),
        staffed_by=_e(card.get("name")), badge_kind=_e(card.get("badge")))


def _finding_table(ctx, kind: str, empty: str) -> str:
    fs = _findings(ctx, kind)
    if not fs:
        return "<p class='ox-nodata'>%s</p>" % _e(empty)
    return ("<div class='ox-tw'><table class='ox-t'><thead><tr><th>SKU</th>"
            "<th>What</th><th>Read from</th><th>Fix</th></tr></thead><tbody>"
            + "".join("<tr><td class='ox-wire'>%s</td><td>%s</td>"
                      "<td class='ox-wire'>%s</td><td>%s</td></tr>"
                      % (_e(f.get("sku") or "n/a"), _e(f.get("what")),
                         _e(f.get("field")), _e(f.get("fix"))) for f in fs)
            + "</tbody></table></div>")


# ==========================================================================
def _s11a(ctx) -> str:
    c = _commerce(ctx)
    return K.screen(
        "11a", "Manager's Command Center",
        "Catalogue health, the five desks, and what is waiting on you.",
        K.grid(K.bp(K.stat(c.get("counted"), "products read", "/commerce")),
               K.bp(K.stat(c.get("priced"), "with a price", "/commerce")),
               K.bp(K.stat(c.get("tracked_stock"), "tracking stock",
                           "/commerce")),
               K.bp(K.stat(len(_l(c.get("findings"))) if c.get("ok") else None,
                           "issues found", "/commerce")))
        + (_no_read(ctx) or _finding_table(
            ctx, "", "the catalogue read cleanly, with nothing to flag"))
        + K.grid(K.agent_card(_card(ctx))),
        staffed_by="📦 Commerce Analyst",
        badge_kind=_e(_card(ctx).get("badge") or "notstaffed"))


def _s11b(ctx) -> str:
    return _desk(
        ctx, "11b", "Inventory Controller's desk",
        "Inbound, stock levels, SKU integrity and reorder.",
        extra=K.bp("<span class='ox-lbl'>Low stock</span>"
                   + _finding_table(ctx, "low_stock",
                                    "nothing tracked is running low")
                   + "<p class='ox-sub'>A product whose platform returns no "
                     "stock number is NOT counted as zero. Not tracked and "
                     "none left are different facts.</p>"),
        quick=["What is running out?", "Which SKUs are untracked?"],
        note="This desk reads. It does not change stock levels in the shop.")


def _s11c(ctx) -> str:
    return _desk(
        ctx, "11c", "Pricing Analyst's desk",
        "Margins, competitor prices, and price proposals.",
        extra=K.bp("<span class='ox-lbl'>Price proposals waiting on you</span>"
                   + _price_table(ctx))
        + K.bp("<span class='ox-lbl'>Products with no price</span>"
               + _finding_table(ctx, "no_price",
                                "every product carries a price")
               + "<p class='ox-sub'>Cost price comes from Shopify's "
                 "inventory item. WooCommerce has no native cost field, so "
                 "against Woo a proposal shows revenue impact only and says "
                 "margin is unknown, rather than computing one from a cost "
                 "of zero. Competitor prices need a source this engine does "
                 "not have.</p>"),
        quick=["Which products are under target margin?",
               "What would a 10% rise do to margin?"],
        note="A price touches money, so a change arrives as a gated proposal "
             "with its margin preview and is written only after you approve "
             "it by name. Nothing here edits a price directly.")


def _s11d(ctx) -> str:
    return _desk(
        ctx, "11d", "Merchandiser's desk",
        "Top sellers, slow movers, bundles and product research.",
        extra=K.bp("<span class='ox-lbl'>Duplicate titles</span>"
                   + _finding_table(ctx, "duplicate",
                                    "no two products share a title")
                   + "<p class='ox-sub'>Top sellers and slow movers need "
                     "order data. No connected platform is returning orders "
                     "to this engine, so that ranking is absent rather than "
                     "guessed from catalogue position.</p>"),
        quick=["Which products compete with each other?"],
        note="Merchandising changes are content changes, so they go through "
             "the content pipeline and its approval room.")


def _s11e(ctx) -> str:
    return _desk(
        ctx, "11e", "Promotions Manager's desk",
        "Discounts, coupons and flash sales, with a margin preview before "
        "anything runs.",
        extra=K.bp("<span class='ox-lbl'>How a discount happens here</span>"
                   "<p class='ox-sub'>There is still no button that simply "
                   "applies a discount, and there never will be. A price move "
                   "arrives as a proposal carrying its margin impact, you "
                   "approve it by name, and only then is it written to the "
                   "shop. That is the SPEND gate, and no autonomy setting "
                   "opens it.</p>"
                   "<p class='ox-sub'>A single step may not move a price by "
                   "more than %g%%. That is not a budget: it is a guard "
                   "against a decimal point reaching a live shop.</p>"
                   % _MAX_MOVE)
        + K.bp("<span class='ox-lbl'>Open proposals</span>"
               + _price_table(ctx)),
        quick=["Propose a promotion on slow movers"],
        note="Approving here records your name against the change.")


def _s11f(ctx) -> str:
    return _desk(
        ctx, "11f", "Lifecycle Analyst's desk",
        "Monitor the stage a product is in and route the right call.",
        extra=K.bp("<span class='ox-lbl'>Products nobody can buy</span>"
                   + _finding_table(ctx, "dead_sku",
                                    "every product is published")
                   + "<p class='ox-sub'>This is the one lifecycle signal the "
                     "catalogue actually carries: status. Launch, growth and "
                     "decline stages need order history, which no connected "
                     "platform sends here.</p>"),
        quick=["What is unpublished but still listed?"],
        note="Publishing state is a shop setting. This desk reports it and "
             "does not change it.")


def _s11g(ctx) -> str:
    return K.screen(
        "11g", "Hand-off to Marketing",
        "The bridge from Commerce to the content pipeline.",
        K.grid(
            K.bp("<span class='ox-lbl'>How the hand-off already works</span>"
                 "<p class='ox-sub'>The CMS layer decides whether this "
                 "business is a shop or a service, and the planner reads "
                 "that verdict to choose what gets written. A shop gets "
                 "product and category pages; a service gets guides and "
                 "case studies. That bridge is live and is why the writer "
                 "stopped producing blog posts for a catalogue.</p>"
                 + K.source_chip("/commerce/business-type")),
            K.bp("<span class='ox-lbl'>What it does not do yet</span>"
                 "<p class='ox-sub'>A specific SKU cannot yet be pushed to "
                 "Marketing as a named brief. That is stage 2 work, and it "
                 "needs order data to know which product is worth the "
                 "effort.</p>"),
            cols="two"),
        staffed_by="📦 Commerce Analyst and 🧭 Content Strategist",
        badge_kind="inspector")


def _s11h(ctx) -> str:
    card = _card(ctx)
    slots = "".join(
        "<span class='ox-slot ox-s-%s'><b>%s</b>%s</span>"
        % (_e(_d(s).get("status")),
           K.STATUS_LABEL.get(str(_d(s).get("status")),
                              K.STATUS_LABEL["empty"])[0], _e(_d(s).get("tool")))
        for s in _l(card.get("slots"))) or "<span class='ox-nodata'>none</span>"
    return K.screen(
        "11h", "Data, Tools and Control Room",
        "Sources, staffing, and the rule that money moves only by proposal.",
        K.grid(
            K.bp("<span class='ox-lbl'>Its tools</span>"
                 "<div class='ox-slots'>%s</div>"
                 "<p class='ox-sub'>Read scope only. The desk holds no "
                 "credential that can write to a shop.</p>" % slots),
            K.bp("<span class='ox-lbl'>Money moves by proposal, always</span>"
                 "<p class='ox-sub'>Price and promotion changes are behind "
                 "the SPEND gate at every autonomy setting, including the "
                 "highest. Autonomy can widen what runs automatically inside "
                 "the low-stakes band and can never open a gate.</p>"),
            cols="two")
        + K.bp("<span class='ox-lbl'>Stage 1 of 2</span>"
               "<p class='ox-sub'>%s</p>" % _e(card.get("why"))),
        staffed_by="you", badge_kind="")


def _s11i(ctx) -> str:
    c = _commerce(ctx)
    connected = K.bp(
        "<span class='ox-lbl'>Connected now</span>"
        + ("<p class='ox-sub'>Reading from <b>%s</b>, %s products.</p>"
           % (_e(c.get("platform")), _e(c.get("counted")))
           if c.get("ok") else
           "<p class='ox-nodata'>%s</p>" % _e(c.get("why") or "no shop")))
    return K.screen(
        "11i", "Sales Channels",
        "Every pipeline visible at once, so the right product goes to the "
        "right place.",
        connected + K.grid(*[K.planned(w, n) for w, n in PLANNED_CHANNELS])
        + K.bp("<span class='ox-lbl'>Why these are empty</span>"
               "<p class='ox-sub'>Each of these channels is drawn in the "
               "design and has no credential in this engine. They are laid "
               "out with the credential that would fill them, and show no "
               "numbers at all. Shopware 6 is marked [PLANNED] in your own "
               "wireframe.</p>"),
        staffed_by="📦 Commerce Analyst",
        badge_kind=_e(_card(ctx).get("badge") or "notstaffed"))


def _s10a(ctx) -> str:
    c = _commerce(ctx)
    rows = "".join(
        "<tr><td class='ox-wire'>%s</td><td>%s</td><td>%s</td></tr>"
        % (_e(_d(p).get("sku") or _d(p).get("id")), _e(_d(p).get("title")),
           _e(_d(p).get("status")))
        for p in _l(c.get("products"))[:20])
    editor = K.bp(
        "<span class='ox-lbl'>Write once, push per platform</span>"
        "<p class='ox-sub'>A product description is content, so it is "
        "written by the Content Producer, checked by QA, and published by "
        "the Publisher. It uses the same pipeline and the same approval "
        "room as every other piece: a second publishing path would be a "
        "second thing to keep in agreement.</p>"
        + K.source_chip("/jobs"))
    return K.screen(
        "10a", "Product Publisher",
        "Write the product description once, and push it with proper native "
        "formatting per platform.",
        K.grid(editor,
               K.bp("<span class='ox-lbl'>Catalogue</span>"
                    + (("<div class='ox-tw'><table class='ox-t'><thead><tr>"
                        "<th>SKU</th><th>Title</th><th>Status</th></tr>"
                        "</thead><tbody>%s</tbody></table></div>" % rows)
                       if rows else
                       "<p class='ox-nodata'>%s</p>"
                       % _e(c.get("why") or "nothing to list"))),
               cols="two")
        + K.grid(*[K.planned(w, n) for w, n in PLANNED_CHANNELS[:2]]),
        staffed_by="✍ Content Producer and 📤 Publisher", badge_kind="live")


# ==========================================================================
SCREENS_11 = ("11a", "11b", "11c", "11d", "11e", "11f", "11g", "11h", "11i")
SCREENS_10 = ("10a",)


def commerce_section(ctx: Dict[str, Any]) -> str:
    """4 · Commerce, in the shell his wireframe uses.

    Sidebar of modules, this module's screens as a subnav
    nested under it, and the screens stacked in main. His own
    subnav links are anchors, so stacking is how his prototype
    navigates rather than a shortcut.
    """
    ctx = _d(ctx)
    body = (_s11a(ctx) + _s11b(ctx) + _s11c(ctx)
            + _s11d(ctx) + _s11e(ctx) + _s11f(ctx) + _s11g(ctx) + _s11h(ctx)
            + _s11i(ctx) + _s10a(ctx))
    return ("<div class='osx'>"
            + K.frame('4 · Commerce', SUBNAV_COMMERCE, body)
            + "</div>")



def check(ctx: Dict[str, Any] = None) -> Dict[str, Any]:
    ctx = _d(ctx)
    problems = []
    html = commerce_section(ctx)
    for sid in SCREENS_11 + SCREENS_10:
        n = html.count("id='os-%s'" % sid)
        if n == 0:
            problems.append("screen %s not rendered" % sid)
        elif n > 1:
            problems.append("screen %s rendered %d times" % (sid, n))
    if _card(ctx):
        for sid in SHARED_DESKS:
            seg = html[html.find("id='os-%s'" % sid):]
            seg = seg[:seg.find("</section>") + 10]
            if "One worker, five desks" not in seg:
                problems.append("%s does not disclose its shared worker" % sid)
    flat = " ".join(html.split())
    # STAGE 1 MUST NOT DRAW A STAGE 2 CONTROL.
    # STAGE 2 IS BUILT, so the screens must say HOW a price change
    # happens rather than that it cannot. The check moves with the text.
    if "no button that simply" not in flat:
        problems.append("11e no longer explains how a discount happens")
    if "approved one at a time, never in a batch" not in flat:
        problems.append("the pink rule is not stated where prices are "
                        "approved")
    for word in ("SPEND gate", "margin preview"):
        if word not in flat:
            problems.append("the money rule is not stated: %s missing" % word)
    return {"ok": not problems, "problems": problems,
            "screens": len(SCREENS_11) + len(SCREENS_10), "chars": len(html)}


if __name__ == "__main__":
    import content_engine_agentos as _A

    class _S:
        def get_setting(self, k, d=None):
            return {"BRAND_NAME": "acme"}.get(k, d)

        def set_setting(self, k, v):
            pass

        def list_jobs(self, status=None):
            return []

        def daily_cost(self):
            return 0.0

    r = check(_A.build_ctx(_S()))
    assert r["ok"], r["problems"]
    print("screens:", r["screens"], "chars:", r["chars"])
