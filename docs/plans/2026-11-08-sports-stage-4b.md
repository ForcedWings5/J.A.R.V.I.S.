# Sports, stage 4b: the 3D player — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the owner picks a league on the globe, a downloaded 3D character runs in,
controls the ball, takes his touches and strikes it to the country. He is a hologram outline in
a Roma-red "JARVIS 5 SPQR" shirt. The code-drawn kick plays whenever the 3D player is not ready.

**Architecture:**
- **three.js 0.170.0 is kept inside JARVIS** (`static/js/vendor/`), its imports rewritten to
  our own paths so no inline import map is needed.
- **A one-off bake tool turns the owner's two Mixamo files into one compact model:**
  `scripts/bake_player.py`, a small local server, plus `scripts/bake_player/bake.html`.
  - It writes `static/models/player.glb` (the character and one joined animation) and
    `player.json` (the moments and the ball's positions).
  - `static/models/` is git-ignored, so the files stay on the Mac.
- **`static/js/sports-player.js`, an ES module,** loads those files when the globe first opens.
  - It draws the player and the ball (in 3D, so the player hides it correctly) until the
    strike.
  - From the strike on, the existing 2D flight code takes the ball to the pin.
  - It offers the same `{ done, skip(), cancel() }` as `playKick`, so skipping, cancelling and
    the safety timeout work unchanged.

**Tech Stack:**
- three.js 0.170.0: `three.module.min.js` and `GLTFLoader`, plus `FBXLoader` and
  `GLTFExporter` for the bake tool only.
- Plain JavaScript and CSS, WebGL shaders.
- Python's standard library for the bake server.
- pytest, and the browser pane.

**Spec:** `docs/specs/2026-11-07-sports-space.md`: "The 3D player (stage 4b)" and its rows in
Decisions, Files, Security, Build order and Risks.

## Global Constraints

- **Branch:** `sports-stage-4b` (the spec is at `88aac7f`, on top of `main` `3169606`).
  Commit after each task. Never on `main`. Do not push.
- **three.js is exactly 0.170.0,** from the npm registry tarball
  `https://registry.npmjs.org/three/-/three-0.170.0.tgz`.
  - Ask the owner's OK before downloading, naming the file, source and size (CLAUDE.md).
  - Check it against the registry's published `dist.integrity` (sha512) before using anything
    in it.
  - Extract it into its own empty scratchpad folder. Run nothing from it.
- **The served vendor files** are `static/js/vendor/three.module.min.js`, `GLTFLoader.js`,
  `BufferGeometryUtils.js` and `LICENSE`. They are byte-for-byte the tarball's files, except
  for rewritten import paths (`'three'` becomes `'./three.module.min.js'`, and
  `'../utils/X.js'` becomes `'./X.js'`).
- **The Content Security Policy is unchanged.**
  - No inline scripts or import maps.
  - No `blob:` images, so no textures in the model.
  - Everything is loaded from JARVIS's own address.
  - Nothing new goes online.
- **The model files:**
  - `static/models/player.glb` and `static/models/player.json` are never committed;
    `static/models/` goes in `.gitignore`.
  - The owner's Mixamo downloads live in `models/mixamo/`, which is already ignored through
    `models/`. Move them from the Desktop only with the owner's OK.
- **The look (spec, exact):**
  - jersey `#8e1f2f`, trim `#f0bc42`;
  - the print in gold: "JARVIS" above a large "5", and "SPQR" below;
  - the hair dimmed to 0.4;
  - no eyelashes;
  - the ball is `drawSportAt(…, 'football', …)`.
- **The timing (spec):** pace 1.25 times the recorded speed. The strike comes at about 3.7 s
  and the page at about 4.9 s. The safety timeout is the end plus 0.4 s.
- **What does not change:** a click or Esc skips; leaving, the Back button or a new address
  cancels; Reduce motion means no kick; addresses open the page directly; the league's data is
  asked for as the kick starts.
- **The fallback:** `playKick` (the code-drawn kick) plays whenever `sportsPlayer.ready` is
  false. A failure logs one `console.warn` and never throws into the page.
- **Demos:** their own database, backups and log, on port 8016, launched with stage 4's
  launcher (scratchpad `demo5/run_demo.py`) and `--canned`.
  - Check port 8000 first with `lsof -iTCP:8000 -sTCP:LISTEN`.
  - Keep a `securitypolicyviolation` listener on.
  - The browser pane may be hidden, which means no frames. Then check timing with the
    `requestAnimationFrame` stand-in used in stage 4, and the look from stills. Say so in
    CHANGELOG.

## Review Focus

1. **A click before the model is ready, or while it loads, or after loading failed:** the
   code-drawn kick plays at once; never two kicks, never a wait; one warning, not one per
   click. Pinned by Task 5's demo step "Not ready".
2. **WebGL unavailable, or the context lost (`webglcontextlost`):** the kick in progress still
   ends (its safety timeout); later kicks use the fallback; nothing throws in a frame. Pinned
   by Task 4's page check "Lost context" and Task 5's demo step "Lost".
3. **Skipping or leaving during the 3D kick** (a click, Esc, key 1, the Back button): the 3D
   and kick canvases are hidden, the render loop stops, nothing is drawn late, and the page
   follows the address. Pinned by Task 5's demo steps "Skipping" and "Leaving".
4. **A broken `player.json` or `player.glb`** (missing fields, NaN, times out of order,
   truncated file): the fallback plays and the page never breaks. Pinned by Task 2's pytest
   checker cases, Task 4's page check "Checker" and Task 5's demo step "Broken".
5. **Different window sizes and a resize mid-kick:** the player stays in view, and the ball
   lands on the pin. Pinned by Task 5's demo step "Resize".

---

### Task 1: three.js inside JARVIS

**Files:**
- Create: `static/js/vendor/three.module.min.js`, `static/js/vendor/GLTFLoader.js`,
  `static/js/vendor/BufferGeometryUtils.js`, `static/js/vendor/LICENSE`
- Test: `tests/test_server.py`

**Interfaces:**
- Produces: the vendor files. In `tests/test_server.py`, `VENDOR_SHA256`, a dict from file
  name to hex digest.

- [ ] **Step 1: Ask the owner**

Look up the tarball's size and integrity from `https://registry.npmjs.org/three/0.170.0`
(`dist.unpackedSize`, `dist.integrity`, and the tarball's `Content-Length` with a HEAD
request). Ask the owner's OK to download `three-0.170.0.tgz` from registry.npmjs.org, naming
its size. Wait for a yes.

- [ ] **Step 2: Download and check**

Download into a new empty scratchpad folder `three-0.170.0/`. Compute
`openssl dgst -sha512 -binary three-0.170.0.tgz | base64` and compare it with `dist.integrity`
(after its `sha512-` prefix).
Expected: identical. If not, stop and tell the owner. Then extract with
`tar -xzf … -C three-0.170.0/x`.

- [ ] **Step 3: Write the failing tests** in `tests/test_server.py`

```python
VENDOR = ROOT / "static" / "js" / "vendor"
VENDOR_SHA256 = {}   # filled in Step 5 from the files as copied (after the import rewrite)


def test_three_is_kept_inside_jarvis_and_pinned():
    """three.js 0.170.0, owner's agreement 2026-11-08: a silent change to it must fail CI."""
    assert sorted(p.name for p in VENDOR.iterdir()) == [
        "BufferGeometryUtils.js", "GLTFLoader.js", "LICENSE", "three.module.min.js"]
    assert "MIT" in (VENDOR / "LICENSE").read_text()
    for name, digest in VENDOR_SHA256.items():
        assert hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() == digest, name
    assert set(VENDOR_SHA256) == {"BufferGeometryUtils.js", "GLTFLoader.js", "three.module.min.js"}


def test_the_vendored_scripts_import_only_our_own_copies():
    """An import map would be inline code, which the policy blocks, so the paths are rewritten."""
    for name in ("GLTFLoader.js", "BufferGeometryUtils.js", "three.module.min.js"):
        for target in re.findall(r"\bfrom\s*['\"]([^'\"]+)['\"]", (VENDOR / name).read_text()):
            assert target.startswith("./") and (VENDOR / target[2:]).exists(), (name, target)
```

Change `test_the_scripts_use_nothing_the_policy_blocks` to scan
`list(js.glob("*.js")) + list(js.glob("vendor/*.js"))`.

- [ ] **Step 4: Run them to see them fail**

Run: `python -m pytest -q tests/test_server.py -k "three or vendored or policy_blocks"`
Expected: FAIL (no `static/js/vendor`).

- [ ] **Step 5: Copy, rewrite, pin**
- **Copy:** `package/build/three.module.min.js`, `package/examples/jsm/loaders/GLTFLoader.js`,
  `package/examples/jsm/utils/BufferGeometryUtils.js` and `package/LICENSE` into
  `static/js/vendor/`.
- **Rewrite only the import specifiers** to the paths in Global Constraints, with a one-line
  comment at the top of each changed file: `// three.js 0.170.0, imports rewritten for
  JARVIS (no import map: CSP)`.
  - If `three.module.min.js` itself imports another file (a split build), stop. Rule on it, and
    note the extra file in the ledger.
- **Pin:** fill `VENDOR_SHA256` with the copied files' digests.

- [ ] **Step 6: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass (819 before, plus 2); `All checks passed!`.
- If the policy scan finds a blocked word in a vendor file, stop and tell the owner. That would
  mean the policy blocks three.js, which is a security decision.

- [ ] **Step 7: Commit**

```bash
git add static/js/vendor tests/test_server.py
git commit -m "Sports stage 4b: three.js 0.170.0 kept inside JARVIS, pinned by fingerprint"
```

---

### Task 2: The bake tool and the model files

**Files:**
- Create: `scripts/bake_player.py`, `scripts/bake_player/bake.html`, and
  `scripts/bake_player/vendor/` (from the same verified tarball: `FBXLoader.js`,
  `GLTFExporter.js`, and the files they import, such as `fflate.module.js`, `NURBSCurve.js`,
  `NURBSUtils.js` and `TextureUtils.js`, as found, with imports rewritten as in Task 1). All
  of these are for the bake tool only and never served by JARVIS.
- Modify: `.gitignore` (`static/models/`)
- Test: `tests/test_bake_player.py`

**Interfaces:**
- Produces, in `scripts/bake_player.py` (standard library only, run with `python -I`):
  - `check_player_json(data: object) -> str | None`: returns an error, or `None` when it is
    valid. The rules:
    - `version == 1`;
    - `end` finite in (0, 8];
    - `strike` finite in (0, `end`];
    - `ballR` in (0, 0.5];
    - `incoming = {from, to, start}`, with 0 ≤ `from` < `to` ≤ `strike` and `start` 3 finite
      numbers;
    - `ball`: 2 to 12 items `{t, p}`, with `t` not decreasing, the first `t` ≥ `incoming.to`,
      the last `t` ≤ `strike`, and each `p` 3 finite numbers;
    - every coordinate |v| ≤ 20;
    - `camera = {target, forward}`, each 3 finite numbers, with `forward`'s length > 0.1.
  - `SAVE_NAMES = {"player.glb": 30_000_000, "player.json": 100_000}`: the only files it
    writes, with their size limits.
  - `save_path(name: str, out_dir: Path) -> Path | None`
  - `serve_path(url_path: str, roots: list[Path]) -> Path | None`: refuses `..`, absolute
    paths and anything outside the roots.
  - `main(argv)`: `bake_player.py RECEIVE.fbx STRIKE.fbx`. It serves on `127.0.0.1:8018`:
    - `/` is `bake.html`;
    - `/vendor/…` is `scripts/bake_player/vendor/` first, then `static/js/vendor/`;
    - `/sports-objects.js`;
    - `/fbx/receive.fbx` and `/fbx/strike.fbx` are the two given files;
    - `POST /save/<name>` writes to `static/models/<name>` after the size check, and for the
      JSON after `check_player_json`. It answers 400 with the reason otherwise.
- Produces, on the owner's Mac: `static/models/player.glb` and `static/models/player.json`, in
  the shape above. Times are seconds at pace 1.25 from the start of the kick; positions are
  metres in the exported scene.

- [ ] **Step 1: Write the failing tests** in `tests/test_bake_player.py`

These cover `check_player_json` with one good example and these bad ones:
- `version` 2;
- `end` NaN;
- `strike` > `end`;
- `ball` times out of order;
- 13 `ball` items;
- a coordinate of 21;
- `forward` of [0, 0, 0];
- a missing `camera`.

They also cover:
- `save_path`: only the two names; `../x`, `player.glb/..`, `other.txt` → `None`;
- `serve_path`: refuses `/../config.py`, `/vendor/../../jarvis.db` and `//etc/passwd`;
- that the server address is `127.0.0.1`, read from the module constant `ADDRESS`;
- that `.gitignore` has `static/models/` as a line.

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest -q tests/test_bake_player.py`
Expected: FAIL (`No module named bake_player`). Import it with `importlib.util` from
`scripts/`, as the tests for `make_coastlines.py` would.

- [ ] **Step 3: Implement `scripts/bake_player.py` and `.gitignore`.**

- [ ] **Step 4: Run them to see them pass**

Run: `python -m pytest -q tests/test_bake_player.py && ruff check .`
Expected: all pass.

- [ ] **Step 5: Write `scripts/bake_player/bake.html`**

This is the joining from the throwaway `model.html` (scratchpad `player3d/`), made one-off:
- **Load** `/fbx/receive.fbx` and `/fbx/strike.fbx`, and scale the character to 1.8 m.
- **Join** with the values from the test: blend at `TB = 4.2` from `TS0 = 0`, `BLEND = 0.4`,
  the strike turned to face the run-up. The touch at the left foot's highest point in
  (0.8, 1.5) s; the strike where the right toe moves fastest in (0.25, 0.6) s.
- **Bake** at 30 frames per second over the joined time, dividing every time by `PACE = 1.25`:
  - a `QuaternionKeyframeTrack` for every bone;
  - `mixamorigHips.position`;
  - `PlayerRoot.position` and `.quaternion` for the wrapper group, named `PlayerRoot`.
  - The clip is named `kick`.
- **Strip:** remove the `Eyelashes` mesh. Give every mesh a plain `MeshBasicMaterial` (no
  maps). Delete each geometry's `uv` attribute.
- **Export** with `GLTFExporter` (`binary: true`, `animations: [clip]`), and POST to
  `/save/player.glb`.
- **Write the JSON:**
  - `incoming` runs from touch−0.9 to touch, with `start` = the touch point + (0, 6, 0) + the
    run's forward direction × 3;
  - `ball` holds the test's touch points (1.45, 1.85, 2.25, 2.85, 4.05, strike − 0.03, all
    divided by the pace);
  - `camera` holds `target` = the run's middle at a height of 1.0, and `forward`;
  - POST it to `/save/player.json`.
- **Show** "Saved player.glb (N MB) and player.json", or the server's reason.

- [ ] **Step 6: Make the files**

Ask the owner's OK, then move `~/Desktop/Receive Soccerball.fbx` and
`~/Desktop/Strike Foward Jog.fbx` into `models/mixamo/`. Then run:

```bash
python -I scripts/bake_player.py "models/mixamo/Receive Soccerball.fbx" "models/mixamo/Strike Foward Jog.fbx"
```

Open `http://127.0.0.1:8018/` in the browser pane.

Expected: "Saved"; `static/models/player.glb` under 30 MB (reported in the ledger) and
`player.json` valid. Then check:
- `git status --short static/models` prints nothing (ignored);
- `python -I -c` loading the JSON through `check_player_json` prints `None`;
- `strike` is about 3.7, and `end` is about 4.5 to 4.7.

- [ ] **Step 7: Commit** (the tool only; the model files stay out of git)

```bash
git add scripts/bake_player.py scripts/bake_player tests/test_bake_player.py .gitignore
git commit -m "Sports stage 4b: the bake tool (Mixamo files to player.glb and player.json, kept on this Mac)"
```

---

### Task 3: The ball's flight, shared by both kicks

**Files:**
- Modify: `static/js/sports-kick.js`

**Interfaces:**
- Produces: `drawFlight(ctx, t, path, r)`, which draws, for `t` ≥ `KICK.STRIKE_MS` (kick
  milliseconds), the trail, the ball (`drawSportAt`, squashed and shrinking) and the landing
  ripple. `path` is `kickMath.ballAt`'s; `r` is the ball's radius at rest in pixels.
  `drawKick` calls it for `t` ≥ `STRIKE_MS`; before the strike it draws as now.

- [ ] **Step 1: Move** the trail, ball and ripple drawing out of `drawKick` into `drawFlight`.
  The behaviour is unchanged.

- [ ] **Step 2: Check**

Run: `python -m pytest -q && ruff check .`
Expected: all pass.

In the demo, run stage 4's kick page check (`docs/plans/2026-11-07-sports-stage-4.md` Task 3
Step 5).
Expected: `'all kick checks passed'`. Compare stills of `drawKick` at 760, 1250 and 1950 ms
with stage 4's: the same.

