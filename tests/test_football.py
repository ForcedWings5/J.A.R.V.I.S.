"""Tests for football.py. Stage 1 holds only the key: read from the environment or .env,
never from the real .env in a test (conftest.py points JARVIS_ENV at an empty file).
Spec: docs/specs/2026-11-07-sports-space.md.
"""
import os

import pytest

import config
import football

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
