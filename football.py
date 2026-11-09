"""Football, for the Sports space: data from football-data.org's free plan.

Every request goes through the shared door (outside.py) with the key in its header. Replies are
outside data: every value is read through outside.num, text and obj, names are cleaned, and
everything the page or the model sees is worked out here, never by the model. JARVIS's tools
come last: the model picks a league or a team from fixed names, and hears facts written here.
Spec: docs/specs/2026-11-07-sports-space.md.
"""
import os
import re
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from time import monotonic   # its own name, so tests can move the cache's clock

import config
import outside
from tools import ShowLeague, tool

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
        return datetime.fromisoformat(stamp).astimezone(_ZONE).replace(tzinfo=None)
    except (ValueError, OverflowError):    # not a date, or one at the calendar's edge
        return None


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


# ---------- the summaries, worked out in code (pure: they only read what they are given) ----------

_PENDING = ("upcoming", "live", "postponed", "suspended")


def _when(m: dict) -> tuple[str, str]:
    return m["date"], m["time"]


def _real_rounds(matches: list[dict]) -> set[int]:
    """The matchdays with at least FOOTBALL_ROUND_MIN_MATCHES of these matches, or all of them
    if none has that many (the start of a season). A game postponed, rescheduled or brought
    forward is usually one or two of its round, so it cannot take a round's place (final
    review, stage 2)."""
    counts: dict[int, int] = {}
    for m in matches:
        counts[m["matchday"]] = counts.get(m["matchday"], 0) + 1
    real = {day for day, n in counts.items() if n >= config.FOOTBALL_ROUND_MIN_MATCHES}
    return real or set(counts)


def latest_round(matches: list[dict]) -> dict:
    """The finished matches of the highest real round that has any, in kick-off order."""
    done = [m for m in matches if m and m["status"] == "finished" and m["matchday"] is not None]
    if not done:
        return {"matchday": None, "matches": []}
    day = max(_real_rounds(done))
    return {"matchday": day, "matches": sorted((m for m in done if m["matchday"] == day), key=_when)}


def next_round(matches: list[dict]) -> dict:
    """The lowest real round with matches to play (upcoming or live), in kick-off order, with
    that round's postponed and suspended games too, so they show as such."""
    ms = [m for m in matches if m and m["matchday"] is not None]
    to_play = [m for m in ms if m["status"] in ("upcoming", "live")]
    if not to_play:
        return {"matchday": None, "matches": []}
    day = min(_real_rounds(to_play))
    return {"matchday": day, "matches": sorted(
        (m for m in ms if m["matchday"] == day and m["status"] in _PENDING), key=_when)}


def result_for(match: dict, team_id: int) -> str | None:
    """W, D or L from the team's side, for a finished match with a score; otherwise None."""
    score = match.get("score")
    if match.get("status") != "finished" or not score:
        return None
    if match["home"]["id"] == team_id:
        ours, theirs = score["home"], score["away"]
    elif match["away"]["id"] == team_id:
        ours, theirs = score["away"], score["home"]
    else:
        return None
    return "W" if ours > theirs else "D" if ours == theirs else "L"


def team_block(slug: str, table: list[dict], team_matches: list[dict],
               cl_table: list[dict] | None) -> dict:
    """What a themed page shows for the followed team. Missing data gives None or empty
    lists, never a guess: a team not in the table has no position."""
    team = config.FOOTBALL_TEAMS[slug]
    ms = sorted((m for m in team_matches if m), key=_when)
    row = next((r for r in table if r["team"]["id"] == team["id"]), None)
    results = [{"result": result_for(m, team["id"]), "match": m} for m in ms]
    form = [r for r in results if r["result"]][-5:]
    live = [m for m in ms if m["status"] == "live"]
    coming = [m for m in ms if m["status"] in ("live", "upcoming")][:5]
    upcoming = [m for m in ms if m["status"] == "upcoming"]
    return {
        "slug": slug,
        "name": team["name"],
        "id": team["id"],
        "position": row["position"] if row else None,
        "position_words": ordinal(row["position"]) if row else None,
        "points": row["points"] if row else None,
        "next": live[0] if live else upcoming[0] if upcoming else None,
        "form": form,
        "recent": list(reversed(form)),
        "coming": coming,
        "champions_league": cl_table,
        "cup_note": team["cup_note"],
    }


def season_started(table: list[dict]) -> bool:
    return any((r["played"] or 0) > 0 for r in table)


