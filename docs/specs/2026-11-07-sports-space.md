# The Sports space, and one shared door to the internet

Status: design agreed with the owner in conversation on 2026-11-03 (paused) and 2026-11-07.
Not built. Builds on `docs/specs/2026-10-27-spaces-and-work.md` (spaces, `registerSpace`) and
`docs/specs/2026-11-05-weather-space.md` (outside data, the globe, the privacy rule).

## Why

Sports is the fourth space: the owner's football teams, and later other sports, on one page
JARVIS can also talk about. It is the second outside service, after Weather, so it is also the
moment to give JARVIS one shared door to the internet instead of one per service.

## What the owner asked for

- A Sports hub with the sports' balls floating around: a football, a basketball, an American
  football, a baseball, and a tyre for F1. Click one to open that sport.
- Football opens a second level where you pick a league: Premier League, Serie A, La Liga,
  Bundesliga, Ligue 1.
- Serie A is themed for AS Roma, the Premier League for Newcastle United. La Liga, the
  Bundesliga and Ligue 1 are general: standings and match results.
- F1, NBA and NFL general for now (an F1 team is still to be chosen). Baseball added to the hub
  on 2026-11-07 (taken to mean MLB, general).
- Animations in the spirit of the Weather globe: pick the football and a silhouette kicks it;
  the ball flies and lands on the league's country (Serie A in Italy). Later: a silhouette
  dribbles and shoots (NBA), catches and throws (NFL), and an F1 car drives across the screen.
- Ask JARVIS about it out loud.

## Decisions

| Question | Decision | Why |
|---|---|---|
| Data for football | football-data.org, free plan, key in `.env` | Free plan covers all five leagues and the Champions League (decided 2026-11-03). |
| What the first build holds | The hub, Football and its five league pages. F1, NBA, NFL and MLB float on the hub and say "coming soon". | Each other sport needs its own data source, terms and agreement; each comes as its own build, with its animation. |
| How you pick a league | On the globe: click a country, then the kick lands there | The kick always lands somewhere meaningful; the globe is the picker. |
| F1's object on the hub | A tyre; its transition (later) is a car driving across | Round like the balls; the car is the one animation with no poses. |
| Themed page | The general page plus the team's header, next match with countdown, form, the team's fixtures, its other competitions, club colours | Owner agreed the recommendation. |
| JARVIS | Answers about Roma, Newcastle and the five leagues; opens a league, with its animation, only when asked to show one | Same rule as every space: the screen changes only when asked (eval `space_weather_mentioned_no_switch`). |
| Code shape | One `sports` space with levels inside it (hub, football, league); each sport registers itself | Adding F1 later is a new file and a registration, not a rebuild. |
| The door to the internet | One shared module, `outside.py`, for Weather and Football | One place where JARVIS goes online, one place to check. Owner's agreement 2026-11-07 (it moves a security control). |
| Silhouette quality | Code-drawn: a jointed body model, about 12 key poses per animation, smooth curves between them | A throwaway test (2026-11-07) was judged good enough by the owner. No images, so the security policy is unchanged. |
| Crests and logos | None; club colours instead | Logos need permission. |

## The privacy rule, and what Football sends

The rule (`SECURITY.md` section 5) is unchanged: nothing personal leaves the Mac unencrypted;
public data may be fetched over HTTPS from a short list of fixed addresses written in code,
carrying only what the service needs; the model never chooses the address.

What a football request sends, to football-data.org only: the key (in the `X-Auth-Token`
header), a competition code (`SA`) or a team id, and a date range. With it, as with every
website, the Mac's IP address. Nothing from the calendar, tasks, notes or conversation. The
owner agreed to this on 2026-11-07.

What is new compared with Weather: **the key links the requests to the owner's football-data.org
account**, and so to the email used to sign up. football-data.org can therefore see which
leagues and teams the account looks at, and when. Accepted as low risk (it is public sports
data and a stated interest in two clubs); `SECURITY.md` section 7 records it.

## Version 1: what is in it

### How it works, end to end

1. Key 4, the space chip, `#sports`, or "open sports" opens the hub: five objects drift slowly
   and tilt. Hovering grows one a little and shows its name. Clicking the basketball, the
   American football, the baseball or the tyre shows "NBA: coming soon" (and so on) for a
   moment and changes nothing else.
