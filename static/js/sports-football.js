// ---------- Football, in the Sports space (docs/specs/2026-11-07-sports-space.md) ----------
// The league picker on the globe, and the league pages. Talks only to JARVIS's own
// POST /sports/league (football.py), which does the fetching and every sum.

// The five leagues, as config.FOOTBALL_LEAGUES (a test checks they match): where each
// country's pin goes on the globe
const SPORTS_LEAGUES = [
  { slug: 'premier-league', name: 'Premier League', country: 'England', lat: 52.5, lon: -1.5 },
  { slug: 'serie-a', name: 'Serie A', country: 'Italy', lat: 42.8, lon: 12.5 },
  { slug: 'la-liga', name: 'La Liga', country: 'Spain', lat: 40.2, lon: -3.7 },
  { slug: 'bundesliga', name: 'Bundesliga', country: 'Germany', lat: 51.2, lon: 10.4 },
  { slug: 'ligue-1', name: 'Ligue 1', country: 'France', lat: 46.6, lon: 2.4 },
];
// The globe framed on the five countries
const SPORTS_EUROPE = { lat: 47, lon: 6, zoom: 3 };

// ---------- the league picker: the globe, its pins, and a plain list beside it ----------
const sportsGlobeCanvas = document.getElementById('sp-globe');
const sportsPins = document.getElementById('sp-pins');
const sportsLeagueList = document.getElementById('sp-league-list');
const sportsGlobe = makeGlobe(sportsGlobeCanvas);
let sportsPickerOn = false;
const sportsPinButtons = [];

for (const league of SPORTS_LEAGUES) {
  const pin = document.createElement('button');
  pin.className = 'sp-pin';
  pin.textContent = league.country + ' · ' + league.name;
  pin.addEventListener('click', () => sportsKick(league.slug));
  sportsPins.append(pin);
  sportsPinButtons.push({ pin, league });

  const item = document.createElement('button');
  item.className = 'sp-league-item';
  item.textContent = league.name;
  const where = document.createElement('span');
  where.className = 'muted';
  where.textContent = league.country;
  item.append(where);
  item.addEventListener('click', () => sportsKick(league.slug));
  sportsLeagueList.append(item);
}

// Each pin sits on its country; set through the CSSOM (allowed by the security policy)
function footballPlacePins() {
  if (!sportsPickerOn) return;
  for (const { pin, league } of sportsPinButtons) {
    const p = sportsGlobe.screenPoint(league.lat, league.lon);
    pin.style.left = p.x + 'px';
    pin.style.top = p.y + 'px';
    pin.hidden = !p.visible;
  }
}
new ResizeObserver(footballPlacePins).observe(sportsGlobeCanvas);

// ---------- small pure functions: the page's wording, from the server's plain values ----------
// (kept apart so they can be checked on their own, and tested if a JS test runner is added)

const FOOTBALL_DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const FOOTBALL_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const FOOTBALL_STATUS_WORDS = { postponed: 'Postponed', suspended: 'Suspended', cancelled: 'Cancelled' };

function footballPad(n) { return String(n).padStart(2, '0'); }
function footballDateOf(d) { return `${d.getFullYear()}-${footballPad(d.getMonth() + 1)}-${footballPad(d.getDate())}`; }

// Whole calendar days from one 'YYYY-MM-DD' to another (by UTC midnight, so a clock change
// in between cannot make a day 23 or 25 hours long)
function footballDaysBetween(from, to) {
  return Math.round((Date.parse(to + 'T00:00:00Z') - Date.parse(from + 'T00:00:00Z')) / 86400000);
}

// "Live", "Today 20:45", "Tomorrow 20:45", "in 3 days", or "Postponed"
function footballCountdown(match, now) {
  if (match.status === 'live') return 'Live';
  if (FOOTBALL_STATUS_WORDS[match.status]) return FOOTBALL_STATUS_WORDS[match.status];
  const days = footballDaysBetween(footballDateOf(now), match.date);
  if (days <= 0) return 'Today ' + match.time;
  if (days === 1) return 'Tomorrow ' + match.time;
  return `in ${days} days`;
}

