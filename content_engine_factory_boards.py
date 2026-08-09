# -*- coding: utf-8 -*-
"""SHIM. The Content Factory now lives in content_engine_factory_ui.

This file used to hold sixteen boards: a command board, a brief board, a
calendar, an image board, competitive intel, a pipeline view, quality,
routing, repurposing and cost, plus six platform preview screens. All of
it is replaced by the nine-screen Content Factory OS, which draws the
same job as one loop rather than sixteen views onto a job list.

THE NAME SURVIVES ON PURPOSE. content_engine_dashboard imports this
module and calls factory_section(ctx). Renaming or deleting the file
breaks that import and takes the whole dashboard down with it, so the
name stays and the two public functions delegate.

WHAT WAS DELIBERATELY DROPPED, and where it went:

  the sixteen boards          -> nine screens (spec 5: nine is the cap,
                                 and "do not create dozens of nested
                                 modules" is the same sentence)
  per-platform preview boards -> Review, which previews the variant that
                                 will actually ship
  cost board                  -> Settings, as a per-content ceiling, and
                                 the agent budget that enforces it
  competitive intel board     -> the Inbox, as a signal from whichever OS
                                 observed it. The factory does not
                                 research competitors; section 2.

The previous file is kept at _factory_boards_replaced.bak in the working
tree for one release, so a diff is possible without going to git.
"""
from __future__ import annotations

from typing import Any, Dict

import content_engine_factory_ui as _UI

#: Kept so an old caller importing these names still resolves.
SCREENS = _UI.SCREENS
EVENTS = _UI.EVENTS
API = _UI.API


def factory_section(ctx=None) -> str:
    """The Content Factory section. Now the nine-screen OS."""
    return _UI.factory_section(ctx or {})


def factory_pages(ctx=None) -> Dict[str, str]:
    """Each screen alone, for a caller that wants one panel."""
    return _UI.factory_pages(ctx or {})


def receive_signal(raw, *, at="") -> Dict[str, Any]:
    """The external-OS front door, re-exported for convenience."""
    return _UI.receive_signal(raw, at=at)


def check_screens() -> Dict[str, Any]:
    return _UI.check_screens()
