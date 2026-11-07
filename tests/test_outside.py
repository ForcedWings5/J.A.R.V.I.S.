"""Tests for outside.py: JARVIS's one door to the internet, shared by Weather and Football.

Nothing here goes online: conftest.py makes outside._fetch fail loudly, and each test that
needs a reply puts a made-up one in its place (spec: docs/specs/2026-11-07-sports-space.md).
"""
import collections
import http.server
import logging
import ssl
import threading
import time
import types
import urllib.error
import urllib.request

import pytest
import truststore

import config
import outside
import weather

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


# ---------- the rate guard ----------

@pytest.fixture
def minute(monkeypatch):
    """A clock the test moves by hand."""
    now = types.SimpleNamespace(t=1000.0)
    monkeypatch.setattr(outside, "monotonic", lambda: now.t)
    return now


def test_the_tenth_football_request_in_a_minute_is_refused_unsent(monkeypatch, minute, caplog):
    seen = fake_fetch(monkeypatch, b"{}")
    for _ in range(9):
        outside.get(FOOT, {})
    with caplog.at_level(logging.INFO, logger="jarvis.outside"):
        with pytest.raises(outside.OutsideError, match="busy"):
            outside.get(FOOT, {})
    assert len(seen) == 9 and "rate guard" in caplog.text
    minute.t += 60.01
    outside.get(FOOT, {})
    assert len(seen) == 10


def test_failed_requests_count_too(monkeypatch, minute):
    fake_fetch(monkeypatch, TimeoutError())
    for _ in range(9):
        with pytest.raises(outside.OutsideError, match="unreachable"):
            outside.get(FOOT, {})
    with pytest.raises(outside.OutsideError, match="busy"):
        outside.get(FOOT, {})


def test_open_meteo_has_no_guard(monkeypatch, minute):
    seen = fake_fetch(monkeypatch, b"{}")
    for _ in range(20):
        outside.get(config.WEATHER_FORECAST_URL, {"latitude": 1})
    assert len(seen) == 20


class _SlowCount(collections.deque):
    """The count is taken, then a moment passes before the guard can record the request, so
    other threads run in between with the same count. Without the lock, more than 9 requests
    then get through (checked: 20 of 20)."""

    def __len__(self):
        count = super().__len__()
        time.sleep(0.001)
        return count


def test_the_guard_holds_with_requests_at_the_same_time(monkeypatch, minute):
    seen = fake_fetch(monkeypatch, b"{}")
    monkeypatch.setitem(outside._sent, "api.football-data.org", _SlowCount())
    results = []
    start = threading.Barrier(20)               # all 20 ask at the same moment

    def ask():
        start.wait()
        try:
            outside.get(FOOT, {})
            results.append("ok")
        except outside.OutsideError as e:
            results.append(e.kind)

    threads = [threading.Thread(target=ask) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == 9 and results.count("busy") == 11 and len(seen) == 9


def test_headers_go_only_to_football_data(monkeypatch):
    seen = fake_fetch(monkeypatch, b"{}")
    with pytest.raises(ValueError):
        outside.get(config.WEATHER_FORECAST_URL, {"latitude": 1}, headers={"X-Auth-Token": KEY})
    assert seen == []


@pytest.mark.parametrize("at, admitted", [(59.99, False), (60.0, True)])
def test_the_guards_minute_ends_exactly_at_60_seconds(monkeypatch, minute, at, admitted):
    seen = fake_fetch(monkeypatch, b"{}")
    for _ in range(9):
        outside.get(FOOT, {})
    minute.t += at
    if admitted:
        outside.get(FOOT, {})
    else:
        with pytest.raises(outside.OutsideError, match="busy"):
            outside.get(FOOT, {})
    assert len(seen) == 9 + admitted


# ---------- reading replies (shared with Weather) ----------

def test_the_readers_are_shared_with_weather():
    assert weather._num is outside.num and weather._text is outside.text and weather._obj is outside.obj
    assert outside.clean("a\u202eb  c\x00", 3) == "ab"
    assert outside.num(10 ** 400) is None and outside.num(-(10 ** 400)) is None


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