// "Updated 3 min ago", or "From Sat 7 Nov, 14:05 (couldn't reach the football data)" for an
// earlier copy. `updated` is the oldest fetch behind the page ('YYYY-MM-DDTHH:MM', local).
function footballUpdatedText(updated, earlier, now) {
  const m = /^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)$/.exec(String(updated || ''));
  if (!m) return '';
  const at = new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
  const day = footballDateOf(at) === footballDateOf(now)
    ? '' : `${FOOTBALL_DAYS[at.getDay()]} ${at.getDate()} ${FOOTBALL_MONTHS[at.getMonth()]}, `;
  if (earlier) return `From ${day}${earlier} (couldn't reach the football data)`;
  const minutes = Math.floor((now - at) / 60000);
  if (minutes < 1) return 'Updated just now';
  if (minutes < 60) return `Updated ${minutes} min ago`;
  return `Updated at ${day}${m[4]}:${m[5]}`;
}

// "Roma 2–1 Lazio", or "Roma v Lazio" before it is played
function footballScoreLine(match) {
  const s = match.score;
  return s ? `${match.home.name} ${s.home}–${s.away} ${match.away.name}`
    : `${match.home.name} v ${match.away.name}`;
}

// Goal difference: "+3", "0", "−2"; "–" when unknown
function footballGd(n) {
  if (typeof n !== 'number') return '–';
  return n > 0 ? '+' + n : n < 0 ? '−' + Math.abs(n) : '0';
}

// ---------- the league page ----------
// Asked for one league at a time (CHANGELOG section 60): two quick looks would otherwise
// spend most of the free plan's minute. The newest wanted league is asked for when the
// request in flight ends; a reply for a league no longer wanted is dropped.

// Which leagues have a followed team, and so a theme
const SPORTS_THEMES = { 'serie-a': 'roma', 'premier-league': 'newcastle' };

const fbEl = id => document.getElementById(id);
const fb = {
  title: fbEl('sp-title'), subtitle: fbEl('sp-subtitle'), crest: fbEl('sp-crest'), status: fbEl('sp-status'), retry: fbEl('sp-retry'),
  next: fbEl('sp-next'), form: fbEl('sp-form'), table: fbEl('sp-table'),
  results: fbEl('sp-results'), resultsTitle: fbEl('sp-results-title'),
  upcoming: fbEl('sp-upcoming'), upcomingTitle: fbEl('sp-upcoming-title'),
  fixtures: fbEl('sp-fixtures'), cl: fbEl('sp-cl'), cup: fbEl('sp-cup'), updated: fbEl('sp-updated'),
  kick: fbEl('sp-kick'),
  teamPanels: [...document.querySelectorAll('#sp-league .sp-team-only')],
  clPanel: fbEl('sp-cl-panel'),
};

let footballWanted = null;   // the league the page wants shown
let footballAsking = null;   // the league whose request is in flight
let footballPage = null;     // the page data shown
let footballSlow = null;     // the "still waiting" timer
let footballTick = null;     // the 30-second redraw of the countdown and the updated line

function fbNode(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = text;
  return n;
}
function fbNote(box, text) { box.textContent = ''; box.append(fbNode('div', 'muted', text)); }

function footballLoading(slug) {
  const league = sportsLeagueInfo(slug);
  fb.title.textContent = league.name;
  fb.subtitle.textContent = league.country;
  fb.status.textContent = 'Loading…';
  fb.retry.hidden = true;
  for (const box of [fb.next, fb.form, fb.table, fb.results, fb.upcoming, fb.fixtures, fb.cl]) fbNote(box, 'Loading');
  fb.cup.textContent = '';
  fb.updated.textContent = '';
  // "Still waiting" after 4 seconds of loading this league, whether its request is sent now or
  // waits behind one already in flight (final review: re-picking during a slow request)
  clearTimeout(footballSlow);
  footballSlow = setTimeout(() => {
    if (footballWanted === slug && fb.status.textContent === 'Loading…') {
      fb.status.textContent = 'Still waiting for the football data…';
    }
  }, 4000);
  const themed = Boolean(SPORTS_THEMES[slug]);
  for (const p of fb.teamPanels) p.hidden = !themed;
  if (themed) sportsSection.dataset.theme = SPORTS_THEMES[slug];
  else delete sportsSection.dataset.theme;
  footballCrest(themed ? SPORTS_THEMES[slug] : null);
}

// The followed club's badge, from a file the owner keeps on this Mac (never in git). If the
// file is not there, the badge is simply not shown.
function footballCrest(club) {
  if (!club) { fb.crest.hidden = true; fb.crest.removeAttribute('src'); return; }
  fb.crest.src = `/static/img/crests/${club}.png`;
  fb.crest.hidden = false;
}

