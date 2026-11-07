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
  pin.addEventListener('click', () => sportsGo('league', league.slug));
  sportsPins.append(pin);
  sportsPinButtons.push({ pin, league });

  const item = document.createElement('button');
  item.className = 'sp-league-item';
  item.textContent = league.name;
  const where = document.createElement('span');
  where.className = 'muted';
  where.textContent = league.country;
  item.append(where);
  item.addEventListener('click', () => sportsGo('league', league.slug));
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

const sportsFootball = {
  enterPicker() {
    loadCoastlines().then(lines => sportsGlobe.setLines(lines));   // fetched once, shared
    sportsPickerOn = true;
    sportsGlobe.jumpTo(SPORTS_EUROPE.lat, SPORTS_EUROPE.lon, SPORTS_EUROPE.zoom);
    sportsGlobe.start();
    setTimeout(footballPlacePins, 0);       // once the picker is laid out
  },
  openLeague() {},
  leaveLeague() {},
  leave() {
    sportsPickerOn = false;
    sportsGlobe.stop();
    this.leaveLeague();
  },
  drawn() { return sportsGlobe.drawn; },
};
