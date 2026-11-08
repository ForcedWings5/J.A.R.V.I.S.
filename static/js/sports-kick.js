// ---------- The kick (docs/specs/2026-11-07-sports-space.md, "Animations") ----------
// A silhouette runs in from the bottom left and kicks the football; the ball arcs to the
// league's country on the globe, bounces once with a ripple, and the league page follows.
// The body model, its 12 key poses and their timing come unchanged from the throwaway test
// the owner judged good enough (2026-11-07). The maths is pure (kickMath) so it can be checked
// on its own in the page; drawKick draws one frame; playKick runs it. sports-football.js says
// when.

// The body and its poses. Lengths are model units (the figure is about 190 tall). In a pose,
// n is the near (kicking) side and f the far (standing) side: T thigh angle, K knee bend,
// A upper arm, E elbow bend, F toe point, all in degrees from straight down (+ is forward);
// x is how far the hips have travelled, lean the body's lean, air a lift off the floor.
const KICK = (() => {
  const LEN = { torso: 60, neck: 8, head: 12, thigh: 46, shin: 45, foot: 17, upper: 31, fore: 29 };
  const KEYS = [
    { x: 0,   lean: 14, nT: 28,  nK: 18,  fT: -26, fK: 70,  nA: -35, nE: 80, fA: 35, fE: 80 },
    { x: 45,  lean: 13, nT: 2,   nK: 12,  fT: 15,  fK: 100, nA: 0,   nE: 75, fA: 0,  fE: 75, air: 5 },
    { x: 90,  lean: 14, nT: -26, nK: 70,  fT: 28,  fK: 18,  nA: 35,  nE: 80, fA: -35, fE: 80 },
    { x: 135, lean: 13, nT: 15,  nK: 100, fT: 2,   fK: 12,  nA: 0,   nE: 75, fA: 0,  fE: 75, air: 5 },
    { x: 188, lean: 6,  nT: -32, nK: 50,  fT: 40,  fK: 12,  nA: -40, nE: 40, fA: 50, fE: 40, air: 7, nF: 30 },
    { x: 214, lean: -6, nT: -36, nK: 98, fT: 8,   fK: 24,  nA: -55, nE: 25, fA: 78, fE: 15, nF: 35 },
    { x: 221, lean: -5, nT: 4,   nK: 96,  fT: 4,   fK: 22,  nA: -42, nE: 22, fA: 82, fE: 12, nF: 35 },
    { x: 225, lean: -10, nT: 38, nK: 12,  fT: 0,   fK: 16,  nA: -35, nE: 20, fA: 85, fE: 10, nF: 32 },
    { x: 231, lean: -16, nT: 78, nK: 6,   fT: -6,  fK: 10,  nA: -15, nE: 30, fA: 70, fE: 20, nF: 30, fF: 20 },
    { x: 241, lean: -18, nT: 95, nK: 14,  fT: -12, fK: 8,   nA: 0,   nE: 40, fA: 55, fE: 30, air: 5, nF: 25, fF: 35 },
    { x: 268, lean: -2, nT: 35,  nK: 45,  fT: -10, fK: 25,  nA: -10, nE: 50, fA: 25, fE: 40, air: 9, fF: 30 },
    { x: 290, lean: 4,  nT: 14,  nK: 12,  fT: -12, fK: 20,  nA: -8,  nE: 25, fA: 10, fE: 25 },
  ];
  const GAPS = [105, 105, 105, 125, 140, 90, 55, 90, 140, 170, 220];   // ms between key poses
  const STRIKE = 7;                                                      // the pose where foot meets ball
  const FIELDS = ['x', 'lean', 'nT', 'nK', 'fT', 'fK', 'nA', 'nE', 'fA', 'fE', 'air', 'nF', 'fF'];
  const TIMES = [0];
  for (const g of GAPS) TIMES.push(TIMES[TIMES.length - 1] + g);
  const FLY_MS = 1100;
  return {
    LEN, KEYS, GAPS, STRIKE, FIELDS, TIMES,
    STRIKE_MS: TIMES[STRIKE],                 // 725: the foot meets the ball
    FIGURE_MS: TIMES[TIMES.length - 1],       // 1345: the last pose; the figure then fades
    FLY_MS,
    LAND_MS: TIMES[STRIKE] + FLY_MS,          // 1825: the ball lands
    HOP_MS: 300,                              // its one bounce
    END_MS: 2300,                             // the league page (spec: about 2.3 s in all)
    BALL: 11,                                 // the ball's radius, model units
  };
})();

