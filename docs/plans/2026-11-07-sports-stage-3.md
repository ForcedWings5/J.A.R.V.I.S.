# Sports, stage 3: the page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Space 4, Sports, works with plain fades: a hub of five sports (Football opens; the
rest say "coming soon"), the globe as Football's league picker, and the league pages
(general, and themed for Roma and Newcastle) filled from `POST /sports/league`, with a trail,
Esc up one level, and addresses that survive a reload.

**Architecture:** The space is one `<section data-level>` with three levels (hub, football,
league), drawn by CSS from `data-level` as Weather's views are. `space-sports.js` owns the
levels, the hub, the trail, Esc and the addresses; `sports-football.js` owns the globe picker
(a second `makeGlobe`, sharing the coastlines) and the league pages (fetching one at a time,
loading, slow, error, earlier-copy states, and drawing with `textContent` only). Small pure
functions hold the page's logic so they can be checked in the browser. Server side, only
`config.SPACES` and `open_space`'s description change, which changes the prompt: full eval
before and after.

**Tech Stack:** Plain JavaScript (no build step, shared globals, scripts in order), CSS, a
canvas globe (`globe.js`), pytest for what Python can pin, the browser pane for the rest.

**Spec:** `docs/specs/2026-11-07-sports-space.md` (sections "How it works, end to end" 1 to 4,
"The league pages", "Files", "When something goes wrong", "Testing" (Page), "Build order"
stage 3).

## Global Constraints

- Branch `sports-stage-3` from `main` (`022e24e`). Commit after each task. Never on `main`. Do
  not push.
- Plain fades only; no animation beyond CSS opacity transitions (stage 4 does the motion).
  Reduce motion: no transition at all.
- The Content Security Policy is unchanged: no inline scripts, styles, `style=` or `on...=`
  attributes in `index.html`, no `setAttribute('style'`, no `innerHTML` with outside text.
  Positions set from JS use `el.style.left/top` (CSSOM, allowed). Every outside value reaches
  the page through `textContent`.
- The page talks only to JARVIS: `POST /sports/league`. Never to football-data.org.
- One football request at a time from the page (CHANGELOG section 60): while one is in flight,
  no other is sent; the newest wanted league is fetched when it ends.
- Addresses: `#sports` (hub), `#sports/football` (picker), `#sports/<slug>` (league), slugs as
  in `config.FOOTBALL_LEAGUES`. Anything else under `#sports/` opens the hub. Key 4, the chip,
  or "open sports" open the hub.
- Copy (spec, exact): "coming soon" note as "<Sport>: coming soon"; "Free scores arrive late";
  "The season hasn't started."; "No match scheduled yet."; the credit "Football data provided
  by the Football-Data.org API"; the server's `detail` shown as given.
