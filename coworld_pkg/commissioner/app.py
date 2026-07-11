"""ASGI entrypoint for Muster's custom commissioner image.

The upstream image runs `uvicorn commissioners.common.app:app`, which builds the
app from COMMISSIONER_KEY (default "config_driven"). We instead point uvicorn at
THIS module: importing it registers the "muster" key, then we build the app for
that key explicitly. Same server, same config loading — only the strategy class
differs (per-division variant selection; see muster_commissioner.py).
"""
from __future__ import annotations

from commissioners.common.app import commissioner_app

# Importing the package registers the "muster" commissioner key as a side effect.
import coworld_pkg.commissioner  # noqa: F401

app = commissioner_app("muster")
