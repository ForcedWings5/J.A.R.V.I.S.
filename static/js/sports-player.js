// ---------- The 3D player (docs/specs/2026-11-07-sports-space.md, "The 3D player") ----------
// The kick's player as a downloaded 3D character: a hologram outline in a Roma-red shirt with
// JARVIS 5 SPQR on the back, controlling the ball, taking his touches and striking it. Drawn
// with three.js (kept in ./vendor, pinned by fingerprint). The character and its one baked
// animation are files the owner keeps on this Mac (static/models/, made by
// scripts/bake_player.py); without them, or without WebGL, `ready` stays false and the
// code-drawn kick (sports-kick.js) plays instead.
//
// An ES module, loaded last: it gives the classic scripts window.sportsPlayer =
// { ready, load(), play(kickCanvas, target), checkData(data) }. play() returns the same
// { done, skip(), cancel() } as playKick, so space-sports.js holds either the same way.
// three.js itself is read only when the globe first opens (load()), not at every page start
let THREE = null, GLTFLoader = null;

const PLAYER_FILES = { model: '/static/models/player.glb', data: '/static/models/player.json' };
const PLAYER_PACE = 1.25;      // the owner's choice; the bake already plays at this speed
// The camera: behind the player and to his right, low, aimed right of and above the run, so
// the whole run stays in the lower left of the globe's square, clear of most pins (tuned in
// the picker on 2026-11-08; the test page's values were for a whole window)
const PLAYER_VIEW = { fov: 30, az: 34, el: 6, dist: 9.5, aimRight: 1.0, aimAhead: 0, aimUp: 1.0 };
const PLAYER_KIT = { jersey: '#8e1f2f', trim: '#f0bc42', hairGain: 0.4 };

// ---------- the checks on player.json (the bake tool checks the same before saving) ----------
const isNum = v => typeof v === 'number' && Number.isFinite(v);
const isVec = v => Array.isArray(v) && v.length === 3 && v.every(x => isNum(x) && Math.abs(x) <= 20);

function checkData(d) {
  if (!d || typeof d !== 'object' || Array.isArray(d)) return 'not an object';
  if (d.version !== 1) return 'version must be 1';
  if (!(isNum(d.end) && d.end > 0 && d.end <= 8)) return 'end must be a number of seconds, more than 0 and at most 8';
  if (!(isNum(d.strike) && d.strike > 0 && d.strike <= d.end)) return 'strike must be within the animation';
  if (!(isNum(d.ballR) && d.ballR > 0 && d.ballR <= 0.5)) return 'ballR must be more than 0 and at most 0.5';
  const inc = d.incoming;
  if (!(inc && isNum(inc.from) && isNum(inc.to) && inc.from >= 0 && inc.from < inc.to && inc.to <= d.strike && isVec(inc.start))) {
    return "incoming must run from 'from' to 'to' before the strike, from a 'start' point";
  }
  if (!(Array.isArray(d.ball) && d.ball.length >= 2 && d.ball.length <= 12)) return 'ball must have 2 to 12 points';
  let last = inc.to;
  for (let i = 0; i < d.ball.length; i++) {
    const b = d.ball[i];
    if (!(b && isNum(b.t) && isVec(b.p))) return `ball point ${i} needs a time t and a position p`;
    if (b.t < last - 1e-6 || b.t > d.strike + 1e-6) return `ball point ${i} is out of order`;
    last = b.t;
  }
  const cam = d.camera;
  if (!(cam && isVec(cam.target) && isVec(cam.forward) && Math.hypot(...cam.forward) > 0.1)) return 'camera needs a target and a forward direction';
  return null;
}

// ---------- the look: the hologram, and the shirt in its colours ----------
const VERT = `
  #include <common>
  #include <skinning_pars_vertex>
  varying vec3 vBind; varying vec3 vBindN; varying vec3 vN; varying vec3 vView;
  void main() {
    vBind = position; vBindN = normal;
    #include <beginnormal_vertex>
    #include <skinbase_vertex>
    #include <skinnormal_vertex>
    #include <begin_vertex>
    #include <skinning_vertex>
    vec4 mv = modelViewMatrix * vec4(transformed, 1.0);
    vN = normalize(normalMatrix * objectNormal);
    vView = -mv.xyz;
    gl_Position = projectionMatrix * mv;
  }`;
