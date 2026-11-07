"""Tests for football.py. Stage 1 holds only the key: read from the environment or .env,
never from the real .env in a test (conftest.py points JARVIS_ENV at an empty file).
Spec: docs/specs/2026-11-07-sports-space.md.
"""
import os
import urllib.error
from datetime import datetime  # noqa: F401  (used by later tests)
from zoneinfo import ZoneInfo

import pytest

import config
import football
import football_data as data

KEY = "abcdef0123456789"


def env_file(tmp_path, monkeypatch, text):
    path = tmp_path / ".env"
    path.write_text(text, newline="")
    monkeypatch.setattr(config, "ENV_FILE", path)


def test_tests_never_read_the_real_env_file():
    assert str(config.ENV_FILE) == os.devnull and "FOOTBALL_DATA_KEY" not in os.environ


def test_no_key_anywhere_means_none():
    assert football._key() is None


def test_the_key_is_read_from_the_env_file(tmp_path, monkeypatch):
    env_file(tmp_path, monkeypatch, f"# football\n\nOTHER=1\nFOOTBALL_DATA_KEY={KEY}\n")
    assert football._key() == KEY


@pytest.mark.parametrize("line", [f'FOOTBALL_DATA_KEY="{KEY}"', f"FOOTBALL_DATA_KEY = '{KEY}'",
                                  f"export FOOTBALL_DATA_KEY={KEY}", f"FOOTBALL_DATA_KEY={KEY}\r\n"])
def test_common_ways_of_writing_it_work(tmp_path, monkeypatch, line):
    env_file(tmp_path, monkeypatch, line)
    assert football._key() == KEY


@pytest.mark.parametrize("value", ["", "short", "a" * 65, "abc def 0123456789",
                                   "abc-0123456789", "kéy0123456789", f"{KEY} # mine"])
def test_a_key_that_does_not_look_right_counts_as_missing(tmp_path, monkeypatch, value):
    env_file(tmp_path, monkeypatch, f"FOOTBALL_DATA_KEY={value}\n")
    assert football._key() is None


def test_the_environment_wins_over_the_file(tmp_path, monkeypatch):
    env_file(tmp_path, monkeypatch, "FOOTBALL_DATA_KEY=" + "f" * 20)
    monkeypatch.setenv("FOOTBALL_DATA_KEY", KEY)
    assert football._key() == KEY


def test_an_unreadable_env_file_counts_as_missing(tmp_path, monkeypatch):
    for target in (tmp_path, tmp_path / "missing"):          # a folder; no file
        monkeypatch.setattr(config, "ENV_FILE", target)
        assert football._key() is None
    bad = tmp_path / "bad"
    bad.write_bytes(b"FOOTBALL_DATA_KEY=\xff\xfe0123456789\n")
    monkeypatch.setattr(config, "ENV_FILE", bad)
    assert football._key() is None


@pytest.mark.parametrize("raw", [("\ufeff" + f"FOOTBALL_DATA_KEY={KEY}").encode(),
                                 f"export\tFOOTBALL_DATA_KEY={KEY}".encode()])
def test_a_byte_order_mark_and_a_tab_after_export_work(tmp_path, monkeypatch, raw):
    path = tmp_path / ".env"
    path.write_bytes(raw)
    monkeypatch.setattr(config, "ENV_FILE", path)
    assert football._key() == KEY


# ---------- asking football-data.org, and reading its replies ----------

STANDINGS = config.FOOTBALL_API + "/competitions/SA/standings"


@pytest.fixture
def frozen(monkeypatch):
    data.freeze(monkeypatch)


def test_no_key_means_no_request(monkeypatch, frozen):
    monkeypatch.delenv("FOOTBALL_DATA_KEY")
    served = data.serve(monkeypatch, {})
    with pytest.raises(football.FootballError) as caught:
        football._get(STANDINGS, {})
    assert caught.value.kind == "no_key" and served.calls == []
    assert str(caught.value) == "Football needs a free key from football-data.org: see README"


def test_the_key_goes_in_the_header(monkeypatch, frozen):
    served = data.serve(monkeypatch, {"/competitions/SA/standings": data.standings()})
    football._get(STANDINGS, {})
    assert served.calls == [(STANDINGS, {"X-Auth-Token": data.KEY})]


@pytest.mark.parametrize("code, kind, message", [
    (403, "refused", "The football data key was refused. Check it in .env."),
    (429, "busy", "Too many requests just now. Try again in a minute."),
    (500, "unreachable", "Couldn't reach the football data.")])
def test_failures_keep_their_kind(monkeypatch, frozen, code, kind, message):
    data.serve(monkeypatch, {"/competitions/SA/standings":
                             urllib.error.HTTPError(STANDINGS, code, "x", {}, None)})
    with pytest.raises(football.FootballError) as caught:
        football._get(STANDINGS, {})
    assert caught.value.kind == kind and str(caught.value) == message


