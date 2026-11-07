"""Shared test setup.

Two safety rules live here:
1. Tests use a throwaway in-memory database, never your real jarvis.db.
2. Tests use a frozen clock (Monday 2030-01-07, 08:00), so they pass on any day.
3. Tests never read the real .env, and never see a real football key.
"""
import os

# This must happen BEFORE anything imports config, because the database opens on import.
os.environ["JARVIS_DB"] = ":memory:"
# The same for secrets: an empty file instead of .env, and no key from the shell
os.environ["JARVIS_ENV"] = os.devnull
os.environ.pop("FOOTBALL_DATA_KEY", None)

from datetime import datetime  # noqa: E402

import pytest  # noqa: E402

import database  # noqa: E402
import jcal  # noqa: E402
# Registers every tool in the order the app uses, whichever test file runs first
import brain  # noqa: E402, F401
import football  # noqa: E402
import outside  # noqa: E402
import weather  # noqa: E402  (after brain, which imports it last: its tools come last)


class Clock:
    """The fake 'now'. Tests move it with clock.set(hour, minute, day)."""

    def __init__(self):
        self.now = datetime(2030, 1, 7, 8, 0)      # a Monday

    def set(self, hour, minute=0, day=7):
        self.now = datetime(2030, 1, day, hour, minute)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    """Runs before every test: empty database, frozen clock."""
    with database.lock:
        database.conn.execute("DELETE FROM events")
        database.conn.execute("DELETE FROM event_exceptions")
        database.conn.execute("DELETE FROM tasks")
        database.conn.execute("DELETE FROM notes")
        database.conn.commit()

    fake = Clock()

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            n = fake.now
            return cls(n.year, n.month, n.day, n.hour, n.minute)

    monkeypatch.setattr(jcal, "datetime", FakeDateTime)
    return fake


@pytest.fixture(autouse=True)
def no_internet(monkeypatch):
    """Runs before every test: JARVIS's one door to the internet (outside.py) fails loudly,
    so no test can depend on Open-Meteo or football-data.org (CI has no network to count on,
    and tests must stay offline)."""
    def refuse(address, headers=None):
        raise AssertionError(f"a test tried to reach the internet: {address}")
    monkeypatch.setattr(outside, "_fetch", refuse)
    outside.forget_rate_guard()     # no requests counted from another test
    football.forget_everything()    # no football replies kept from another test
    weather.forget_everything()     # no cache, ids or place carried over from another test
