/* Gloam dither kit — ordered (Bayer) dithering for pixel pages.
   Everything here draws whole pixels: gradients, tiles, transitions, light pools.
   Global: window.Dither */
(() => {
  const B2 = [0, 2, 3, 1].map(v => (v + .5) / 4);
  const B4 = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map(v => (v + .5) / 16);
  const B8 = [0, 32, 8, 40, 2, 34, 10, 42, 48, 16, 56, 24, 50, 18, 58, 26, 12, 44, 4, 36, 14, 46, 6, 38, 60, 28, 52, 20, 62, 30, 54, 22,
    3, 35, 11, 43, 1, 33, 9, 41, 51, 19, 59, 27, 49, 17, 57, 25, 15, 47, 7, 39, 13, 45, 5, 37, 63, 31, 55, 23, 61, 29, 53, 21].map(v => (v + .5) / 64);
  const MATRICES = { none: { n: 1, m: [.5] }, b2: { n: 2, m: B2 }, b4: { n: 4, m: B4 }, b8: { n: 8, m: B8 } };
  let M = MATRICES.b8;

  const thr = (x, y) => M.m[(y % M.n) * M.n + (x % M.n)];
  const t8 = (x, y) => B8[(y & 7) * 8 + (x & 7)];

  function rgb(h) { h = h.replace('#', ''); return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]; }
  function u32(h) { const [r, g, b] = rgb(h); return (255 << 24) | (b << 16) | (g << 8) | r; }
  const clamp = (v, a = 0, b = 1) => v < a ? a : v > b ? b : v;

  /** palette index for value t∈[0,1] across n colours, ordered-dithered at (x,y) */
  function q(t, n, x, y) {
    const v = clamp(t) * (n - 1), i = v | 0;
    return (v - i > thr(x, y)) ? Math.min(i + 1, n - 1) : i;
  }

  /** an 8×8 tile with `level` (0..1) of fg pixels over bg (null = transparent) → data URL */
  const tileCache = new Map();
  function tile(level, fg, bg = null, matrix = 'b8') {
    const key = level.toFixed(3) + fg + bg + matrix;
    if (tileCache.has(key)) return tileCache.get(key);
    const mm = MATRICES[matrix], c = document.createElement('canvas');
    c.width = c.height = 8;
    const x = c.getContext('2d'), d = x.createImageData(8, 8), F = rgb(fg), Bg = bg ? rgb(bg) : null;
    for (let j = 0; j < 8; j++) for (let i = 0; i < 8; i++) {
      const on = level > mm.m[(j % mm.n) * mm.n + (i % mm.n)], k = (j * 8 + i) * 4;
      const col = on ? F : Bg;
      if (col) { d.data[k] = col[0]; d.data[k + 1] = col[1]; d.data[k + 2] = col[2]; d.data[k + 3] = 255; }
    }
    x.putImageData(d, 0, 0);
    const url = c.toDataURL();
    tileCache.set(key, url);
    return url;
  }
  /** paint an element's background with a dither tile; px = size of one dither pixel in CSS px */
  function bg(el, level, fg, bgc = null, px = 2, matrix = 'b8') {
    el.style.backgroundImage = `url(${tile(level, fg, bgc, matrix)})`;
    el.style.backgroundSize = `${8 * px}px ${8 * px}px`;
    el.style.imageRendering = 'pixelated';
  }
  /** apply to every [data-dither="level fg [bg] [px]"] */
  function scan(root = document) {
    root.querySelectorAll('[data-dither]').forEach(el => {
      const [lv, fg, b, px] = el.dataset.dither.split(/\s+/);
      bg(el, +lv, fg, b && b !== '-' ? b : null, +(px || 2));
    });
  }

  /** a low-res canvas buffer you can poke 32-bit pixels into, then blit scaled */
  class Buffer {
    constructor(w, h) { this.resize(w, h); }
    resize(w, h) {
      this.w = w; this.h = h;
      this.c = document.createElement('canvas'); this.c.width = w; this.c.height = h;
      this.x = this.c.getContext('2d');
      this.img = this.x.createImageData(w, h);
      this.px = new Uint32Array(this.img.data.buffer);
    }
    flush() { this.x.putImageData(this.img, 0, 0); return this.c; }
    blit(ctx, dw, dh, dx = 0, dy = 0) { ctx.imageSmoothingEnabled = false; ctx.drawImage(this.flush(), dx, dy, dw ?? this.w, dh ?? this.h); }
  }

  /** fill a Buffer with fn(x,y) → t, dithered across palette (array of hex) */
  function field(buf, pal, fn) {
    const P = pal.map(u32), n = P.length, { w, h, px } = buf;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const t = fn(x, y);
      if (t === null) continue;
      px[y * w + x] = P[q(t, n, x, y)];
    }
  }

  /* ---------- full-screen transitions ---------- */
  let tcv = null;
  function overlay() {
    if (tcv) return tcv;
    tcv = document.createElement('canvas');
    Object.assign(tcv.style, { position: 'fixed', inset: '0', width: '100%', height: '100%', zIndex: 9999, pointerEvents: 'none', imageRendering: 'pixelated' });
    document.body.appendChild(tcv);
    return tcv;
  }
  const PATTERNS = {
    bayer: (x, y) => t8(x, y),
    iris: (x, y, W, H) => clamp(1 - Math.hypot(x - W / 2, (y - H / 2) * 1.6) / Math.hypot(W / 2, H * .8) + (t8(x, y) - .5) * .18),
    blinds: (x, y) => ((y % 8) / 8) * .82 + t8(x, y) * .18,
    diamond: (x, y, W, H) => clamp((Math.abs(x - W / 2) / W + Math.abs(y - H / 2) / H) + (t8(x, y) - .5) * .25),
    sweep: (x, y, W) => clamp(x / W * .8 + t8(x, y) * .2),
    rain: (x, y, W, H) => clamp(y / H * .7 + ((x * 7919) % 13) / 13 * .15 + t8(x, y) * .15),
  };
  /** cover the screen with dithered cells, call mid(), then reveal. Returns a Promise. */
  function transition({ pattern = 'bayer', color = '#0b0910', cell = 6, ms = 520, mid = null, out = null } = {}) {
    const cv = overlay(), ctx = cv.getContext('2d');
    const W = Math.ceil(innerWidth / cell), H = Math.ceil(innerHeight / cell);
    cv.width = W; cv.height = H;
    const f = PATTERNS[pattern] || PATTERNS.bayer, g = PATTERNS[out || pattern] || f;
    const vals = new Float32Array(W * H), vals2 = new Float32Array(W * H);
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { vals[y * W + x] = f(x, y, W, H); vals2[y * W + x] = g(x, y, W, H); }
    const img = ctx.createImageData(W, H), px = new Uint32Array(img.data.buffer), C = u32(color);
    const draw = (p, v) => { for (let i = 0; i < px.length; i++) px[i] = v[i] < p ? C : 0; ctx.putImageData(img, 0, 0); };
    return new Promise(res => {
      const t0 = performance.now();
      let phase = 0;
      const step = now => {
        const k = Math.min(1, (now - t0) / ms);
        if (phase === 0) {
          draw(k * 1.02, vals);
          if (k >= 1) { phase = 1; Promise.resolve(mid && mid()).then(() => { const t1 = performance.now(); const step2 = n2 => { const k2 = Math.min(1, (n2 - t1) / ms); draw(1.02 - k2 * 1.04, vals2); if (k2 < 1) requestAnimationFrame(step2); else { ctx.clearRect(0, 0, W, H); res(); } }; requestAnimationFrame(step2); }); return; }
        }
        requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  }

  /* ---------- chip sound (lazy, user-gesture only) ---------- */
  const Sound = {
    ctx: null, on: true,
    ensure() { if (!this.ctx) { try { this.ctx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { this.on = false; } } if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume().catch(() => {}); return this.ctx; },
    blip(freq = 660, dur = .05, type = 'square', vol = .05, slide = 0, when = 0) {
      if (!this.on) return; const c = this.ensure(); if (!c) return;
      const t = c.currentTime + when, o = c.createOscillator(), g = c.createGain();
      o.type = type; o.frequency.setValueAtTime(freq, t); if (slide) o.frequency.exponentialRampToValueAtTime(Math.max(30, freq + slide), t + dur);
      g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(.0001, t + dur);
      o.connect(g).connect(c.destination); o.start(t); o.stop(t + dur + .02);
    },
    move() { this.blip(880, .035, 'square', .035); },
    ok() { this.blip(660, .06, 'square', .05); this.blip(990, .09, 'square', .05, 0, .06); },
    back() { this.blip(440, .07, 'square', .045, -200); },
    coin() { this.blip(988, .06, 'square', .05); this.blip(1319, .18, 'square', .05, 0, .06); },
    hurt() { this.blip(220, .25, 'sawtooth', .06, -160); },
    noise(dur = .3, vol = .05) {
      if (!this.on) return; const c = this.ensure(); if (!c) return;
      const b = c.createBuffer(1, c.sampleRate * dur, c.sampleRate), d = b.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / d.length);
      const s = c.createBufferSource(), g = c.createGain(); g.gain.value = vol; s.buffer = b; s.connect(g).connect(c.destination); s.start();
    },
  };

  /* ---------- tiny chiptune loop ---------- */
  const Music = {
    timer: null, step: 0,
    // A minor-ish: lead arpeggios over a walking bass, 16 steps per bar
    bass: [45, 45, 52, 52, 41, 41, 48, 48, 43, 43, 50, 50, 40, 40, 47, 47],
    lead: [69, 72, 76, 72, 69, 72, 76, 79, 65, 69, 72, 69, 65, 69, 72, 77, 67, 71, 74, 71, 67, 71, 74, 79, 64, 68, 71, 68, 64, 68, 71, 76],
    start(bpm = 132) {
      if (this.timer) return; const c = Sound.ensure(); if (!c) return;
      const dt = 60 / bpm / 4;
      this.timer = setInterval(() => {
        const s = this.step++, hz = m => 440 * Math.pow(2, (m - 69) / 12);
        Sound.blip(hz(this.lead[s % 32]), dt * .9, 'square', .022);
        if (s % 2 === 0) Sound.blip(hz(this.bass[(s >> 1) % 16]), dt * 1.8, 'triangle', .07);
        if (s % 4 === 2) Sound.noise(.04, .025);
      }, dt * 1000);
    },
    stop() { clearInterval(this.timer); this.timer = null; },
  };

  /* ---------- palettes for scenes (dark → light) ---------- */
  const PALETTES = {
    ember: ['#07040a', '#160b18', '#2c1324', '#4f1d26', '#8a3324', '#d0662a', '#f2c23a', '#fff1a8'],
    moss:  ['#030704', '#0a140b', '#132414', '#1f3a1a', '#36571f', '#5f8a2a', '#9fd14f', '#e8ffb4'],
    frost: ['#02040a', '#070e1e', '#0f1d38', '#1a3156', '#2b5584', '#4a8ac0', '#6fbef0', '#e4f7ff'],
    ghost: ['#050309', '#0f0a1a', '#1c1430', '#2d2149', '#4a3870', '#7a64a8', '#c6b6f2', '#ffffff'],
    blood: ['#060102', '#140306', '#26060b', '#420a10', '#6b1218', '#a8241f', '#e2453c', '#ffc0a8'],
    bone:  ['#050505', '#100f0c', '#1f1c16', '#332e24', '#524a39', '#857a5f', '#e9dfc4', '#ffffff'],
  };

  function setMatrix(name) { M = MATRICES[name] || MATRICES.b8; }

  window.Dither = { B2, B4, B8, t8, thr, q, rgb, u32, clamp, tile, bg, scan, Buffer, field, transition, Sound, Music, PALETTES, setMatrix, MATRICES, get matrix() { return M; } };
})();