const kickRad = d => d * Math.PI / 180;
const kickDown = a => [Math.sin(kickRad(a)), Math.cos(kickRad(a))];    // + is forward
const kickUp = a => [Math.sin(kickRad(a)), -Math.cos(kickRad(a))];
const kickAdd = (p, v, l) => [p[0] + v[0] * l, p[1] + v[1] * l];
const kickMid = (a, b, u) => [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u];

const kickMath = {
  // The pose at t ms: Catmull-Rom between the key poses, so the motion flows through them
  // instead of stopping at each
  poseAt(t) {
    const { KEYS, GAPS, TIMES, FIELDS } = KICK;
    t = Math.max(0, Math.min(KICK.FIGURE_MS, t));
    const at = (k, f) => KEYS[Math.max(0, Math.min(KEYS.length - 1, k))][f] || 0;
    let i = 0;
    while (i < GAPS.length - 1 && t > TIMES[i + 1]) i++;
    const u = (t - TIMES[i]) / GAPS[i], P = {};
    for (const f of FIELDS) {
      const p0 = at(i - 1, f), p1 = at(i, f), p2 = at(i + 1, f), p3 = at(i + 2, f);
      P[f] = 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u);
    }
    return P;
  },

  // The joints for a pose, with the lowest foot on the floor (y = 0), raised by `air`: no
  // sinking, no floating. Model units, y down.
  skeleton(P) {
    const L = KICK.LEN;
    const build = hip => {
      const tu = kickUp(P.lean);
      const chest = kickAdd(hip, tu, L.torso - 16), neck = kickAdd(hip, tu, L.torso);
      const head = kickAdd(neck, tu, L.neck + L.head), sh = kickAdd(hip, tu, L.torso - 7);
      const leg = (T, K, F) => {
        const knee = kickAdd(hip, kickDown(T), L.thigh), s = T - K;
        const ank = kickAdd(knee, kickDown(s), L.shin);
        return { knee, ank, toe: kickAdd(ank, kickDown(s + 90 - F), L.foot) };
      };
      const arm = (A, E) => {
        const el = kickAdd(sh, kickDown(A), L.upper);
        return { el, hand: kickAdd(el, kickDown(A + E), L.fore) };
      };
      return { hip, chest, neck, head, sh, n: leg(P.nT, P.nK, P.nF), f: leg(P.fT, P.fK, P.fF), na: arm(P.nA, P.nE), fa: arm(P.fA, P.fE) };
    };
    const b = build([P.x, 0]);
    const depth = Math.max(b.n.ank[1] + 4, b.n.toe[1] + 3, b.f.ank[1] + 4, b.f.toe[1] + 3);
    return build([P.x, -depth - P.air]);
  },

  // Model units to canvas pixels: the figure starts near the left, standing on a floor 80%
  // of the way down
  layout(w, h) {
    return { s: Math.min(h / 430, w / 820), ox: w * 0.08, gy: h * 0.8 };
  },

  // Where the ball is at t ms, in canvas pixels. path: { from, to } as [x, y], `peak` the
  // height of the arc's control point, `hop` the bounce's height. scale shrinks it as it
  // flies away (1 to 0.5); squash flattens it at the strike and the landing.
  ballAt(t, path) {
    const { from, to, peak, hop } = path;
    if (t < KICK.STRIKE_MS) return { x: from[0], y: from[1], scale: 1, spin: 0, squash: 1 };
    if (t < KICK.LAND_MS) {
      const p = (t - KICK.STRIKE_MS) / KICK.FLY_MS, e = 1 - Math.pow(1 - p, 1.7);
      const cx = (from[0] + to[0]) / 2, a = (1 - e) * (1 - e), b = 2 * (1 - e) * e, c = e * e;
      return {
        x: a * from[0] + b * cx + c * to[0],
        y: a * from[1] + b * peak + c * to[1],
        scale: 1 - 0.5 * e, spin: p * 14, squash: p < 0.06 ? 0.8 : 1,
      };
    }
    const p = Math.min(1, (t - KICK.LAND_MS) / KICK.HOP_MS);
    return { x: to[0], y: to[1] - Math.sin(Math.PI * p) * hop, scale: 0.5, spin: 14 + p * 2, squash: p < 0.12 ? 0.75 : 1 };
  },
};

