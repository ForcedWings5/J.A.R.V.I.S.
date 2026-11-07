"""Football, for the Sports space: data from football-data.org's free plan.

Every request goes through the shared door (outside.py) with the key in its header. Replies are
outside data: every value is read through outside.num, text and obj, names are cleaned, and
everything the page or the model sees is worked out here, never by the model. JARVIS's tools
come in a later stage. Spec: docs/specs/2026-11-07-sports-space.md.
"""
import os
import re
from datetime import datetime

import config
import outside

_KEY_NAME = "FOOTBALL_DATA_KEY"
_KEY_SHAPE = re.compile(r"[A-Za-z0-9]{10,64}", re.ASCII)


def _from_env_file() -> str | None:
    """The last FOOTBALL_DATA_KEY line of .env, written in any of the usual ways
    (`NAME=value`, spaces round `=`, quotes, `export NAME=value`)."""
    try:
        text = config.ENV_FILE.read_text(encoding="utf-8-sig")   # some editors add a mark at the start
    except (OSError, UnicodeDecodeError):     # no file, a folder, unreadable, not UTF-8
        return None
    found = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^export\s+", "", line)
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


# ---------- asking football-data.org ----------

# What each kind of failure says, on the page and to JARVIS (spec, exact wording)
MESSAGES = {
    "no_key": "Football needs a free key from football-data.org: see README",
    "refused": "The football data key was refused. Check it in .env.",
    "busy": "Too many requests just now. Try again in a minute.",
    "unreachable": "Couldn't reach the football data.",
}


class FootballError(Exception):
    """A football request failed. `kind` is one of MESSAGES, and the message is safe to show."""

    def __init__(self, kind: str):
        super().__init__(MESSAGES[kind])
        self.kind = kind


_ZONE = None        # the time zone kick-offs are shown in: None is the Mac's own (tests set one)


def _now() -> datetime:
    """Local time now. Its own function, so tests can freeze it."""
    return datetime.now()


def _get(address: str, params: dict) -> dict:
    """Ask one of the fixed football addresses, with the key in the header. No key: nothing
    is sent. The OutsideError's cause is dropped (`from None`): its kind says all there is."""
    key = _key()
    if key is None:
        raise FootballError("no_key")
    try:
        return outside.get(address, params, headers={"X-Auth-Token": key})
    except outside.OutsideError as e:
        raise FootballError(e.kind) from None


# ---------- reading replies ----------

_STATUS = {
    "IN_PLAY": "live", "PAUSED": "live", "EXTRA_TIME": "live", "PENALTY_SHOOTOUT": "live",
    "SCHEDULED": "upcoming", "TIMED": "upcoming",
    "FINISHED": "finished", "AWARDED": "finished",
    "POSTPONED": "postponed", "SUSPENDED": "suspended", "CANCELLED": "cancelled",
}
# English names, not the Mac's language settings, so what JARVIS says never changes with them
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December")
_UTC_STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d)?Z")


def _int(x) -> int | None:
    n = outside.num(x)
    return n if isinstance(n, int) else None


def _local(utc) -> datetime | None:
    """'2030-01-12T19:45:00Z' (UTC) -> naive local time, or None if it is not such a stamp."""
    stamp = outside.text(utc)
    if not _UTC_STAMP.fullmatch(stamp):
        return None
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return moment.astimezone(_ZONE).replace(tzinfo=None)


def _team(t) -> dict | None:
    t = outside.obj(t)
    team_id = _int(t.get("id"))
    name = outside.clean(outside.text(t.get("shortName")) or outside.text(t.get("name")),
                         config.FOOTBALL_NAME_MAX)
    return {"id": team_id, "name": name} if team_id is not None and name else None


def _match(m) -> dict | None:
    """One match as plain values, or None when what it needs is missing or unknown."""
    m = outside.obj(m)
    at = _local(m.get("utcDate"))
    status = _STATUS.get(outside.text(m.get("status")))
    home, away = _team(m.get("homeTeam")), _team(m.get("awayTeam"))
    match_id = _int(m.get("id"))
    if at is None or status is None or home is None or away is None or match_id is None:
        return None
    score = None
    if status in ("finished", "live"):
        full = outside.obj(outside.obj(m.get("score")).get("fullTime"))
        goals = _int(full.get("home")), _int(full.get("away"))
        if None not in goals:
            score = {"home": goals[0], "away": goals[1]}
    competition = outside.obj(m.get("competition"))
    return {
        "id": match_id,
        "date": at.strftime("%Y-%m-%d"),
        "time": at.strftime("%H:%M"),
        "day": f"{_WEEKDAYS[at.weekday()]} {at.day} {_MONTHS[at.month - 1]}",
        "competition": outside.clean(outside.text(competition.get("name")), config.FOOTBALL_NAME_MAX),
        "code": outside.clean(outside.text(competition.get("code")), 5),
        "matchday": _int(m.get("matchday")),
        "status": status,
        "home": home,
        "away": away,
        "score": score,
    }


def _table(reply) -> list[dict]:
    """The TOTAL standing's rows. A row without a position, team or points is left out."""
    standings = outside.obj(reply).get("standings")
    if not isinstance(standings, list):
        return []
    total = next((outside.obj(s) for s in standings if outside.obj(s).get("type") == "TOTAL"), {})
    rows = total.get("table")
    if not isinstance(rows, list):
        return []
    table = []
    for r in rows:
        r = outside.obj(r)
        position, team, points = _int(r.get("position")), _team(r.get("team")), _int(r.get("points"))
        if position is None or team is None or points is None:
            continue
        table.append({"position": position, "team": team, "played": _int(r.get("playedGames")),
                      "won": _int(r.get("won")), "drawn": _int(r.get("draw")),
                      "lost": _int(r.get("lost")), "goal_difference": _int(r.get("goalDifference")),
                      "points": points})
    return table


def ordinal(n: int) -> str:
    """3 -> '3rd', 11 -> '11th', 21 -> '21st'."""
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"
