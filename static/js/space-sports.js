// ---------- The Sports space (docs/specs/2026-11-07-sports-space.md) ----------
// Three levels in one section: the hub of sports, Football's league picker on the globe, and
// a league's page. <section data-level> says which, and CSS shows it. This file owns the
// levels, the hub, the trail, Esc and the addresses (#sports, #sports/football,
// #sports/<league>); sports-football.js owns the picker and the league pages.
// The animations (stage 4): the football growing into the globe is here; the kick is
// sports-kick.js's, started by sports-football.js. One plays at a time (sportsAnim).

const sportsSection = document.getElementById('space-sports');
const sportsTrail = document.getElementById('sp-trail');
const sportsBack = document.getElementById('sp-back');
const sportsNote = document.getElementById('sp-note');

// The hub's objects, in order. Only Football has a page so far; each other sport comes as its
// own build, with its own data source (spec, Build order).
const SPORTS_OBJECTS = [
  { name: 'football', title: 'Football', ready: true },
  { name: 'basketball', title: 'NBA' },
  { name: 'american-football', title: 'NFL' },
  { name: 'baseball', title: 'MLB' },
  { name: 'f1', title: 'F1' },
];

let sportsLeague = null;     // the league whose page is shown or asked for (a slug)
let sportsNoteTimer = null;

function sportsLevel() { return sportsSection.dataset.level; }

// The hub's objects turn slowly while the hub is shown (sports-objects.js draws them); with
// Reduce motion they are drawn once, still. Each starts at its own angle.
const sportsCanvases = [...sportsSection.querySelectorAll('.sp-object .sp-canvas')];
let sportsSpin = null;
let sportsObjectsAt = 0.6;   // the turn last drawn, so the flying football carries on from it
function sportsDrawObjects(seconds) {
  sportsObjectsAt = seconds;
  sportsCanvases.forEach((c, i) => drawSportObject(c, c.parentElement.dataset.sport, seconds + i * 1.3));
}
function sportsStartObjects() {
  sportsStopObjects();
  sportsDrawObjects(0.6);
  if (globeCalm()) return;
  const start = performance.now();
  const step = now => {
    if (globeCalm()) { sportsSpin = null; return; }
    sportsDrawObjects(0.6 + (now - start) / 1000);
    sportsSpin = requestAnimationFrame(step);
  };
  sportsSpin = requestAnimationFrame(step);
}
function sportsStopObjects() {
  if (sportsSpin) cancelAnimationFrame(sportsSpin);
  sportsSpin = null;
}

// ---------- the animations ----------
// Each is { done, skip(), cancel() }: done resolves true when it ends or is skipped, false
// when cancelled. A click in the space or Esc skips it (spec); leaving the space, the Back
// button or a new address cancels it, so nothing is drawn late.
let sportsAnim = null;

function sportsPlay(anim, then) {
  sportsAnim = anim;
  anim.done.then(ok => {
    if (sportsAnim !== anim) return;   // cancelled, or replaced
    sportsAnim = null;
    if (ok) then();
  });
}
function sportsSkip() {
  if (!sportsAnim) return false;
  sportsAnim.skip();
  return true;
}
function sportsCancelAnim() {
  const anim = sportsAnim;
  sportsAnim = null;
  if (anim) anim.cancel();
}

const SPORTS_PICK_MS = 200;    // the other objects fade
const SPORTS_FLY_MS = 500;     // the football flies to the globe's place and grows into it

function sportsBox(r) {
  return { left: r.left + 'px', top: r.top + 'px', width: r.width + 'px', height: r.height + 'px' };
}