2. Clicking the football: it flies to the middle and grows into the globe (about 0.7 s) while
   the others fade. The globe (Weather's code) turns to Europe and marks five countries:
   England, France, Spain, Germany, Italy, each labelled with its league.
3. Clicking a country: a silhouette runs in from the bottom left and kicks; the ball arcs to
   that country, shrinking as it goes, bounces once with a ripple, and the league page fades
   in (about 2.3 s in all). The page's data is fetched as the kick starts, so it is usually
   ready when the animation ends; if not, the panels say "Loading".
4. Esc or the Back button goes up one level: league page, globe, hub. A trail at the top shows
   where you are ("Sports / Football / Serie A"). The address follows each level: `#sports`,
   `#sports/football`, `#sports/serie-a`; reload or the browser's Back keeps the place.
5. "Show me Serie A" from anywhere: JARVIS opens Sports straight at the globe and plays the
   kick, as if clicked.

### Animations

- Each plays about 0.7 s (football to globe) or 2.3 s (the kick). A click or Esc during one
  skips to its end (so Esc then means "skip", not "back").
- Reduce motion (the system setting or JARVIS's own): every animation becomes a short fade.
- Every animation has a safety timeout (as `globe.js` and `motion.js` do): if frames stop
  (a hidden pane, a slow Mac), the end state is drawn anyway. Nothing animates while the page
  is hidden.
- The silhouette is JARVIS's pale cyan with its glow, far limbs dimmer than near ones. Its
  body model, poses and timing come from the 2026-11-07 test: limbs keep their lengths, the
  lowest foot always touches the floor, about 12 key poses joined by Catmull-Rom curves.
- The ball: shaded, with panels, a short squash at the strike, spin, a trail, a floor shadow
  that fades as it rises, one bounce and a ripple on landing.

### The league pages

Every page ends with the credit line "Football data provided by the Football-Data.org API"
(kept as a courtesy: the terms page could not be read on 2026-11-07, see Risks) and "Updated
3 min ago" (or "From 14:05" when showing an earlier copy, see When something goes wrong).

**General page** (La Liga, Bundesliga, Ligue 1, and the base of the themed pages):
- The table: position, team, played, won, drawn, lost, goal difference, points. All teams;
  it scrolls inside its panel.
- The latest results: the most recent round (matchday) with finished matches, with scores.
- Upcoming: the next round, with date and kick-off time in the Mac's local time.

**Themed page** (Serie A for Roma, Premier League for Newcastle), adding:
- A header in the club's colours: the team, its position and points ("3rd · 24 pts").
- The next match: opponent, home or away, competition, date and time, and a countdown ("in 3
  days", then "Today 20:45"). During a match: "Live" and the score, with "Free scores arrive
  late" (the free plan delays scores; football-data.org does not say by how much).
- Form: the last 5 finished matches in all competitions as W, D or L, newest on the right;
  hovering one shows the opponent and score.
- The team's fixtures: the last 5 results and the next 5 matches, each tagged with its
  competition.
- Other competitions: if the team has Champions League matches, the Champions League table
  with the team lit. One quiet line names the cups the free plan lacks ("The Coppa Italia
  isn't in the free data", "The FA Cup isn't in the free data").
- Theme: Roma dark red and gold; Newcastle black and white with a silver accent (so it shows
  on the dark page). The glass stays; only accent colours change. The team's table row is lit.

Not in version 1: zone markings in the table (European places, relegation), which differ by
league and season; player data (not on the free plan).

## How it works

### Files

| File | What it holds |
|---|---|
| `outside.py` (new) | The one door to the internet: `_fetch`, `get`, the refused redirects, truststore, the size and time limits, the rate guard, the log line. Moved from `weather.py`. |
| `weather.py` | Calls `outside.get`; its behaviour, messages and tests are unchanged. |
| `football.py` (new) | The key, the football requests, safe reading, the summaries, the cache and the earlier copy, the tools `show_league`, `get_league`, `get_team`. |
| `config.py` | The settings below; `"sports"` added to `SPACES`; `ENV_FILE`. |
| `tools.py` | `ShowLeague(league, reply)`: a tool result that changes only the view, like `ShowPlaces`. |
| `brain.py` | `import football` after `weather` (its tools come last). `run_tool` handles `ShowLeague`; `chat_stream` streams the `league` event. |
| `server.py` | `POST /sports/league`. |
| `static/js/spaces.js` | An address like `#sports/serie-a` opens the `sports` space (the part before `/`); the space reads the rest. |
| `static/js/globe.js` | The coastlines are loaded once here and shared, so Weather's globe and Sports' globe use one copy (moved from `space-weather.js`). |
| `static/js/space-sports.js` (new) | `registerSpace` for Sports (key 4): the levels, the hub, the league picker on the globe, the league pages, the trail, Esc. Talks only to `/sports/...`. Each sport registers with `registerSport({name, title, object, ready})`. |
| `static/js/sports-kick.js` (new) | The body model, the kick's key poses and timing, the ball's flight. Pure functions (`poseAt(t)`, `skeleton(pose)`, `ballAt(t)`) plus drawing. |
| `static/css/space-sports.css` (new) | Layout, glass, and the themes (`data-theme="roma"`, `"newcastle"`). |
| `static/index.html` | The Sports section and the new files, in order. |
| `tests/football_data.py` (new) | Made-up replies shaped like football-data.org's (from its docs, read 2026-11-07), and `serve`. |

### Settings (`config.py`)

| Setting | Value |
|---|---|
| `ENV_FILE` | `.env` in the project folder; the `JARVIS_ENV` environment variable overrides it (tests point it at nothing) |
| `FOOTBALL_LEAGUES` | slug → competition code, name, country, globe position: `premier-league` PL England (52.5, −1.5); `serie-a` SA Italy (42.8, 12.5); `la-liga` PD Spain (40.2, −3.7); `bundesliga` BL1 Germany (51.2, 10.4); `ligue-1` FL1 France (46.6, 2.4) |
| `FOOTBALL_TEAMS` | `roma`: id 100, league `serie-a`, cup note "The Coppa Italia isn't in the free data"; `newcastle`: id 67, league `premier-league`, cup note "The FA Cup isn't in the free data". The ids are from memory of the API and are confirmed against a real reply in stage 2 before anything relies on them. |
| `FOOTBALL_ADDRESSES` | Built from three templates and the fixed codes above: `https://api.football-data.org/v4/competitions/{code}/standings` for the five leagues and `CL`; `.../competitions/{code}/matches` for the five leagues; `.../teams/{id}/matches` for the two teams (which includes their Champions League matches). 13 addresses in all. |
| `FOOTBALL_REQUESTS_PER_MINUTE` | 9 (the plan allows 10; one spare for clock differences) |
| `FOOTBALL_CACHE_SECONDS` | 600 |
| `FOOTBALL_LIVE_CACHE_SECONDS` | 120 (while a match in the reply is live) |
| `FOOTBALL_EARLIER_COPY_SECONDS` | 21,600 (6 hours: an earlier copy shown when the service fails) |
| `FOOTBALL_CACHE_ENTRIES` | 30 |
| `FOOTBALL_NAME_MAX` | 40 characters (each team or competition name) |
| `FOOTBALL_WINDOW_DAYS` | 10 (a league's matches: today ± 10 days); 60 for a team's |
| `OUTSIDE_TIMEOUT_SECONDS`, `OUTSIDE_MAX_BYTES` | 5 and 1,000,000: Weather's limits, renamed now that they are shared |

### The shared door (`outside.py`)

Weather's rules, moved unchanged, plus what football needs:

- `get(address, params, headers=None) -> dict`. `address` must be one of
  `outside.ADDRESSES` (Weather's three plus `FOOTBALL_ADDRESSES`), else `ValueError`. Code adds
  the query with `urlencode`. HTTPS only. Redirects refused. truststore, both checks on.
  5 seconds, 1 MB, JSON objects only, NaN and Infinity refused.
- `_fetch(address, headers)` is the one function that touches the network. Tests replace it.
- Failures become `OutsideError(kind)`: `"unreachable"` (no answer, a timeout, a broken
  reply, a 5xx), `"refused"` (HTTP 400, 401 or 403: the key was not accepted), `"busy"`
  (HTTP 429, or the rate guard).
- **The rate guard**: per host, at most `FOOTBALL_REQUESTS_PER_MINUTE` requests in any 60
  seconds for football-data.org; the next is refused *before* it is sent (`"busy"`).
  Open-Meteo has no guard (none needed today).
- The log line: host, outcome and milliseconds, as now. Never the address, never a header.
- `weather.py` keeps `WeatherError` and its messages: it catches `OutsideError` and raises
  `WeatherError(UNREACHABLE)`, so nothing Weather says changes.

### The key

- `football._key()` reads `FOOTBALL_DATA_KEY` from the environment, else from `ENV_FILE`
  (lines `NAME=value`; `#` comments and blank lines skipped), when first needed. A key must be
  10 to 64 letters and digits, else it counts as missing.
- It goes only into the `X-Auth-Token` header of a request to a football address. Never into
  a log line, an error message, a reply to the page, a tool result, or the model's input
  (pinned by a test that searches all of them for a known test key).
- No key: the page shows "Football needs a free key from football-data.org: see README"; the
  tools return "Error: football needs a free key. The owner can add one (README)."

### Reading replies, and worked out in code

- Every value is read as a real number, cleaned text (control characters removed, at most 40
  characters), a valid date and time, or treated as missing, with the helpers Weather uses
  (`_num`, `_text`, `_obj`, `clean`). Raw reply text never reaches the page or the model.
- Times: `utcDate` (UTC) to the Mac's local date, weekday and 24-hour time
  (`datetime.astimezone()`); tests fix the zone, including the end of summer time.
- Positions in words ("3rd"); points; goal difference with its sign.
- Form: the team's last 5 finished matches in any competition: W, D or L from the score and
  which side the team was on.
- Next match: the earliest `SCHEDULED` or `TIMED` match; a match `IN_PLAY`, `PAUSED`,
  `EXTRA_TIME` or `PENALTY_SHOOTOUT` is "Live"; `POSTPONED`, `SUSPENDED` and `CANCELLED` are
  shown as such; `AWARDED` counts as a result.
- Latest results: the most recent matchday in the window with finished matches. Upcoming: the
  next matchday with scheduled ones.
- The table: the `TOTAL` standing. Empty, or no games played: "The season hasn't started."
- No next match in the window: "No match scheduled yet."

### Requests, the cache and the earlier copy

- A general page: 2 requests (standings, the league's matches for today ± 10 days). A themed
  page adds the team's matches (today ± 60 days) and, only if those include Champions League
  matches, the Champions League standings: at most 4.
- Each reply is kept in memory 10 minutes (2 while it holds a live match). At most 30 entries.
- An earlier copy of each is kept up to 6 hours. If a request fails and an earlier copy exists,
  the page and the tools use it, marked with its time ("From 14:05").
- All in memory: nothing in `jarvis.db`, nothing in backups, no schema change.

### Endpoint

**`POST /sports/league`** `{league}`: one of the five slugs, else 422. POST, though it only
reads, so the `Origin` check and the `text/plain` refusal cover every request that goes online.
Returns the page's data: the league, the table rows, latest results, upcoming fixtures, and for
a themed league the team block (position, points, next match, form, fixtures, Champions League
rows or none, the cup note), plus `updated` and `earlier` (the time of an earlier copy, or
null). Failures: no key 503, key refused 502, busy 429, unreachable with no earlier copy 502,
each with a plain `detail`.

### The tools

Registered last (`import football` after `weather` in `brain.py`). The model only picks from
fixed names (an enum in each schema); it never gives an address, id or date.

- **`show_league(league)`**: Premier League, Serie A, La Liga, Bundesliga, Ligue 1. Returns
  `ShowLeague`; the page opens Sports at the globe and plays the kick. The model sees "Opened
  Serie A on the screen."
- **`get_league(league)`**: facts written by code: the top four with points, the followed
  team's place if the league has one, the latest round's results and the next round's
  fixtures, with dates and local times in words.
- **`get_team(team)`**: Roma or Newcastle. Position and points, the last result, the next
  match ("Next: Roma v Lazio, Sunday 9 November at 20:45, Serie A"), form in words, and the
  Champions League place if any.
- Errors: "Error: football needs a free key. ...", "Error: the football data key was refused.",
  "Error: too many football requests just now. Try again in a minute.", "Error: couldn't reach
  the football data." An earlier copy is used with its time stated ("as of 14:05").
- Ticker lines: "Opened Serie A", "Checked La Liga", "Checked Roma".
- No confirmation card: they change nothing.

### Chat events

`league` is new, streamed straight after `show_league`'s step: `{"type": "league", "league":
"serie-a"}`. It is sent before the `space` event (`"sports"`), as `places` is before Weather's,
so the page knows the league before the space opens (with Reduce motion or "open on home" there
is no wait to cover a late event; CHANGELOG section 58).

### When something goes wrong

- No key, key refused, busy, unreachable: the plain messages above, in place of the panels,
  with a Try again button (not for no key). An earlier copy is shown instead when there is one.
- Nothing else in JARVIS waits on football: a slow reply holds only its own page.
- An address that is not a level or league (`#sports/xyz`): the hub.
- An animation that stalls: its safety timeout draws the end. The space's own code failing never
  stops a switch (`runSafely`).

## Security and privacy

- Unchanged: the server on 127.0.0.1, `TrustedHostMiddleware`, the `Origin` check, the
  `text/plain` refusal, the Content Security Policy (canvas drawing only, no images, no inline
  code), the confirmation path (no Sports tool changes anything).
- Changed, with the owner's agreement: the door to the internet moves to `outside.py`;
  football-data.org's 13 addresses join the list; requests may carry a header (the key).
- `SECURITY.md`: section 3 (the door), section 4 (controls), section 5 a new "Outside data:
  Football" (what goes out, the key and the account link, what football-data.org sees),
  section 7 (the account link, accepted). `CLAUDE.md`: architecture, the boundary line
  "Outside requests go only through `outside.get`", the tool order.
- Outside text: team and competition names (cleaned, at most 40 characters) and numbers reach
  the page and the model; nothing longer. News stays out until its own prompt-injection design.

## Testing

pytest, with no internet and no real key (`conftest.py`'s `no_internet` now replaces
`outside._fetch`, and `JARVIS_ENV` points at nothing):

- **The door**: only listed addresses; HTTPS only; redirects refused; size and time limits;
  the log has host and outcome only; `OutsideError` kinds from 400/401/403, 429, 5xx, timeouts
  and broken JSON; the rate guard refuses the 10th football request within 60 seconds without
  calling `_fetch`, and allows it after the minute.
- **Weather unchanged**: every existing Weather test and eval passes with only its hook moved
  (`_fetch`'s new signature).
- **The key**: read from the environment and from a file; bad format counts as missing; a
  known test key appears in the header and nowhere else (log, errors, endpoint replies, tool
  results, the model's messages).
- **Reading replies**: `tests/football_data.py` with good and broken replies: wrong types,
  missing fields, NaN, very long and control-character names, unknown statuses.
- **Summaries**: form, next match, live, postponed, latest round, upcoming round, the season
  not started, local times across the end of summer time.
- **Cache and earlier copy**: kept 10 minutes, 2 when live; an earlier copy used on failure and
  labelled; nothing kept past 6 hours.
- **Endpoint**: each league; themed and general; `Origin`; `text/plain`; unknown league; each
  failure's status and `detail`.
- **Tools and events**: enums; errors; `league` before `space`; ticker lines; tool order.
- **Page**: no JavaScript test runner (the owner's decision, 2026-11-05). Logic stays in small
  functions; the CSP scans keep running; each stage is checked in a demo with a CSP violation
  listener, then by the owner in Safari.

### Evals

About 8 new cases, offline through `tests/football_data.py`'s canned replies, as Weather's:
"When do Roma play next?" (`get_team`), "How did Newcastle do at the weekend?" (`get_team`),
"Who's top of La Liga?" (`get_league`), "Where are Roma in the table?" (`get_team` or
`get_league`), "Show me the Bundesliga" (`show_league`), a league mentioned with no request to
show it (no `show_league`), a team JARVIS does not follow ("How did Juventus do?": `get_league`,
no made-up score), "open sports" (`open_space`). A full eval before and after, with both scores
and the prompt hashes in the commit message.

## Build order

One branch per stage; each merged when CI is green and the owner has checked it.

1. **The shared door.** `outside.py`, Weather moved onto it unchanged, football-data.org's
   addresses, the key reading, the rate guard. `SECURITY.md` and `CLAUDE.md` updated. A
   security change, so it stands alone, and Weather's tests prove nothing changed.
2. **The football server.** `football.py` (requests, reading, summaries, cache, earlier copy),
   `POST /sports/league`, `tests/football_data.py`. The team ids confirmed against a real
   reply, with the owner's key, before they are relied on.
3. **The page.** Space 4, the hub (objects still, "coming soon"), the globe as the league
   picker, the league pages and themes, the trail, Esc, the addresses. Transitions are plain
   fades.
4. **The animations.** The floating objects, football to globe, the silhouette kick and the
   ball's flight and landing.
5. **JARVIS.** `show_league`, `get_league`, `get_team`, the `league` event, the eval cases, a
   full eval before and after.

Later, each its own design and build: F1 (a team to be chosen; the car), NBA (dribble and
shoot), NFL (catch and throw), MLB. Each needs its own data source, terms and the owner's
agreement before anything is fetched.

## Risks

- **The free plan changes** (competitions, limits, delays). The pages say what is missing
  rather than failing.
- **The credit wording**: remembered from the 2026-11-03 reading; on 2026-11-07 the terms page
  answered 404 and the docs state no credit rule. The line stays as a courtesy; recheck before
  stage 3.
- **Team ids** (Roma 100, Newcastle 67) are from memory; stage 2 confirms them first.
- **Browsing many leagues quickly** can reach the rate guard (a general page costs 2 requests,
  a themed one up to 4). The page says "Try again in a minute"; pages seen in the last 10
  minutes cost nothing.
- **Delayed scores**: the free plan is not live. The page says so during a match.
- **The animation's quality** is stylised by design (the test was judged good enough); more
  lifelike motion would need recorded motion or drawn frames, which JARVIS does not have.
- **Two globes** on one page (Weather's and Sports') share the coastlines; each draws only when
  its space is shown.
