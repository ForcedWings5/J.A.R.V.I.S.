"""Made-up football-data.org replies for the tests and evals, shaped like the real ones (from
its v4 docs, read 2026-11-07), and `serve`, which answers the shared door (outside._fetch)
with them. Spec: docs/specs/2026-11-07-sports-space.md.
"""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import football
import outside

KEY = "abcdef0123456789"


def freeze(monkeypatch):
    """Monday 2030-01-07 08:00 in London (conftest's clock), with a key set."""
    monkeypatch.setattr(football, "_now", lambda: datetime(2030, 1, 7, 8, 0))
    monkeypatch.setattr(football, "_ZONE", ZoneInfo("Europe/London"))
    monkeypatch.setenv("FOOTBALL_DATA_KEY", KEY)


def team(id, name, short=None):
    return {"id": id, "name": name, "shortName": short or name, "tla": (short or name)[:3].upper(),
            "crest": f"https://crests.football-data.org/{id}.png"}


ROMA = team(100, "AS Roma", "Roma")
LAZIO = team(110, "SS Lazio", "Lazio")
NEWCASTLE = team(67, "Newcastle United FC", "Newcastle")


def match(id, utc, status, home, away, score=None, matchday=None, code="SA", name="Serie A"):
    home_goals, away_goals = score if score else (None, None)
    return {"id": id, "utcDate": utc, "status": status, "matchday": matchday,
            "stage": "REGULAR_SEASON", "lastUpdated": utc,
            "competition": {"id": 2019, "name": name, "code": code, "type": "LEAGUE"},
            "homeTeam": home, "awayTeam": away,
            "score": {"winner": None, "duration": "REGULAR",
                      "fullTime": {"home": home_goals, "away": away_goals},
                      "halfTime": {"home": None, "away": None}}}


def matches(*ms):
    return {"filters": {}, "resultSet": {"count": len(ms)}, "matches": list(ms)}


def row(position, team, played, won, draw, lost, gd, points):
    return {"position": position, "team": team, "playedGames": played, "form": None,
            "won": won, "draw": draw, "lost": lost, "points": points,
            "goalsFor": None, "goalsAgainst": None, "goalDifference": gd}


def standings(*rows):
    """A reply with a HOME table first, so the code must pick the TOTAL one."""
    return {"filters": {}, "competition": {"code": "SA"}, "season": {},
            "standings": [{"stage": "REGULAR_SEASON", "type": "HOME", "group": None, "table": []},
                          {"stage": "REGULAR_SEASON", "type": "TOTAL", "group": None,
                           "table": list(rows)}]}


class Served:
    def __init__(self):
        self.calls = []          # (address, headers) for each request


def serve(monkeypatch, replies: dict) -> Served:
    """Answer the shared door by the part of the address after /v4 (such as
    "/competitions/SA/standings"): a dict becomes its JSON, an exception is raised, and a
    request nobody prepared for fails the test."""
    served = Served()

    def fetch(address, headers):
        served.calls.append((address, dict(headers)))
        path = address.split("/v4", 1)[1].split("?", 1)[0]
        if path not in replies:
            raise AssertionError(f"no made-up reply for {path}")
        answer = replies[path]
        if isinstance(answer, BaseException):
            raise answer
        return json.dumps(answer).encode()

    monkeypatch.setattr(outside, "_fetch", fetch)
    return served