// The football flies to the middle and grows into the globe (about 0.7 s). A copy of it on a
// canvas of its own does the flying, so the hub can be swapped for the picker underneath.
function sportsGrow(button) {
  const hub = document.getElementById('sp-hub');
  const from = button.querySelector('.sp-canvas').getBoundingClientRect();
  const flyer = document.createElement('canvas');
  flyer.className = 'sp-flyer';
  flyer.setAttribute('aria-hidden', 'true');
  Object.assign(flyer.style, sportsBox(from));
  document.body.append(flyer);
  hub.classList.add('sp-picking');
  button.classList.add('sp-chosen');

  let resolve, frame = null, timer = null, arrive = null, flight = null, flipped = false, finished = false;
  const done = new Promise(r => { resolve = r; });
  const start = performance.now(), turned = sportsObjectsAt;
  const spin = now => {
    drawSportObject(flyer, 'football', turned + (now - start) / 1000);
    frame = requestAnimationFrame(spin);
  };
  frame = requestAnimationFrame(spin);

  // The real switch, once: the picker is laid out but kept clear until the end
  const flip = () => {
    if (flipped) return;
    flipped = true;
    sportsSection.classList.add('sp-arriving');
    sportsGo('football');
  };
  const end = ok => {
    if (finished) return;
    finished = true;
    clearTimeout(timer);
    clearTimeout(arrive);
    cancelAnimationFrame(frame);
    if (flight) flight.cancel();
    if (ok) flip();
    flyer.remove();
    hub.classList.remove('sp-picking');
    button.classList.remove('sp-chosen');
    sportsSection.classList.remove('sp-arriving');   // restarts the picker's fade: the globe appears
    resolve(ok);
  };

  timer = setTimeout(() => {
    flip();
    const wrap = sportsSection.querySelector('.sp-globe-wrap').getBoundingClientRect();
    const side = Math.min(wrap.width, wrap.height);
    const to = { left: wrap.left + (wrap.width - side) / 2, top: wrap.top + (wrap.height - side) / 2, width: side, height: side };
    // It flies for the first 70%, then fades as the globe fades in under it
    flight = flyer.animate([
      { ...sportsBox(from), opacity: 1, easing: 'cubic-bezier(.2,.8,.2,1)' },
      { ...sportsBox(to), opacity: 1, offset: 0.7 },
      { ...sportsBox(to), opacity: 0 },
    ], { duration: SPORTS_FLY_MS, fill: 'forwards' });
    arrive = setTimeout(() => sportsSection.classList.remove('sp-arriving'), SPORTS_FLY_MS * 0.7);
    // A safety timeout, as motion.js has: with no frames (a hidden pane) it still ends
    const safety = new Promise(r => { timer = setTimeout(r, SPORTS_FLY_MS + 400); });
    Promise.race([flight.finished.catch(() => {}), safety]).then(() => end(true));
  }, SPORTS_PICK_MS);

  return { done, skip: () => end(true), cancel: () => end(false) };
}

// The way into a league from the picker, and for JARVIS's "show me Serie A" (sportsShowLeague):
// the player kicks the ball onto the country, and the league's data is asked for as it starts.
// From anywhere else, or with Reduce motion, the page simply opens.
function sportsKick(slug) {
  if (!sportsLeagueInfo(slug) || sportsAnim) return;
  if (globeCalm() || sportsLevel() !== 'football') { sportsGo('league', slug); return; }
  sportsFootball.prepare(slug);
  sportsPlay(sportsFootball.kick(slug), () => sportsGo('league', slug));
}

// ---------- JARVIS's "show me Serie A" (the `league` event, chat.js) ----------
// The event comes just before the `space` one, so Sports opens at the picker, waits for its
// opening animation (and the 3D player, briefly), then kicks, as if the country were clicked.
// Leaving, the Back button or a new address drop a kick still waiting (the token).
const SPORTS_OPENING_WAIT_MS = 8000;     // at most this long for Sports' opening animation...
const SPORTS_PLAYER_WAIT_MS = 3000;      // ...then this long for the 3D player's first load
const SPORTS_PENDING_MAX_AGE_MS = 10000; // a league older than this is forgotten, not kicked later
let sportsPending = null;                // { slug, at } JARVIS asked to show, not yet kicked
let sportsPendingToken = 0;

function sportsShowLeague(slug) {
  if (!sportsLeagueInfo(slug)) return;
  // A switch playing (you pressed 2 just as JARVIS answered): wait for it, as switchSpaceWhenFree
  // does, so this lands after its leave() and the next enter() takes it (final review)
  if (typeof seq !== 'undefined' && seq) { setTimeout(() => sportsShowLeague(slug), 100); return; }
  if (currentSpace === 'sports' && sportsLevel() === 'league' && sportsLeague === slug) return;
  // The same league again (the model may ask twice in one turn): already waiting, or being
  // kicked to, so restarting would only cancel the kick under way
  if (sportsPending && sportsPending.slug === slug &&
      Date.now() - sportsPending.at < SPORTS_PENDING_MAX_AGE_MS) return;
  if (sportsAnim && footballWanted === slug) return;
  sportsPending = { slug, at: Date.now() };
  if (currentSpace !== 'sports') return;   // the `space` event opens Sports; enter() goes on
  sportsCancelAnim();
  if (sportsLevel() !== 'football') sportsGo('football');
  sportsKickWhenReady(slug);
}