// Bright where the surface turns away from you, nearly clear in the middle; scan lines, flicker
const HOLO_FRAG = `
  uniform float uTime, uGain;
  varying vec3 vBind; varying vec3 vBindN; varying vec3 vN; varying vec3 vView;
  void main() {
    vec3 n = normalize(vN), v = normalize(vView);
    float edge = pow(1.0 - abs(dot(n, v)), 2.2);
    float I = 0.035 + 0.95 * edge;
    float scan = mod(gl_FragCoord.y + uTime * 40.0, 3.0) < 1.0 ? 0.65 : 1.0;
    float flicker = 0.93 + 0.07 * sin(uTime * 14.0) * sin(uTime * 43.0);
    vec3 c = vec3(0.30, 0.79, 0.94) * I + vec3(0.6, 0.2, 0.06) * I * I * I;
    gl_FragColor = vec4(c * scan * flicker * uGain, 1.0);
  }`;
// The character's own shirt as the jersey. Its rest shape (vBind) places the trims and the
// print: the hem at the bottom, the collar at the top, the sleeve ends at the sides.
const SHIRT_FRAG = `
  uniform sampler2D uPrint; uniform vec3 uJersey, uTrim; uniform vec3 uMin, uMax; uniform float uBody;
  varying vec3 vBind; varying vec3 vBindN; varying vec3 vN; varying vec3 vView;
  void main() {
    vec3 n = normalize(vN), v = normalize(vView);
    float shade = 0.38 + 0.62 * max(0.0, dot(n, normalize(vec3(0.3, 0.8, 0.6))));
    float ax = abs(vBind.x - (uMin.x + uMax.x) * 0.5);
    bool hem = vBind.y < uMin.y + 0.022 * uBody;
    bool collar = vBind.y > uMax.y - 0.03 * uBody && ax < 0.08 * uBody;
    bool cuff = ax > (uMax.x - uMin.x) * 0.5 - 0.02 * uBody;
    vec3 col = ((hem || collar || cuff) ? uTrim : uJersey) * shade;
    float top = uMax.y - 0.075 * uBody, bottom = top - 0.2 * uBody;
    if (vBindN.z < -0.15 && ax < 0.1 * uBody && vBind.y > bottom && vBind.y < top) {
      vec2 uv = vec2((0.1 * uBody - (vBind.x - (uMin.x + uMax.x) * 0.5)) / (0.2 * uBody), (vBind.y - bottom) / (top - bottom));
      vec4 t = texture2D(uPrint, uv);
      col = mix(col, t.rgb * shade, t.a);
    }
    float rim = pow(1.0 - max(0.0, dot(n, v)), 3.0);
    gl_FragColor = vec4(col + vec3(0.30, 0.79, 0.94) * rim * 0.6, 1.0);
  }`;

