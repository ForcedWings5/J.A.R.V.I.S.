"""The bake tool (scripts/bake_player.py): what it will save, and what it will serve.

It runs only on the owner's Mac, by hand, to turn the Mixamo downloads into
static/models/player.glb and player.json (Sports stage 4b). These tests pin its limits."""

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("bake_player", ROOT / "scripts" / "bake_player.py")
bake = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bake)

GOOD = {
    "version": 1, "pace": 1.25, "end": 4.6, "strike": 3.7, "ballR": 0.11,
    "incoming": {"from": 0.16, "to": 0.88, "start": [0.1, 6.3, 5.4]},
    "ball": [
        {"t": 0.88, "p": [0.0, 0.4, 2.5]},
        {"t": 1.16, "p": [0.1, 0.11, 2.6]},
        {"t": 3.67, "p": [-0.1, 0.11, 4.0]},
    ],
    "camera": {"target": [0.0, 1.0, 2.4], "forward": [0.0, 0.0, 1.0]},
}


def bad(change):
    data = copy.deepcopy(GOOD)
    change(data)
    return data


def test_a_good_file_passes():
    assert bake.check_player_json(GOOD) is None


@pytest.mark.parametrize("data", [
    bad(lambda d: d.update(version=2)),
    bad(lambda d: d.update(end=float("nan"))),
    bad(lambda d: d.update(end=9)),
    bad(lambda d: d.update(strike=5.0)),
    bad(lambda d: d.update(strike="3.7")),
    bad(lambda d: d.update(ballR=0)),
    bad(lambda d: d["incoming"].update(to=0.1)),
    bad(lambda d: d["ball"].reverse()),
    bad(lambda d: d.update(ball=[{"t": 1.0, "p": [0, 0.11, 2]}] * 13)),
    bad(lambda d: d.update(ball=d["ball"][:1])),
    bad(lambda d: d["ball"][1].update(p=[21, 0.11, 2])),
    bad(lambda d: d["ball"][1].update(p=[0, 0.11])),
    bad(lambda d: d["ball"][0].update(t=0.5)),                 # before the ball has arrived
    bad(lambda d: d["ball"][2].update(t=3.8)),                 # after the strike
    bad(lambda d: d["camera"].update(forward=[0, 0, 0])),
    bad(lambda d: d.pop("camera")),
    [1, 2, 3],
    None,
])
def test_a_bad_file_is_refused(data):
    assert isinstance(bake.check_player_json(data), str)


def test_it_saves_only_its_two_files(tmp_path):
    assert bake.save_path("player.glb", tmp_path) == tmp_path / "player.glb"
    assert bake.save_path("player.json", tmp_path) == tmp_path / "player.json"
    for name in ("../player.glb", "player.glb/..", "other.txt", "", "/etc/passwd"):
        assert bake.save_path(name, tmp_path) is None
    assert bake.SAVE_NAMES == {"player.glb": 30_000_000, "player.json": 100_000}


def test_it_serves_nothing_outside_its_folders(tmp_path):
    (tmp_path / "a.js").write_text("x")
    assert bake.serve_path("/a.js", [tmp_path]) == tmp_path / "a.js"
    for path in ("/../config.py", "/vendor/../../jarvis.db", "//etc/passwd", "/missing.js", "/"):
        assert bake.serve_path(path, [tmp_path]) is None


def test_it_listens_on_this_mac_only():
    assert bake.ADDRESS == ("127.0.0.1", 8018)


def test_the_model_files_stay_on_this_mac():
    """Mixamo's licence does not allow passing the files on: never in git."""
    assert "static/models/" in (ROOT / ".gitignore").read_text().splitlines()
