# -*- coding: utf-8 -*-
"""SHIM. Business Intelligence now lives in content_engine_bi_ui.

This file used to hold sixteen boards: command, demand, markets,
channels, content, leads, outreach, consultations, funnel, revenue,
customers, econ, spend, cost and exec. They reported what the business
EARNED and had almost nothing to say about what it PAID to earn it.

The revised specification calls that a major mistake: if twenty agents
generate value while consuming LLM, SERP, crawling, video, image,
enrichment, email, storage, proxy and automation cost, the BI layer must
know. Cost Intelligence is now BI core rather than a settings page, and
the nine MVP screens are built around

    BUSINESS VALUE - MEDIA - AI - API - CONTENT - DATA - AUTOMATION
    - INFRASTRUCTURE - OTHER VARIABLE = CONTRIBUTION.

THE NAME SURVIVES ON PURPOSE. content_engine_dashboard imports this
module and calls bi_section(ctx); renaming the file takes the dashboard
down with it.

WHAT MOVED WHERE:

  board_command, board_exec   -> 01 Executive, now with the margin
                                 waterfall and both CACs
  board_revenue, board_econ   -> 01 Executive and 03 Funnel
  board_channels, board_demand,
  board_markets, board_content -> 02 Growth, ranked by value per unit
                                 cost rather than by volume
  board_leads, board_outreach,
  board_consultations, board_funnel -> 03 Funnel
  board_spend, board_cost     -> 04 Costs, which is now a cost
                                 INTELLIGENCE screen: registry, dated
                                 pricing, waste, budgets and forecast
  nothing previously          -> 05 Agent Economics, 06 Risks and
                                 Opportunities, 07 AI Decisions,
                                 08 Initiatives, 09 Data and Cost Health

content_engine_bi.py is UNCHANGED and still computes the value half:
deals, revenue, funnel, demand, channel mix. This OS subtracts cost from
what that module reports; it does not replace it.

The previous file is kept at _bi_boards_replaced.bak in the working tree
for one release, so a diff is possible without going to git.
"""
from __future__ import annotations

from typing import Any, Dict

import content_engine_bi_ui as _UI

#: Kept so an old caller importing these names still resolves.
SCREENS = _UI.SCREENS
MANDATORY = _UI.MANDATORY


def bi_section(ctx=None) -> str:
    """The Business Intelligence section. Now the nine-screen OS."""
    return _UI.bi_section(ctx or {})


def bi_pages(ctx=None) -> Dict[str, str]:
    """Each screen alone, for a caller that wants one panel."""
    return _UI.bi_pages(ctx or {})


def receive(raw) -> Dict[str, Any]:
    """The cost-event front door, re-exported for convenience."""
    return _UI.receive(raw)


def check_screens() -> Dict[str, Any]:
    return _UI.check_screens()
