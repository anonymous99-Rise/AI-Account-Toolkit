# -*- coding: utf-8 -*-
"""Blacklist read/reset helpers for the monitor UI."""

from __future__ import annotations

try:
    from webui.blacklist_store import read_blacklist, reset_blacklist
except ImportError:  # running from webui/
    from blacklist_store import read_blacklist, reset_blacklist  # type: ignore


__all__ = ["read_blacklist", "reset_blacklist"]
