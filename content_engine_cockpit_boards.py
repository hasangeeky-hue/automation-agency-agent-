# -*- coding: utf-8 -*-
"""SHIM. The Command Cockpit now lives in content_engine_command_ui.

This file held sixteen tabs in the old dark design: command, decision
queue, decision log, signal router, three approval tabs, budget,
autonomy, keys, loops, jobs, engine state, playbook, what-works and
experiments. Sixteen tabs is a filing cabinet, and the specification
replaces it with ONE command canvas: business pulse, machine pulse,
what changed, decision queue, quick fix, loops, initiatives, cost
pulse, data health and the Commander panel, exception-first, in the
shared light design.

THE NAME SURVIVES ON PURPOSE: content_engine_dashboard imports this
module at line 4385 and renaming the file takes the dashboard down.

WHAT MOVED WHERE:
  board_command                  -> Business Pulse + Machine Pulse
  board_decisions, decision log  -> Decision Queue (contract-checked:
                                    DECISION_INCOMPLETE cannot rank)
  approval tabs                  -> decision cards carry approve or
                                    reject; the domain OS holds detail
  board_budget, cost pieces      -> Cost Pulse (fed by the BI Cost OS)
  board_loops                    -> Loops + Initiatives, measured on
                                    target outcomes, not actions done
  board_keys, board_engine       -> Machine Pulse via the Control Plane
  board_jobs, failures           -> Quick Fix, with rollback and
                                    verification or no button at all
  playbook, works, experiments   -> the domain OS screens they described

The previous file is kept at _cockpit_boards_replaced.bak for one
release.
"""
from __future__ import annotations

from typing import Any, Dict

import content_engine_command_ui as _UI

#: Kept so an old caller importing these names still resolves.
TABS = [("ckcmd", "", "Command Cockpit")]
GROUPS = [("ckdec", "COMMAND", "What deserves attention now?",
           ["ckcmd"])]


def cockpit_section(ctx=None) -> str:
    """The cockpit. Now one command canvas."""
    return _UI.cockpit_section(ctx or {})


def cockpit_pages(ctx=None) -> Dict[str, str]:
    return _UI.cockpit_pages(ctx or {})


def check_contract() -> Dict[str, Any]:
    return _UI.check_contract()
