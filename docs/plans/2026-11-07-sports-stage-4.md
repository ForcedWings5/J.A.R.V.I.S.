# Sports, stage 4: the animations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Sports space moves: the hub's five objects float, the football flies to the
middle and grows into the globe, and clicking a country plays the silhouette's kick, the ball
landing on that country before its league page fades in.

**Architecture:** Three animations, each a plain object `{ done, skip(), cancel() }` held in
one place (`sportsAnim` in `space-sports.js`), so a click or Esc skips whatever is playing and
leaving the space cancels it. The float is CSS only. The football's flight is a temporary
canvas moved with the Web Animations API, as `motion.js` moves its frames. The kick is a new
file, `sports-kick.js`: the body model and timing from the 2026-11-07 test as pure functions
(`kickMath.poseAt`, `skeleton`, `ballAt`), and a runner that draws them on a canvas laid over
the globe. The league's data is asked for as the kick starts. No server change, no prompt
change, so no eval.

**Tech Stack:** Plain JavaScript (no build step, shared globals, scripts in order), CSS,
canvas 2D, the Web Animations API, pytest for what Python can pin, the browser pane for the
rest.

**Spec:** `docs/specs/2026-11-07-sports-space.md` (sections "How it works, end to end" 1 to 3,
"Animations", "Files" (`sports-kick.js`), "When something goes wrong" (an animation that
stalls), "Build order" stage 4).

## Global Constraints

- Branch `sports-stage-4` from `main` (`f51bffa`). Commit after each task. Never on `main`. Do
  not push.
- Timing (spec): football to globe about 0.7 s; the kick about 2.3 s in all. The kick's poses
  and timing are the test's, unchanged: 12 key poses, gaps
  `[105, 105, 105, 125, 140, 90, 55, 90, 140, 170, 220]` ms, the strike at key pose 7
  (725 ms), the flight 1100 ms (lands at 1825 ms), one hop 300 ms, the page at 2300 ms.
- A click inside the Sports space or Esc during an animation skips to its end (Esc then means
  "skip", not "back"). Leaving the space, the browser's Back button or a new address cancels
  it: nothing is drawn late and nothing is left on screen.
- Reduce motion (`globeCalm()`: JARVIS's own setting or the system's): no float, no flight, no
  kick; every change is a short fade (0.2 s opacity). The hub's objects stay still (stage 3).
- Every animation has a safety timeout: if frames stop (a hidden pane, a slow Mac), its end
  state is drawn anyway. Nothing draws while the page is hidden (`requestAnimationFrame` does
  not run then).
- The silhouette: the test's colours (near limbs `#e3f7ff`, body `#cdeffa`, far limbs
  `#5f8a9c`, glow `rgba(76,201,240,.55)`, the far side's glow `.25`); limbs keep their
  lengths; the lowest foot touches the floor unless the pose is in the air.
- The Content Security Policy is unchanged: no inline scripts or styles, no `style=` or
  `on...=` in `index.html`, no `setAttribute('style'`. Positions and sizes set from JS go
  through the CSSOM (`el.style.left`) or `el.animate(...)`, as `motion.js` does.