// You moved yourself (Back, Esc, the trail, a new address, leaving): JARVIS's kick no longer lands
function sportsDropPending() {
  sportsPending = null;
  ++sportsPendingToken;
}

async function sportsKickWhenReady(slug) {
  const token = ++sportsPendingToken;
  const wait = ms => new Promise(r => setTimeout(r, ms));
  // enter() calls this in the middle of motion.js's switch, while it has emptied seq for a
  // moment (swapSpace): look only once that is over, or the kick starts under the opening
  await wait(0);
  // No other switch can start while this one plays (spaces.js refuses), so this is Sports' own
  const until = Date.now() + SPORTS_OPENING_WAIT_MS;
  while (typeof seq !== 'undefined' && seq && Date.now() < until) await wait(100);
  // The 3D player (enterPicker started loading it): the first "show me" waits for him briefly,
  // so it is not the drawn kick just because he was still loading
  if (!globeCalm() && window.sportsPlayer && token === sportsPendingToken) {
    await Promise.race([window.sportsPlayer.load(), wait(SPORTS_PLAYER_WAIT_MS)]);
  }
  // Not while a switch plays: one starting now is the user going elsewhere (its leave() comes
  // partway through), so the kick would only start and be cancelled under it
  const still = token === sportsPendingToken && sportsPending && sportsPending.slug === slug &&
    currentSpace === 'sports' && sportsLevel() === 'football' && !(typeof seq !== 'undefined' && seq);
  if (token === sportsPendingToken) sportsPending = null;
  if (still) sportsKick(slug);
}

function sportsLeagueInfo(slug) {
  return SPORTS_LEAGUES.find(l => l.slug === slug) || null;
}

