"""Pytest helpers live in portraits.py (added to pythonpath)."""

from __future__ import annotations

import os
import re

# Rich help wrapping in CI (80 cols + ANSI) can split option names.
os.environ.setdefault("COLUMNS", "120")
os.environ.setdefault("NO_COLOR", "1")
os.environ.setdefault("TERM", "dumb")

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def visible_help(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)
