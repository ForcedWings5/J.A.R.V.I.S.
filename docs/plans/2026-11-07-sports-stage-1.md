# Sports, stage 1: one shared door to the internet — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** JARVIS has exactly one place that goes online, `outside.py`, used by Weather today
and ready for football-data.org, with a rate guard and the football key read from `.env`;
Weather behaves exactly as before.

**Architecture:** Weather's door (`_fetch`, `_get`'s checks, `_OPENER`, truststore, refused
redirects, the limits, the log line) moves into `outside.py` as `get(address, params,
headers=None)`. `weather._get` stays as a thin wrapper: it allows only Weather's three
addresses and turns any `OutsideError` into the same `WeatherError` as now. `config.py` gains
football-data.org's 13 fixed addresses, the rate limit and `ENV_FILE`; `football.py` starts
with only `_key()`. Tests, the test data helper and the eval runner replace `outside._fetch`
instead of `weather._fetch`. Nothing is fetched from football-data.org in this stage.

**Tech Stack:** Python 3.13 standard library (`urllib`, `collections.deque`, `threading`),
truststore (already a dependency), pytest. No new dependency, no prompt change (no eval run
needed beyond one quick case proving the eval runner's hook still works).

**Spec:** `docs/specs/2026-11-07-sports-space.md` (sections "Settings", "The shared door",
"The key", "Security and privacy", "Testing", "Build order" stage 1).

## Global Constraints

- Branch `sports-stage-1` (already holds the spec, `e0c0b55`). Commit after each task. Never on
  `main`. Do not push.
- Weather's behaviour and every message it gives are unchanged ("Couldn't reach the weather
  service." for any failure). Existing Weather tests may change only how they replace the door
  (`outside._fetch`, new signature) and where the door's own tests live; none is weakened.
- Every outside request goes through `outside.get`; `outside._fetch(address, headers)` is the
  only function that touches the network.
- HTTPS only; redirects refused; truststore with `verify_mode == CERT_REQUIRED` and
  `check_hostname is True`; 5 s; 1,000,000 bytes; JSON objects only; NaN and Infinity refused.
- The log records host, outcome and milliseconds. Never the address, never a header value.
- `FOOTBALL_REQUESTS_PER_MINUTE = 9`, per host, any 60 seconds, refused before sending.
- A key is 10 to 64 ASCII letters and digits; anything else counts as missing. Tests never read
  the real `.env` and never see a real key.
- Ruff (E, F, B; line length 100). Python 3.13. Plain English comments that say why.

## Review Focus

1. **The key in a failure.** A request that fails (timeout, HTTP 403) must not put the key or
   the address into the log or the error. Pinned by
   `test_the_log_and_errors_never_hold_the_address_or_a_header` (Task 1).
2. **Failed requests and the guard.** A request that was sent and failed still counts, or
   repeated failures could exceed the plan's limit. Pinned by `test_failed_requests_count_too`
   (Task 2).
3. **Requests at the same moment** (the server runs handlers in threads) must not slip past the
   guard. Pinned by `test_the_guard_holds_with_requests_at_the_same_time` (Task 2).
4. **Ordinary ways of writing `.env`** (quotes, spaces round `=`, `export `, Windows line ends)
   must work, and a missing, unreadable or non-UTF-8 file must count as no key, never crash.
   Pinned by `test_common_ways_of_writing_it_work` and
   `test_an_unreadable_env_file_counts_as_missing` (Task 3).
5. **Weather facing the new kinds.** Open-Meteo answering 400, 403, 429 or 500 must still give
   Weather's one message, and Weather must not be able to use a football address. Pinned by
   `test_weather_says_the_same_whatever_the_kind` and
   `test_weather_cannot_use_footballs_addresses` (Task 1).

---

### Task 1: `outside.py`, the settings, and Weather moved onto it

**Files:**
- Create: `outside.py`, `tests/test_outside.py`
- Modify: `config.py:66-80` (Weather block: the two limits renamed; a Football block added),
  `weather.py:11-93` (imports and the door), `tests/conftest.py` (`no_internet`),
  `tests/test_weather.py:1-123` (the door's tests leave; `fake_fetch` patches `outside`),
  `tests/weather_data.py:80-98` (`serve`), `evals/__main__.py:28-45` (the hook)

**Interfaces:**
- Produces, in `config.py`:
  - `OUTSIDE_TIMEOUT_SECONDS = 5`, `OUTSIDE_MAX_BYTES = 1_000_000` (replacing
    `WEATHER_TIMEOUT_SECONDS`, `WEATHER_MAX_BYTES`)
  - `FOOTBALL_API = "https://api.football-data.org/v4"`
  - `FOOTBALL_LEAGUES: dict[str, dict]`: `"premier-league"` `{"code": "PL", "name": "Premier
    League", "country": "England", "lat": 52.5, "lon": -1.5}`; `"serie-a"` SA Serie A Italy
    42.8, 12.5; `"la-liga"` PD La Liga Spain 40.2, -3.7; `"bundesliga"` BL1 Bundesliga Germany
    51.2, 10.4; `"ligue-1"` FL1 Ligue 1 France 46.6, 2.4
  - `FOOTBALL_TEAMS: dict[str, dict]`: `"roma"` `{"id": 100, "name": "Roma", "league":
    "serie-a", "cup_note": "The Coppa Italia isn't in the free data"}`; `"newcastle"` `{"id":
    67, "name": "Newcastle", "league": "premier-league", "cup_note": "The FA Cup isn't in the
    free data"}` (ids confirmed in stage 2, comment says so)
  - `FOOTBALL_ADDRESSES: tuple[str, ...]`: built in code from the two dicts: `.../competitions/
    {code}/standings` for the five codes and `CL`; `.../competitions/{code}/matches` for the
    five codes; `.../teams/{id}/matches` for the two ids. 13 entries.
  - `FOOTBALL_REQUESTS_PER_MINUTE = 9`
- Produces, in `outside.py` (logger `jarvis.outside`):
  - `ADDRESSES: frozenset[str]`: Weather's three URLs and `FOOTBALL_ADDRESSES`
  - `class OutsideError(Exception)` with `.kind` in `{"unreachable", "refused", "busy"}`;
    `str(error) == kind`
  - `_fetch(address: str, headers: dict[str, str]) -> bytes`
  - `get(address: str, params: dict, headers: dict[str, str] | None = None) -> dict`
  - `_OPENER` (refusing redirects, truststore HTTPS handler)
- Weather keeps: `weather.ADDRESSES` (its three), `weather._get(base, params) -> dict`,
  `WeatherError`, `UNREACHABLE`.

- [ ] **Step 1: Write the failing tests** in `tests/test_outside.py`

```python
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
```

Also move here from `tests/test_weather.py`, unchanged except that they use `outside`:
`test_redirects_are_refused` (`outside._OPENER`), `test_https_checks_certificates_against_the_macs_trust_list`
(`outside._OPENER`), and `test_tests_cannot_reach_the_internet` (`outside._fetch(FOOT, {})`).
Rewrite `test_each_request_is_logged_without_its_address` for logger `jarvis.outside`.

In `tests/test_weather.py` add:

```python
@pytest.mark.parametrize("code", [400, 403, 429, 500])
def test_weather_says_the_same_whatever_the_kind(monkeypatch, code):
    fake_fetch(monkeypatch, urllib.error.HTTPError(config.WEATHER_FORECAST_URL, code, "x", {}, None))
    with pytest.raises(weather.WeatherError, match="Couldn't reach the weather service."):
        weather._get(config.WEATHER_FORECAST_URL, {"latitude": 1})

def test_weather_cannot_use_footballs_addresses(monkeypatch):
    fake_fetch(monkeypatch, b"{}")
    with pytest.raises(ValueError):
        weather._get(config.FOOTBALL_ADDRESSES[0], {})
```

- [ ] **Step 2: Run them to see them fail**

Run: `source .venv/bin/activate && python -m pytest -q tests/test_outside.py`
Expected: FAIL at collection, `ModuleNotFoundError: No module named 'outside'`.

- [ ] **Step 3: Add the settings to `config.py`**

Rename the two Weather limits to `OUTSIDE_*` (they are now shared; comment says so). Add the
Football block from the Interfaces list under a comment naming the spec and `SECURITY.md`
section 5. Build `FOOTBALL_ADDRESSES` with a tuple comprehension over `FOOTBALL_LEAGUES` and
`FOOTBALL_TEAMS`, so the codes are written once.

- [ ] **Step 4: Write `outside.py`**

Move from `weather.py`: `_RefuseRedirects`, `_TLS`, `_OPENER`, `_refuse_constant`, and the body
of `_get` as `get`. Changes from the moved code:
- `_fetch(address, headers)` opens `urllib.request.Request(address, headers=headers)` with
  `config.OUTSIDE_TIMEOUT_SECONDS` and reads at most `config.OUTSIDE_MAX_BYTES + 1`.
- `get` raises `ValueError` for an address not in `ADDRESSES`; adds `"?" + urlencode(params)`
  only when `params` is not empty; passes `headers or {}`.
- Failures: `urllib.error.HTTPError` with code 400, 401 or 403 → `OutsideError("refused")`,
  429 → `OutsideError("busy")`, any other code and every other `OSError`, `ValueError` or
  `RecursionError` → `OutsideError("unreachable")`. Close an `HTTPError` before raising
  (it holds the open reply).
- Log line, logger `jarvis.outside`: `"outside request: %s, %s in %d ms"` (host, outcome,
  milliseconds), as Weather's was.

- [ ] **Step 5: Put Weather on the door**

`weather._get(base, params)` keeps its docstring's promise: `ValueError` if `base` is not in
`weather.ADDRESSES`; otherwise `return outside.get(base, params)`, turning `OutsideError` into
`WeatherError(UNREACHABLE)` with `from e`. Remove the moved code and the imports ruff then
reports unused (`truststore`, `ssl`, `urllib.request`, and any other).

- [ ] **Step 6: Move the hooks**

- `tests/conftest.py`: `import outside`; `no_internet`'s `refuse(address, headers=None)` is set
  on `outside._fetch`; its docstring names `outside`.
- `tests/test_weather.py`: `fake_fetch`'s inner `fetch(address, headers=None)` is set on
  `outside._fetch`; delete the four door tests moved in Step 1; the module docstring says
  `outside._fetch`.
- `tests/weather_data.py`: `serve`'s `fetch(address, headers=None)` is set on `outside._fetch`;
  docstrings name `outside._fetch`.
- `evals/__main__.py`: `import outside`; `outside._fetch = lambda address, headers=None:
  weather_data.canned_fetch(address, NOW)`; the comment above it names the shared door.

- [ ] **Step 7: Run the tests and lint**

Run: `python -m pytest -q tests/test_outside.py tests/test_weather.py && python -m pytest -q && ruff check .`
Expected: all pass (the full suite was 684 before this task; it is 684 plus the new tests,
minus none), ruff `All checks passed!`.

- [ ] **Step 8: Commit**

```bash
git add outside.py config.py weather.py tests/test_outside.py tests/test_weather.py tests/conftest.py tests/weather_data.py evals/__main__.py
git commit -m "Sports stage 1: one shared door to the internet (outside.py)"
```

---

### Task 2: The rate guard

**Files:**
- Modify: `outside.py`, `tests/conftest.py` (`no_internet` also forgets the guard)
- Test: `tests/test_outside.py`

**Interfaces:**
- Consumes: Task 1's `outside.get`, `OutsideError`, `fake_fetch`, `FOOT`.
- Produces: `outside.forget_rate_guard() -> None`; `outside.monotonic` (imported by name with
  `from time import monotonic`, so tests can move it, as `weather.py` does).

- [ ] **Step 1: Write the failing tests** in `tests/test_outside.py`

```python
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

def test_the_guard_holds_with_requests_at_the_same_time(monkeypatch, minute):
    seen = fake_fetch(monkeypatch, b"{}")
    results = []
    def ask():
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest -q tests/test_outside.py -k "guard or tenth or count_too"`
Expected: FAIL (`AttributeError: ... 'monotonic'` from the fixture, or no `busy` raised).

- [ ] **Step 3: Implement the guard in `outside.py`**

`_LIMITS = {"api.football-data.org": config.FOOTBALL_REQUESTS_PER_MINUTE}`; a
`dict[str, collections.deque[float]]` of send times and one `threading.Lock`. In `get`, after
the address check and before `_fetch`, for a host in `_LIMITS`: under the lock, drop times older
than `monotonic() - 60`; if as many remain as the limit, log `"outside request: %s, refused by
the rate guard"` and raise `OutsideError("busy")`; else record now. `forget_rate_guard()`
clears the times. Comment why: the free plan allows 10 a minute; 9 keeps one spare for clock
differences; refusing before sending means JARVIS can never get the key blocked.

- [ ] **Step 4: Forget the guard between tests**

`tests/conftest.py`: `no_internet` calls `outside.forget_rate_guard()`.

- [ ] **Step 5: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass; `All checks passed!`.

- [ ] **Step 6: Commit**

```bash
git add outside.py tests/test_outside.py tests/conftest.py
git commit -m "Sports stage 1: the rate guard for football-data.org"
```

---

### Task 3: Reading the football key

**Files:**
- Create: `football.py`, `tests/test_football.py`
- Modify: `config.py` (`ENV_FILE`), `tests/conftest.py` (top: `JARVIS_ENV`, no key in the
  environment)

**Interfaces:**
- Produces: `config.ENV_FILE: Path` (from `JARVIS_ENV`, else `ROOT / ".env"`);
  `football._key() -> str | None`. Not imported by `brain.py` in this stage.

- [ ] **Step 1: Write the failing tests** in `tests/test_football.py`

```python
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest -q tests/test_football.py`
Expected: FAIL at collection, `ModuleNotFoundError: No module named 'football'` (and
`test_tests_never_read_the_real_env_file` would fail on `ENV_FILE`).

- [ ] **Step 3: Implement**

- `config.py`: `ENV_FILE = Path(os.environ.get("JARVIS_ENV", str(ROOT / ".env")))`, next to
  `DB_PATH`, with a comment: secrets such as the football key live in `.env` (ignored by git);
  tests point `JARVIS_ENV` at nothing.
- `football.py`: module docstring (Football from football-data.org; this stage holds only the
  key; spec path). `_key()` reads the `FOOTBALL_DATA_KEY` environment variable if set and not
  empty, else the last `FOOTBALL_DATA_KEY` line of `config.ENV_FILE`: lines stripped, blank and
  `#` lines skipped, an optional leading `export `, split at the first `=`, name and value
  stripped, one pair of matching quotes removed. Read on every call (a tiny file), so a key
  added while JARVIS runs works without a restart. `OSError` and `UnicodeDecodeError` mean no
  key. The value must match `[A-Za-z0-9]{10,64}` (`re.fullmatch`, ASCII only), else `None`.
  It never logs.
- `tests/conftest.py`, before any project import, next to `JARVIS_DB`:
  `os.environ["JARVIS_ENV"] = os.devnull` and `os.environ.pop("FOOTBALL_DATA_KEY", None)`, with
  a comment (the third safety rule in its docstring: tests never read the real `.env`).

- [ ] **Step 4: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass; `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
git add football.py tests/test_football.py config.py tests/conftest.py
git commit -m "Sports stage 1: reading the football key from .env"
```

---

### Task 4: Live check and documentation

**Files:**
- Modify: `SECURITY.md` (sections 3, 4, 5, 7; line 53), `CLAUDE.md` (intro, architecture
  diagram and table, the outside-requests boundary, the testing note on `no_internet`),
  `requirements.in` and `requirements-dev.in` (truststore's comment names `outside.py`; comments
  only, so the compiled files are unchanged), `plan.md` (Sports in progress), `CHANGELOG.md`
  (section 59, Status, file layout if listed)

- [ ] **Step 1: Live check, one real Weather request through the new door**

Run: `JARVIS_DB=:memory: JARVIS_ENV=/dev/null python -c "import weather; print(weather.find_places('Paris')[0]['name'])"`
Expected: `Paris`. (One request to Open-Meteo, as Weather already makes. If the Mac is offline,
record that it was not checked.)

- [ ] **Step 2: The eval runner's hook still works**

Run: `python -m evals --runs 1 -k weather_find_paris`
Expected: `1/1` (needs Ollama; if it is not running, record that it was not checked).

- [ ] **Step 3: Update the documents**

- `SECURITY.md`:
  - section 3: outside requests go through `outside.py`;
  - section 4: the controls row names `outside.get`, the 16 fixed addresses (Weather's 3 and
    football-data.org's 13), the rate guard, and that headers are never logged;
  - section 5: Weather's subsection says the door moved; a new subsection "Outside data:
    Football (Sports)". It covers what will go out (the key in `X-Auth-Token`, a competition
    code or team id, a date range; the Mac's IP), the account link, the guard, the key's rules
    (`.env`, never logged, never to the page or model), and that nothing is fetched until stage 2;
  - section 7: the account link, accepted;
  - line 53: truststore is used by `outside.py`.
- `CLAUDE.md`:
  - the intro's list of services adds football-data.org (Sports, being built);
  - the diagram and table gain `outside.py` and `football.py` (stage 1: the key only);
  - `weather.py`'s row no longer holds the door;
  - the boundary becomes "Outside requests go only through `outside.get`, to the fixed HTTPS
    addresses in `config.py` (`WEATHER_*_URL`, `FOOTBALL_ADDRESSES`)", with the guard and
    "headers are never logged";
  - the testing note names `outside._fetch` and `JARVIS_ENV`.
- `CHANGELOG.md` section 59, "Sports, stage 1: one shared door to the internet", in the style of
  sections 55 to 58. It says what moved and why, the guard, the key reading, the tests (counts
  from the real run), what was checked live, and what was not (nothing football is fetched yet;
  the team ids are unconfirmed). Update the Status table.

- [ ] **Step 4: Full checks**

Run: `python -m pytest -q && ruff check .`
Expected: all pass; `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
git add SECURITY.md CLAUDE.md requirements.in requirements-dev.in plan.md CHANGELOG.md
git commit -m "Document Sports stage 1 (CHANGELOG section 59)"
```