// Where the ball waits, in model units: just in front of the kicking foot at the strike
const KICK_REST = (() => {
  const B = kickMath.skeleton(kickMath.poseAt(KICK.STRIKE_MS));
  return [B.n.toe[0] + KICK.BALL * 0.7, -KICK.BALL];
})();

// ---------- drawing ----------

// A tapered limb: round at both ends, r1 wide at a and r2 at b
function kickLimb(ctx, a, b, r1, r2) {
  const ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
  ctx.moveTo(a[0], a[1]);
  ctx.arc(a[0], a[1], r1, ang + Math.PI / 2, ang - Math.PI / 2);
  ctx.arc(b[0], b[1], r2, ang - Math.PI / 2, ang + Math.PI / 2);
  ctx.closePath();
}

// The figure in JARVIS's pale cyan with its glow; the far limbs dimmer, drawn first
function kickFigure(ctx, B, ratio) {
  const part = (color, glow, draw) => {
    ctx.beginPath();
    draw();
    ctx.fillStyle = color;
    ctx.shadowColor = glow;
    ctx.shadowBlur = 16 * ratio;
    ctx.fill();
    ctx.shadowBlur = 0;
  };
  const far = '#5f8a9c', near = '#e3f7ff', body = '#cdeffa';
  const glow = 'rgba(76,201,240,.55)', farGlow = 'rgba(76,201,240,.25)';
  const leg = L => () => {
    kickLimb(ctx, B.hip, L.knee, 12, 8);
    kickLimb(ctx, L.knee, kickMid(L.knee, L.ank, 0.3), 8, 8.4);
    kickLimb(ctx, kickMid(L.knee, L.ank, 0.3), L.ank, 8.4, 4.4);
    kickLimb(ctx, L.ank, L.toe, 4.8, 3.4);
  };
  const arm = A => () => {
    kickLimb(ctx, B.sh, A.el, 7.6, 5.6);
    kickLimb(ctx, A.el, A.hand, 5.6, 4);
    ctx.moveTo(A.hand[0] + 5, A.hand[1]);
    ctx.arc(A.hand[0], A.hand[1], 5, 0, 2 * Math.PI);
  };
  part(far, farGlow, arm(B.fa));
  part(far, farGlow, leg(B.f));
  part(body, glow, () => {
    kickLimb(ctx, B.hip, B.chest, 14, 18);
    kickLimb(ctx, B.chest, B.neck, 18, 7.5);
    ctx.moveTo(B.head[0] + 12, B.head[1]);
    ctx.arc(B.head[0], B.head[1], 12, 0, 2 * Math.PI);
  });
  part(near, glow, leg(B.n));
  part(near, glow, arm(B.na));
}

