"""Football, for the Sports space: data from football-data.org's free plan.

Stage 1 of the build holds only the key. The requests, the summaries and JARVIS's tools come
in later stages. Spec: docs/specs/2026-11-07-sports-space.md.
"""
import os
import re

import config

_KEY_NAME = "FOOTBALL_DATA_KEY"
_KEY_SHAPE = re.compile(r"[A-Za-z0-9]{10,64}", re.ASCII)


def _from_env_file() -> str | None:
    """The last FOOTBALL_DATA_KEY line of .env, written in any of the usual ways
    (`NAME=value`, spaces round `=`, quotes, `export NAME=value`)."""
    try:
        text = config.ENV_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):     # no file, a folder, unreadable, not UTF-8
        return None
    found = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ").lstrip()
        name, sep, value = line.partition("=")
        if sep and name.strip() == _KEY_NAME:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            found = value
    return found


def _key() -> str | None:
    """The football-data.org key, or None. Read on every call (a tiny file), so a key added
    while JARVIS runs works without a restart. Anything that does not look like a key counts
    as none. Never logged: it goes only into the request header (outside.get)."""
    value = os.environ.get(_KEY_NAME) or _from_env_file()
    if value and _KEY_SHAPE.fullmatch(value):
        return value
    return None