- Demos: their own database, backups and log, port 8016 (check `lsof -iTCP:8000 -sTCP:LISTEN`
  first; the owner's JARVIS reloads on file changes). A `securitypolicyviolation` listener
  stays on in every demo. Live football requests only with the owner's key and only as many
  as the step says.
- The full eval takes about 20 minutes per run; it needs Ollama.

## Review Focus

1. **Clicking leagues quickly, or the same league twice**: one request at a time; the last
   league asked for is the one shown; no page drawn for a league you already left. Pinned by
   Task 5's demo step "One at a time".
2. **Leaving mid-load or mid-page** (Esc, another space, the Back button): a late reply draws
   nothing and switches nothing, and the countdown's timer stops. Pinned by Task 5's demo step
   "Leaving".
3. **An address typed or reloaded by hand** (`#sports/serie-a` on reload, `#sports/eredivisie`,
   `#sports/`, `#SPORTS/Serie-A`): the right level, or the hub, never Home and never an error.
   Pinned by Task 3's demo step "Addresses".
4. **A reply with parts missing** (no next match, a season not started, no results, no team
   block): the page shows the plain notes and never the words "undefined", "null" or "NaN".
   Pinned by Task 5's demo step "Missing parts".
5. **Failures** (no key, busy, unreachable after a slow wait, an earlier copy from yesterday):
   the server's message, Try again except for no key, "still waiting" after 4 seconds, and the
   earlier copy's day when it is not today. Pinned by Task 5's demo step "Failures".

---

### Task 1: Sports joins the spaces (server side, with the eval)

**Files:**
- Modify: `config.py` (`SPACES`), `spaces.py` (`open_space`'s description), `evals/cases.py`
- Test: `tests/test_spaces.py`, `tests/test_server.py`

**Interfaces:**
- Produces: `config.SPACES == ("home", "work", "weather", "sports")`; `open_space` accepts
  `"sports"`; `/chat` accepts `space: "sports"`.

- [ ] **Step 1: Confirm the "before" score**

Run: `source .venv/bin/activate && python -m evals --runs 1 -k space_weather 2>&1 | grep -i hash`
Expected: prompt hash `0a1a37f7968e`, the hash of the last full run (228/231, CHANGELOG
section 58). Stages 1 and 2 changed no prompt. If the hash differs, run the full eval
(`python -m evals`) now and use that as "before".

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_spaces.py
def test_sports_is_a_space():
    """Sports stage 3 (docs/specs/2026-11-07-sports-space.md)."""
    assert config.SPACES == ("home", "work", "weather", "sports")
    assert spaces.open_space("Sports") == tools.ShowSpace("sports", "Showing the Sports space.")
    description = next(s for s in tools.SCHEMAS if s["function"]["name"] == "open_space")["function"]["description"]
    assert "sports has football" in description

```

In `tests/test_server.py`, add `test_chat_accepts_the_sports_space`: a copy of
`test_chat_accepts_the_weather_space` (line 306) with `"sports"` in place of `"weather"`.

- [ ] **Step 3: Run them to see them fail**

Run: `python -m pytest -q tests/test_spaces.py tests/test_server.py -k "sports"`
Expected: FAIL (`SPACES` has three names; `/chat` answers 422 for `"sports"`).

- [ ] **Step 4: Implement**

- `config.py`: `SPACES = ("home", "work", "weather", "sports")`.
- `spaces.py`: after "weather has a globe and the weather for a place;" add "sports has football:
  league tables and results, with Roma and Newcastle followed;" (the rest unchanged).
- `evals/cases.py`, after the two Weather space cases, under a comment naming this stage:
  `Case("space_sports", "Open sports.", expect=[("open_space", {"name": "sports"})],
  max_calls={"open_space": 1})` and `Case("space_sports_mentioned_no_switch", "I played
  football with friends yesterday.", forbid=["open_space"])`.

- [ ] **Step 5: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass (806 before, plus the new ones; `tests/test_evals.py`'s case checks
included); `All checks passed!`.

- [ ] **Step 6: The full eval, after**

Run: `python -m evals` (about 20 minutes)
Expected: the two new cases pass every run; the total close to 228/231 plus 6 runs of the new
cases. Before calling a failure a model problem, read the reply (`-v`, CLAUDE.md). Record
the score and the new prompt hash for the commit message and the CHANGELOG.

- [ ] **Step 7: Commit**

```bash
git add config.py spaces.py evals/cases.py tests/test_spaces.py tests/test_server.py
git commit -m "Sports stage 3: Sports joins the spaces (evals: before 228/231 0a1a37f7968e, after <score> <hash>)"
```

---

### Task 2: The coastlines shared, and a globe that can frame Europe

**Files:**
- Modify: `static/js/globe.js`, `static/js/space-weather.js`

**Interfaces:**
- Produces, in `globe.js`: `loadCoastlines() -> Promise<Array>` (fetches
  `/static/data/coastlines.json` once and gives every caller the same promise; on failure it
  resolves to `[]` and warns once, as Weather did); `globe.jumpTo(lat, lon, zoom)` (zoom
  optional; when given, sets the zoom too).
- `space-weather.js` uses `loadCoastlines().then(globe.setLines)` instead of its own
  `wxLoadLines`.

- [ ] **Step 1: Implement** the two changes. Weather's behaviour does not change.

- [ ] **Step 2: Check**

Run: `python -m pytest -q && ruff check .`
Expected: all pass (the CSP scans and the files-exist test cover the scripts).

Then a demo (Task 3's launcher, made-up data): open Weather (key 3). Expected: the globe draws
coastlines; the network panel shows `coastlines.json` fetched once; no console errors, no
policy violations.

- [ ] **Step 3: Commit**

```bash
git add static/js/globe.js static/js/space-weather.js
git commit -m "Sports stage 3: the coastlines loaded once and shared"
```

---

### Task 3: The space, the hub, the trail and the addresses

**Files:**
- Modify: `static/index.html` (the Sports section, the stylesheet link, the scripts:
  `globe.js`, `space-weather.js`, `space-sports.js`, `sports-football.js`, `motion.js` in that
  order), `static/js/spaces.js` (`spaceFromAddress`: the part before the first `/`)
- Create: `static/js/space-sports.js`, `static/js/sports-football.js` (for now only
  `const SPORTS_LEAGUES = [];` and a `sportsFootball` object with no-op `enterPicker`,
  `openLeague` and `leave`), `static/css/space-sports.css`
- Create (scratch, not committed): `demo4/run_demo.py` in the session's scratchpad, like
  Weather's launcher (its own database, backups and log; port 8016), with `--canned` that
  replaces `outside._fetch` for football with replies from `tests/football_data.py` (Task 5
  lists them) and sets a made-up key, and `--nokey` that removes the key. Without `--canned`,
  football requests use the owner's real key.
- Test: `tests/test_server.py`

**Interfaces:**
- Produces, in `space-sports.js` (globals):
  - `SPORTS_OBJECTS`: `[{name: 'football', title: 'Football', ready: true}, {name:
    'basketball', title: 'NBA'}, {name: 'american-football', title: 'NFL'}, {name: 'baseball',
    title: 'MLB'}, {name: 'f1', title: 'F1'}]` (the hub's order).
  - `sportsFromAddress(hash) -> {level: 'hub' | 'football' | 'league', league: string | null}`:
    lower-cases; `#sports/football` is the picker; `#sports/<slug>` with a slug in
    `SPORTS_LEAGUES` (Task 4) is that league; anything else is the hub.
  - `sportsAddress(level, league) -> string`: the inverse.
  - `sportsGo(level, league = null, {fromAddress = false} = {})`: sets `data-level` on the
    section, calls `sportsFootball.enterPicker()`, `.openLeague(slug)` or `.leave()` as the level
    needs, draws the trail, and pushes the address unless `fromAddress`.
  - `registerSpace({name: 'sports', title: 'SPORTS', key: '4', section, enter, leave, ready,
    readout})`: `enter` follows `location.hash` if it starts with `#sports`, else the hub;
    `leave` calls `sportsFootball.leave()`; `readout` is `"SPORTS ONLINE"`, `"PICK A
    LEAGUE"`, or the league's name in capitals.
  - Esc (capture phase, as Weather's): in Sports, not typing, no access sequence running:
    league → picker, picker → hub, hub → nothing.
  - `hashchange`/`popstate`: when Sports is shown and the address starts with `#sports`, follow
    it with `fromAddress: true`.
- Produces, in `index.html`: `<section class="space" id="space-sports" data-space="sports"
  data-level="hub" aria-label="Sports" hidden>` with `#sp-trail` (buttons per level, and
  `#sp-back`), `#sp-hub` (one `<button class="sp-object" data-sport="...">` per object,
  each holding a small SVG drawn with classes, no `style`), `#sp-note` (`aria-live`),
  `#sp-picker` (Task 4) and `#sp-league` (Task 5).

- [ ] **Step 1: Write the failing tests** in `tests/test_server.py`

```python
SPORTS_JS = ["static/js/space-sports.js", "static/js/sports-football.js"]

def test_the_sports_section_and_its_files_are_on_the_page(client):
    page = client.get("/").text
    assert 'id="space-sports"' in page and 'data-level="hub"' in page
    assert '/static/css/space-sports.css' in page
    order = [page.index(f"/static/js/{name}.js") for name in
             ("globe", "space-weather", "space-sports", "sports-football", "motion")]
    assert order == sorted(order)

def test_every_element_the_sports_scripts_look_up_exists():
    page = (ROOT / "static" / "index.html").read_text()
    for path in SPORTS_JS:
        for element_id in re.findall(r"getElementById\('([^']+)'\)", (ROOT / path).read_text()):
            assert f'id="{element_id}"' in page, (path, element_id)

def test_the_hub_has_the_five_sports():
    page = (ROOT / "static" / "index.html").read_text()
    assert re.findall(r'data-sport="([^"]+)"', page) == ["football", "basketball", "american-football", "baseball", "f1"]
```

(`ROOT` is the project folder; add it if the file has none.)

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest -q tests/test_server.py -k "sports_section or look_up or five_sports"`
Expected: FAIL (no section, no files).

- [ ] **Step 3: Implement** the files in the Interfaces block, and `space-sports.css`: the hub as
  a row of glass circles (`--glass`, `--blur`, `--rim`), the trail at the top, the levels shown
  by `[data-level]` with an opacity fade (none under Reduce motion), the note under the hub.
  Clicking a not-ready object writes "<title>: coming soon" to `#sp-note` for 1.5 seconds.

- [ ] **Step 4: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass; `All checks passed!`.

- [ ] **Step 5: Demo check** (`demo4/run_demo.py --canned`, 1440×900, the violation listener)

- Key 4: the hub with five objects; chips read `1 HOME 2 WORK 3 WEATHER 4 SPORTS`.
- Click the basketball: "NBA: coming soon", gone after 1.5 s; nothing else changes.
- Click the football: the picker level (empty for now), address `#sports/football`, trail
  "Sports / Football"; Esc: the hub, address `#sports`.
- **Addresses**: load `#sports/football` (picker), `#sports/eredivisie` (hub), `#sports/`
  (hub), `#SPORTS/FOOTBALL` (picker), `#weather` then the browser's Back (follows); none
  shows Home or an error.
- Esc in the command box only leaves the box (spaces.js), as everywhere.
- No console errors; no policy violations.

- [ ] **Step 6: Commit**

```bash
git add static/index.html static/js/spaces.js static/js/space-sports.js static/js/sports-football.js static/css/space-sports.css tests/test_server.py
git commit -m "Sports stage 3: the space, the hub, the trail and the addresses"
```

---

### Task 4: The league picker on the globe

**Files:**
- Modify: `static/js/sports-football.js`, `static/index.html` (`#sp-picker`: `<canvas
  id="sp-globe">`, `#sp-pins`, and `#sp-league-list` with one button per league),
  `static/css/space-sports.css`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `makeGlobe`, `loadCoastlines`, `globe.jumpTo(lat, lon, zoom)`, `globe.screenPoint`
  (Task 2); `sportsGo` (Task 3).
- Produces, in `sports-football.js`:
  - `SPORTS_LEAGUES`: `[{slug, name, country, lat, lon}]`, the same five as
    `config.FOOTBALL_LEAGUES`, in its order.
  - `SPORTS_EUROPE = {lat: 47, lon: 6, zoom: 3}`.
  - `sportsFootball.enterPicker()`: loads the coastlines, starts the globe, jumps to Europe,
    places one pin button per league (`"<country> · <league>"`) at its `screenPoint`, again on
    window resize; `sportsFootball.leave()` stops the globe.
  - Clicking a pin or a list button calls `sportsGo('league', slug)`.

- [ ] **Step 1: Write the failing test**

```python
def test_the_page_knows_the_same_leagues_as_the_server():
    source = (ROOT / "static" / "js" / "sports-football.js").read_text()
    found = re.findall(r"slug: '([^']+)', name: '([^']+)', country: '([^']+)', lat: ([-\d.]+), lon: ([-\d.]+)", source)
    assert found == [(slug, lg["name"], lg["country"], str(lg["lat"]), str(lg["lon"]))
                     for slug, lg in config.FOOTBALL_LEAGUES.items()]
```

- [ ] **Step 2: Run it to see it fail**

Run: `python -m pytest -q tests/test_server.py -k same_leagues`
Expected: FAIL (`found == []`).

- [ ] **Step 3: Implement** the Interfaces items, writing each league in `SPORTS_LEAGUES` on one
  line in the form the test reads.

- [ ] **Step 4: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass; `All checks passed!`.

- [ ] **Step 5: Demo check**

- The football: the globe framed on Europe with coastlines, five labelled pins on England,
  France, Spain, Germany and Italy, and the list beside it; resizing the window keeps the
  pins on their countries.
- Clicking Italy's pin or "Serie A" in the list: address `#sports/serie-a`, trail
  "Sports / Football / Serie A" (the league page itself comes in Task 5).
- Leaving Sports stops the globe (no frames drawn while hidden: `sportsGlobe` not running).
- No console errors; no policy violations.

- [ ] **Step 6: Commit**

```bash
git add static/js/sports-football.js static/index.html static/css/space-sports.css tests/test_server.py
git commit -m "Sports stage 3: the league picker on the globe"
```

---

### Task 5: The league pages

**Files:**
- Modify: `static/js/sports-football.js`, `static/index.html` (`#sp-league`: the head, the
  status line `#sp-status` with `#sp-retry`, the panels `#sp-table`, `#sp-results`,
  `#sp-upcoming`, `#sp-team` (next match, form, fixtures), `#sp-cl`, `#sp-cup`, and the foot
  `#sp-credit`, `#sp-updated`), `static/css/space-sports.css` (panels; the themes
  `[data-theme="roma"]` dark red and gold, `[data-theme="newcastle"]` black, white and silver;
  the followed team's table row)
- Modify: `tests/football_data.py` (Newcastle's made-up season and a Premier League table and
  round, `newcastle_replies()`, for the demo)

**Interfaces:**
- Consumes: `POST /sports/league` → the stage 2 page dict, or `{detail}` with 503, 502 or 429.
- Produces, in `sports-football.js`:
  - Pure functions (checked in the browser with fixed inputs):
    `footballCountdown(match, now) -> string`: `"Live"` for live; `"Today 20:45"`,
    `"Tomorrow 20:45"`, else `"in N days"` (calendar days between local dates);
    `"Postponed"`, `"Suspended"`, `"Cancelled"` for those.
    `footballUpdatedText(updated, earlier, now) -> string`: with no earlier copy, `"Updated
    just now"` under a minute, `"Updated N min ago"` under an hour, else `"Updated at
    HH:MM"` (with `"Sat 7 Nov, "` before the time when not today); with an earlier copy,
    `"From HH:MM"` today or `"From Sat 7 Nov, HH:MM"`, then `" (couldn't reach the football
    data)"`.
    `footballScoreLine(match) -> string`: `"Roma 2–1 Lazio"` with a score, `"Roma v Lazio"`
    without. `footballGd(n) -> string`: `"+3"`, `"0"`, `"−2"`, `"–"` for null.
  - `sportsFootball.openLeague(slug)`: shows the page with "Loading" in every panel at once,
    sets `data-theme` (`roma`, `newcastle` or none) from the slug's followed team, and asks for
    the league **one request at a time**: if one is in flight, it only records the wanted
    slug, and when the reply comes, a reply for a slug no longer wanted is dropped and the
    wanted one is asked for. After 4 seconds still loading, `#sp-status` reads "Still waiting
    for the football data…".
  - Failure: `#sp-status` shows the server's `detail` (status 0: "Couldn't reach JARVIS."); Try
    again (`#sp-retry`) shown for every failure except 503.
  - Drawing (only `createElement` and `textContent`): the table (position, team, P, W, D, L, GD,
    Pts; the followed team's row marked); latest results ("Matchday N", score lines);
    upcoming (day, time, line, or its status); for a themed page the header ("Roma · 2nd ·
    27 pts"), the next match with `footballCountdown` and, when live, "Free scores arrive
    late", form as W/D/L markers whose `title` is the score line, fixtures (recent newest
    first, then coming, each tagged with its competition), the Champions League table when
    present, and the cup note; the foot: the credit and `footballUpdatedText`. Season not
    started: the table panel says "The season hasn't started."; no next match: "No match
    scheduled yet."; an empty latest round: "No results in the last 10 days."; an empty next
    round: "No matches in the next 10 days."
  - The countdown and the updated line re-drawn every 30 seconds while the league page is
    shown; the timer is cleared in `leave()` and when the level changes.

- [ ] **Step 1: Implement** the Interfaces items and the `tests/football_data.py` additions.

- [ ] **Step 2: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass (the scans cover the new code: no `innerHTML`, no inline style);
`All checks passed!`.

- [ ] **Step 3: Demo check, made-up data** (`--canned`; the launcher answers Serie A with
  `serie_a_replies(cl=True)`, the Premier League with `newcastle_replies()`, La Liga with the
  `PD_TABLE` and an empty round, the Bundesliga with HTTP 429, and Ligue 1 after a 6-second
  wait with a timeout)

- **The pure functions**, evaluated in the page with fixed inputs: each rule above gives its
  exact string, including `footballUpdatedText` across midnight.
- **Serie A**: Roma's header in dark red and gold, 3rd · 40 pts, the next match with its
  countdown, form D L W W L oldest first with the score in each marker's title, fixtures, the
  Champions League table, "The Coppa Italia isn't in the free data", the credit, "Updated just
  now".
- **Premier League**: Newcastle's theme; **La Liga**: no team panels, and the empty rounds read
  "No results in the last 10 days." and "No matches in the next 10 days."
- **Missing parts**: the page text contains none of "undefined", "null", "NaN".
- **One at a time**: click Serie A, then La Liga, then Serie A quickly: the network panel shows
  no two `/sports/league` requests overlapping, and the page ends on Serie A.
- **Leaving**: open Ligue 1 (slow) and press Esc at once: back on the picker; when the reply
  comes 6 s later nothing redraws and the address stays `#sports/football`. On a league page,
  switch to Home: the 30-second timer is cleared.
- **Failures**: Bundesliga: "Too many requests just now. Try again in a minute." with Try again;
  Ligue 1: "Loading", then "Still waiting for the football data…" at 4 s, then "Couldn't reach
  the football data." with Try again; `--nokey`: "Football needs a free key from
  football-data.org: see README" without Try again.
- **Reload** on `#sports/serie-a`: the Serie A page directly.
- No console errors; no policy violations.

- [ ] **Step 4: Demo check, live** (without `--canned`, the owner's key; about 8 requests)

Open Serie A and the Premier League once each. Expected: the real tables, Roma's and
Newcastle's real positions and next matches, matching what the live check of stage 2 saw.

- [ ] **Step 5: Commit**

```bash
git add static/js/sports-football.js static/index.html static/css/space-sports.css tests/football_data.py
git commit -m "Sports stage 3: the league pages"
```

---

### Task 6: Documentation

**Files:**
- Modify: `CLAUDE.md` (the `static/` row: `space-sports.js`, `sports-football.js`, the shared
  coastlines; `config.py`'s spaces; the architecture's spaces), `README.md` (using Sports: key
  4, the hub, the globe, Esc, the key), `SECURITY.md` (section 3: `/sports/league` in the
  endpoint list if missing), `CHANGELOG.md` (section 61 and Status), `plan.md`

- [ ] **Step 1: Update the documents.** CHANGELOG section 61, "Sports, stage 3: the page", in
  the style of sections 59 and 60: what you see, one request at a time, the states, the eval
  before and after with both hashes, the demo checks, and what was not checked (Safari, motion,
  JARVIS's tools).

- [ ] **Step 2: Full checks**

Run: `python -m pytest -q && ruff check .`
Expected: all pass; `All checks passed!`.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md README.md SECURITY.md CHANGELOG.md plan.md
git commit -m "Document Sports stage 3 (CHANGELOG section 61)"
```
