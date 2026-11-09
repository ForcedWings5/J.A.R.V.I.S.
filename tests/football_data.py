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
INTER = team(108, "FC Internazionale Milano", "Inter")
MILAN = team(98, "AC Milan", "Milan")
NAPOLI = team(113, "SSC Napoli", "Napoli")


def match(id, utc, status, home, away, score=None, matchday=None, code="SA", name="Serie A"):
    home_goals, away_goals = score if score else (None, None)
    return {"id": id, "utcDate": utc, "status": status, "matchday": matchday,
            "stage": "REGULAR_SEASON", "lastUpdated": utc,
            "competition": {"id": 2019, "name": name, "code": code, "type": "LEAGUE"},
            "homeTeam": home, "awayTeam": away,
            "score": {"winner": None, "duration": "REGULAR",
                      "fullTime": {"home": home_goals, "away": away_goals},
                      "halfTime": {"home": None, "away": None}}}


# Roma's Serie A games around Monday 2030-01-07: 7 finished (oldest first, from Roma's side:
# W W D L W W L), one postponed, then 6 to come
ROMA_SEASON = (
    match(201, "2029-11-10T14:00:00Z", "POSTPONED", ROMA, MILAN, None, 12),
    match(202, "2029-11-24T17:00:00Z", "FINISHED", ROMA, NAPOLI, (2, 0), 13),
    match(203, "2029-12-01T19:45:00Z", "FINISHED", LAZIO, ROMA, (0, 1), 14),
    match(204, "2029-12-08T17:00:00Z", "FINISHED", ROMA, INTER, (1, 1), 15),
    match(205, "2029-12-15T19:45:00Z", "FINISHED", MILAN, ROMA, (2, 0), 16),
    match(206, "2029-12-21T19:45:00Z", "FINISHED", ROMA, LAZIO, (3, 1), 17),
    match(207, "2029-12-29T14:00:00Z", "FINISHED", NAPOLI, ROMA, (0, 2), 18),
    match(208, "2030-01-05T17:00:00Z", "FINISHED", INTER, ROMA, (2, 1), 19),
    match(209, "2030-01-12T19:45:00Z", "TIMED", ROMA, MILAN, None, 20),
    match(210, "2030-01-19T17:00:00Z", "TIMED", LAZIO, ROMA, None, 21),
    match(211, "2030-01-26T19:45:00Z", "TIMED", ROMA, NAPOLI, None, 22),
    match(212, "2030-02-02T17:00:00Z", "TIMED", INTER, ROMA, None, 23),
    match(213, "2030-02-09T19:45:00Z", "SCHEDULED", ROMA, MILAN, None, 24),
    match(214, "2030-02-16T17:00:00Z", "SCHEDULED", LAZIO, ROMA, None, 25),
)


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


# Whole replies for the league pages on Monday 2030-01-07
SA_TABLE = standings(row(1, INTER, 19, 14, 3, 2, 25, 45), row(2, NAPOLI, 19, 13, 3, 3, 18, 42),
                     row(3, ROMA, 19, 12, 4, 3, 20, 40), row(4, MILAN, 19, 11, 4, 4, 12, 37),
                     row(5, LAZIO, 19, 10, 3, 6, 5, 33))
SA_ROUNDS = matches(
    match(301, "2030-01-04T19:45:00Z", "FINISHED", MILAN, NAPOLI, (0, 2), 19),
    match(208, "2030-01-05T17:00:00Z", "FINISHED", INTER, ROMA, (2, 1), 19),
    match(209, "2030-01-12T19:45:00Z", "TIMED", ROMA, MILAN, None, 20),
    match(302, "2030-01-12T17:00:00Z", "TIMED", NAPOLI, LAZIO, None, 20))
