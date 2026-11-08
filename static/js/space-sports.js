// ---------- The Sports space (docs/specs/2026-11-07-sports-space.md) ----------
// Three levels in one section: the hub of sports, Football's league picker on the globe, and
// a league's page. <section data-level> says which, and CSS shows it. This file owns the
// levels, the hub, the trail, Esc and the addresses (#sports, #sports/football,
// #sports/<league>); sports-football.js owns the picker and the league pages.
// Plain fades for now; the floating objects and the kick come in stage 4.

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
function sportsDrawObjects(seconds) {
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
    if (!last) el.addEventListener('click', () => sportsGo(p.level));
    sportsTrail.append(el);
  });
  sportsBack.hidden = sportsLevel() === 'hub';
}

function sportsUp() {
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
    if (sport.ready) sportsGo('football');
    else sportsSay(sport.title + ': coming soon');
  });
}
sportsBack.addEventListener('click', sportsUp);

registerSpace({
  name: 'sports', title: 'SPORTS', key: '4', section: sportsSection,
  // From an address ('#sports/serie-a', a reload, the Back button) go where it says;
  // key 4, the chip or "open sports" open the hub (spec)
  enter() {
    const where = location.hash.toLowerCase().startsWith('#sports')
      ? sportsFromAddress(location.hash) : { level: 'hub', league: null };
    sportsGo(where.level, where.league, { fromAddress: true });
  },
  leave() { sportsStopObjects(); sportsFootball.leave(); },
  ready: () => sportsLevel() !== 'football' || sportsFootball.drawn(),
  readout: () => (sportsLevel() === 'league' ? sportsLeagueInfo(sportsLeague).name.toUpperCase()
    : sportsLevel() === 'football' ? 'PICK A LEAGUE' : 'SPORTS ONLINE'),
});

// Within Sports, a new address (the Back button, or one typed) moves between levels.
// spaces.js only switches spaces, so it ignores these.
function sportsFollowAddress() {
  if (currentSpace !== 'sports' || !location.hash.toLowerCase().startsWith('#sports')) return;
  const where = sportsFromAddress(location.hash);
  if (where.level !== sportsLevel() || where.league !== sportsLeague) {
    sportsGo(where.level, where.league, { fromAddress: true });
  }
}
window.addEventListener('popstate', sportsFollowAddress);
window.addEventListener('hashchange', sportsFollowAddress);

// Esc goes up one level. Not while typing (the first Esc only leaves the box, spaces.js) or
// while an access sequence plays. Capture phase, as Weather's, so it runs before app.js's.
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape' || currentSpace !== 'sports') return;
  if (typeof seq !== 'undefined' && seq) return;
  if (typingIn(e.target)) return;
  if (sportsLevel() !== 'hub') { e.preventDefault(); sportsUp(); }
}, true);
