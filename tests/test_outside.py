"""Tests for outside.py: JARVIS's one door to the internet, shared by Weather and Football.

Nothing here goes online: conftest.py makes outside._fetch fail loudly, and each test that
needs a reply puts a made-up one in its place (spec: docs/specs/2026-11-07-sports-space.md).
"""
import http.server
import logging
import ssl
import threading
import urllib.error
import urllib.request

import pytest
import truststore

import config
import outside

FOOT = config.FOOTBALL_API + "/competitions/SA/standings"
KEY = "testkey0123456789"


def fake_fetch(monkeypatch, reply):
    """Replace the door: record (address, headers) and give `reply`, or raise it."""
    seen = []

    def fetch(address, headers):
        seen.append((address, dict(headers)))
        if isinstance(reply, BaseException):
            raise reply
        return reply

    monkeypatch.setattr(outside, "_fetch", fetch)
    return seen


def http_error(code):
    return urllib.error.HTTPError(FOOT, code, "x", {}, None)


# ---------- the fixed addresses ----------

def test_the_addresses_are_weathers_three_and_footballs_thirteen():
    assert len(config.FOOTBALL_ADDRESSES) == 13 == len(set(config.FOOTBALL_ADDRESSES))
    assert outside.ADDRESSES == {config.WEATHER_GEOCODE_URL, config.WEATHER_FORECAST_URL,
                                 config.WEATHER_AIR_URL, *config.FOOTBALL_ADDRESSES}
    assert all(a.startswith("https://api.football-data.org/v4/") for a in config.FOOTBALL_ADDRESSES)
    assert config.FOOTBALL_API + "/competitions/CL/standings" in config.FOOTBALL_ADDRESSES
    assert config.FOOTBALL_API + "/competitions/CL/matches" not in config.FOOTBALL_ADDRESSES
    assert config.FOOTBALL_API + "/teams/100/matches" in config.FOOTBALL_ADDRESSES
    assert config.FOOTBALL_API + "/teams/67/matches" in config.FOOTBALL_ADDRESSES


def test_an_unlisted_address_is_refused_before_anything_is_sent(monkeypatch):
    seen = fake_fetch(monkeypatch, b"{}")
    for bad in ("https://example.com/v4/competitions/SA/standings", FOOT + "/../../x",
                FOOT.replace("https://", "http://"), config.FOOTBALL_API + "/teams/1/matches"):
        with pytest.raises(ValueError):
            outside.get(bad, {})
    assert seen == []


def test_params_are_encoded_and_headers_passed_on(monkeypatch):
    seen = fake_fetch(monkeypatch, b"{}")
    outside.get(FOOT, {"season": "2026&x=1"}, headers={"X-Auth-Token": KEY})
    outside.get(FOOT, {})
    assert seen == [(FOOT + "?season=2026%26x%3D1", {"X-Auth-Token": KEY}), (FOOT, {})]


# ---------- failures ----------

@pytest.mark.parametrize("reply, kind", [
    (TimeoutError(), "unreachable"), (urllib.error.URLError("down"), "unreachable"),
    (b"not json", "unreachable"), (b"[1, 2]", "unreachable"), (b"x" * 1_000_001, "unreachable"),
    (b'{"a": NaN}', "unreachable"), (b"[" * 200_000, "unreachable"),
    (http_error(404), "unreachable"), (http_error(500), "unreachable"),
    (http_error(400), "refused"), (http_error(401), "refused"), (http_error(403), "refused"),
    (http_error(429), "busy")])
def test_every_failure_becomes_one_of_three_kinds(monkeypatch, reply, kind):
    fake_fetch(monkeypatch, reply)
    with pytest.raises(outside.OutsideError) as caught:
        outside.get(FOOT, {})
    assert caught.value.kind == kind and str(caught.value) == kind


@pytest.mark.parametrize("reply", [b"{}", http_error(403), TimeoutError()])
def test_the_log_and_errors_never_hold_the_address_or_a_header(monkeypatch, caplog, reply):
    fake_fetch(monkeypatch, reply)
    with caplog.at_level(logging.INFO, logger="jarvis.outside"):
        try:
            outside.get(FOOT, {"season": "2026"}, headers={"X-Auth-Token": KEY})
        except outside.OutsideError as e:
            assert KEY not in repr(e) and "season" not in repr(e)
    assert "api.football-data.org" in caplog.text
    for secret in (KEY, "competitions", "season"):
        assert secret not in caplog.text


def test_each_request_is_logged_without_its_address(monkeypatch, caplog):
    fake_fetch(monkeypatch, b"{}")
    with caplog.at_level(logging.INFO, logger="jarvis.outside"):
        outside.get(config.WEATHER_GEOCODE_URL, {"name": "Paris"})
    assert "geocoding-api.open-meteo.com" in caplog.text and "Paris" not in caplog.text


# ---------- how the door itself connects (moved from test_weather.py) ----------

def test_redirects_are_refused():
    """A real server on this Mac answers 302; the opener must not follow it."""
    hits = {"elsewhere": 0}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/elsewhere":
                hits["elsewhere"] += 1
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")
                return
            self.send_response(302)
            self.send_header("Location", "/elsewhere")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    # A short poll, so shutdown() returns at once instead of after half a second
    thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as caught:
            outside._OPENER.open(f"http://127.0.0.1:{server.server_port}/start", timeout=2)
        assert caught.value.code == 302
        caught.value.close()
        assert hits["elsewhere"] == 0
    finally:
        server.shutdown()
        server.server_close()


def test_https_checks_certificates_against_the_macs_trust_list():
    """python.org's Python has no list of trusted certificate signers of its own, so every
    request failed (CHANGELOG section 56). The opener checks against macOS's own list, the
    one Safari uses (the owner's choice), and never skips the check."""
    https = [h for h in outside._OPENER.handlers if isinstance(h, urllib.request.HTTPSHandler)]
    assert len(https) == 1
    context = https[0]._context
    assert isinstance(context, truststore.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname is True


def test_tests_cannot_reach_the_internet():
    with pytest.raises(AssertionError, match="internet"):
        outside._fetch(FOOT, {})