REAL_MADRID = team(86, "Real Madrid CF", "Real Madrid")
BARCELONA = team(81, "FC Barcelona", "Barça")
PD_TABLE = standings(row(1, REAL_MADRID, 19, 15, 2, 2, 30, 47), row(2, BARCELONA, 19, 14, 3, 2, 28, 45))
BAYERN = team(5, "FC Bayern München", "Bayern")
CL_GAME = match(401, "2030-01-21T20:00:00Z", "TIMED", ROMA, BAYERN, None, 7,
                code="CL", name="UEFA Champions League")
CL_TABLE = standings(row(1, BAYERN, 6, 5, 1, 0, 10, 16), row(9, ROMA, 6, 3, 1, 2, 2, 10))


def serie_a_replies(cl=False):
    """The replies for Serie A's page on 2030-01-07; Roma has Champions League games if cl."""
    roma = list(ROMA_SEASON) + ([CL_GAME] if cl else [])
    return {"/competitions/SA/standings": SA_TABLE, "/competitions/SA/matches": SA_ROUNDS,
            "/teams/100/matches": matches(*roma), "/competitions/CL/standings": CL_TABLE}


# Newcastle's Premier League page on Monday 2030-01-07 (the demo uses it): 6 finished games,
# then 4 to come, and no Champions League games
ARSENAL = team(57, "Arsenal FC", "Arsenal")
LIVERPOOL = team(64, "Liverpool FC", "Liverpool")
SPURS = team(73, "Tottenham Hotspur FC", "Tottenham")
VILLA = team(58, "Aston Villa FC", "Aston Villa")


def _pl(id, utc, status, home, away, score=None, md=None):
    return match(id, utc, status, home, away, score, md, code="PL", name="Premier League")


NEWCASTLE_SEASON = (
    _pl(501, "2029-12-01T15:00:00Z", "FINISHED", NEWCASTLE, ARSENAL, (1, 2), 14),
    _pl(502, "2029-12-07T15:00:00Z", "FINISHED", LIVERPOOL, NEWCASTLE, (3, 0), 15),
    _pl(503, "2029-12-14T15:00:00Z", "FINISHED", NEWCASTLE, SPURS, (2, 1), 16),
    _pl(504, "2029-12-21T17:30:00Z", "FINISHED", VILLA, NEWCASTLE, (1, 1), 17),
    _pl(505, "2029-12-28T15:00:00Z", "FINISHED", NEWCASTLE, LIVERPOOL, (0, 2), 18),
    _pl(506, "2030-01-04T15:00:00Z", "FINISHED", ARSENAL, NEWCASTLE, (2, 2), 19),
    _pl(507, "2030-01-11T12:30:00Z", "TIMED", NEWCASTLE, VILLA, None, 20),
    _pl(508, "2030-01-18T15:00:00Z", "TIMED", SPURS, NEWCASTLE, None, 21),
    _pl(509, "2030-01-25T17:30:00Z", "TIMED", NEWCASTLE, ARSENAL, None, 22),
    _pl(510, "2030-02-01T15:00:00Z", "SCHEDULED", LIVERPOOL, NEWCASTLE, None, 23),
)
PL_TABLE = standings(row(1, LIVERPOOL, 19, 15, 3, 1, 30, 48), row(2, ARSENAL, 19, 13, 4, 2, 22, 43),
                     row(3, VILLA, 19, 11, 4, 4, 9, 37), row(4, SPURS, 19, 10, 3, 6, 6, 33),
                     row(11, NEWCASTLE, 19, 7, 5, 7, -1, 26))
PL_ROUNDS = matches(
    _pl(506, "2030-01-04T15:00:00Z", "FINISHED", ARSENAL, NEWCASTLE, (2, 2), 19),
    _pl(601, "2030-01-04T17:30:00Z", "FINISHED", LIVERPOOL, SPURS, (2, 0), 19),
    _pl(602, "2030-01-05T14:00:00Z", "FINISHED", VILLA, team(65, "Manchester City FC", "Man City"), (1, 3), 19),
    _pl(507, "2030-01-11T12:30:00Z", "TIMED", NEWCASTLE, VILLA, None, 20),
    _pl(603, "2030-01-11T15:00:00Z", "TIMED", SPURS, ARSENAL, None, 20),
    _pl(604, "2030-01-12T16:30:00Z", "POSTPONED", LIVERPOOL, team(65, "Manchester City FC", "Man City"), None, 20))


