"""Settings in one place.

Paths are built from this file's folder, so the server works no matter which
folder it is started from.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# The real calendar and tasks. Tests and evals set JARVIS_DB=":memory:" before
# importing anything, so they never touch it.
DB_PATH = os.environ.get("JARVIS_DB", str(ROOT / "jarvis.db"))
# Secrets, such as the football key, live in .env (ignored by git), never in code. Tests set
# JARVIS_ENV to an empty file, so they never read the real one.
ENV_FILE = Path(os.environ.get("JARVIS_ENV", str(ROOT / ".env")))
BACKUP_DIR = ROOT / "backups"
BACKUP_KEEP_DAYS = 7
# Encrypted copies, made for leaving this Mac (SECURITY.md section 5). Locked with the
# public key below; the private key that unlocks them is on paper, never on this Mac.
BACKUP_ENCRYPTED_DIR = BACKUP_DIR / "encrypted"
BACKUP_ENCRYPTED_KEEP_DAYS = 30
BACKUP_PUBLIC_KEY = ROOT / "backup_public_key.txt"
LOG_DIR = ROOT / "logs"
STATIC_DIR = ROOT / "static"
MODELS_DIR = ROOT / "models"

# Language model (Ollama). Check the pinned ID in README.md after an update.
# gemma4:26b replaced gemma4:latest (the small e4b) after evals on both: just as reliable,
# and about twice as fast, because only about 4 billion of its 26 billion parameters work
# on each word (CHANGELOG section 37). 31b was as reliable but 6 times slower.
MODEL = "gemma4:26b"
MAX_ROUNDS = 4          # tool rounds per message, so a confused model can't loop forever
# gemma4 "thinks" (hidden reasoning) before it answers. Keep it ON: with it off, replies
# came 7x faster but the evals fell from 102/102 to 73/102, with wrong arithmetic stated
# as fact and tasks claimed as done without any tool call (CHANGELOG section 27). Measured
# again on gemma4:26b: 4 times faster, but 144/156 instead of 156/156, guessing instead of
# asking (CHANGELOG section 38).
# The cost is a pause of up to a few seconds before the first spoken word.
MODEL_THINK = True
# How long Ollama keeps the model loaded after the last request (its default is 5 minutes).
# Loading gemma4:26b takes about 3 s on the first message after a pause (measured
# 2026-10-21); it is 18 GB on disk.
MODEL_KEEP_ALIVE = "1h"
# The most tokens one model round may write, thinking included. Real rounds have written 184
# at the median and 1,751 at most (the log, 2026-10-27). Once, in an eval, the model looped
# and wrote 121,120 in 39 minutes, blocking everything behind it (CHANGELOG section 47). At
# about 50 tokens a second, this stops such a loop after about 80 seconds.
MODEL_MAX_TOKENS = 4096
# The conversation is trimmed when the model was given more than HISTORY_MAX_TOKENS
# (gemma4:26b's window is 262144), down to about HISTORY_KEEP_TOKENS, oldest exchanges
# first. Each trim makes Ollama re-read everything once, so it cuts a lot, rarely.
HISTORY_MAX_TOKENS = 60_000
HISTORY_KEEP_TOKENS = 30_000
# A delete card left unanswered this long can no longer be confirmed (ask again instead).
CONFIRM_TIMEOUT_SECONDS = 300

# Spaces (docs/specs/2026-10-27-spaces-and-work.md): the names the open_space tool and /chat
# accept. The page registers the same names in static/js/spaces.js and space-<name>.js.
SPACES = ("home", "work", "weather")

# Work space (docs/specs/2026-10-27-spaces-and-work.md, CHANGELOG section 51): free time is
# counted within this working day, gaps shorter than this are left out, and a deadline's bar
# starts to fill this many days before it is due. Agreed with the owner.
WORK_DAY_START = "08:00"
WORK_DAY_END = "22:00"
WORK_MIN_GAP_MINUTES = 30
DEADLINE_WINDOW_DAYS = 14

# Weather (docs/specs/2026-11-05-weather-space.md): the only outside addresses JARVIS may
# fetch from, fixed here so the model can never choose one (SECURITY.md section 5).
WEATHER_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_CACHE_SECONDS = 600       # matches, forecasts and air quality are kept 10 minutes
WEATHER_CACHE_ENTRIES = 50
WEATHER_MATCHES = 5                # places offered for one search
WEATHER_QUERY_MAX = 80             # characters in a search
WEATHER_NAME_MAX = 60              # characters kept of each outside name
WEATHER_COORD_DECIMALS = 2         # about 1 km: the forecast is the same, a street is not named
WEATHER_RAIN_CHANCE = 40           # percent; hours at or above this count as rain

# Football, for the Sports space (docs/specs/2026-11-07-sports-space.md): football-data.org's
# free plan. Every address JARVIS may ask is built here from these fixed codes, so the model can
# never choose one (SECURITY.md section 5).
FOOTBALL_API = "https://api.football-data.org/v4"
FOOTBALL_LEAGUES = {
    "premier-league": {"code": "PL", "name": "Premier League", "country": "England", "lat": 52.5, "lon": -1.5},
    "serie-a": {"code": "SA", "name": "Serie A", "country": "Italy", "lat": 42.8, "lon": 12.5},
    "la-liga": {"code": "PD", "name": "La Liga", "country": "Spain", "lat": 40.2, "lon": -3.7},
    "bundesliga": {"code": "BL1", "name": "Bundesliga", "country": "Germany", "lat": 51.2, "lon": 10.4},
    "ligue-1": {"code": "FL1", "name": "Ligue 1", "country": "France", "lat": 46.6, "lon": 2.4},
}
# The teams followed. Their ids are from memory of the API (its docs do not list them); stage 2
# confirms them against a real reply before anything relies on them.
FOOTBALL_TEAMS = {
    "roma": {"id": 100, "name": "Roma", "league": "serie-a",
             "cup_note": "The Coppa Italia isn't in the free data"},
    "newcastle": {"id": 67, "name": "Newcastle", "league": "premier-league",
                  "cup_note": "The FA Cup isn't in the free data"},
}
FOOTBALL_ADDRESSES = (
    *(f"{FOOTBALL_API}/competitions/{code}/standings"
      for code in (*(lg["code"] for lg in FOOTBALL_LEAGUES.values()), "CL")),
    *(f"{FOOTBALL_API}/competitions/{lg['code']}/matches" for lg in FOOTBALL_LEAGUES.values()),
    *(f"{FOOTBALL_API}/teams/{team['id']}/matches" for team in FOOTBALL_TEAMS.values()),
)
# The free plan allows 10 requests a minute; 9 keeps one spare for clock differences
FOOTBALL_REQUESTS_PER_MINUTE = 9
FOOTBALL_CACHE_SECONDS = 600              # a reply is kept 10 minutes...
FOOTBALL_LIVE_CACHE_SECONDS = 120         # ...or 2 while a match in it is being played
FOOTBALL_EARLIER_COPY_SECONDS = 21_600    # an earlier copy, shown for 6 hours if the service fails
FOOTBALL_CACHE_ENTRIES = 30
FOOTBALL_NAME_MAX = 40                    # characters kept of each team or competition name
FOOTBALL_WINDOW_DAYS = 10                 # a league's matches: today, give or take 10 days
FOOTBALL_TEAM_WINDOW_DAYS = 60            # a followed team's: today, give or take 60 days

# The one door to the internet (outside.py), shared by Weather and Football
OUTSIDE_TIMEOUT_SECONDS = 5
OUTSIDE_MAX_BYTES = 1_000_000      # a reply larger than this is refused

# Notes and memory (SECURITY.md section 5): trivial preferences, never secrets
NOTE_MAX_CHARS = 300
NOTES_RECALL_LIMIT = 5     # notes given to the model per recall

# Speech
STT_MODEL = "mlx-community/whisper-large-v3-turbo"
# Whisper loads from the copy already on this Mac and never asks huggingface.co whether the
# model changed, so nothing leaves the Mac and the model cannot change by itself (CHANGELOG
# section 45). The Hugging Face library reads this when it is first imported, which happens
# only when Whisper first loads, long after config. To download or update the model on
# purpose, use the command in README.md (it sets HF_HUB_OFFLINE=0, which setdefault keeps).
os.environ.setdefault("HF_HUB_OFFLINE", "1")
MAX_AUDIO_BYTES = 10_000_000
VOICE_LANG = "en-gb"
VOICE_SPEED = 1.1       # 1.0 is normal speed
