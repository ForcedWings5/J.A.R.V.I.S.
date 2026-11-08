// ---------- The Sports hub's objects (docs/specs/2026-11-07-sports-space.md) ----------
// Each sport's object is 3D points and lines, turned and drawn in cyan on a canvas, the way
// the globe is (globe.js): lines nearer the viewer are brighter, which gives the depth.
// Drawing only; space-sports.js says when. Chosen by the owner from a throwaway test
// (2026-11-07) over flat drawings and a downloaded icon set.

const SPORT_PHI = (1 + Math.sqrt(5)) / 2;
const SPORT_RGB = '76,201,240';     // --accent

const sv = {
  norm: p => { const l = Math.hypot(p[0], p[1], p[2]); return [p[0] / l, p[1] / l, p[2] / l]; },
  sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
  add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
  mul: (a, k) => [a[0] * k, a[1] * k, a[2] * k],
  dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
  cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
  lerp: (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t],
};

// Turn around the vertical axis, then tip towards the viewer; z points at you
function sportTurn(p, ay, ax) {
  let x = p[0], y = p[1], z = p[2], c = Math.cos(ay), s = Math.sin(ay);
  [x, z] = [x * c + z * s, -x * s + z * c];
  c = Math.cos(ax); s = Math.sin(ax);
  [y, z] = [y * c - z * s, y * s + z * c];
  return [x, y, z];
}
// A line along the sphere's surface, so a ball's edges curve with it
function sportArc(a, b, n = 8) { const pts = []; for (let i = 0; i <= n; i++) pts.push(sv.norm(sv.lerp(a, b, i / n))); return pts; }
function sportSegs(pts, closed) {
  const s = [];
  for (let i = 0; i < pts.length - 1; i++) s.push([pts[i], pts[i + 1]]);
  if (closed) s.push([pts[pts.length - 1], pts[0]]);
  return s;
}
function sportCircle(f, n = 72) { const pts = []; for (let i = 0; i < n; i++) pts.push(f(2 * Math.PI * i / n)); return pts; }

// The football: a truncated icosahedron, 12 pentagons and 20 hexagons, on the sphere
function sportFootball() {
  const raw = [];
  for (const b of [[0, 1, 3 * SPORT_PHI], [1, 2 + SPORT_PHI, 2 * SPORT_PHI], [SPORT_PHI, 2, 2 * SPORT_PHI + 1]]) {
    for (const sx of [1, -1]) for (const sy of [1, -1]) for (const sz of [1, -1]) {
      const v = [b[0] * sx, b[1] * sy, b[2] * sz];
      for (let k = 0; k < 3; k++) raw.push([v[k % 3], v[(k + 1) % 3], v[(k + 2) % 3]]);
    }
  }
  const verts = [];
  for (const v of raw) if (!verts.some(u => Math.hypot(...sv.sub(u, v)) < 1e-6)) verts.push(v);
  const unit = verts.map(sv.norm);
  const segs = [];
  for (let i = 0; i < verts.length; i++) {
    for (let j = i + 1; j < verts.length; j++) {
      if (Math.abs(Math.hypot(...sv.sub(verts[i], verts[j])) - 2) < 1e-6) segs.push(...sportSegs(sportArc(unit[i], unit[j]), false));
    }
  }
  const pentas = [];               // around the icosahedron's 12 corners
  for (const sy of [1, -1]) for (const sz of [1, -1]) {
    const v = [0, sy, SPORT_PHI * sz];
    for (let k = 0; k < 3; k++) {
      const c = sv.norm([v[k % 3], v[(k + 1) % 3], v[(k + 2) % 3]]);
      const near = unit.map((u, i) => [sv.dot(u, c), i]).sort((a, b) => b[0] - a[0]).slice(0, 5).map(x => unit[x[1]]);
      const e1 = sv.norm(sv.sub(near[0], sv.mul(c, sv.dot(near[0], c)))), e2 = sv.cross(c, e1);
      near.sort((a, b) => Math.atan2(sv.dot(a, e2), sv.dot(a, e1)) - Math.atan2(sv.dot(b, e2), sv.dot(b, e1)));
      const outline = [];
      for (let i = 0; i < 5; i++) outline.push(...sportArc(near[i], near[(i + 1) % 5], 6).slice(0, -1));
      pentas.push({ c, outline });
    }
  }
  return { segs, pentas, sphere: true };
}