# ---------- the cache, the earlier copy, and the league page ----------

CREDIT = "Football data provided by the Football-Data.org API"
_LIVE_STATUSES = {"IN_PLAY", "PAUSED", "EXTRA_TIME", "PENALTY_SHOOTOUT"}

# All in memory, never in jarvis.db. _fresh: (address, params) -> (expires, fetched_at, reply),
# kept 10 minutes (2 while a match is live). _earlier: address -> the same, kept 6 hours, shown
# when the service fails. By address alone, so it survives the date window moving at midnight.
_fresh: OrderedDict = OrderedDict()
_earlier: OrderedDict = OrderedDict()
_lock = threading.Lock()


def forget_everything() -> None:
    """For the tests: nothing kept from another test."""
    with _lock:
        _fresh.clear()
        _earlier.clear()


def _keep(store: OrderedDict, key, expires: float, fetched: datetime, reply: dict) -> None:
    """Store, dropping expired entries first, then the oldest beyond the cap."""
    now = monotonic()
    for old in [k for k, (until, _, _) in store.items() if until <= now]:
        del store[old]
    store[key] = (expires, fetched, reply)
    store.move_to_end(key)
    while len(store) > config.FOOTBALL_CACHE_ENTRIES:
        store.popitem(last=False)


def _is_live(reply: dict) -> bool:
    games = outside.obj(reply).get("matches")
    return isinstance(games, list) and any(
        outside.text(outside.obj(g).get("status")) in _LIVE_STATUSES for g in games)


def _fetched(address: str, params: dict) -> tuple[dict, datetime, bool]:
    """A reply, when it was fetched, and whether it is an earlier copy standing in for a
    failed request. A missing or refused key never falls back to an earlier copy: the owner
    must see that problem. Failures are not kept, so the next look asks again."""
    key = (address, tuple(sorted(params.items())))
    with _lock:
        hit = _fresh.get(key)
        if hit and hit[0] > monotonic():
            return hit[2], hit[1], False
    try:
        reply = _get(address, params)          # outside the lock: this may wait on the network
    except FootballError as e:
        if e.kind in ("busy", "unreachable"):
            with _lock:
                old = _earlier.get(address)
                if old and old[0] > monotonic():
                    return old[2], old[1], True
        raise
    fetched, now = _now(), monotonic()
    keep = config.FOOTBALL_LIVE_CACHE_SECONDS if _is_live(reply) else config.FOOTBALL_CACHE_SECONDS
    with _lock:
        _keep(_fresh, key, now + keep, fetched, reply)
        _keep(_earlier, address, now + config.FOOTBALL_EARLIER_COPY_SECONDS, fetched, reply)
    return reply, fetched, False


def _matches_in(reply) -> list[dict]:
    games = outside.obj(reply).get("matches")
    return [m for m in map(_match, games if isinstance(games, list) else []) if m]


def league_page(slug: str) -> dict:
    """Everything a league page shows. A general league costs 2 requests; a themed one 3, or 4
    when the team has Champions League games in its window."""
    league = config.FOOTBALL_LEAGUES.get(slug)
    if league is None:
        raise ValueError(f"not a league: {slug}")
    today = _now().date()
    used = []                                   # (fetched_at, earlier) for each reply

    def ask(address: str, params: dict | None = None) -> dict:
        reply, fetched, earlier = _fetched(address, params or {})
        used.append((fetched, earlier))
        return reply

    def window(days: int) -> dict:
        return {"dateFrom": (today - timedelta(days=days)).isoformat(),
                "dateTo": (today + timedelta(days=days)).isoformat()}

    api, code = config.FOOTBALL_API, league["code"]
    table = _table(ask(f"{api}/competitions/{code}/standings"))
    games = _matches_in(ask(f"{api}/competitions/{code}/matches", window(config.FOOTBALL_WINDOW_DAYS)))
    team = None
    followed = next((s for s, t in config.FOOTBALL_TEAMS.items() if t["league"] == slug), None)
    if followed:
        team_id = config.FOOTBALL_TEAMS[followed]["id"]
        team_games = _matches_in(ask(f"{api}/teams/{team_id}/matches",
                                     window(config.FOOTBALL_TEAM_WINDOW_DAYS)))
        cl = None
        if any(m["code"] == "CL" for m in team_games):
            cl = _table(ask(f"{api}/competitions/CL/standings"))
        team = team_block(followed, table, team_games, cl)
    earlier = [fetched for fetched, was_earlier in used if was_earlier]
    return {
        "league": {"slug": slug, "name": league["name"], "country": league["country"]},
        "season_started": season_started(table),
        "table": table,
        "results": latest_round(games),
        "upcoming": next_round(games),
        "team": team,
        "updated": min(fetched for fetched, _ in used).strftime("%Y-%m-%dT%H:%M"),
        "earlier": min(earlier).strftime("%H:%M") if earlier else None,
        "credit": CREDIT,
    }