- The page talks only to JARVIS (`POST /sports/league`), one football request at a time
  (stage 3's rule); the kick never adds a second request for the same league.
- Demos: their own database, backups and log, port 8016 (check `lsof -iTCP:8000 -sTCP:LISTEN`
  first; the owner's JARVIS reloads on file changes). Launcher: copy stage 3's
  (scratchpad `demo4/run_demo.py`) to a new `demo5/` and run it with `--canned`. A
  `securitypolicyviolation` listener stays on in every demo. No live football requests in
  this stage.

## Review Focus

1. **Leaving during an animation** (key 1, a space chip, the browser's Back button mid-kick or
   mid-flight): no league page drawn late, no flying canvas or kick canvas left on screen, the
   hub's objects not left faded, the address where you went. Pinned by Task 2's demo step
   "Leaving" and Task 4's demo step "Leaving".
2. **Clicking again or pressing Esc during an animation** (a second pin, the same pin, the
   football twice, the trail): skips to the end; never a second kick, a second flight or a
   second request; the next Esc goes up one level. Pinned by Task 2's "Skipping" and Task 4's
   "Skipping".
3. **Frames that stop** (a hidden pane, a slow Mac): the safety timeout shows the picker or the
   league page anyway. Pinned by the "No frames" steps in Tasks 2 and 4 (frames stubbed out).
4. **The data and the kick out of step** (the reply before landing, after landing, a failure,
   a 6-second wait): the page shows the data, "Loading", the server's message or "Still
   waiting…"; a reply that arrives during the kick is not dropped. Pinned by Task 4's "Data".
5. **Reduce motion, and the window resized mid-kick**: no motion with Reduce motion, only the
   short fade; after a resize the ball still lands on the country's pin. Pinned by Task 1's
   "Reduce motion", Task 4's "Reduce motion" and "Resize".

---

### Task 1: The hub floats

**Files:**
- Modify: `static/css/space-sports.css`
- Test: `tests/test_server.py`

**Interfaces:**
- Produces: the CSS class `sp-picking` on `#sp-hub` fades every object but the one with
  `sp-chosen` (opacity 0 over 0.2 s); Task 2 sets both.

- [ ] **Step 1: Write the failing test**

```python
def test_the_hub_floats_only_with_motion():
    """The objects drift (stage 4), but never with Reduce motion, JARVIS's or the system's."""
    css = (ROOT / "static" / "css" / "space-sports.css").read_text()
    assert "@keyframes sp-drift" in css
    assert re.search(r"body\.reduce [^{]*\.sp-object[^{]*\{[^}]*animation:\s*none", css)
    reduced = css[css.index("@media (prefers-reduced-motion: reduce)"):]
    assert re.search(r"\.sp-object[^{]*\{[^}]*animation:\s*none", reduced)
```

- [ ] **Step 2: Run it to see it fail**

Run: `python -m pytest -q tests/test_server.py -k floats`
Expected: FAIL (no `sp-drift`).

- [ ] **Step 3: Implement** in `space-sports.css`:
- `@keyframes sp-drift`: a slow loop of `transform: translate(...) rotate(...)`, at most 12 px
  of travel and 3 degrees of tilt. Each of the five `.sp-object:nth-child(n)` gets its own
  duration between 6 and 9 s and a negative delay, so no two move together.
- Hover and keyboard focus grow an object with the separate `scale` property (`scale:1.06`,
  `transition: scale .2s ease`), so it does not fight the drift's `transform`.
- `.sp-picking .sp-object:not(.sp-chosen) { opacity:0; transition:opacity .2s ease; }`.
- Reduce motion: `.sp-object` gets `animation:none` under `body.reduce` and under the
  `prefers-reduced-motion` query. The level fade becomes `animation: sp-in .2s ease` there
  instead of `none` (spec: "every animation becomes a short fade"; stage 3 had no fade at
  all).
- The file's header comment: stage 4 adds the motion (no longer "stage 4 adds the motion").

- [ ] **Step 4: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass (816 before, plus this one); `All checks passed!`.

- [ ] **Step 5: Demo**

Launcher as in Global Constraints, open `http://127.0.0.1:8016/#sports`. Expected:
- The five objects drift out of step and keep turning; hovering one grows it a little.
- **Reduce motion**: JARVIS's own setting on: the objects stand still, no drift; with it off
  again they drift. No console errors, no policy violations.

- [ ] **Step 6: Commit**

```bash
git add static/css/space-sports.css tests/test_server.py
git commit -m "Sports stage 4: the hub's objects float"
```

---

### Task 2: The football grows into the globe

**Files:**
- Modify: `static/js/space-sports.js`, `static/css/space-sports.css`

**Interfaces:**
- Consumes: `sp-picking` and `sp-chosen` (Task 1); `drawSportObject(canvas, name, seconds)`
  (`sports-objects.js`); `globeCalm()` (`globe.js`).
- Produces, in `space-sports.js`:
  - `let sportsAnim = null` — the animation playing: `{ done: Promise<boolean>, skip(),
    cancel() }`. `done` resolves `true` when it ends or is skipped, `false` when cancelled.
  - `sportsPlay(anim, then)` — holds `anim` in `sportsAnim`; when `done` resolves `true` and
    `anim` is still the one held, clears `sportsAnim` and calls `then()`; when `false`, only
    clears it.
  - `sportsSkip() -> boolean` — skips the one playing; `false` if none.
  - `sportsCancelAnim()` — cancels the one playing, if any.
  - `sportsGrow(button) -> anim` — the flight below.
- `sportsGo` does **not** cancel animations (the flight itself calls it halfway). The three
  ways in from outside cancel first: `registerSpace`'s `enter()` and `leave()`, and
  `sportsFollowAddress()`.

- [ ] **Step 1: Implement the holder and the skip**
- `sportsPlay`, `sportsSkip`, `sportsCancelAnim` as above.
- A click listener on `sportsSection` in the capture phase: while `sportsAnim` is set, it
  stops the click (`stopPropagation`, `preventDefault`) and skips. So a second click on a pin,
  the football or the trail never starts anything new.
- The Esc listener: after its `seq` and typing checks, if `sportsSkip()` returns `true` it
  calls `preventDefault()` and stops there; otherwise it goes up one level as before.
- `enter()`, `leave()` and `sportsFollowAddress()` call `sportsCancelAnim()` first.

- [ ] **Step 2: Implement `sportsGrow(button)`**

The football button's click calls `sportsPlay(sportsGrow(button), () => {})` instead of
`sportsGo('football')`, unless `globeCalm()`, when it calls `sportsGo('football')` as now.
The flight (about 0.7 s):
1. 0 to 200 ms: `#sp-hub` gets `sp-picking`, the button `sp-chosen`. The button's own canvas is
   hidden (`visibility:hidden`) and a temporary canvas (`.sp-flyer`: `position:fixed`,
   `pointer-events:none`, `aria-hidden`, appended to `body`) is placed exactly over it and
   drawn with `drawSportObject(flyer, 'football', seconds)` every frame, so it keeps turning.
2. At 200 ms: the section gets `sp-arriving` (CSS: `.sp-arriving .sp-picker { opacity:0;
   animation:none; }`) and `sportsGo('football')` runs (the address, the trail, the globe).
3. 200 to 700 ms: the flyer moves from its place to a square centred on `.sp-globe-wrap`, as
   wide as the wrap's shorter side, with `flyer.animate` on `left`, `top`, `width`, `height`
   (500 ms, `cubic-bezier(.2,.8,.2,1)`), fading to 0 over its last 30%.
4. The end: the flyer is removed, `sp-picking`, `sp-chosen`, `sp-arriving` and the hidden
   canvas are undone. Removing `sp-arriving` restarts the picker's own `sp-in` fade, which is
   the globe appearing.

The safety timeout: each wait races a `setTimeout` (the 200 ms one is a timeout already; the
flight races 900 ms), as `motion.js` does. `skip()` jumps to step 4 (doing step 2 first if it
has not run). `cancel()` removes the flyer and the classes and does not run step 2.

- [ ] **Step 3: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass (the CSP scans and the element test cover the script); `All checks
passed!`.

- [ ] **Step 4: Demo**

Expected, at `#sports`:
- Clicking the football: the others fade, the football flies to the globe's place and grows
  as the globe of Europe fades in, about 0.7 s; the address is `#sports/football`; the trail
  reads "Sports / Football".
- **Skipping**: click again, or press Esc, during the flight: the picker shows at once, no
  flyer left. The next Esc goes back to the hub, where all five objects show (none faded).
- **Leaving**: press 1 during the flight: Home, no flyer left on screen; key 4 then opens the
  hub with all five objects showing.
- **No frames**: in the console, `window.requestAnimationFrame = () => 0` (then reload after):
  clicking the football still shows the picker within a second.
- **Reduce motion**: the picker fades in (0.2 s), no flyer.
- No console errors, no policy violations.

- [ ] **Step 5: Commit**

```bash
git add static/js/space-sports.js static/css/space-sports.css
git commit -m "Sports stage 4: the football grows into the globe"
```

---

### Task 3: The kick (`sports-kick.js`)

**Files:**
- Create: `static/js/sports-kick.js`
- Modify: `static/js/sports-objects.js` (one function split), `static/index.html` (the kick
  canvas and the script), `static/css/space-sports.css`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `drawSportAt` (below).
- Produces:
  - In `sports-objects.js`: `drawSportAt(ctx, name, seconds, cx, cy, R)`, the drawing that
    `drawSportObject` did after sizing its canvas, so the kicked ball is the hub's 3D football.
    `drawSportObject` calls it; the hub looks the same.
  - In `sports-kick.js`:
    - `KICK = { LEN, KEYS, GAPS, STRIKE, FIELDS, TIMES, STRIKE_MS: 725, FIGURE_MS: 1345,
      FLY_MS: 1100, LAND_MS: 1825, HOP_MS: 300, END_MS: 2300, BALL: 11 }`. `LEN`, `KEYS`,
      `GAPS`, `STRIKE`, `FIELDS` are copied from the test (scratchpad
      `kick-test/index.html`, lines 26 to 51); `TIMES`, `STRIKE_MS`, `FIGURE_MS`, `LAND_MS`
      are worked out from them. `BALL` is the ball's radius in model units.
    - `kickMath.poseAt(t) -> pose` and `kickMath.skeleton(pose) -> joints`: the test's
      functions, unchanged (Catmull-Rom between key poses; the lowest foot on the floor,
      `y = 0`, raised by `air`). Joints: `hip, chest, neck, head, sh, n, f, na, fa` as in the
      test.
    - `kickMath.layout(w, h) -> { s, ox, gy }`: model units to canvas pixels, as the test's
      `layout()` (`s = min(h/430, w/820)`, `ox = w*0.08`, `gy = h*0.8`).
    - `kickMath.ballAt(t, path) -> { x, y, scale, spin, squash }`, with `path = { from, to,
      peak, hop }` in canvas pixels (`from` and `to` are `[x, y]`; `peak` is the arc's control
      point's height; `hop` the bounce's height). Before the strike: at `from`, scale 1. In
      flight: the test's quadratic curve with easing `1 - (1-p)^1.7`, scale 1 to 0.5, spin
      `p*14`, squash 0.8 for the first 6%. After landing: at `to`, scale 0.5, one hop of
      `hop` pixels over `HOP_MS`, squash 0.75 for its first 12%.
    - `drawKick(canvas, t, target)`: one frame. `target()` returns the country's point in the
      canvas's CSS pixels, read every frame so a resize follows the pin. Draws the floor line,
      the figure and its shadow (fading over 500 ms after `FIGURE_MS`), the ball with
      `drawSportAt` (squash by scaling about its centre), its trail (12 earlier positions from
      `ballAt(t - 16*k)` during flight, no stored state), its floor shadow fading as it rises,
      and the ripple at the landing. `peak = max(radius, min(from.y, to.y) - h*0.38)`;
      `hop = 8*s`.
    - `playKick(canvas, target) -> { done, skip(), cancel() }` (Task 2's shape): shows the
      canvas, draws `drawKick` each frame from 0 to `END_MS`, then hides and clears it and
      resolves `true`. Safety timeout `END_MS + 400`. `skip()` ends at once (`true`);
      `cancel()` ends at once (`false`). A canvas with no size resolves `true` at once.
- In `index.html`: `<canvas id="sp-kick" class="sp-kick" aria-hidden="true" hidden></canvas>`
  inside `.sp-globe-wrap`, after `#sp-pins`; `sports-kick.js` loaded after
  `sports-objects.js`, before `space-sports.js`. CSS: `.sp-kick` covers the wrap (`position:
  absolute; inset:0; width:100%; height:100%; pointer-events:none`), `.sp-kick[hidden] {
  display:none; }`.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_kick_script_loads_in_order():
    page = (ROOT / "static" / "index.html").read_text()
    order = [page.index(f"/static/js/{name}") for name in
             ("sports-objects.js", "sports-kick.js", "space-sports.js", "sports-football.js", "motion.js")]
    assert order == sorted(order)


def test_the_kick_keeps_the_tested_poses_and_timing():
    """The owner judged the 2026-11-07 test good enough: its 12 poses and timing, unchanged."""
    source = (ROOT / "static" / "js" / "sports-kick.js").read_text()
    keys = source[source.index("KEYS"):source.index("GAPS")]
    assert len(re.findall(r"\{ x:", keys)) == 12
    gaps = [int(n) for n in re.search(r"GAPS = \[([^\]]+)\]", source).group(1).split(",")]
    assert gaps == [105, 105, 105, 125, 140, 90, 55, 90, 140, 170, 220]
    assert "END_MS: 2300" in source
```

Add `"static/js/sports-kick.js"` to `SPORTS_JS`, so `#sp-kick` must exist.

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest -q tests/test_server.py -k "kick or sports_scripts"`
Expected: FAIL (no `sports-kick.js`).

- [ ] **Step 3: Implement** the interfaces above.

- [ ] **Step 4: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass; `All checks passed!`.

- [ ] **Step 5: Check the pure functions in the page**

In the demo, run this in the page (the browser pane's JavaScript tool):

```js
const fails = [], near = (a, b, e = 1e-6) => Math.abs(a - b) < e, d = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1]);
KICK.KEYS.forEach((k, i) => KICK.FIELDS.forEach(f => {   // the curve passes through every key pose
  if (!near(kickMath.poseAt(KICK.TIMES[i])[f], k[f] || 0)) fails.push(`pose ${i} ${f}`); }));
for (let t = 0; t <= KICK.FIGURE_MS; t += 10) {
  const P = kickMath.poseAt(t), B = kickMath.skeleton(P);
  const low = Math.max(B.n.ank[1] + 4, B.n.toe[1] + 3, B.f.ank[1] + 4, B.f.toe[1] + 3);
  if (!near(low, -P.air)) fails.push(`floor ${t}`);
  if (!near(d(B.hip, B.n.knee), 46) || !near(d(B.n.knee, B.n.ank), 45) || !near(d(B.sh, B.na.el), 31)) fails.push(`length ${t}`);
}
const path = { from: [100, 400], to: [500, 150], peak: 20, hop: 6 };
const at = t => kickMath.ballAt(t, path);
if (!near(at(0).x, 100) || !near(at(KICK.STRIKE_MS - 1).y, 400) || at(0).scale !== 1) fails.push('rest');
if (!near(at(KICK.LAND_MS).x, 500, 0.5) || !near(at(KICK.LAND_MS).y, 150, 0.5) || !near(at(KICK.LAND_MS).scale, 0.5, 0.01)) fails.push('land');
if (!(at(KICK.STRIKE_MS + 20).squash < 1)) fails.push('squash');
for (let t = 0; t <= KICK.END_MS; t += 5) if (at(t).y < path.peak - 1e-9) fails.push(`above the arc ${t}`);
fails.length ? fails.slice(0, 10) : 'all kick checks passed';
```

Expected: `'all kick checks passed'`.

Then the hub at `#sports`: the objects look exactly as before (the split changed nothing).

- [ ] **Step 6: Commit**

```bash
git add static/js/sports-kick.js static/js/sports-objects.js static/index.html static/css/space-sports.css tests/test_server.py
git commit -m "Sports stage 4: the kick's body model, poses and ball flight"
```

---

### Task 4: The kick lands on the league

**Files:**
- Modify: `static/js/sports-football.js`, `static/js/space-sports.js`

**Interfaces:**
- Consumes: `playKick(canvas, target)` (Task 3); `sportsPlay`, `sportsAnim` (Task 2).
- Produces:
  - In `space-sports.js`: `sportsKick(slug)` — the one way into a league from the picker
    (stage 5's `league` event will call it too). With `globeCalm()`: `sportsGo('league',
    slug)`. Otherwise: `sportsFootball.prepare(slug)`, then
    `sportsPlay(sportsFootball.kick(slug), () => sportsGo('league', slug))`.
  - In `sports-football.js`, on `sportsFootball`:
    - `prepare(slug)`: what `openLeague` did for the data (`leaveLeague()`, `footballWanted =
      slug`, `footballLoading(slug)`, `footballAsk()`), without stopping the globe: the
      request starts with the kick (spec).
    - `kick(slug) -> anim`: `playKick(#sp-kick, () => sportsGlobe.screenPoint(lat, lon))` for
      the league's country (the middle of the canvas if the point is on the far side).
    - `openLeague(slug)`: when `footballWanted === slug` already (the kick asked), it only
      stops the globe and the picker; otherwise as now.
  - `footballAsk` draws a reply when `footballWanted === slug && currentSpace === 'sports'`
    (no longer also requiring the league level), so a reply that lands during the kick fills
    the hidden page instead of being dropped. Leaving still clears `footballWanted`, so a late
    reply after leaving draws nothing.
- The pins and the list call `sportsKick(league.slug)` instead of `sportsGo('league', ...)`.
  Addresses, reloads and the Back button still go straight to the page, with no kick (spec:
  "go where it says").

- [ ] **Step 1: Implement** the interfaces above.

- [ ] **Step 2: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass; `All checks passed!`.

- [ ] **Step 3: Demo** (canned: Serie A with Roma, Premier League with Newcastle, La Liga with
no matches, Bundesliga answers 429, Ligue 1 waits 6 s then fails)

Expected, from `#sports/football`:
- Clicking Italy: the silhouette runs in from the bottom left and kicks; the ball arcs to
  Italy's pin, shrinking and spinning, with a trail and a fading floor shadow; one bounce and
  a ripple; the Serie A page (Roma) fades in at about 2.3 s, already filled. The network panel
  shows one `/sports/league` request, sent as the kick started.
- **Data**: Bundesliga: after landing, the busy message and Try again. Ligue 1: after landing,
  "Loading…", then "Still waiting for the football data…", then the failure. La Liga: the
  table and the "no matches" notes. Never "undefined", "null" or "NaN".
- **Skipping**: click anywhere in the space during the kick, or press Esc: the league page at
  once, no figure left; still one request. A second pin clicked during a kick is a skip, not a
  second kick. After a skip, Esc goes back to the globe.
- **Leaving**: press 1 during the kick: Home, nothing drawn later, the kick canvas hidden.
  The browser's Back during the kick: the hub, and no league page drawn later.
- **No frames**: `window.requestAnimationFrame = () => 0` in the console, then click Spain:
  the La Liga page shows within 2.7 s. Reload afterwards.
- **Resize**: resize the pane during a kick: the ball still lands on the pin.
- **Reduce motion**: clicking a country fades to its page (0.2 s), no kick.
- Address `#sports/serie-a` typed, or a reload there: the page at once, no kick.
- No console errors, no policy violations.

- [ ] **Step 4: Commit**

```bash
git add static/js/sports-football.js static/js/space-sports.js
git commit -m "Sports stage 4: the kick lands on the league"
```

---

### Task 5: Documentation

**Files:**
- Modify: `CHANGELOG.md` (section 62 and the Status table), `CLAUDE.md` (the `static/` row:
  `sports-kick.js` in the script order and what it owns; `sports-objects.js`'s `drawSportAt`;
  the animations held in `sportsAnim`), `plan.md` if it lists the Sports stages.

- [ ] **Step 1: Write** CHANGELOG section 62 in plain language: what moves and when; the skip
  and cancel rules; Reduce motion now fades for 0.2 s (stage 3 had no fade); the kicked ball
  is the hub's 3D football rather than the test's white ball; the data is asked for as the
  kick starts; what was checked (the pytest count, the page checks, the demo steps) and what
  was not (Safari, the owner's own look). No prompt change, so no eval.

- [ ] **Step 2: Check**

Run: `python -m pytest -q && ruff check .`
Expected: all pass; `All checks passed!`.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md CLAUDE.md plan.md
git commit -m "Document Sports stage 4 (CHANGELOG section 62)"
```