def test_a_match_is_read_into_plain_values(frozen):
    m = football._match(data.match(1, "2030-01-12T19:45:00Z", "TIMED", data.ROMA,
                                   data.LAZIO, matchday=20))
    assert m == {"id": 1, "date": "2030-01-12", "time": "19:45", "day": "Saturday 12 January",
                 "competition": "Serie A", "code": "SA", "matchday": 20, "status": "upcoming",
                 "home": {"id": 100, "name": "Roma"}, "away": {"id": 110, "name": "Lazio"},
                 "score": None}


@pytest.mark.parametrize("status, word", [
    ("IN_PLAY", "live"), ("PAUSED", "live"), ("EXTRA_TIME", "live"),
    ("PENALTY_SHOOTOUT", "live"), ("SCHEDULED", "upcoming"), ("FINISHED", "finished"),
    ("AWARDED", "finished"), ("POSTPONED", "postponed"), ("SUSPENDED", "suspended"),
    ("CANCELLED", "cancelled")])
def test_every_status_has_a_word(frozen, status, word):
    m = data.match(1, "2030-01-12T19:45:00Z", status, data.ROMA, data.LAZIO, score=(1, 0))
    assert football._match(m)["status"] == word


def test_times_are_local_across_the_clock_change(frozen):
    def at(utc):
        return football._match(data.match(1, utc, "TIMED", data.ROMA, data.LAZIO))
    assert (at("2030-10-26T13:00:00Z")["time"], at("2030-10-27T13:00:00Z")["time"]) == ("14:00", "13:00")
    football._ZONE = ZoneInfo("Europe/Rome")         # the fixture puts it back
    late = at("2030-01-12T23:30:00Z")
    assert (late["date"], late["time"], late["day"]) == ("2030-01-13", "00:30", "Sunday 13 January")


@pytest.mark.parametrize("change", [
    {"utcDate": "soon"}, {"utcDate": None}, {"status": "ON_FIRE"}, {"homeTeam": None},
    {"awayTeam": {"id": "x", "name": "Lazio"}}, {"score": {"fullTime": {"home": "two", "away": 1}}}])
def test_odd_matches_are_left_out_or_cleaned(frozen, change):
    m = dict(data.match(1, "2030-01-12T19:45:00Z", "FINISHED", data.ROMA, data.LAZIO, score=(2, 1)), **change)
    read = football._match(m)
    assert read is None or read["score"] is None
    named = football._match(data.match(1, "2030-01-12T19:45:00Z", "TIMED",
                                       data.team(5, "Evil\u202e\x00" + "x" * 300), data.LAZIO))
    assert named["home"]["name"].startswith("Evil") and len(named["home"]["name"]) <= 40
    assert "\u202e" not in named["home"]["name"] and "\x00" not in named["home"]["name"]


def test_odd_table_rows_never_crash():
    reply = data.standings(data.row(1, data.ROMA, 19, 12, 4, 3, 20, 40))
    reply["standings"][1]["table"] += [None, {"position": "first"}, {"team": {"id": 1}},
                                       data.row(3, data.LAZIO, "x", 1, 1, 1, 0, 30)]
    rows = football._table(reply)
    assert [r["team"]["name"] for r in rows] == ["Roma", "Lazio"] and rows[1]["played"] is None
    assert football._table({"standings": "nope"}) == [] and football._table({}) == []


@pytest.mark.parametrize("n, word", [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"),
    (12, "12th"), (13, "13th"), (21, "21st"), (22, "22nd"), (23, "23rd"), (101, "101st"), (111, "111th")])
def test_positions_in_words(n, word):
    assert football.ordinal(n) == word


# ---------- the summaries, worked out in code ----------

def read(*ms):
    return [football._match(m) for m in ms]


def test_the_latest_round_is_the_highest_finished_matchday(frozen):
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


def test_results_from_the_teams_side(frozen):
    win, draw = read(data.match(1, "2030-01-05T17:00:00Z", "FINISHED", data.LAZIO, data.ROMA, (0, 2), 19),
                     data.match(2, "2030-01-06T17:00:00Z", "FINISHED", data.ROMA, data.INTER, (1, 1), 19))
    assert (football.result_for(win, 100), football.result_for(win, 110)) == ("W", "L")
    assert football.result_for(draw, 100) == "D"


def test_the_team_block(frozen):
    table = football._table(data.standings(data.row(1, data.INTER, 19, 14, 3, 2, 25, 45),
                                           data.row(2, data.NAPOLI, 19, 13, 3, 3, 18, 42),
                                           data.row(3, data.ROMA, 19, 12, 4, 3, 20, 40)))
    block = football.team_block("roma", table, read(*data.ROMA_SEASON), None)
    assert (block["position"], block["position_words"], block["points"]) == (3, "3rd", 40)
    assert [f["result"] for f in block["form"]] == ["D", "L", "W", "W", "L"]
    assert [r["result"] for r in block["recent"]] == ["L", "W", "W", "L", "D"]
    assert len(block["coming"]) == 5 and block["next"] == block["coming"][0]
    assert block["next"]["status"] == "upcoming" and block["champions_league"] is None
    assert block["cup_note"] == "The Coppa Italia isn't in the free data"
    assert (block["slug"], block["name"], block["id"]) == ("roma", "Roma", 100)


def test_a_live_match_is_next(frozen):
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