// The print on the back, drawn in code: JARVIS, a large 5, SPQR, in gold
function printTexture() {
  const c = document.createElement('canvas');
  c.width = 256; c.height = 300;
  const g = c.getContext('2d');
  g.textAlign = 'center'; g.lineJoin = 'round';
  const word = (text, size, y, spacing) => {
    g.font = `800 ${size}px "Helvetica Neue", Arial, sans-serif`;
    if ('letterSpacing' in g) g.letterSpacing = spacing + 'px';
    g.lineWidth = size * 0.12; g.strokeStyle = 'rgba(60,10,16,.9)'; g.strokeText(text, 128, y);
    g.fillStyle = PLAYER_KIT.trim; g.fillText(text, 128, y);
  };
  word('JARVIS', 38, 52, 4); word('5', 175, 222, 0); word('SPQR', 42, 278, 6);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// ---------- the scene, built once ----------
let data = null, canvas = null, renderer = null, scene = null, camera = null, mixer = null, clip = null;
let ballSprite = null, ballCanvas = null, ballTexture = null;
const holoMaterials = [];
let loading = null;

async function build() {
  THREE = await import('./vendor/three.module.min.js');
  ({ GLTFLoader } = await import('./vendor/GLTFLoader.js'));
  const res = await fetch(PLAYER_FILES.data);
  if (!res.ok) throw new Error('player.json ' + res.status);
  data = await res.json();
  const problem = checkData(data);
  if (problem) throw new Error('player.json: ' + problem);
  const gltf = await new GLTFLoader().loadAsync(PLAYER_FILES.model);
  clip = gltf.animations.find(a => a.name === 'kick') || gltf.animations[0];
  if (!clip) throw new Error('player.glb has no animation');

  canvas = document.getElementById('sp-player');
  renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  canvas.addEventListener('webglcontextlost', e => {
    e.preventDefault();
    player.ready = false;
    console.warn('3D player unavailable: the 3D canvas was lost');
  });
  scene = new THREE.Scene();
  scene.add(gltf.scene);
  camera = new THREE.PerspectiveCamera(PLAYER_VIEW.fov, 1, 0.05, 100);

  let bodyH = 1;
  gltf.scene.traverse(o => {
    if (o.isMesh && /Body/.test(o.name)) { o.geometry.computeBoundingBox(); bodyH = o.geometry.boundingBox.max.y - o.geometry.boundingBox.min.y; }
  });
  const print = printTexture();
  gltf.scene.traverse(o => {
    if (!o.isSkinnedMesh) return;
    o.frustumCulled = false;
    if (/Shirt/.test(o.name)) {
      o.geometry.computeBoundingBox();
      const gb = o.geometry.boundingBox;
      o.material = new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: SHIRT_FRAG, uniforms: {
        uPrint: { value: print }, uJersey: { value: new THREE.Color(PLAYER_KIT.jersey) }, uTrim: { value: new THREE.Color(PLAYER_KIT.trim) },
        uMin: { value: gb.min }, uMax: { value: gb.max }, uBody: { value: bodyH } } });
      o.renderOrder = 0;                 // drawn first, so it hides what is behind it
    } else {
      o.material = new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: HOLO_FRAG,
        uniforms: { uTime: { value: 0 }, uGain: { value: /Hair/.test(o.name) ? PLAYER_KIT.hairGain : 1 } },
        blending: THREE.AdditiveBlending, transparent: true, depthWrite: false });
      o.renderOrder = 1;
      holoMaterials.push(o.material);
    }
  });

  // The ball: the hub's 3D football (sports-objects.js) drawn on a small canvas each frame and
  // shown as a sprite in the scene, so the player hides it when it is behind him
  ballCanvas = document.createElement('canvas');
  ballCanvas.width = ballCanvas.height = 128;
  ballTexture = new THREE.CanvasTexture(ballCanvas);
  ballSprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: ballTexture, transparent: true, depthWrite: false }));
  ballSprite.scale.set(data.ballR * 2.3, data.ballR * 2.3, 1);
  scene.add(ballSprite);

  mixer = new THREE.AnimationMixer(gltf.scene);
  mixer.clipAction(clip).play();
  // Prepare every shader now, while nothing moves: done on the first kick's first frame, it
  // took 137 ms there and skipped the start of the run (final review)
  // and draw one practice frame (hidden), so the textures are sent to the graphics card and
  // the animation is bound before the first kick, not during it
  placeCamera(canvas.clientWidth || 600, canvas.clientHeight || 600);
  renderer.compile(scene, camera);
  mixer.setTime(0);
  drawSportAt(ballCanvas.getContext('2d'), 'football', 0, 64, 64, 50);
  ballTexture.needsUpdate = true;
  renderer.render(scene, camera);
  player.ready = true;
}

function load() {
  if (!loading) {
    loading = build().catch(e => {
      player.ready = false;
      console.warn('3D player unavailable: ' + ((e && e.message) || e));
    });
  }
  return loading;
}

// ---------- each frame ----------
const v3 = (a) => new THREE.Vector3(a[0], a[1], a[2]);