- [ ] **Step 3: Commit**

```bash
git add static/js/sports-kick.js
git commit -m "Sports stage 4b: the ball's flight drawn by one function for both kicks"
```

---

### Task 4: `sports-player.js`, the 3D player

**Files:**
- Create: `static/js/sports-player.js`
- Modify: `static/index.html`, `static/css/space-sports.css`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `drawFlight`, `kickMath.ballAt`, `KICK` (Task 3, `sports-kick.js`); `drawSportAt`
  (`sports-objects.js`); `static/js/vendor/*` (Task 1); the shape of `player.json` (Task 2).
- Produces `window.sportsPlayer`:
  - `ready: boolean`;
  - `load(): Promise<void>`, idempotent; fetches and checks the files and builds the scene
    once; never rejects;
  - `play(kickCanvas, target) -> { done, skip(), cancel() }`, with the same contract as
    `playKick`;
  - `checkData(data) -> string | null`, the same rules as Task 2's `check_player_json`.
- In `index.html`:
  - `<canvas id="sp-player" class="sp-player" aria-hidden="true" hidden></canvas>` inside
    `.sp-globe-wrap`, before `#sp-kick`;
  - `<script type="module" src="/static/js/sports-player.js"></script>` after `motion.js`.
  - CSS: `.sp-player` covers the wrap like `.sp-kick`, with
    `filter: drop-shadow(0 0 6px rgba(76,201,240,.55))`, and
    `.sp-player[hidden] { display:none; }`.