async function footballAsk() {
  if (footballAsking || !footballWanted) return;
  const slug = footballWanted;
  footballAsking = slug;
  let reply;
  try {
    const res = await fetch('/sports/league', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ league: slug }),
    });
    let data = {};
    try { data = (await res.json()) || {}; } catch (e) { /* not JSON: keep {} */ }
    reply = { ok: res.ok, status: res.status, data };
  } catch (e) {
    reply = { ok: false, status: 0, data: {} };
  }
  footballAsking = null;
  // Drawn even while the kick still plays (the page is hidden until it lands), so a quick reply
  // is not lost; leaving clears footballWanted, so a reply after leaving draws nothing
  if (footballWanted === slug && currentSpace === 'sports') {
    if (reply.ok) footballDraw(reply.data);
    else footballFailed(reply);
  }
  if (footballWanted && footballWanted !== slug) footballAsk();   // a newer league is wanted
}

function footballFailed(reply) {
  const detail = typeof reply.data.detail === 'string' ? reply.data.detail : '';
  fb.status.textContent = reply.status === 0 ? "Couldn't reach JARVIS." : (detail || "Couldn't reach the football data.");
  fb.retry.hidden = reply.status === 503;              // no key: trying again cannot help
  for (const box of [fb.next, fb.form, fb.table, fb.results, fb.upcoming, fb.fixtures, fb.cl]) box.textContent = '';
}

// One table: position, team, played, won, drawn, lost, goal difference, points
function footballTable(rows, teamId) {
  const table = fbNode('table', 'sp-table');
  const head = table.createTHead().insertRow();
  for (const h of ['', 'Team', 'P', 'W', 'D', 'L', 'GD', 'Pts']) head.append(fbNode('th', null, h));
  const body = table.createTBody();
  for (const r of rows) {
    const tr = body.insertRow();
    if (r.team.id === teamId) tr.className = 'sp-mine';
    const cells = [r.position, r.team.name, r.played, r.won, r.drawn, r.lost, footballGd(r.goal_difference), r.points];
    cells.forEach((c, i) => tr.append(fbNode('td', i === 1 ? 'sp-team' : null, typeof c === 'number' || i === 1 || i === 6 ? c : '–')));
  }
  return table;
}

function footballMatchRow(m, extra) {
  const row = fbNode('div', 'sp-match');
  const when = FOOTBALL_STATUS_WORDS[m.status] || (m.status === 'live' ? 'Live' : `${m.day} · ${m.time}`);
  row.append(fbNode('div', 'sp-when muted', when), fbNode('div', 'sp-line', footballScoreLine(m)));
  if (extra) row.append(extra);
  return row;
}

function footballRound(box, title, round, words, empty) {
  title.textContent = round.matchday ? `${words} · MATCHDAY ${round.matchday}` : words;
  box.textContent = '';
  if (!round.matches.length) { fbNote(box, empty); return; }
  for (const m of round.matches) box.append(footballMatchRow(m));
}

function footballNext(team, now) {
  fb.next.textContent = '';
  const m = team.next;
  if (!m) { fbNote(fb.next, 'No match scheduled yet.'); return; }
  fb.next.append(fbNode('div', 'sp-countdown', footballCountdown(m, now)),
    fbNode('div', 'sp-next-line', footballScoreLine(m)),
    fbNode('div', 'muted', `${m.day} · ${m.time} · ${m.competition}`));
  if (m.status === 'live') fb.next.append(fbNode('div', 'muted', 'Free scores arrive late'));
}

function footballDrawTeam(page, now) {
  const team = page.team;
  const where = team.position_words ? ` · ${team.position_words} · ${team.points} pts` : '';
  fb.title.textContent = team.name + where;
  fb.subtitle.textContent = `${page.league.name} · ${page.league.country}`;
  footballNext(team, now);
  fb.form.textContent = '';
  if (!team.form.length) fbNote(fb.form, 'No results yet.');
  for (const f of team.form) {
    const mark = fbNode('span', 'sp-result sp-' + f.result, f.result);
    mark.title = `${footballScoreLine(f.match)} · ${f.match.day}`;
    fb.form.append(mark);
  }
  fb.fixtures.textContent = '';
  for (const r of team.recent) fb.fixtures.append(footballMatchRow(r.match, fbNode('span', 'sp-result sp-' + r.result, r.result)));
  for (const m of team.coming) fb.fixtures.append(footballMatchRow(m, fbNode('span', 'sp-tag muted', m.competition)));
  if (!team.recent.length && !team.coming.length) fbNote(fb.fixtures, 'No matches in the window.');
  fb.clPanel.hidden = !Array.isArray(team.champions_league);
  fb.cl.textContent = '';
  if (Array.isArray(team.champions_league)) fb.cl.append(footballTable(team.champions_league, team.id));
  fb.cup.textContent = team.cup_note || '';
}