function placeCamera(w, h) {
  const up = new THREE.Vector3(0, 1, 0), target = v3(data.camera.target);
  const fwd = v3(data.camera.forward).setY(0).normalize(), right = new THREE.Vector3().crossVectors(fwd, up).normalize();
  const az = THREE.MathUtils.degToRad(PLAYER_VIEW.az), el = THREE.MathUtils.degToRad(PLAYER_VIEW.el), d = PLAYER_VIEW.dist;
  camera.position.copy(target).addScaledVector(fwd, -d * Math.cos(el) * Math.cos(az))
    .addScaledVector(right, d * Math.cos(el) * Math.sin(az)).addScaledVector(up, d * Math.sin(el));
  camera.lookAt(target.clone().addScaledVector(right, PLAYER_VIEW.aimRight).addScaledVector(fwd, PLAYER_VIEW.aimAhead)
    .addScaledVector(up, PLAYER_VIEW.aimUp));
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

// Where the ball is at T (seconds), before the strike: dropping in, then from touch to touch.
// After a touch in the air it falls to the floor; on the floor it rolls, quick then slowing.
function ballBefore(T) {
  const inc = data.incoming, R = data.ballR;
  if (T < inc.from) return null;
  if (T < inc.to) {
    const u = (T - inc.from) / (inc.to - inc.from), a = v3(inc.start), b = v3(data.ball[0].p);
    const p = a.clone().lerp(b, u);
    p.y = a.y + (b.y - a.y) * u * u;
    return p;
  }
  let i = 0;
  while (i < data.ball.length - 2 && T > data.ball[i + 1].t) i++;
  const A = data.ball[i], B = data.ball[i + 1];
  const u = Math.max(0, Math.min(1, (T - A.t) / Math.max(1e-3, B.t - A.t)));
  const a = v3(A.p), b = v3(B.p);
  if (a.y > R + 0.01) { const p = a.clone().lerp(b, u); p.y = a.y + (R - a.y) * u * u; return p; }
  return a.lerp(b, 1 - (1 - u) * (1 - u));
}

function toCanvas(p, w, h) {
  const q = p.clone().project(camera);
  return [(q.x + 1) / 2 * w, (1 - q.y) / 2 * h];
}

function drawFrame(T, kickCanvas, target) {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h, false);
  placeCamera(w, h);
  mixer.setTime(Math.min(T, clip.duration - 1e-3));
  for (const m of holoMaterials) m.uniforms.uTime.value = performance.now() / 1000;
  canvas.style.opacity = T > data.end ? String(Math.max(0, 1 - (T - data.end) / 0.5)) : '';

  // The 2D layer above: clear, and from the strike on, the flight to the country
  const ratio = window.devicePixelRatio || 1;
  if (kickCanvas.width !== Math.round(w * ratio) || kickCanvas.height !== Math.round(h * ratio)) {
    kickCanvas.width = Math.round(w * ratio);
    kickCanvas.height = Math.round(h * ratio);
  }
  const ctx = kickCanvas.getContext('2d');
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, w, h);

  if (T < data.strike) {
    const p = ballBefore(T);
    ballSprite.visible = Boolean(p);
    if (p) {
      ballSprite.position.copy(p);
      const g = ballCanvas.getContext('2d');
      g.setTransform(1, 0, 0, 1, 0, 0);
      g.clearRect(0, 0, 128, 128);
      drawSportAt(g, 'football', T * 5, 64, 64, 50);
      ballTexture.needsUpdate = true;
    }
  } else {
    ballSprite.visible = false;
    const restP = v3(data.ball[data.ball.length - 1].p);
    const from = toCanvas(restP, w, h);
    const r = Math.abs(toCanvas(restP.clone().add(new THREE.Vector3(0, data.ballR, 0)), w, h)[1] - from[1]);
    const goal = target(), to = [goal.x, goal.y];
    const path = { from, to, peak: Math.max(r, Math.min(from[1], to[1]) - h * 0.38), hop: r * 8 / KICK.BALL };
    drawFlight(ctx, KICK.STRIKE_MS + (T - data.strike) * 1000 * PLAYER_PACE, path, r);
  }
  renderer.render(scene, camera);
}

// Play the kick: the same contract as playKick (sports-kick.js). The page comes when the code-
// drawn kick's would, measured from the strike; a safety timeout ends it if frames stop.
function play(kickCanvas, target) {
  let resolve, frame = null, safety = null, finished = false;
  const done = new Promise(r => { resolve = r; });
  const end = ok => {
    if (finished) return;
    finished = true;
    cancelAnimationFrame(frame);
    clearTimeout(safety);
    if (canvas) { canvas.hidden = true; canvas.style.opacity = ''; }
    kickCanvas.hidden = true;
    resolve(ok);
  };
  if (!player.ready || !canvas) { end(true); return { done, skip() {}, cancel() {} }; }
  canvas.hidden = false;
  kickCanvas.hidden = false;
  if (!canvas.clientWidth || !canvas.clientHeight) { end(true); return { done, skip() {}, cancel() {} }; }
  const endT = data.strike + (KICK.END_MS - KICK.STRIKE_MS) / 1000 / PLAYER_PACE;
  const start = performance.now();
  const step = now => {
    const T = Math.max(0, (now - start) / 1000);
    if (T >= endT) { end(true); return; }
    try {
      drawFrame(T, kickCanvas, target);
    } catch (e) {                                  // never let a frame break the page
      player.ready = false;
      console.warn('3D player unavailable: ' + ((e && e.message) || e));
      end(true);
      return;
    }
    frame = requestAnimationFrame(step);
  };
  frame = requestAnimationFrame(step);
  safety = setTimeout(() => end(true), endT * 1000 + 400);
  return { done, skip: () => end(true), cancel: () => end(false) };
}

const player = {
  ready: false, load, play, checkData,
  // For checks by hand in a demo only (CHANGELOG section 63): lose the 3D canvas, and draw
  // one moment (T in seconds) without frames
  _loseContext() { if (renderer) renderer.forceContextLoss(); },
  _still(T, kickCanvas, target) { canvas.hidden = false; kickCanvas.hidden = false; drawFrame(T, kickCanvas, target); },
};
window.sportsPlayer = player;