# ---------- JARVIS's tools: the model names a league or a team; code writes the facts ----------

# What each kind of failure tells the model (spec, exact wording)
TOOL_MESSAGES = {
    "no_key": "Error: football needs a free key. The owner can add one (README).",
    "refused": "Error: the football data key was refused.",
    "busy": "Error: too many football requests just now. Try again in a minute.",
    "unreachable": "Error: couldn't reach the football data.",
}
_RESULT_WORDS = {"W": "a win", "D": "a draw", "L": "a loss"}
_WITH_THE = {"premier-league", "bundesliga"}    # "in the Premier League", but "in Serie A"
_FORM_WORDS = {"W": "won", "D": "drew", "L": "lost"}


def league_name(slug: str) -> str:
    """The league's name as said in a sentence: 'the Premier League', 'Serie A'."""
    name = config.FOOTBALL_LEAGUES[slug]["name"]
    return f"the {name}" if slug in _WITH_THE else name


def _slug(value) -> str:
    """' Serie A ' -> 'serie-a': the shape every slug has, so a name works as well as a slug."""
    return re.sub(r"[\s_]+", "-", str(value).strip().lower())


def league_slug(value) -> str | None:
    slug = _slug(value)
    return slug if slug in config.FOOTBALL_LEAGUES else None


def team_slug(value) -> str | None:
    slug = _slug(value)
    return slug if slug in config.FOOTBALL_TEAMS else None


def _score(m: dict) -> str:
    """'Inter 2 Roma 1', or 'Inter v Roma' when there is no score."""
    if m["score"] is None:
        return f"{m['home']['name']} v {m['away']['name']}"
    return f"{m['home']['name']} {m['score']['home']} {m['away']['name']} {m['score']['away']}"


def _coming(m: dict) -> str:
    """A match still to be played, or being played, in a round."""
    if m["status"] == "live":
        return f"{_score(m)}, live now (free scores arrive late)"
    fixture = f"{m['home']['name']} v {m['away']['name']} on {m['day']}"
    return f"{fixture} at {m['time']}" if m["status"] == "upcoming" else f"{fixture}, {m['status']}"


def _as_of(page: dict) -> str:
    """An earlier copy can be up to 6 hours old, so after midnight it names the day. `updated`
    is the oldest reply used, which is the earlier copy (as the page reads it)."""
    if not page["earlier"]:
        return ""
    day, today = page["updated"][:10], _now().date()
    when = page["earlier"]
    if day == (today - timedelta(days=1)).isoformat():
        when = f"yesterday at {when}"
    elif day != today.isoformat():
        when = f"{day} at {when}"
    return f"As of {when} (an earlier copy: fresh data couldn't be fetched just now). "


def league_facts(page: dict) -> str:
    """What JARVIS is told about a league: written from league_page's values, nothing else."""
    name, table, team = page["league"]["name"], page["table"], page["team"]
    parts = []
    if not page["season_started"] or not table:
        parts.append(f"The {name} season hasn't started.")
    else:
        top = ", ".join(f"{ordinal(r['position'])} {r['team']['name']} {r['points']} points"
                        for r in table[:config.FOOTBALL_TOP_ROWS])
        parts.append(f"{name} table: {top}.")
        if team and team["position"] is not None:
            parts.append(f"{team['name']} are {team['position_words']} with {team['points']} points.")
    days = config.FOOTBALL_WINDOW_DAYS
    results, upcoming = page["results"], page["upcoming"]
    if results["matches"]:
        parts.append(f"Latest results, round {results['matchday']}: "
                     + "; ".join(f"{_score(m)} on {m['day']}" for m in results["matches"]) + ".")
    else:
        parts.append(f"No results in the last {days} days.")
    if upcoming["matches"]:
        parts.append(f"Next round, {upcoming['matchday']}: "
                     + "; ".join(_coming(m) for m in upcoming["matches"]) + ".")
    else:
        parts.append(f"No matches in the next {days} days.")
    return _as_of(page) + " ".join(parts)


