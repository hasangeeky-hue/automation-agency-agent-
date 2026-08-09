"""
content_engine_media_boards.py
============================================================================
RETIRED, DELIBERATELY. The 16-tab media UI that lived here (1574 lines,
296 cards, then 16 screens) is gone on the founder's order: "this design
gonna remove media buying UI completely."

What remains is the one entry point the dashboard calls, delegating to
content_engine_media_center, the Media Buying OS section. Same signature,
same call site in content_engine_dashboard, so the assembly did not move;
only what it draws did. The same surgery outreach_boards had when the
email OS replaced it (1581 lines to 70).

The DATA all still exists elsewhere: orders in content_engine_media_orders,
economics in content_engine_ads, platform capability in
content_engine_media_platforms, and the canonical model in
content_engine_media_os / _plan / _perf / _creative.
============================================================================
"""

from __future__ import annotations

import logging

log = logging.getLogger("content_engine.media_boards")


def media_section(ctx, legacy_campaigns: str = "",
                  legacy_tracking: str = "") -> str:
    """The Media Buying OS section. Everything is in the centre now."""
    import content_engine_media_center as MCTR
    return MCTR.section(ctx or {}, legacy_campaigns=legacy_campaigns,
                        legacy_tracking=legacy_tracking)
