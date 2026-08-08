"""
content_engine_outreach_boards.py
============================================================================
THE ONE FUNCTION THE DASHBOARD CALLS FOR LEADS AND OUTREACH.

WHAT USED TO BE HERE
  Fourteen tabs and roughly two hundred and forty cards, plus a group rail
  and a run bar. All of it is gone. The section is now the engagement OS:
  one band, one grouped rail, one panel, and every control on it is native.

WHY THIS FILE STILL EXISTS AT ALL
  The dashboard imports it by name and passes the context it has always
  passed. Keeping the entry point means the removal touched one call site
  instead of every caller, and the old signature still works.
============================================================================
"""

from __future__ import annotations

#: The order the founder's working blocks are carried through in. They are
#: passed in ALREADY RENDERED by the dashboard, so every send button on
#: them keeps calling the endpoint it always did.
LIVE_ORDER = ("outbox_pointer", "outbox", "replies", "leads_table",
              "maps_form")


def outreach_section(ctx, live=None) -> str:
    """The Email and Lead Engagement OS, as one section.

    ONE NAVIGATION GRAMMAR. A band, a grouped rail, a panel. The tab strip
    that used to sit here was a second grammar on top of the rail and the
    run bar was a third; that stacking is what the founder scored zero on
    twice, so there is exactly one now.

    THE LIVE BLOCKS COME BACK. The previous build silently dropped the
    outbox, the replies inbox, the leads table and the Maps form. They are
    reattached to Overview, unmodified, because they are the controls that
    actually send.
    """
    ctx = ctx if isinstance(ctx, dict) else {}
    import content_engine_os_screens as SCR
    osctx = dict(ctx.get("os") or {})
    if not osctx:
        return ("<div class='card full' style='border-color:#F5B14C'>"
                "<p class='ct'>The engagement OS has nothing to read yet</p>"
                "<p class='cc'>The context builder did not hand this section "
                "an OS view. Press Re-read the engine once the page loads, or "
                "check the server log for the reason.</p></div>")
    osctx.setdefault("attribution", ctx.get("attribution") or {})
    blocks = live if isinstance(live, dict) else (ctx.get("live") or {})
    joined = ""
    if isinstance(blocks, dict):
        joined = "".join(str(blocks.get(k) or "") for k in LIVE_ORDER)
    elif blocks:
        joined = str(blocks)
    return SCR.build(osctx, live=joined or None)




# ---------------------------------------------------------------- self-check
if __name__ == "__main__":
    import content_engine_os_screens as SCR
    html = outreach_section({"os": {"summary": {}, "campaigns": []}},
                            live={"outbox": "<b>LIVE</b>"})
    assert "os-rail" in html and "LIVE" in html
    assert "class='stabs'" not in html and "sgroups" not in html
    print(f"outreach_boards self-check OK - one section, "
          f"{len(SCR.PANELS)} screens, no cards, no tab strip, and the "
          f"founder's live blocks carried through")
