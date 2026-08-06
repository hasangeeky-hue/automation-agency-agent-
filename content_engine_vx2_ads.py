"""COMPATIBILITY SHIM. The ad platform environments were born inside the VX2
experiment; VX2 is cancelled and they serve the old dashboard's Media Buying
section, so they live in content_engine_media_platforms now. This name keeps
old imports and gates working and holds no code of its own."""
from content_engine_media_platforms import *  # noqa: F401,F403
from content_engine_media_platforms import (  # noqa: F401
    CSS, JS, PLATFORMS, ORDER, SAMPLE)