// '#sports/serie-a' -> {level: 'league', league: 'serie-a'}. Lower case; anything that is not
// a level or a league is the hub, so a mistyped address never shows Home or an error.
function sportsFromAddress(hash) {
  const parts = String(hash || '').replace(/^#/, '').toLowerCase().split('/');
  if (parts[0] !== 'sports' || parts.length < 2) return { level: 'hub', league: null };
  if (parts[1] === 'football' && parts.length === 2) return { level: 'football', league: null };
  if (parts.length === 2 && sportsLeagueInfo(parts[1])) return { level: 'league', league: parts[1] };
  return { level: 'hub', league: null };
}

function sportsAddress(level, league) {
  if (level === 'league' && league) return '#sports/' + league;
  if (level === 'football') return '#sports/football';
  return '#sports';
}

// Show a level. The football levels are drawn by sports-football.js; leaving them tells it,
// so its globe stops and a late reply draws nothing.
function sportsGo(level, league = null, { fromAddress = false } = {}) {
  if (level === 'league' && !sportsLeagueInfo(league)) { level = 'hub'; league = null; }
  const before = sportsLevel();
  sportsSection.dataset.level = level;
  sportsLeague = level === 'league' ? league : null;
  if (level === 'hub') {
    sportsFootball.leave();
    sportsStartObjects();
  } else {
    sportsStopObjects();
    if (level === 'football') { if (before === 'league') sportsFootball.leaveLeague(); sportsFootball.enterPicker(); }
    else sportsFootball.openLeague(league);
  }
  sportsDrawTrail();
  // A click adds a history entry. Following an address only tidies a Sports one in place
  // ('#SPORTS/x' -> '#sports'); coming from another space, spaces.js adds the entry itself.
  const address = sportsAddress(level, league);
  if (!fromAddress) {
    if (location.hash !== address) history.pushState(null, '', address);
  } else if (location.hash.toLowerCase().startsWith('#sports') && location.hash !== address) {
    history.replaceState(null, '', address);
  }
}

// "Sports / Football / Serie A": each part but the last goes back to its level
function sportsDrawTrail() {
  const parts = [{ text: 'Sports', level: 'hub' }];
  if (sportsLevel() !== 'hub') parts.push({ text: 'Football', level: 'football' });
  if (sportsLevel() === 'league') parts.push({ text: sportsLeagueInfo(sportsLeague).name, level: 'league' });
  sportsTrail.textContent = '';
  parts.forEach((p, i) => {
    if (i) sportsTrail.append(' / ');
    const last = i === parts.length - 1;
    const el = document.createElement(last ? 'span' : 'button');
    el.className = last ? 'sp-here' : 'sp-crumb';
    el.textContent = p.text;
    if (!last) el.addEventListener('click', () => { sportsDropPending(); sportsGo(p.level); });
    sportsTrail.append(el);
  });
  sportsBack.hidden = sportsLevel() === 'hub';
}

function sportsUp() {
  sportsDropPending();
  if (sportsLevel() === 'league') sportsGo('football');
  else if (sportsLevel() === 'football') sportsGo('hub');
}

function sportsSay(text) {
  sportsNote.textContent = text;
  clearTimeout(sportsNoteTimer);
  sportsNoteTimer = setTimeout(() => { sportsNote.textContent = ''; }, 1500);
}

for (const button of sportsSection.querySelectorAll('.sp-object')) {
  button.addEventListener('click', () => {
    const sport = SPORTS_OBJECTS.find(s => s.name === button.dataset.sport);
    if (!sport) return;
    if (!sport.ready) sportsSay(sport.title + ': coming soon');
    else if (globeCalm()) sportsGo('football');            // Reduce motion: the short fade only
    else sportsPlay(sportsGrow(button), () => {});
  });
}
sportsBack.addEventListener('click', sportsUp);

// A click anywhere in the space during an animation skips it, and does nothing else (so a
// second click on a pin or the football never starts a second one)
sportsSection.addEventListener('click', e => {
  if (!sportsAnim) return;
  e.stopPropagation();
  e.preventDefault();
  sportsSkip();
}, true);

registerSpace({
  name: 'sports', title: 'SPORTS', key: '4', section: sportsSection,
  // From an address ('#sports/serie-a', a reload, the Back button) go where it says;
  // key 4, the chip or "open sports" open the hub (spec)
  enter() {
    sportsCancelAnim();
    if (sportsPending && Date.now() - sportsPending.at < SPORTS_PENDING_MAX_AGE_MS) {
      sportsGo('football', null, { fromAddress: true });
      sportsKickWhenReady(sportsPending.slug);
      return;
    }
    sportsPending = null;
    const where = location.hash.toLowerCase().startsWith('#sports')
      ? sportsFromAddress(location.hash) : { level: 'hub', league: null };
    sportsGo(where.level, where.league, { fromAddress: true });
  },
  leave() { sportsCancelAnim(); sportsStopObjects(); sportsFootball.leave(); sportsPending = null; ++sportsPendingToken; },
  ready: () => sportsLevel() !== 'football' || sportsFootball.drawn(),
  readout: () => (sportsLevel() === 'league' ? sportsLeagueInfo(sportsLeague).name.toUpperCase()
    : sportsLevel() === 'football' ? 'PICK A LEAGUE' : 'SPORTS ONLINE'),
  // So JARVIS's "show me" from another space leaves '#sports/football', and Back finds the picker
  address: () => sportsAddress(sportsLevel(), sportsLeague),
});

// Within Sports, a new address (the Back button, or one typed) moves between levels.
// spaces.js only switches spaces, so it ignores these.
function sportsFollowAddress() {
  if (currentSpace !== 'sports') return;
  sportsPending = null; ++sportsPendingToken;    // a kick JARVIS asked for no longer lands
  // Any new address cancels an animation, even one leading out of Sports: motion.js calls
  // leave() only partway through its sequence, and a kick landing before that would push its
  // league's address over the one the Back button chose (final review)
  sportsCancelAnim();
  if (!location.hash.toLowerCase().startsWith('#sports')) return;
  const where = sportsFromAddress(location.hash);
  if (where.level !== sportsLevel() || where.league !== sportsLeague) {
    sportsGo(where.level, where.league, { fromAddress: true });
  }
}
window.addEventListener('popstate', sportsFollowAddress);
window.addEventListener('hashchange', sportsFollowAddress);

// Esc skips an animation, or else goes up one level. Not while typing (the first Esc only leaves the box, spaces.js) or
// while an access sequence plays. Capture phase, as Weather's, so it runs before app.js's.
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape' || currentSpace !== 'sports') return;
  if (typeof seq !== 'undefined' && seq) return;
  if (typingIn(e.target)) return;
  if (sportsSkip()) { e.preventDefault(); return; }
  if (sportsLevel() !== 'hub') { e.preventDefault(); sportsUp(); }
}, true);