// A winding seam, as on a tennis ball or a baseball; b sets how far it winds
function sportWinding(b) {
  const k = 2 * Math.sqrt(b * (1 - b));
  return t => [(1 - b) * Math.cos(t) + b * Math.cos(3 * t), (1 - b) * Math.sin(t) - b * Math.sin(3 * t), k * Math.sin(2 * t)];
}

// The basketball: one winding seam and two straight seams at right angles (Paul Bourke,
// "Geometry of sports balls"), turned so the straight seams cross like a plus sign
function sportBasketball() {
  const segs = sportSegs(sportCircle(sportWinding(0.22), 160), true);
  for (const n of [[0, 0, 1], sv.norm([1, -1, 0])]) {
    const u = sv.norm(sv.cross(n, Math.abs(n[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0])), v = sv.cross(n, u);
    segs.push(...sportSegs(sportCircle(t => sv.add(sv.mul(u, Math.cos(t)), sv.mul(v, Math.sin(t)))), true));
  }
  const up = p => [p[0], p[2], -p[1]];
  return { segs: segs.map(([p, q]) => [up(p), up(q)]), sphere: true };
}

// The baseball: its winding seam, with stitches along both sides
function sportBaseball() {
  const P = sportWinding(0.3);
  const segs = sportSegs(sportCircle(P, 140), true);
  const accent = [];
  for (let i = 0; i < 56; i++) {
    const t = 2 * Math.PI * i / 56, p = P(t), q = P(t + 0.01);
    const tan = sv.norm(sv.sub(q, p)), side = sv.norm(sv.cross(tan, p));
    for (const s of [1, -1]) {
      accent.push([sv.norm(sv.add(p, sv.add(sv.mul(side, 0.035 * s), sv.mul(tan, -0.02)))),
                   sv.norm(sv.add(p, sv.add(sv.mul(side, 0.085 * s), sv.mul(tan, 0.02))))]);
    }
  }
  return { segs, accent, sphere: true };
}

// The American football: a stretched ball, four seams, two stripes at each end, the laces
function sportAmerican() {
  const R = 0.6;
  const pt = (s, a) => { const r = R * Math.pow(Math.max(0, 1 - s * s), 0.72); return [s, r * Math.cos(a), r * Math.sin(a)]; };
  const along = (f, n = 60) => { const p = []; for (let i = 0; i <= n; i++) p.push(f(-1 + 2 * i / n)); return p; };
  const segs = [], faint = [], accent = [];
  for (let k = 0; k < 4; k++) segs.push(...sportSegs(along(s => pt(s, Math.PI / 4 + k * Math.PI / 2)), false));
  for (let k = 0; k < 8; k++) faint.push(...sportSegs(along(s => pt(s, k * Math.PI / 4)), false));
  for (const s of [-0.62, -0.3, 0, 0.3, 0.62]) faint.push(...sportSegs(sportCircle(a => pt(s, a), 48), true));
  for (const s of [-0.74, -0.68, 0.68, 0.74]) segs.push(...sportSegs(sportCircle(a => pt(s, a), 48), true));
  const top = Math.PI / 2, out = 1.06;
  accent.push([sv.mul(pt(-0.36, top), out), sv.mul(pt(0.36, top), out)]);
  for (let i = 0; i < 8; i++) {
    const s = -0.3 + i * 0.6 / 7;
    accent.push([sv.mul(pt(s, top - 0.2), out), sv.mul(pt(s, top + 0.2), out)]);
  }
  return { segs, faint, accent };
}

// The F1 car: a low-poly wireframe, from the front wing to the rear wing
function sportCar() {
  const segs = [], accent = [], faint = [];
  const rect = (x, y0, y1, z0, z1) => [[x, y0, z0], [x, y1, z0], [x, y1, z1], [x, y0, z1]];
  const sym = (x, y0, y1, hw) => rect(x, y0, y1, -hw, hw);
  // a shape lofted through cross-sections, each a rectangle at one x
  function loft(sections, out = segs) {
    sections.forEach((s, i) => {
      out.push(...sportSegs(s, true));
      if (i) for (let k = 0; k < 4; k++) out.push([sections[i - 1][k], s[k]]);
    });
  }
  loft([sym(-2.35, 0.10, 0.17, 0.05), sym(-1.75, 0.08, 0.30, 0.15), sym(-0.95, 0.06, 0.42, 0.23),
        sym(-0.55, 0.05, 0.48, 0.27), sym(0.15, 0.05, 0.50, 0.29), sym(0.95, 0.07, 0.38, 0.19), sym(1.55, 0.10, 0.26, 0.11)]);
  loft([sym(-0.15, 0.50, 0.78, 0.12), sym(0.3, 0.50, 0.74, 0.10), sym(1.35, 0.28, 0.33, 0.04)]);     // engine cover
  for (const side of [1, -1]) {                                                                      // sidepods
    const z = (a, b) => (side > 0 ? [a, b] : [-b, -a]);
    loft([rect(-0.55, 0.08, 0.40, ...z(0.27, 0.62)), rect(0.1, 0.08, 0.36, ...z(0.29, 0.60)), rect(0.85, 0.08, 0.22, ...z(0.19, 0.42))]);
  }
  loft([sym(-2.48, 0.03, 0.07, 0.98), sym(-2.12, 0.03, 0.07, 0.98)], accent);                        // front wing
  loft([sym(-2.2, 0.11, 0.14, 0.92), sym(-2.02, 0.12, 0.15, 0.92)]);
  for (const side of [1, -1]) loft([rect(-2.5, 0.03, 0.24, side * 0.96, side * 1.0), rect(-2.0, 0.03, 0.24, side * 0.96, side * 1.0)]);
  loft([sym(1.42, 0.78, 0.84, 0.56), sym(1.78, 0.78, 0.84, 0.56)], accent);                           // rear wing
  loft([sym(1.56, 0.88, 0.92, 0.56), sym(1.8, 0.89, 0.93, 0.56)]);
  for (const side of [1, -1]) loft([rect(1.36, 0.38, 0.96, side * 0.55, side * 0.59), rect(1.86, 0.38, 0.96, side * 0.55, side * 0.59)]);
  segs.push([[1.55, 0.27, 0], [1.55, 0.78, 0]]);
  const halo = [];                                                                                     // the halo
  for (let i = 0; i <= 24; i++) {
    const t = Math.PI * i / 24;
    halo.push([-0.62 + 0.7 * Math.sin(t), 0.66 - 0.06 * Math.sin(t), 0.25 * Math.cos(t)]);
  }
  accent.push(...sportSegs(halo, false), [[-0.62, 0.5, 0], [-0.62, 0.66, 0]]);
  function wheel(xc, r, zc, w) {
    const ring = z => sportCircle(t => [xc + r * Math.cos(t), r + r * Math.sin(t), z], 20);
    const a = ring(zc - w / 2), b = ring(zc + w / 2);
    segs.push(...sportSegs(a, true), ...sportSegs(b, true));
    for (let i = 0; i < 20; i += 2) faint.push([a[i], b[i]]);
    faint.push(...sportSegs(sportCircle(t => [xc + r * 0.45 * Math.cos(t), r + r * 0.45 * Math.sin(t), zc + Math.sign(zc) * w / 2], 12), true));
  }
  for (const side of [1, -1]) {
    wheel(-1.55, 0.33, side * 0.80, 0.30);
    wheel(1.12, 0.36, side * 0.78, 0.40);
    faint.push([[-1.4, 0.26, side * 0.16], [-1.55, 0.33, side * 0.64]], [[-1.2, 0.14, side * 0.2], [-1.55, 0.30, side * 0.64]]);
    faint.push([[0.9, 0.3, side * 0.2], [1.12, 0.36, side * 0.58]], [[1.0, 0.12, side * 0.18], [1.12, 0.32, side * 0.58]]);
  }
  const fit = p => [(p[0] + 0.1) / 1.95, (p[1] - 0.45) / 1.95, p[2] / 1.95];   // centred, sized like a ball
  const fix = list => list.map(([a, b]) => [fit(a), fit(b)]);
  return { segs: fix(segs), accent: fix(accent), faint: fix(faint) };
}

// Each sport's shape, its tilt towards the viewer and how fast it turns (radians a second)
const SPORT_OBJECTS = {
  football: { shape: sportFootball(), tilt: 0.35, speed: 0.45 },
  basketball: { shape: sportBasketball(), tilt: 0.3, speed: 0.5 },
  'american-football': { shape: sportAmerican(), tilt: 0.3, speed: 0.4 },
  baseball: { shape: sportBaseball(), tilt: 0.45, speed: 0.5 },
  f1: { shape: sportCar(), tilt: 0.42, speed: 0.35 },
};

// Lines in four depth bands, so the near side is brighter
function sportStroke(ctx, list, ay, ax, cx, cy, R, weight, bright, ratio) {
  const bands = [[], [], [], []];
  for (const [a, b] of list) {
    const p = sportTurn(a, ay, ax), q = sportTurn(b, ay, ax), z = (p[2] + q[2]) / 2;
    bands[Math.max(0, Math.min(3, Math.floor((z + 1) * 2)))].push([p, q]);
  }
  bands.forEach((band, i) => {
    if (!band.length) return;
    ctx.beginPath();
    for (const [p, q] of band) { ctx.moveTo(cx + p[0] * R, cy - p[1] * R); ctx.lineTo(cx + q[0] * R, cy - q[1] * R); }
    ctx.strokeStyle = `rgba(${SPORT_RGB},${[0.14, 0.26, 0.6, 1][i] * bright})`;
    ctx.lineWidth = weight;
    ctx.shadowColor = `rgba(${SPORT_RGB},${i === 3 ? 0.8 : 0.3})`;
    ctx.shadowBlur = (i === 3 ? 8 : 3) * ratio;
    ctx.stroke();
  });
  ctx.shadowBlur = 0;
}

// Draw one sport's object, turned to `seconds`, filling its canvas
function drawSportObject(canvas, name, seconds) {
  const o = SPORT_OBJECTS[name];
  if (!o) return;
  const ratio = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;                                   // not laid out (hidden)
  if (canvas.width !== Math.round(w * ratio) || canvas.height !== Math.round(h * ratio)) {
    canvas.width = Math.round(w * ratio);
    canvas.height = Math.round(h * ratio);
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, w, h);
  drawSportAt(ctx, name, seconds, w / 2, h / 2, Math.min(w, h) * 0.42);
}

// Draw one sport's object, turned to `seconds`, centred on (cx, cy) with radius R, on a canvas
// already set up (the kick draws the football this way, so it is the hub's ball)
function drawSportAt(ctx, name, seconds, cx, cy, R) {
  const o = SPORT_OBJECTS[name];
  if (!o) return;
  const ratio = window.devicePixelRatio || 1;
  const ay = seconds * o.speed, ax = o.tilt, s = o.shape;
  if (s.sphere) {                                        // a dark, softly lit ball under the lines
    const g = ctx.createRadialGradient(cx - R * 0.35, cy - R * 0.4, R * 0.1, cx, cy, R);
    g.addColorStop(0, 'rgba(30,90,150,.55)');
    g.addColorStop(1, 'rgba(6,22,44,.75)');
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, 2 * Math.PI); ctx.fillStyle = g; ctx.fill();
    ctx.strokeStyle = `rgba(${SPORT_RGB},.45)`; ctx.lineWidth = 1; ctx.stroke();
  }
  if (s.pentas) {                                        // the football's pentagons, lit on the near side
    for (const pen of s.pentas) {
      const c = sportTurn(pen.c, ay, ax);
      if (c[2] < 0) continue;
      ctx.beginPath();
      pen.outline.forEach((p, i) => { const q = sportTurn(p, ay, ax); ctx[i ? 'lineTo' : 'moveTo'](cx + q[0] * R, cy - q[1] * R); });
      ctx.closePath(); ctx.fillStyle = `rgba(${SPORT_RGB},${0.12 + 0.3 * c[2]})`; ctx.fill();
    }
  }
  if (s.faint) sportStroke(ctx, s.faint, ay, ax, cx, cy, R, 1, 0.45, ratio);
  sportStroke(ctx, s.segs, ay, ax, cx, cy, R, 1.4, 1, ratio);
  if (s.accent) sportStroke(ctx, s.accent, ay, ax, cx, cy, R, 1.8, 1.15, ratio);
}
