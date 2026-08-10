# -*- coding: utf-8 -*-
"""SHIM. The System Map now lives in content_engine_control_ui.

This file held fourteen boards: command, wires, connect, agents, jobs,
failures, cost, freshness, flow, deps, drift, deploy, loopmap and agent
activity. They showed pieces of the machine; none of them could answer
"what breaks if I disconnect this" or "where exactly is this loop
stuck", and health was reported per part with no propagation, so a dead
image provider left the factory looking green.

The thirteen-screen System Control Plane replaces them: a registry with
REQUIRED/OPTIONAL dependency propagation (a failed optional dependency
DEGRADES its dependent, a failed required one FAILS it), a clickable
wiring map with impact analysis, loop stall detection against a declared
normal wait, correlation traces, deduplicated alerts with root-cause
chains, credential METADATA with never a value, and real /proc metrics
from the box it runs on.

THE NAME SURVIVES ON PURPOSE: content_engine_dashboard imports this
module at line 4357 and renaming the file takes the dashboard down.

WHAT MOVED WHERE:
  board_command, board_freshness  -> 01 System Overview
  board_wires, board_connect      -> 03 Connections
  board_deps, board_flow          -> 02 Wiring Map, now with impact
  board_agents, agent activity    -> 05 Agent Health
  board_jobs, board_failures      -> 06 Workflows, 11 Logs
  board_cost                      -> 10 API and Tool Usage (economics
                                     live in the BI Cost OS)
  board_loopmap                   -> 07 Loop Map, now with STALLED
  board_deploy, board_drift       -> 12 Alerts and the overview

The previous file is kept at _system_boards_replaced.bak for one
release.
"""
from __future__ import annotations

from typing import Any, Dict

import content_engine_control_ui as _UI

#: Kept so an old caller importing these names still resolves.
SCREENS = _UI.SCREENS
TABS = [(sid, "", label) for sid, _n, label, _f, _q in _UI.SCREENS]


def system_section(ctx=None) -> str:
    """The system section. Now the thirteen-screen Control Plane."""
    return _UI.system_section(ctx or {})


def system_pages(ctx=None) -> Dict[str, str]:
    return _UI.system_pages(ctx or {})


def check_screens() -> Dict[str, Any]:
    return _UI.check_screens()