function footballDraw(page) {
  footballPage = page;
  const now = new Date();
  fb.status.textContent = '';
  fb.retry.hidden = true;
  fb.title.textContent = page.league.name;
  fb.subtitle.textContent = page.league.country;
  const teamId = page.team ? page.team.id : null;
  fb.table.textContent = '';
  if (!page.season_started || !page.table.length) fbNote(fb.table, "The season hasn't started.");
  else fb.table.append(footballTable(page.table, teamId));
  footballRound(fb.results, fb.resultsTitle, page.results, 'LATEST RESULTS', 'No results in the last 10 days.');
  footballRound(fb.upcoming, fb.upcomingTitle, page.upcoming, 'UPCOMING', 'No matches in the next 10 days.');
  for (const p of fb.teamPanels) p.hidden = !page.team;
  if (page.team) footballDrawTeam(page, now);
  else fb.cup.textContent = '';
  fb.updated.textContent = footballUpdatedText(page.updated, page.earlier, now);
  clearInterval(footballTick);
  footballTick = setInterval(footballRedrawClock, 30000);
}

// Every 30 seconds while the page is shown: the countdown and the updated line
function footballRedrawClock() {
  if (!footballPage || currentSpace !== 'sports' || sportsLevel() !== 'league') return;
  const now = new Date();
  if (footballPage.team) footballNext(footballPage.team, now);
  fb.updated.textContent = footballUpdatedText(footballPage.updated, footballPage.earlier, now);
}

fb.crest.addEventListener('error', () => { fb.crest.hidden = true; });
fb.retry.addEventListener('click', () => { if (footballWanted) { footballLoading(footballWanted); footballAsk(); } });

const sportsFootball = {
  enterPicker() {
    loadCoastlines().then(lines => sportsGlobe.setLines(lines));   // fetched once, shared
    // The 3D player, once, in the background, after the football's flight into the globe (0.7 s)
    // so reading it never makes that flight stutter. A click before then plays the drawn kick.
    setTimeout(() => { if (window.sportsPlayer) window.sportsPlayer.load(); }, 800);
    sportsPickerOn = true;
    sportsGlobe.jumpTo(SPORTS_EUROPE.lat, SPORTS_EUROPE.lon, SPORTS_EUROPE.zoom);
    sportsGlobe.start();
    setTimeout(footballPlacePins, 0);       // once the picker is laid out
  },
  openLeague(slug) {
    sportsPickerOn = false;
    sportsGlobe.stop();
    if (footballWanted === slug) return;     // the kick already asked for it
    this.prepare(slug);
  },
  // Ask for a league's data: as the kick starts (spec), so it is usually ready on landing
  prepare(slug) {
    this.leaveLeague();
    footballWanted = slug;
    footballLoading(slug);
    footballAsk();
  },
  // The kick, from the bottom left to the league's country on the globe: the 3D player when he
  // is ready (sports-player.js), the code-drawn one otherwise, so a click never waits
  kick(slug) {
    const league = sportsLeagueInfo(slug);
    const target = () => {
      const p = sportsGlobe.screenPoint(league.lat, league.lon);
      return p.visible ? p : { x: fb.kick.clientWidth / 2, y: fb.kick.clientHeight / 2 };
    };
    const player = window.sportsPlayer;
    return player && player.ready ? player.play(fb.kick, target) : playKick(fb.kick, target);
  },
  // The page is left: no timers, and a late reply draws nothing
  leaveLeague() {
    footballWanted = null;
    footballPage = null;
    clearTimeout(footballSlow);
    clearInterval(footballTick);
    footballTick = null;
    delete sportsSection.dataset.theme;
  },
  leave() {
    sportsPickerOn = false;
    sportsGlobe.stop();
    this.leaveLeague();
  },
  drawn() { return sportsGlobe.drawn; },
};