- [ ] **Step 1: Write the failing tests** in `tests/test_server.py`

```python
def test_the_3d_player_loads_last_as_a_module_with_its_canvas():
    page = (ROOT / "static" / "index.html").read_text()
    assert '<script type="module" src="/static/js/sports-player.js"></script>' in page
    assert page.index("/static/js/motion.js") < page.index("/static/js/sports-player.js")
    assert page.index('id="sp-player"') < page.index('id="sp-kick"')
    assert 'type="importmap"' not in page


def test_the_3d_player_uses_only_our_files():
    source = (ROOT / "static" / "js" / "sports-player.js").read_text()
    assert re.findall(r"\bfrom\s*['\"]([^'\"]+)['\"]", source) == [
        "./vendor/three.module.min.js", "./vendor/GLTFLoader.js"]
    assert "/static/models/player.glb" in source and "/static/models/player.json" in source
    assert "http" not in source.replace("http-equiv", "")
```

Add `"static/js/sports-player.js"` to `SPORTS_JS`.

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest -q tests/test_server.py -k "3d_player or sports_scripts"`
Expected: FAIL.

- [ ] **Step 3: Implement `static/js/sports-player.js`**

Take the throwaway `model.html`'s shaders and print. Use these fixed values:
- `PACE = 1.25`;
- the view `{ fov: 30, az: 34, el: 11, dist: 10.5, aimRight: 0.35, aimAhead: 0.6 }`;
- the hair gain `0.4`;
- the colours and print words from Global Constraints;
- the print texture 256 × 300, with "JARVIS" 38 px at y 52 (spacing 4), "5" 175 px at y 222,
  and "SPQR" 42 px at y 278 (spacing 6).

How it works:
- **`load()`:**
  - fetch `player.json` and check it with `checkData`;
  - `GLTFLoader().loadAsync('/static/models/player.glb')`;
  - the hologram material on every skinned mesh except the one whose name ends in `Shirt`,
    which gets the shirt material;
  - the ball as a `Sprite` whose `CanvasTexture` is redrawn with `drawSportAt` each frame;
  - `renderer = new WebGLRenderer({ canvas: #sp-player, alpha: true, antialias: true })`, with
    the pixel ratio `min(2, devicePixelRatio)`;
  - on `webglcontextlost`, set `ready = false`;
  - any failure: one `console.warn('3D player unavailable: …')`, and `ready` stays `false`.
- **`play()`:** show both canvases, then every frame at time `T` (seconds since the start):
  - **before `strike`:** `mixer.setTime(T)`; the ball sprite on the `incoming` arc, then
    between the `ball` points (falling to the floor after an airborne point, rolling with
    ease-out as in the test); render.
  - **after `strike`:** keep rendering the follow-through until `end`, then fade `#sp-player`
    over 0.5 s.
    - The ball switches to `#sp-kick`: `drawFlight` at kick time
      `KICK.STRIKE_MS + (T − strike) × 1000 × PACE`.
    - Its path goes from the projected rest point (the last `ball` point) to `target()`, which
      is read every frame.
    - The ball's radius at rest is projected too.
  - **The end:** at `strike + (KICK.END_MS − KICK.STRIKE_MS) / 1000 / PACE`.
  - **The safety timeout** is the end plus 400 ms.
  - **`skip()` and `cancel()`** end it at once: hide both canvases, stop the loop, and resolve
    `true` or `false`.

- [ ] **Step 4: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass.

- [ ] **Step 5: Page checks** (demo, with the model files present)
- **Checker:** `sportsPlayer.checkData` returns `null` for the real `player.json` and an error
  for each of Task 2's bad examples (written out in the check snippet).
- **Loads:** `await sportsPlayer.load(); sportsPlayer.ready` gives `true`. There are no policy
  violations and no console errors.
- **Lost context:** `renderer.getContext().getExtension('WEBGL_lose_context').loseContext()`
  (through a test hook `sportsPlayer._loseContext()`, dev only, documented) sets `ready` to
  `false`.

- [ ] **Step 6: Commit**

```bash
git add static/js/sports-player.js static/index.html static/css/space-sports.css tests/test_server.py
git commit -m "Sports stage 4b: the 3D player (hologram, red JARVIS 5 SPQR shirt, the hub's football)"
```

---

### Task 5: Picking the kick

**Files:**
- Modify: `static/js/sports-football.js`

**Interfaces:**
- Consumes: `window.sportsPlayer` (Task 4), `playKick` (stage 4).
- Produces:
  - `sportsFootball.kick(slug)` returns `sportsPlayer.play(fb.kick, target)` when
    `window.sportsPlayer && sportsPlayer.ready`, else `playKick(fb.kick, target)`, with the
    same `target` function.
  - `sportsFootball.enterPicker()` also calls `window.sportsPlayer && sportsPlayer.load()`
    (not awaited).

- [ ] **Step 1: Implement** the two changes.

- [ ] **Step 2: Run the tests and lint**

Run: `python -m pytest -q && ruff check .`
Expected: all pass.

- [ ] **Step 3: Demo**

From `#sports/football`, with the model files present, check:
- **The kick:** clicking Italy plays the 3D kick. The touches have the ball at the feet. The
  strike is at about 3.7 s, and the Serie A page comes at about 4.9 s, filled. There is one
  `/sports/league` request, sent at the start.
- **Frame time:** each frame's render time is logged over one kick. Expected: the median under
  8 ms on this Mac (recorded in CHANGELOG).
- **Skipping:** a click or Esc mid-kick shows the page at once, with both canvases hidden. A
  second pin is a skip.
- **Leaving:** key 1 mid-kick, or the Back button mid-kick: nothing is drawn later, and the
  canvases are hidden.
- **Resize:** resize mid-kick; the player stays in view and the ball lands on the pin. Also
  check a narrow window (the picker at 900 px wide).
- **Reduce motion:** no kick.
- **Not ready:** reload and click a country within 0.2 s of the globe opening: the code-drawn
  kick plays. Also block the model in the console (`fetch` stubbed to answer 404 for
  `/static/models/`, then reload): the code-drawn kick plays, with one warning.
- **Broken:** stub `player.json` with `strike: "x"`: the fallback plays, with one warning.
- **Lost:** `sportsPlayer._loseContext()` mid-kick: the kick ends by its timeout, and the next
  one is code-drawn.
- No policy violations, and no errors except the warnings above.

- [ ] **Step 4: Commit**

```bash
git add static/js/sports-football.js
git commit -m "Sports stage 4b: the 3D kick when it is ready, the code-drawn one otherwise"
```

---

### Task 6: Documentation

**Files:**
- Modify: `CHANGELOG.md` (section 63 and the Status table), `CLAUDE.md`, `README.md`,
  `SECURITY.md`, `plan.md`

- [ ] **Step 1: Write**
- **CHANGELOG section 63:** what moves and why; where three.js came from and how it was
  checked; the model files kept on the Mac; the fallback; the frame time; what was checked and
  what was not (full speed, Safari).
- **CLAUDE.md:**
  - the `static/` row: `sports-player.js`, `vendor/`, and `static/models/`, which is never
    committed;
  - `scripts/bake_player.py`;
  - a line in the security boundaries: "three.js is kept in `static/js/vendor/`, pinned by
    fingerprint; updating it is a deliberate step with the owner".
- **README:** "Making the 3D player": the Mixamo character, the two moves and the download
  settings; `models/mixamo/`; the bake command; what to do on a new Mac.
- **SECURITY.md:** the dependency, its source, the integrity check and the pins.
- **plan.md:** 4b is done.

- [ ] **Step 2: Check**

Run: `python -m pytest -q && ruff check .`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md CLAUDE.md README.md SECURITY.md plan.md
git commit -m "Document Sports stage 4b (CHANGELOG section 63)"
```
