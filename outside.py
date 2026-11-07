"""The one door to the internet, shared by Weather and Football.

Every request JARVIS makes to another computer goes through `get`, and only to one of the
fixed HTTPS addresses in config.py, so the model, or a reply, can never send JARVIS anywhere
else (SECURITY.md section 5). Moved here from weather.py when Football became the second
service (docs/specs/2026-11-07-sports-space.md), so there is still exactly one place to check.
"""
import json
import logging
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

import truststore

import config

log = logging.getLogger("jarvis.outside")

ADDRESSES = frozenset((config.WEATHER_GEOCODE_URL, config.WEATHER_FORECAST_URL,
                       config.WEATHER_AIR_URL, *config.FOOTBALL_ADDRESSES))

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


def get(address: str, params: dict, headers: dict[str, str] | None = None) -> dict:
    """Ask one of the fixed addresses; any failure becomes one plain OutsideError."""
    if address not in ADDRESSES:
        raise ValueError("not one of JARVIS's fixed addresses")
    full = address + "?" + urllib.parse.urlencode(params) if params else address
    host = urllib.parse.urlsplit(address).hostname
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
