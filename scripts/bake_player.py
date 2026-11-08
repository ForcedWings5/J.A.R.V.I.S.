"""Makes static/models/player.glb and player.json, the Sports kick's 3D player (stage 4b).

The owner downloads a character and two moves from Mixamo (Adobe's free library; see README,
"Making the 3D player") and keeps them in models/mixamo/, which git ignores. This tool serves a
page, scripts/bake_player/bake.html, that loads them with three.js, joins the moves, and posts
back the two files it makes. They are saved in static/models/, which git also ignores: Mixamo's
licence does not allow passing the files on.

Usage, from the project folder (the downloads are read as data, never run):
    python -I scripts/bake_player.py "models/mixamo/Receive Soccerball.fbx" "models/mixamo/Strike Foward Jog.fbx"
then open http://127.0.0.1:8018/ and wait for "Saved". Ctrl-C stops it.

Only the standard library. It listens on this Mac only, serves only its own page, the
three.js files and the two downloads, and writes only player.glb and player.json, each
checked first. Spec: docs/specs/2026-11-07-sports-space.md ("The 3D player").
"""
import json
import math
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
PAGE_DIR = Path(__file__).resolve().parent / "bake_player"
VENDOR_DIRS = [PAGE_DIR / "vendor", ROOT / "static" / "js" / "vendor"]
OUT_DIR = ROOT / "static" / "models"
ADDRESS = ("127.0.0.1", 8018)
SAVE_NAMES = {"player.glb": 30_000_000, "player.json": 100_000}   # the only files, and their size limits
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".fbx": "application/octet-stream"}


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _vec(v) -> bool:
    """Three finite numbers, none further than 20 m from the middle of the scene."""
    return isinstance(v, list) and len(v) == 3 and all(_num(x) and abs(x) <= 20 for x in v)


def check_player_json(data: object) -> str | None:
    """Why player.json is unusable, or None. The page checks the same rules (sports-player.js)."""
    if not isinstance(data, dict):
        return "not an object"
    if data.get("version") != 1:
        return "version must be 1"
    end, strike, ball_r = data.get("end"), data.get("strike"), data.get("ballR")
    if not (_num(end) and 0 < end <= 8):
        return "end must be a number of seconds, more than 0 and at most 8"
    if not (_num(strike) and 0 < strike <= end):
        return "strike must be within the animation"
    if not (_num(ball_r) and 0 < ball_r <= 0.5):
        return "ballR must be more than 0 and at most 0.5"
    inc = data.get("incoming")
    if not (isinstance(inc, dict) and _num(inc.get("from")) and _num(inc.get("to"))
            and 0 <= inc["from"] < inc["to"] <= strike and _vec(inc.get("start"))):
        return "incoming must run from 'from' to 'to' before the strike, from a 'start' point"
    ball = data.get("ball")
    if not (isinstance(ball, list) and 2 <= len(ball) <= 12):
        return "ball must have 2 to 12 points"
    last = inc["to"]
    for i, b in enumerate(ball):
        if not (isinstance(b, dict) and _num(b.get("t")) and _vec(b.get("p"))):
            return f"ball point {i} needs a time t and a position p"
        if b["t"] < last - 1e-6 or b["t"] > strike + 1e-6:
            return f"ball point {i} is out of order"
        last = b["t"]
    cam = data.get("camera")
    if not (isinstance(cam, dict) and _vec(cam.get("target")) and _vec(cam.get("forward"))
            and math.hypot(*cam["forward"]) > 0.1):
        return "camera needs a target and a forward direction"
    return None


def save_path(name: str, out_dir: Path) -> Path | None:
    """Where a posted file goes: only player.glb or player.json, in out_dir."""
    return out_dir / name if name in SAVE_NAMES else None


def serve_path(url_path: str, roots: list[Path]) -> Path | None:
    """The file a URL path names inside one of the roots (the first that has it), or None."""
    rel = url_path[1:] if url_path.startswith("/") else url_path
    if not rel or rel.startswith("/") or "\\" in rel or ".." in rel.split("/"):
        return None
    for root in roots:
        candidate = root / rel
        try:
            inside = candidate.resolve().is_relative_to(root.resolve())
        except OSError:
            continue
        if inside and candidate.is_file():
            return candidate
    return None


def make_handler(receive: Path, strike: Path):
    fixed = {"/": PAGE_DIR / "bake.html", "/fbx/receive.fbx": receive, "/fbx/strike.fbx": strike,
             "/sports-objects.js": ROOT / "static" / "js" / "sports-objects.js"}

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code: int, body: bytes, kind: str = "text/plain; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # JARVIS's own rule (server.py): only this address, and no other website's page. A
        # page elsewhere can still send a request to 127.0.0.1, or reach it under its own name
        # (DNS rebinding); both are refused before any work (final review)
        def _allowed(self) -> bool:
            port = self.server.server_address[1]
            hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            origin = self.headers.get("Origin")
            return self.headers.get("Host") in hosts and (origin is None or origin in {"http://" + h for h in hosts})

        def do_GET(self):
            if not self._allowed():
                return self._reply(403, b"only this tool's own page")
            path = unquote(urlsplit(self.path).path)
            if path in fixed:
                file = fixed[path]
            elif path.startswith("/vendor/"):
                file = serve_path(path[len("/vendor"):], VENDOR_DIRS)
            else:
                file = None
            if file is None or not file.is_file():
                return self._reply(404, b"not found")
            self._reply(200, file.read_bytes(), TYPES.get(file.suffix, "application/octet-stream"))

        def do_POST(self):
            if not self._allowed():
                return self._reply(403, b"only this tool's own page")
            path = unquote(urlsplit(self.path).path)
            # /check/player.json checks without saving: the page asks first, so a refused JSON
            # never leaves a new player.glb beside an old player.json (final review)
            only_check = path == "/check/player.json"
            name = "player.json" if only_check else path[len("/save/"):] if path.startswith("/save/") else ""
            target = save_path(name, OUT_DIR)
            if target is None:
                return self._reply(404, b"only player.glb and player.json can be saved")
            try:
                size = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                size = -1
            if not 0 < size <= SAVE_NAMES[name]:
                return self._reply(400, f"{name} must be 1 to {SAVE_NAMES[name]} bytes".encode())
            body = self.rfile.read(size)
            if name.endswith(".json"):
                try:
                    problem = check_player_json(json.loads(body))
                except ValueError:
                    problem = "not JSON"
                if problem:
                    return self._reply(400, f"player.json refused: {problem}".encode())
                if only_check:
                    return self._reply(200, b"player.json is fine")
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            part = target.with_name(target.name + ".part")
            part.write_bytes(body)
            part.replace(target)                          # never a half-written file
            self._reply(200, f"saved {name}, {len(body)} bytes".encode())

        def log_message(self, fmt, *args):                # quiet: one line per request is enough
            sys.stderr.write("bake: " + (fmt % args) + "\n")

    return Handler


def main(argv: list[str]) -> int:
    if len(argv) != 3 or not all(a.lower().endswith(".fbx") and Path(a).is_file() for a in argv[1:]):
        print(__doc__)
        return 2
    server = ThreadingHTTPServer(ADDRESS, make_handler(Path(argv[1]).resolve(), Path(argv[2]).resolve()))
    print(f"Open http://{ADDRESS[0]}:{ADDRESS[1]}/ and wait for 'Saved'. Ctrl-C stops.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
