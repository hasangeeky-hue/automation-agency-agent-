"""COMPATIBILITY SHIM. The SEO screens were born inside the VX2 experiment;
the founder cancelled VX2 and moved the screens into the old dashboard, so
they now live in content_engine_seo_screens. This name keeps old imports and
gates working and holds no code of its own."""
from content_engine_seo_screens import *  # noqa: F401,F403
from content_engine_seo_screens import (  # noqa: F401
    _rows_for, _issue_row, _measure_rows, _open, CSS, JS)