// One frame at t ms. target() gives the country's point in the canvas's CSS pixels ({x, y}),
// read every frame so a resize follows the pin.
function drawKick(canvas, t, target) {
  const ratio = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  if (canvas.width !== Math.round(w * ratio) || canvas.height !== Math.round(h * ratio)) {
    canvas.width = Math.round(w * ratio);
    canvas.height = Math.round(h * ratio);
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const L = kickMath.layout(w, h);

  // The floor: a soft line that fades at both ends
  const floor = ctx.createLinearGradient(0, 0, w, 0);
  floor.addColorStop(0, 'rgba(120,215,255,0)');
  floor.addColorStop(0.3, 'rgba(120,215,255,.35)');
  floor.addColorStop(0.7, 'rgba(120,215,255,.12)');
  floor.addColorStop(1, 'rgba(120,215,255,0)');
  ctx.fillStyle = floor;
  ctx.fillRect(0, L.gy, w, 1.5);

  // The figure and its shadow, fading once the kick is done
  const fade = t > KICK.FIGURE_MS ? Math.max(0, 1 - (t - KICK.FIGURE_MS) / 500) : 1;
  if (fade > 0) {
    const B = kickMath.skeleton(kickMath.poseAt(t));
    ctx.save();
    ctx.translate(L.ox, L.gy);
    ctx.scale(L.s, L.s);
    ctx.globalAlpha = fade;
    ctx.beginPath();
    ctx.ellipse(B.hip[0], 0, 34, 4, 0, 0, 2 * Math.PI);
    ctx.fillStyle = 'rgba(0,0,0,.5)';
    ctx.fill();
    kickFigure(ctx, B, ratio);
    ctx.restore();
  }

  // The ball: its path from where it waits to the country
  const r = KICK.BALL * L.s;
  const from = [L.ox + KICK_REST[0] * L.s, L.gy + KICK_REST[1] * L.s];
  const goal = target();
  const to = [goal.x, goal.y];
  const path = { from, to, peak: Math.max(r, Math.min(from[1], to[1]) - h * 0.38), hop: 8 * L.s };
  const ball = kickMath.ballAt(t, path);

  // Its shadow on the floor, fainter as it rises
  if (t < KICK.STRIKE_MS + 200) {
    const up = Math.max(0, from[1] - ball.y);
    ctx.beginPath();
    ctx.ellipse(ball.x, L.gy, r * ball.scale * Math.max(0.3, 1 - up / 300), 3, 0, 0, 2 * Math.PI);
    ctx.fillStyle = `rgba(0,0,0,${0.5 * Math.max(0, 1 - up / 200)})`;
    ctx.fill();
  }
  if (t >= KICK.STRIKE_MS) drawFlight(ctx, t, path, r);
  else kickBall(ctx, ball, r);                    // waiting at the foot
}

// The ball: the hub's 3D football, squashed for a moment at the strike and landing
function kickBall(ctx, ball, r) {
  ctx.save();
  ctx.translate(ball.x, ball.y);
  ctx.scale(1 / ball.squash, ball.squash);
  drawSportAt(ctx, 'football', ball.spin, 0, 0, r * ball.scale);
  ctx.restore();
}

// The ball from the strike on (t in kick ms, at or after KICK.STRIKE_MS): its trail, the ball,
// and the ripple where it lands. path is kickMath.ballAt's; r the ball's radius at rest, in
// pixels. Both kicks use it: this one and the 3D player's (sports-player.js).
function drawFlight(ctx, t, path, r) {
  // The trail: where it was over the last moments of the flight (worked out, not stored)
  for (let k = 12; k >= 1; k--) {
    const tk = t - 16 * k;
    if (tk < KICK.STRIKE_MS || tk >= KICK.LAND_MS) continue;
    const q = kickMath.ballAt(tk, path), i = 12 - k;
    ctx.beginPath();
    ctx.arc(q.x, q.y, r * q.scale * (0.4 + 0.6 * i / 12), 0, 2 * Math.PI);
    ctx.fillStyle = `rgba(160,225,255,${0.25 * i / 12})`;
    ctx.fill();
  }
  kickBall(ctx, kickMath.ballAt(t, path), r);
  // The landing: a ripple that grows and fades
  if (t > KICK.LAND_MS) {
    const p = Math.min(1, (t - KICK.LAND_MS) / 900);
    ctx.beginPath();
    ctx.arc(path.to[0], path.to[1], 6 + p * 40, 0, 2 * Math.PI);
    ctx.strokeStyle = `rgba(76,201,240,${0.8 * (1 - p)})`;
    ctx.lineWidth = 2;
    ctx.stroke();
  }
}

// Play the kick on a canvas: { done, skip(), cancel() } (space-sports.js holds it). done
// resolves true at the end or on a skip, false when cancelled. A safety timeout ends it if
// frames stop (a hidden pane, a slow Mac), as globe.js and motion.js have.
function playKick(canvas, target) {
  let resolve, frame = null, safety = null, finished = false;
  const done = new Promise(r => { resolve = r; });
  const end = ok => {
    if (finished) return;
    finished = true;
    cancelAnimationFrame(frame);
    clearTimeout(safety);
    canvas.hidden = true;
    resolve(ok);
  };
  canvas.hidden = false;
  if (!canvas.clientWidth || !canvas.clientHeight) {      // not laid out: nothing to show
    end(true);
    return { done, skip() {}, cancel() {} };
  }
  const start = performance.now();
  const step = now => {
    const t = now - start;
    if (t >= KICK.END_MS) { end(true); return; }
    drawKick(canvas, t, target);
    frame = requestAnimationFrame(step);
  };
  drawKick(canvas, 0, target);
  frame = requestAnimationFrame(step);
  safety = setTimeout(() => end(true), KICK.END_MS + 400);
  return { done, skip: () => end(true), cancel: () => end(false) };
}
