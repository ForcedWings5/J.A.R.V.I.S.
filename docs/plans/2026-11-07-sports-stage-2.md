# Sports, stage 2: the football server — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `POST /sports/league` returns a finished league page (table, latest results, upcoming,
and for Serie A and the Premier League the Roma or Newcastle block), built in code from
football-data.org through the shared door, cached, and safe with any reply.

**Architecture:** `football.py` grows from `_key()` into the whole football server: `_get`
(the key header, through `outside.get`; failures become `FootballError(kind)`), a two-level
cache (fresh for 10 minutes or 2 while live; an earlier copy kept 6 hours for when the service
fails), safe readers for matches and table rows, summaries worked out in code, and
`league_page(slug)`. The safe readers Weather uses move into `outside.py`, which already owns
everything that comes from the internet; Weather keeps its names for them. `server.py` adds
one endpoint. Tests use made-up replies in `tests/football_data.py`. A live check with the
owner's key confirms the team ids and the reply shape. The stage also closes the five
follow-ups from the stage 1 review (CHANGELOG section 59).

**Tech Stack:** Python 3.13 standard library (`datetime`, `zoneinfo` in tests), FastAPI,
pytest. No new dependency. No prompt or tool change (no eval).

**Spec:** `docs/specs/2026-11-07-sports-space.md` (sections "The league pages", "Settings",
"The key", "Reading replies, and worked out in code", "Requests, the cache and the earlier
copy", "Endpoint", "When something goes wrong", "Testing", "Build order" stage 2).

## Global Constraints

- Branch `sports-stage-2` from `main` (`2c661a3`). Commit after each task. Never on `main`. Do
  not push.
- Every request goes through `outside.get`; the key goes only into the `X-Auth-Token` header of
  a football address. Never into a log line, an error, a reply to the page, or a tool result.
- Settings (spec, verbatim values): `FOOTBALL_CACHE_SECONDS = 600`,
  `FOOTBALL_LIVE_CACHE_SECONDS = 120`, `FOOTBALL_EARLIER_COPY_SECONDS = 21_600`,
  `FOOTBALL_CACHE_ENTRIES = 30`, `FOOTBALL_NAME_MAX = 40`, `FOOTBALL_WINDOW_DAYS = 10`,
  `FOOTBALL_TEAM_WINDOW_DAYS = 60`.
- Statuses (spec): live = `IN_PLAY`, `PAUSED`, `EXTRA_TIME`, `PENALTY_SHOOTOUT`; upcoming =
  `SCHEDULED`, `TIMED`; finished = `FINISHED`, `AWARDED`; shown as such = `POSTPONED`,
  `SUSPENDED`, `CANCELLED`. Any other status: the match is left out.
- Messages (spec, exact): no key "Football needs a free key from football-data.org: see
  README" (503); refused "The football data key was refused. Check it in .env." (502); busy "Too
  many requests just now. Try again in a minute." (429); unreachable "Couldn't reach the
  football data." (502).
- Credit line, exact: "Football data provided by the Football-Data.org API".
- Times are the Mac's local time, worked out in code from the reply's UTC. Datetimes are naive
  local time once converted (CLAUDE.md).
- Weather's behaviour, messages and tests stay unchanged.
- A general page costs 2 requests; a themed page 3, or 4 when the team has Champions League
  matches in its window.

## Review Focus

1. **A reply with odd values** (a score of `"two"`, a `null` team, a name with control
   characters or 300 characters, an unknown status, a date that is not a date) must leave that
   value or match out, never crash or reach the page raw. Pinned by
   `test_odd_matches_are_left_out_or_cleaned` and `test_odd_table_rows_never_crash` (Task 2).
2. **The service failing after a good fetch**: the page must use the earlier copy, labelled
   with its time, for up to 6 hours, and then fail with the plain message. Pinned by
   `test_an_earlier_copy_is_used_when_the_service_fails` (Task 4).
3. **Midnight and the clock change**: kick-off times converted across the end of summer time
   must be right, and a 23:30 UTC match must land on the next local day where the zone is
   ahead. Pinned by `test_times_are_local_across_the_clock_change` (Task 2).
4. **The followed team not in the reply's table** (a new season, a reply cut short) must give
   a team block with no position, not a crash. Pinned by
   `test_a_team_missing_from_the_table_has_no_position` (Task 3).
5. **The key leaking through a failure path** (403, 429, timeout): the endpoint's `detail`, the
   log and the earlier-copy label must not hold it. Pinned by
   `test_the_key_appears_only_in_the_header` (Task 5).

---

### Task 1: The stage 1 follow-ups

**Files:**
- Modify: `outside.py` (headers only to football; the safe readers move in), `weather.py`
  (imports them, keeps its names), `football.py` (`.env` read as `utf-8-sig`, `export` then any
  space), `evals/__main__.py` (top: `JARVIS_ENV`, no shell key)
- Test: `tests/test_outside.py`, `tests/test_football.py`, `tests/test_evals.py`

**Interfaces:**
- Produces, in `outside.py`: `num(x) -> int | float | None`, `text(x) -> str`,
  `obj(x) -> dict`, `clean(text: str | None, limit: int) -> str` (moved from `weather.py`
  unchanged, except `clean`'s `limit` has no default). `weather.py` keeps `_num`, `_text`,
  `_obj` (imported under those names) and `clean(text, limit=config.WEATHER_NAME_MAX)` as a
  one-line wrapper, so its code and tests do not change.
- `outside.get` raises `ValueError` before sending when `headers` is not empty and the address's
  host is not `api.football-data.org`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_outside.py
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

def test_the_readers_are_shared_with_weather():
    assert weather._num is outside.num and weather._text is outside.text and weather._obj is outside.obj
    assert outside.clean("a‮b  c\x00", 3) == "ab"

# tests/test_football.py
@pytest.mark.parametrize("raw", [("﻿" + f"FOOTBALL_DATA_KEY={KEY}").encode(),
                                 f"export\tFOOTBALL_DATA_KEY={KEY}".encode()])
def test_a_byte_order_mark_and_a_tab_after_export_work(tmp_path, monkeypatch, raw):
    path = tmp_path / ".env"
    path.write_bytes(raw)
    monkeypatch.setattr(config, "ENV_FILE", path)
    assert football._key() == KEY

# tests/test_evals.py
def test_the_eval_runner_never_reads_the_real_env_file():
    source = (Path(__file__).parent.parent / "evals" / "__main__.py").read_text()
    first_import = source.index("\nimport argparse")
    assert source.index('os.environ["JARVIS_ENV"] = os.devnull') < first_import
    assert source.index('os.environ.pop("FOOTBALL_DATA_KEY", None)') < first_import
```

- [ ] **Step 2: Run them to see them fail**

Run: `source .venv/bin/activate && python -m pytest -q tests/test_outside.py tests/test_football.py tests/test_evals.py`
Expected: FAIL: `test_headers_go_only_to_football_data` (no ValueError), the readers test
(`AttributeError: num`), the byte-order-mark and tab cases, the eval runner test. The 60-second
edge test passes (it pins today's correct behaviour). Prove it can fail: change `<=` to `<` in
`outside._admit` for one run (the `60.0` case is then refused, so it fails), then restore the
file and confirm `git diff --quiet outside.py`.

- [ ] **Step 3: Implement**

- `outside.py`: the header rule in `get`, before the guard (comment: so the key can only ever
  go to football-data.org); the four readers moved from `weather.py` with their comments.
- `weather.py`: `from outside import num as _num, obj as _obj, text as _text`; `clean` becomes
  the wrapper; remove the moved bodies and any import ruff then reports unused (`math`,
  `unicodedata`).
- `football.py`: `read_text(encoding="utf-8-sig")`; strip a leading `export` followed by any
  whitespace (`re.sub(r"^export\s+", "", line)`).
- `evals/__main__.py`: after `os.environ["JARVIS_DB"] = ":memory:"`, the same two lines as
  `tests/conftest.py`, with its comment.

- [ ] **Step 4: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass (728 before this task, plus the new ones); `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
git add outside.py weather.py football.py evals/__main__.py tests/test_outside.py tests/test_football.py tests/test_evals.py
git commit -m "Sports stage 2: the follow-ups from the stage 1 review"
```

---

### Task 2: Asking football-data.org, and reading its replies

**Files:**
- Create: `tests/football_data.py`
- Modify: `config.py` (the settings in Global Constraints), `football.py`
- Test: `tests/test_football.py`

**Interfaces:**
- Consumes: `outside.get`, `outside.OutsideError`, `outside.num/text/obj/clean`, `football._key`.
- Produces, in `football.py`:
  - `class FootballError(Exception)` with `.kind` in `{"no_key", "refused", "busy",
    "unreachable"}`; `str(e)` is `MESSAGES[kind]`, the spec's exact messages.
  - `_now() -> datetime` (naive local; tests replace it); `_ZONE` (`None` = the Mac's zone;
    tests set a `ZoneInfo`).
  - `_get(address: str, params: dict) -> dict`: no key → `FootballError("no_key")` without
    sending; else `outside.get(address, params, headers={"X-Auth-Token": key})`, with an
    `OutsideError` turned into `FootballError` of the same kind.
  - `_match(m) -> dict | None`: `{"id": int, "date": "YYYY-MM-DD", "time": "HH:MM", "day":
    "Sunday 9 November", "competition": str, "code": str, "matchday": int | None, "status":
    "upcoming" | "live" | "finished" | "postponed" | "suspended" | "cancelled", "home": {"id":
    int, "name": str}, "away": {...}, "score": {"home": int, "away": int} | None}`. Team name:
    `shortName`, else `name`, cleaned to 40. `None` when the date, a team id or name, or the
    status is missing or unknown.
  - `_table(reply) -> list[dict]`: the `TOTAL` standing's rows as `{"position": int, "team":
    {"id", "name"}, "played", "won", "drawn", "lost", "goal_difference", "points"}` (numbers or
    `None`); a row without a position, team id, name or points is left out.
  - `ordinal(n: int) -> str`: `"1st"`, `"2nd"`, `"3rd"`, `"4th"`, `"11th"`, `"12th"`,
    `"13th"`, `"21st"`, `"22nd"`, `"23rd"`, `"101st"`, `"111th"`.
- Produces, in `tests/football_data.py`: `team(id, name, short=None) -> dict`,
  `match(id, utc, status, home, away, score=None, matchday=None, code="SA", name="Serie A") ->
  dict`, `matches(*ms) -> dict` (`{"matches": [...]}`), `row(position, team, played, won,
  draw, lost, gd, points) -> dict`, `standings(*rows) -> dict` (a `TOTAL` standing),
  `ROMA = team(100, "AS Roma", "Roma")`, `NEWCASTLE = team(67, "Newcastle United FC",
  "Newcastle")`, and other teams as needed; `serve(monkeypatch, replies: dict[str, object])
  -> Served`: answers `outside._fetch` by the part of the address after `/v4` (for example
  `"/competitions/SA/standings"`), recording `(address, headers)` in `served.calls`; a dict
  becomes JSON, an exception is raised, an unprepared address fails the test.

- [ ] **Step 1: Write the failing tests** in `tests/test_football.py`

`tests/football_data.py` gets `KEY = "abcdef0123456789"` and `freeze(monkeypatch)`: sets
`football._now` to Monday 2030-01-07 08:00 (conftest's clock), `football._ZONE` to
`ZoneInfo("Europe/London")`, and `FOOTBALL_DATA_KEY` to `KEY`. Both test files use it.

```python
@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    data.freeze(monkeypatch)

STANDINGS = config.FOOTBALL_API + "/competitions/SA/standings"

def test_no_key_means_no_request(monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_KEY")
    served = data.serve(monkeypatch, {})
    with pytest.raises(football.FootballError) as caught:
        football._get(STANDINGS, {})
    assert caught.value.kind == "no_key" and served.calls == []
    assert str(caught.value) == "Football needs a free key from football-data.org: see README"

def test_the_key_goes_in_the_header(monkeypatch):
    served = data.serve(monkeypatch, {"/competitions/SA/standings": data.standings()})
    football._get(STANDINGS, {})
    assert served.calls == [(STANDINGS, {"X-Auth-Token": KEY})]

@pytest.mark.parametrize("code, kind, message", [
    (403, "refused", "The football data key was refused. Check it in .env."),
    (429, "busy", "Too many requests just now. Try again in a minute."),
    (500, "unreachable", "Couldn't reach the football data.")])
def test_failures_keep_their_kind(monkeypatch, code, kind, message):
    data.serve(monkeypatch, {"/competitions/SA/standings":
                             urllib.error.HTTPError(STANDINGS, code, "x", {}, None)})
    with pytest.raises(football.FootballError) as caught:
        football._get(STANDINGS, {})
    assert caught.value.kind == kind and str(caught.value) == message

def test_a_match_is_read_into_plain_values():
    m = football._match(data.match(1, "2030-01-12T19:45:00Z", "TIMED", data.ROMA,
                                   data.LAZIO, matchday=20))
    assert m == {"id": 1, "date": "2030-01-12", "time": "19:45", "day": "Saturday 12 January",
                 "competition": "Serie A", "code": "SA", "matchday": 20, "status": "upcoming",
                 "home": {"id": 100, "name": "Roma"}, "away": {"id": 110, "name": "Lazio"},
                 "score": None}

@pytest.mark.parametrize("status, word", [("IN_PLAY", "live"), ("PAUSED", "live"),
    ("EXTRA_TIME", "live"), ("PENALTY_SHOOTOUT", "live"), ("SCHEDULED", "upcoming"),
    ("FINISHED", "finished"), ("AWARDED", "finished"), ("POSTPONED", "postponed"),
    ("SUSPENDED", "suspended"), ("CANCELLED", "cancelled")])
def test_every_status_has_a_word(status, word):
    m = data.match(1, "2030-01-12T19:45:00Z", status, data.ROMA, data.LAZIO, score=(1, 0))
    assert football._match(m)["status"] == word

def test_times_are_local_across_the_clock_change():
    at = lambda utc: football._match(data.match(1, utc, "TIMED", data.ROMA, data.LAZIO))
    assert (at("2030-10-26T13:00:00Z")["time"], at("2030-10-27T13:00:00Z")["time"]) == ("14:00", "13:00")
    football._ZONE = ZoneInfo("Europe/Rome")         # the fixture puts it back
    late = at("2030-01-12T23:30:00Z")
    assert (late["date"], late["time"], late["day"]) == ("2030-01-13", "00:30", "Sunday 13 January")

@pytest.mark.parametrize("change", [
    {"utcDate": "soon"}, {"utcDate": None}, {"status": "ON_FIRE"}, {"homeTeam": None},
    {"awayTeam": {"id": "x", "name": "Lazio"}}, {"score": {"fullTime": {"home": "two", "away": 1}}}])
def test_odd_matches_are_left_out_or_cleaned(change):
    m = dict(data.match(1, "2030-01-12T19:45:00Z", "FINISHED", data.ROMA, data.LAZIO, score=(2, 1)), **change)
    read = football._match(m)
    assert read is None or read["score"] is None
    named = football._match(data.match(1, "2030-01-12T19:45:00Z", "TIMED",
                                       data.team(5, "Evil‮\x00" + "x" * 300), data.LAZIO))
    assert named["home"]["name"].startswith("Evil") and len(named["home"]["name"]) <= 40
    assert "‮" not in named["home"]["name"] and "\x00" not in named["home"]["name"]

def test_odd_table_rows_never_crash():
    reply = data.standings(data.row(1, data.ROMA, 19, 12, 4, 3, 20, 40))
    reply["standings"][0]["table"] += [None, {"position": "first"}, {"team": {"id": 1}},
                                       data.row(3, data.LAZIO, "x", 1, 1, 1, 0, 30)]
    rows = football._table(reply)
    assert [r["team"]["name"] for r in rows] == ["Roma", "Lazio"] and rows[1]["played"] is None
    assert football._table({"standings": "nope"}) == [] and football._table({}) == []

@pytest.mark.parametrize("n, word", [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"),
    (12, "12th"), (13, "13th"), (21, "21st"), (22, "22nd"), (23, "23rd"), (101, "101st"), (111, "111th")])
def test_positions_in_words(n, word):
    assert football.ordinal(n) == word
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest -q tests/test_football.py`
Expected: FAIL at collection (`ModuleNotFoundError: football_data`), then, once the data file
exists, on `AttributeError` for `FootballError`, `_get`, `_match`, `_table`, `ordinal`.

- [ ] **Step 3: Implement**

- `config.py`: the seven settings in Global Constraints, under the Football block, each with a
  short why.
- `tests/football_data.py`: the builders and `serve` from the Interfaces block. Shapes follow
  football-data.org's v4 docs (read 2026-11-07): a match has `id`, `utcDate`, `status`,
  `matchday`, `competition {id, name, code}`, `homeTeam`/`awayTeam {id, name, shortName,
  tla}`, `score {fullTime {home, away}}`; standings are `{"standings": [{"type": "TOTAL",
  "table": [row]}]}` with rows `{position, team, playedGames, won, draw, lost, points,
  goalsFor, goalsAgainst, goalDifference}`.
- `football.py`: the Interfaces items. Times: `datetime.fromisoformat(utc).astimezone(_ZONE)`,
  then naive; weekday and month names from fixed English lists (as `weather.WEEKDAYS`), not
  the locale. A score is read only when the status is finished or live and both numbers are
  real (`outside.num`, ints only).

- [ ] **Step 4: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass; `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
git add config.py football.py tests/football_data.py tests/test_football.py
git commit -m "Sports stage 2: asking football-data.org, and reading its replies"
```

---

### Task 3: The summaries, worked out in code

**Files:**
- Modify: `football.py`
- Test: `tests/test_football.py`

**Interfaces:**
- Consumes: Task 2's `_match` dicts and `_table` rows; `config.FOOTBALL_TEAMS`.
- Produces, in `football.py`:
  - `latest_round(matches: list[dict]) -> dict`: `{"matchday": int | None, "matches": [...]}`,
    the finished matches of the highest matchday that has any, by date and time; `{"matchday":
    None, "matches": []}` when none.
  - `next_round(matches: list[dict]) -> dict`: the matches of the lowest matchday that has an
    upcoming, live, postponed or suspended match, by date and time (finished ones of that
    matchday left out).
  - `result_for(match: dict, team_id: int) -> str | None`: `"W"`, `"D"` or `"L"` for a finished
    match with a score; `None` otherwise.
  - `team_block(slug: str, table: list[dict], team_matches: list[dict], cl_table: list[dict]
    | None) -> dict`: `{"slug", "name", "id", "position": int | None, "position_words": str |
    None, "points": int | None, "next": match | None, "form": [{"result", "match"}] (last 5
    finished, oldest first), "recent": [{"result", "match"}] (last 5 finished, newest first),
    "coming": [match] (next 5 upcoming or live, soonest first), "champions_league": rows |
    None, "cup_note": str}`. `next` is a live match if there is one, else the soonest upcoming;
    postponed and cancelled matches are not `next`.
  - `season_started(table: list[dict]) -> bool`: any row with `played` above 0.

- [ ] **Step 1: Write the failing tests**

```python
def read(*ms):
    return [football._match(m) for m in ms]

def test_the_latest_round_is_the_highest_finished_matchday():
    ms = read(data.match(1, "2029-12-30T14:00:00Z", "FINISHED", data.ROMA, data.LAZIO, (2, 1), 18),
              data.match(2, "2030-01-05T17:00:00Z", "FINISHED", data.INTER, data.ROMA, (1, 1), 19),
              data.match(3, "2030-01-04T19:45:00Z", "FINISHED", data.MILAN, data.NAPOLI, (0, 2), 19),
              data.match(4, "2030-01-12T19:45:00Z", "TIMED", data.ROMA, data.MILAN, None, 20))
    latest = football.latest_round(ms)
    assert latest["matchday"] == 19 and [m["id"] for m in latest["matches"]] == [3, 2]
    upcoming = football.next_round(ms)
    assert upcoming["matchday"] == 20 and [m["id"] for m in upcoming["matches"]] == [4]

def test_no_matches_means_empty_rounds():
    assert football.latest_round([]) == {"matchday": None, "matches": []}
    assert football.next_round([]) == {"matchday": None, "matches": []}

def test_results_from_the_teams_side():
    win, draw = read(data.match(1, "2030-01-05T17:00:00Z", "FINISHED", data.LAZIO, data.ROMA, (0, 2), 19),
                     data.match(2, "2030-01-06T17:00:00Z", "FINISHED", data.ROMA, data.INTER, (1, 1), 19))
    assert (football.result_for(win, 100), football.result_for(win, 110)) == ("W", "L")
    assert football.result_for(draw, 100) == "D"

def test_the_team_block():
    table = football._table(data.standings(data.row(1, data.INTER, 19, 14, 3, 2, 25, 45),
                                           data.row(2, data.NAPOLI, 19, 13, 3, 3, 18, 42),
                                           data.row(3, data.ROMA, 19, 12, 4, 3, 20, 40)))
    ms = read(*data.ROMA_SEASON)        # 7 finished (oldest first: W W D L W W L), a postponed one, 6 upcoming
    block = football.team_block("roma", table, ms, None)
    assert (block["position"], block["position_words"], block["points"]) == (3, "3rd", 40)
    assert [f["result"] for f in block["form"]] == ["D", "L", "W", "W", "L"]
    assert [r["result"] for r in block["recent"]] == ["L", "W", "W", "L", "D"]
    assert len(block["coming"]) == 5 and block["next"] == block["coming"][0]
    assert block["next"]["status"] == "upcoming" and block["champions_league"] is None
    assert block["cup_note"] == "The Coppa Italia isn't in the free data"

def test_a_live_match_is_next():
    live = data.match(9, "2030-01-07T07:00:00Z", "IN_PLAY", data.ROMA, data.LAZIO, (1, 0), 20)
    block = football.team_block("roma", [], read(live, *data.ROMA_SEASON), None)
    assert block["next"]["id"] == 9 and block["next"]["score"] == {"home": 1, "away": 0}

def test_a_team_missing_from_the_table_has_no_position():
    block = football.team_block("newcastle", [], [], None)
    assert (block["position"], block["position_words"], block["points"], block["next"]) == (None, None, None, None)
    assert block["form"] == [] and block["coming"] == []

def test_the_season_has_started_once_a_game_is_played():
    assert not football.season_started(football._table(data.standings(data.row(1, data.ROMA, 0, 0, 0, 0, 0, 0))))
    assert football.season_started(football._table(data.standings(data.row(1, data.ROMA, 1, 1, 0, 0, 2, 3))))
    assert not football.season_started([])
```

Add `INTER`, `MILAN`, `NAPOLI`, `LAZIO` and `ROMA_SEASON` (the matches the comment describes,
Roma's, around 2030-01-07, all Serie A) to `tests/football_data.py`.

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest -q tests/test_football.py -k "round or result or team or season"`
Expected: FAIL with `AttributeError` (`latest_round`, `team_block`, ...).

- [ ] **Step 3: Implement** the Interfaces items in `football.py`. Sort keys are `(date,
  time)`; "now" is `_now()` for nothing here (the statuses decide), so the summaries are pure
  functions of their inputs.

- [ ] **Step 4: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass; `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
git add football.py tests/football_data.py tests/test_football.py
git commit -m "Sports stage 2: the summaries, worked out in code"
```

---

### Task 4: The cache, the earlier copy, and the league page

**Files:**
- Modify: `football.py`
- Test: `tests/test_football.py`

**Interfaces:**
- Consumes: Tasks 2 and 3.
- Produces, in `football.py`:
  - `monotonic` imported by name (`from time import monotonic`), so tests move the clock.
  - `_fetched(address: str, params: dict) -> tuple[dict, str | None]`: the reply, and `None`
    when fresh or the local `"HH:MM"` it was fetched at when an earlier copy stands in. Fresh
    copies are keyed by `(address, sorted params)`, kept `FOOTBALL_CACHE_SECONDS` (or
    `FOOTBALL_LIVE_CACHE_SECONDS` when any match in the reply is live), at most
    `FOOTBALL_CACHE_ENTRIES`, oldest dropped first. The earlier copy is keyed by `address`
    alone (so it survives the date window moving at midnight) and kept
    `FOOTBALL_EARLIER_COPY_SECONDS`. A `"no_key"` or `"refused"` failure never uses an earlier
    copy (the owner must see the key problem); `"busy"` and `"unreachable"` do. Errors are not
    cached. Every fetch records its local time.
  - `forget_everything() -> None` (tests: clears both stores).
  - `league_page(slug: str) -> dict`: `{"league": {"slug", "name", "country"},
    "season_started": bool, "table": rows, "results": latest_round, "upcoming": next_round,
    "team": team_block | None, "updated": "YYYY-MM-DDTHH:MM" (the oldest fetch time among the
    replies used), "earlier": "HH:MM" | None (the oldest earlier copy used), "credit": "Football
    data provided by the Football-Data.org API"}`. Requests: the league's standings; its
    matches with `dateFrom`/`dateTo` = today ± `FOOTBALL_WINDOW_DAYS`; for a themed league, the
    team's matches with today ± `FOOTBALL_TEAM_WINDOW_DAYS`, and the `CL` standings only when
    one of those matches has code `CL`. `ValueError` for an unknown slug.
- `tests/conftest.py`: `no_internet` also calls `football.forget_everything()`.

- [ ] **Step 1: Write the failing tests**

```python
def serie_a(cl=False):
    """The replies for Serie A's page on 2030-01-07; Roma has Champions League games if cl."""
    roma = list(data.ROMA_SEASON) + ([data.CL_GAME] if cl else [])
    return {"/competitions/SA/standings": data.SA_TABLE, "/competitions/SA/matches": data.SA_ROUNDS,
            "/teams/100/matches": data.matches(*roma), "/competitions/CL/standings": data.CL_TABLE}

def test_a_general_page_costs_two_requests(monkeypatch):
    served = data.serve(monkeypatch, {"/competitions/PD/standings": data.PD_TABLE,
                                      "/competitions/PD/matches": data.matches()})
    page = football.league_page("la-liga")
    assert len(served.calls) == 2 and page["team"] is None
    assert served.calls[1][0].endswith("?dateFrom=2029-12-28&dateTo=2030-01-17")
    assert page["league"] == {"slug": "la-liga", "name": "La Liga", "country": "Spain"}
    assert page["credit"] == "Football data provided by the Football-Data.org API"
    assert page["updated"] == "2030-01-07T08:00" and page["earlier"] is None

@pytest.mark.parametrize("cl, requests", [(False, 3), (True, 4)])
def test_a_themed_page_asks_for_the_champions_league_only_when_needed(monkeypatch, cl, requests):
    served = data.serve(monkeypatch, serie_a(cl))
    page = football.league_page("serie-a")
    assert len(served.calls) == requests and page["team"]["name"] == "Roma"
    assert (page["team"]["champions_league"] is not None) == cl
    assert "dateFrom=2029-11-08&dateTo=2030-03-08" in served.calls[2][0]

def test_a_second_look_within_ten_minutes_costs_nothing(monkeypatch):
    clock = types.SimpleNamespace(t=1000.0)
    monkeypatch.setattr(football, "monotonic", lambda: clock.t)
    served = data.serve(monkeypatch, serie_a())
    football.league_page("serie-a")
    clock.t += 599
    football.league_page("serie-a")
    assert len(served.calls) == 3
    clock.t += 2
    football.league_page("serie-a")
    assert len(served.calls) == 6

def test_a_live_match_is_kept_two_minutes(monkeypatch):
    clock = types.SimpleNamespace(t=1000.0)
    monkeypatch.setattr(football, "monotonic", lambda: clock.t)
    live = data.matches(data.match(9, "2030-01-07T07:00:00Z", "IN_PLAY", data.ROMA, data.LAZIO, (1, 0), 20))
    served = data.serve(monkeypatch, {"/competitions/PD/standings": data.PD_TABLE, "/competitions/PD/matches": live})
    football.league_page("la-liga")
    clock.t += 121
    football.league_page("la-liga")
    assert sum("/matches" in a for a, _ in served.calls) == 2
    assert sum("/standings" in a for a, _ in served.calls) == 1

def test_an_earlier_copy_is_used_when_the_service_fails(monkeypatch):
    clock = types.SimpleNamespace(t=1000.0)
    monkeypatch.setattr(football, "monotonic", lambda: clock.t)
    data.serve(monkeypatch, serie_a())
    good = football.league_page("serie-a")
    clock.t += 3600
    monkeypatch.setattr(football, "_now", lambda: datetime(2030, 1, 7, 9, 0))
    data.serve(monkeypatch, {k: TimeoutError() for k in serie_a()})
    later = football.league_page("serie-a")
    assert later["earlier"] == "08:00" and later["table"] == good["table"]
    clock.t += 21_600
    with pytest.raises(football.FootballError, match="Couldn't reach the football data."):
        football.league_page("serie-a")

def test_a_refused_key_never_falls_back_to_an_earlier_copy(monkeypatch):
    data.serve(monkeypatch, serie_a())
    football.league_page("serie-a")
    football._fresh.clear()             # only the earlier copy remains
    refused = urllib.error.HTTPError(STANDINGS, 403, "x", {}, None)
    data.serve(monkeypatch, {k: refused for k in serie_a()})
    with pytest.raises(football.FootballError, match="refused"):
        football.league_page("serie-a")

def test_an_unknown_league_is_refused():
    with pytest.raises(ValueError):
        football.league_page("eredivisie")
```

Add `SA_TABLE`, `SA_ROUNDS`, `PD_TABLE`, `CL_TABLE` and `CL_GAME` to `tests/football_data.py`.

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest -q tests/test_football.py -k "page or look or live_match_is_kept or earlier or refused_key or unknown_league"`
Expected: FAIL with `AttributeError` (`league_page`, `monotonic`, `_fresh`).

- [ ] **Step 3: Implement** the Interfaces items. One `threading.Lock` for both stores, never
  held while fetching (as `weather._cached`). The two stores are `_fresh` and `_earlier`
  (`OrderedDict`s).

- [ ] **Step 4: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass; `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
git add football.py tests/football_data.py tests/test_football.py tests/conftest.py
git commit -m "Sports stage 2: the cache, the earlier copy, and the league page"
```

---

### Task 5: `POST /sports/league`

**Files:**
- Modify: `server.py` (after the Weather endpoints)
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `football.league_page`, `football.FootballError`.
- Produces: `class LeagueRequest(BaseModel)` with `league: Literal["premier-league", "serie-a",
  "la-liga", "bundesliga", "ligue-1"]` (a test checks it matches `config.FOOTBALL_LEAGUES`);
  `POST /sports/league` returning `league_page`'s dict; `FootballError` → `HTTPException` with
  `STATUS = {"no_key": 503, "refused": 502, "busy": 429, "unreachable": 502}` and `detail =
  str(error)`.

- [ ] **Step 1: Write the failing tests** (in `tests/test_server.py`, with `football_data`
  imported as `fdata`, and a non-autouse fixture `football_ready` that calls
  `fdata.freeze(monkeypatch)`, used by every test below that reaches `league_page`)

```python
def test_the_league_endpoint_returns_the_page(client, monkeypatch, football_ready):
    fdata.serve(monkeypatch, serie_a_replies())
    r = client.post("/sports/league", json={"league": "serie-a"})
    assert r.status_code == 200 and r.json()["team"]["name"] == "Roma"

def test_the_league_names_match_the_settings():
    assert set(typing.get_args(server.LeagueRequest.model_fields["league"].annotation)) == set(config.FOOTBALL_LEAGUES)

@pytest.mark.parametrize("league", ["eredivisie", "", "SERIE-A", None, 3])
def test_an_unknown_league_is_422(client, league):
    assert client.post("/sports/league", json={"league": league}).status_code == 422

@pytest.mark.parametrize("failure, status, detail", [
    (None, 503, "Football needs a free key from football-data.org: see README"),
    (403, 502, "The football data key was refused. Check it in .env."),
    (429, 429, "Too many requests just now. Try again in a minute."),
    (TimeoutError(), 502, "Couldn't reach the football data.")])
def test_each_failure_has_its_status(client, monkeypatch, football_ready, failure, status, detail): ...
    # None: no key (delenv); an int: that HTTP status from every address; else that exception

def test_the_key_appears_only_in_the_header(client, monkeypatch, caplog, football_ready):
    served = fdata.serve(monkeypatch, serie_a_replies())
    with caplog.at_level(logging.DEBUG):
        ok = client.post("/sports/league", json={"league": "serie-a"}).text
        football.forget_everything()
        fdata.serve(monkeypatch, {k: urllib.error.HTTPError("x", 403, "x", {}, None) for k in serie_a_replies()})
        refused = client.post("/sports/league", json={"league": "serie-a"}).text
    assert all(headers == {"X-Auth-Token": fdata.KEY} for _, headers in served.calls)
    for text in (ok, refused, caplog.text):
        assert KEY not in text

def test_the_league_endpoint_refuses_other_websites_and_plain_text(client):
    assert client.post("/sports/league", json={"league": "serie-a"}, headers={"Origin": "http://evil.example"}).status_code == 403
    assert client.post("/sports/league", content='{"league": "serie-a"}', headers={"Content-Type": "text/plain"}).status_code == 422
```

Write `test_each_failure_has_its_status`'s body from its comment. Put `serie_a_replies()` in
`tests/football_data.py` (move Task 4's `serie_a` there) so both test files share it.

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest -q tests/test_server.py -k "league or key_appears"`
Expected: FAIL with 404 for `/sports/league` (no such route) and `AttributeError:
LeagueRequest`.

- [ ] **Step 3: Implement** `LeagueRequest`, `STATUS`, and the endpoint in `server.py`, with a
  comment as Weather's: POST although it only reads, so the `Origin` check and the
  `text/plain` refusal cover every request that goes online.

- [ ] **Step 4: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass; `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_server.py tests/football_data.py tests/test_football.py
git commit -m "Sports stage 2: POST /sports/league"
```

---

### Task 6: Live check with the owner's key

Needs `FOOTBALL_DATA_KEY` in `.env`, made by the owner in their own Terminal. If `.env` has no
key (`JARVIS_DB=:memory: python -c "import football; print(football._key() is not None)"`
prints `False`), **stop and ask the owner**. Never print, read aloud or log the key; the
commands below print only ids, names, counts and field names.

**Files:**
- Modify (only if the live reply differs): `config.py` (team ids), `tests/football_data.py`
  (shapes), with a test for each difference

- [ ] **Step 1: Confirm the team ids** (3 requests: Serie A and Premier League standings, one
  team's matches)

Run: `JARVIS_DB=:memory: python -c "import config, football as f; [print(code, [(r['team']['id'], r['team']['name']) for r in f._table(f._get(f'{config.FOOTBALL_API}/competitions/{code}/standings', {})) if r['team']['name'] in ('Roma', 'Newcastle')]) for code in ('SA', 'PL')]"`
Expected: `SA [(100, 'Roma')]` and `PL [(67, 'Newcastle')]`. A different id: change
`config.FOOTBALL_TEAMS`, and record it.

- [ ] **Step 2: Compare the reply shapes with the made-up ones**

Run the league page for Serie A and the Premier League live
(`JARVIS_DB=:memory: python -c "import football, json; p = football.league_page('serie-a'); print(len(p['table']), p['results']['matchday'], p['upcoming']['matchday'], p['team']['position_words'], p['team']['next'] and p['team']['next']['day'], len(p['team']['form']))"`,
then `premier-league`). Expected: about 20 rows, sensible matchdays, Roma's real position, a
next match, 5 form results. If a field the code reads is missing or shaped differently from
`tests/football_data.py`, fix the made-up reply to match the real one, add a test that fails
with the old reading, then fix the reading.

- [ ] **Step 3: Commit** (only if Step 1 or 2 changed something)

```bash
git add config.py football.py tests/football_data.py tests/test_football.py
git commit -m "Sports stage 2: match the real football-data.org replies"
```

---

### Task 7: Documentation

**Files:**
- Modify: `README.md` (the football key: how to get one free, `.env` line
  `FOOTBALL_DATA_KEY=...` or the environment variable, never in chat or code, how to check it
  is read without printing it), `SECURITY.md` (section 5, Football: the key from the
  environment variable or `.env`; what is fetched now; the earlier copy; section 4 row: headers
  go only to football-data.org), `CLAUDE.md` (`football.py`'s row; `outside.py`'s row: the
  shared readers and the header rule; the boundary: the key "in `FOOTBALL_DATA_KEY`, from the
  environment or `.env`"; `server.py`'s row: `/sports/league`), `CHANGELOG.md` (section 60 and
  Status), `plan.md` (stage 2 done; the test count)

- [ ] **Step 1: Update the documents** as listed. CHANGELOG section 60, "Sports, stage 2: the
  football server", in the style of section 59: what the page data holds, the cache and
  earlier copy, the follow-ups closed, tests (real counts), what the live check found, and
  what was not checked (the page, the tools, Safari).

- [ ] **Step 2: Full checks**

Run: `python -m pytest -q && ruff check .`
Expected: all pass; `All checks passed!`.

- [ ] **Step 3: Commit**

```bash
git add README.md SECURITY.md CLAUDE.md CHANGELOG.md plan.md
git commit -m "Document Sports stage 2 (CHANGELOG section 60)"
```