def newcastle_replies():
    """The replies for the Premier League page on 2030-01-07."""
    return {"/competitions/PL/standings": PL_TABLE, "/competitions/PL/matches": PL_ROUNDS,
            "/teams/67/matches": matches(*NEWCASTLE_SEASON)}


# The other three leagues on Monday 2030-01-07, small but whole, so the evals can ask about any
# of the five (evals/__main__.py)
ATLETICO = team(78, "Club Atlético de Madrid", "Atlético")
SEVILLA = team(559, "Sevilla FC", "Sevilla")
PD_ROUNDS = matches(
    match(701, "2030-01-04T20:00:00Z", "FINISHED", REAL_MADRID, SEVILLA, (3, 1), 19, "PD", "Primera Division"),
    match(702, "2030-01-05T20:00:00Z", "FINISHED", BARCELONA, ATLETICO, (1, 1), 19, "PD", "Primera Division"),
    match(703, "2030-01-11T20:00:00Z", "TIMED", ATLETICO, REAL_MADRID, None, 20, "PD", "Primera Division"),
    match(704, "2030-01-12T20:00:00Z", "TIMED", SEVILLA, BARCELONA, None, 20, "PD", "Primera Division"))
DORTMUND = team(4, "Borussia Dortmund", "Dortmund")
LEVERKUSEN = team(3, "Bayer 04 Leverkusen", "Leverkusen")
BL1_TABLE = standings(row(1, BAYERN, 16, 12, 3, 1, 30, 39), row(2, LEVERKUSEN, 16, 11, 3, 2, 18, 36),
                      row(3, DORTMUND, 16, 9, 4, 3, 12, 31))
BL1_ROUNDS = matches(
    match(801, "2029-12-21T19:30:00Z", "FINISHED", DORTMUND, BAYERN, (1, 2), 16, "BL1", "Bundesliga"),
    match(802, "2030-01-11T14:30:00Z", "TIMED", BAYERN, LEVERKUSEN, None, 17, "BL1", "Bundesliga"))
PSG = team(524, "Paris Saint-Germain FC", "PSG")
MARSEILLE = team(516, "Olympique de Marseille", "Marseille")
FL1_TABLE = standings(row(1, PSG, 17, 13, 3, 1, 29, 42), row(2, MARSEILLE, 17, 10, 4, 3, 14, 34))
FL1_ROUNDS = matches(
    match(901, "2030-01-04T20:00:00Z", "FINISHED", MARSEILLE, PSG, (0, 0), 17, "FL1", "Ligue 1"),
    match(902, "2030-01-11T20:00:00Z", "TIMED", PSG, MARSEILLE, None, 18, "FL1", "Ligue 1"))

# Every football address answered, for the evals: Roma has no Champions League game here, so
# the CL table is there only to be complete
ALL_REPLIES = {
    **serie_a_replies(), **newcastle_replies(),
    "/competitions/PD/standings": PD_TABLE, "/competitions/PD/matches": PD_ROUNDS,
    "/competitions/BL1/standings": BL1_TABLE, "/competitions/BL1/matches": BL1_ROUNDS,
    "/competitions/FL1/standings": FL1_TABLE, "/competitions/FL1/matches": FL1_ROUNDS,
}


def canned_fetch(address: str) -> bytes:
    """The made-up reply for any football address, as outside._fetch would return it."""
    path = address.split("/v4", 1)[1].split("?", 1)[0]
    return json.dumps(ALL_REPLIES[path]).encode()
