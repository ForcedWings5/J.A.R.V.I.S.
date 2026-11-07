"""The one door to the internet, shared by Weather and Football.

Every request JARVIS makes to another computer goes through `get`, and only to one of the
fixed HTTPS addresses in config.py, so the model, or a reply, can never send JARVIS anywhere
else (SECURITY.md section 5). Moved here from weather.py when Football became the second
service (docs/specs/2026-11-07-sports-space.md), so there is still exactly one place to check.
"""
import json
import logging
import math
import ssl
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from time import monotonic   # its own name, so tests can move the guard's clock

import truststore

import config

log = logging.getLogger("jarvis.outside")

ADDRESSES = frozenset((config.WEATHER_GEOCODE_URL, config.WEATHER_FORECAST_URL,
                       config.WEATHER_AIR_URL, *config.FOOTBALL_ADDRESSES))

# The rate guard: football-data.org's free plan allows 10 requests a minute, and going over can
# get the key blocked. JARVIS allows itself 9 (one spare for clock differences) and refuses the
# next *before* it is sent. A request that was sent counts even if it failed. Open-Meteo has no
# limit JARVIS could reach, so no guard.
_LIMITS = {"api.football-data.org": config.FOOTBALL_REQUESTS_PER_MINUTE}
_sent: dict[str, deque] = {}            # host -> when its recent requests were sent
_guard_lock = threading.Lock()          # the server answers requests in threads

_HEADER_HOSTS = {"api.football-data.org"}

# HTTP statuses that mean "your key was not accepted", and "too many requests"
_REFUSED = {400, 401, 403}
_BUSY = 429


class OutsideError(Exception):
    """A request failed. `kind` says how, and is all the message holds: "unreachable" (no
    answer, or one that cannot be read), "refused" (the key was not accepted) or "busy" (too
    many requests). Never the address or a header, which can hold a place or a key."""

    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """urllib normally follows a "go over there instead" reply, which could take JARVIS to
    another site. Returning None makes it raise HTTPError instead, so the address stays fixed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# HTTPS proves it is really the service by a certificate, checked against a list of trusted
# signers. python.org's Python ships without such a list, so every request was refused.
# truststore checks against macOS's own list, the one Safari uses (the owner's choice,
# 2026-11-05), and keeps both checks on: the certificate and the host name.
_TLS = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
_OPENER = urllib.request.build_opener(_RefuseRedirects, urllib.request.HTTPSHandler(context=_TLS))


def _fetch(address: str, headers: dict[str, str]) -> bytes:
    """The one function that touches the network. Tests replace it (tests/conftest.py)."""
    request = urllib.request.Request(address, headers=headers)
    with _OPENER.open(request, timeout=config.OUTSIDE_TIMEOUT_SECONDS) as reply:
        return reply.read(config.OUTSIDE_MAX_BYTES + 1)


def _refuse_constant(name: str):
    """Python's json reads NaN and Infinity, which are not real JSON and not real data."""
    raise ValueError(f"{name} in a reply")


def _kind(error: Exception) -> str:
    """Which of the three kinds a failure is."""
    if isinstance(error, urllib.error.HTTPError):
        if error.code in _REFUSED:
            return "refused"
        if error.code == _BUSY:
            return "busy"
    return "unreachable"


def forget_rate_guard() -> None:
    """Start counting afresh (tests, between one test and the next)."""
    with _guard_lock:
        _sent.clear()


def _admit(host: str) -> bool:
    """Record a request about to be sent, unless the host's limit for this minute is used up."""
    limit = _LIMITS.get(host)
    if limit is None:
        return True
    with _guard_lock:
        now = monotonic()
        times = _sent.setdefault(host, deque())
        while times and times[0] <= now - 60:
            times.popleft()
        if len(times) >= limit:
            return False
        times.append(now)
        return True


def get(address: str, params: dict, headers: dict[str, str] | None = None) -> dict:
    """Ask one of the fixed addresses; any failure becomes one plain OutsideError."""
    if address not in ADDRESSES:
        raise ValueError("not one of JARVIS's fixed addresses")
    full = address + "?" + urllib.parse.urlencode(params) if params else address
    host = urllib.parse.urlsplit(address).hostname
    # Headers (the football key) go only to football-data.org, so a mistake in a caller can
    # never send the key to another service
    if headers and host not in _HEADER_HOSTS:
        raise ValueError("headers go only to football-data.org")
    if not _admit(host):
        log.info("outside request: %s, refused by the rate guard", host)
        raise OutsideError("busy")
    start = time.monotonic()
    outcome = "ok"
    try:
        body = _fetch(full, headers or {})
        if len(body) > config.OUTSIDE_MAX_BYTES:
            raise ValueError("reply too large")
        data = json.loads(body, parse_constant=_refuse_constant)
        if not isinstance(data, dict):
            raise ValueError("reply is not a JSON object")
        return data
    # URLError, HTTPError and timeouts are OSErrors; RecursionError: absurdly nested JSON
    except (OSError, ValueError, RecursionError) as e:
        if isinstance(e, urllib.error.HTTPError):
            e.close()                       # it holds the open reply
        outcome = type(e).__name__
        raise OutsideError(_kind(e)) from e
    finally:
        # The host and timing only: the address can hold a place, a header a key
        log.info("outside request: %s, %s in %d ms", host, outcome,
                 (time.monotonic() - start) * 1000)


# ---------- reading replies (moved from weather.py; Football uses them too) ----------

# A reply is outside data: it is read only through these, so a value of the wrong type (a
# word where a number belongs, a list where a table belongs) becomes "missing", never a
# crash, and never text that reaches the page or the conversation (final review).

def num(x) -> int | float | None:
    """x if it is a real, finite number, else None (True counts as a bool, not a 1)."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    try:
        return x if math.isfinite(x) else None
    except OverflowError:               # an int too large for a float (final review, stage 2)
        return None


def text(x) -> str:
    return x if isinstance(x, str) else ""


def obj(x) -> dict:
    return x if isinstance(x, dict) else {}


def clean(text: str | None, limit: int) -> str:
    """Outside text, made safe to show and to give the model: no control or invisible
    formatting characters (such as one that reverses the text), one space between words,
    and no longer than `limit`."""
    if text is None:
        return ""
    kept = []
    for ch in str(text):
        if ch.isspace():
            kept.append(" ")
        elif not unicodedata.category(ch).startswith("C"):
            kept.append(ch)
    return " ".join("".join(kept).split())[:limit].strip()