def team_facts(page: dict, team: str) -> str:
    """What JARVIS is told about a followed team, from its league's page."""
    block = page["team"]
    if not block or block["slug"] != team:
        raise ValueError(f"{team} is not followed in {page['league']['slug']}")
    name = block["name"]
    parts = []
    if block["position"] is not None:
        parts.append(f"{name} are {block['position_words']} in {league_name(page['league']['slug'])} with "
                     f"{block['points']} points.")
    else:
        parts.append(f"{name}'s league position isn't in the data.")
    if block["recent"]:
        last = block["recent"][0]
        m = last["match"]
        parts.append(f"Last result: {_score(m)}, {_RESULT_WORDS[last['result']]}, on {m['day']} "
                     f"({m['competition']}).")
    else:
        parts.append("No recent result in the data.")
    m = block["next"]
    if m is None:
        parts.append("No match scheduled yet.")
    elif m["status"] == "live":
        parts.append(f"Playing now: {_score(m)} ({m['competition']}, live; free scores arrive late).")
    else:
        where = "at home" if m["home"]["id"] == block["id"] else "away"
        parts.append(f"Next: {m['home']['name']} v {m['away']['name']}, {m['day']} at {m['time']}, "
                     f"{m['competition']}, {where}.")
    if block["form"]:
        words = ", ".join(_FORM_WORDS[r["result"]] for r in block["form"])
        parts.append(f"Form in their last {len(block['form'])}, oldest first: {words}.")
    cl = next((r for r in block["champions_league"] or [] if r["team"]["id"] == block["id"]), None)
    if cl:
        parts.append(f"In the Champions League they are {ordinal(cl['position'])} with "
                     f"{cl['points']} points.")
    parts.append(block["cup_note"] + ".")
    return _as_of(page) + " ".join(parts)


def _no_league(value) -> str:
    names = ", ".join(lg["name"] for lg in config.FOOTBALL_LEAGUES.values())
    return f"Error: no league called '{outside.clean(str(value), config.FOOTBALL_NAME_MAX)}'. Leagues: {names}."


_LEAGUE_ARG = {"type": "string", "enum": list(config.FOOTBALL_LEAGUES),
               "description": "premier-league, serie-a, la-liga, bundesliga or ligue-1"}


@tool("Show one of the five football leagues on screen, with its table, results and fixtures, "
      "after a short animation. Call it only when the user asks to see, show or open a league, "
      "such as 'show me Serie A'. It opens the Sports space itself, so do not also call "
      "open_space. If the user asks to see a league again, call it again: they may have left it. "
      "For questions about a league, use get_league instead.",
      league=_LEAGUE_ARG)
def show_league(league: str) -> ShowLeague | str:
    slug = league_slug(league)
    if slug is None:
        return _no_league(league)
    return ShowLeague(slug, f"Opened {league_name(slug)} on the screen. "
                            "The user can leave it at any time, so it may not be on screen the "
                            "next time they ask.")


@tool("Facts about one of the five football leagues from today's data: the top 4 with points, "
      "the followed team's place, the latest round's results and the next round's fixtures. "
      "Call it for questions such as 'who's top of La Liga?', and for teams other than Roma and "
      "Newcastle. Use only what it returns.",
      league=_LEAGUE_ARG)
def get_league(league: str) -> str:
    slug = league_slug(league)
    if slug is None:
        return _no_league(league)
    try:
        return league_facts(league_page(slug))
    except FootballError as e:
        return TOOL_MESSAGES[e.kind]


@tool("Facts about Roma or Newcastle from today's data: league position and points, the last "
      "result, the next match, recent form and any Champions League place. Call it for questions "
      "about either team, such as 'when do Roma play next?'. Use only what it returns.",
      team={"type": "string", "enum": list(config.FOOTBALL_TEAMS),
            "description": "roma or newcastle"})
def get_team(team: str) -> str:
    slug = team_slug(team)
    if slug is None:
        names = " and ".join(t["name"] for t in config.FOOTBALL_TEAMS.values())
        return f"Error: JARVIS follows only {names}."
    try:
        return team_facts(league_page(config.FOOTBALL_TEAMS[slug]["league"]), slug)
    except FootballError as e:
        return TOOL_MESSAGES[e.kind]
