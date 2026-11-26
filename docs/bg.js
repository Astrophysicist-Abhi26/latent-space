/* Latent Space background and flyers.
   #bg (behind the content): a faint field of equations, neural-network constellations, atoms, galaxies,
   ringed planets, Gaussian-process curves and stars, weighted by the ranking profile's interests.
   #flyers (over the content, click-through): colourful fireflies by night; tiny moons and ringed planets
   drifting across the page by day. Both switch with the theme; flyers are skipped for reduced motion. */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const COLS = ["#38E1FF", "#9B7BFF", "#FF6AD5", "#B6FF5C", "#FFD166"];
  const FIREFLIES = 46, DAY_FLYERS = 9;
  const rnd = (a, b) => a + Math.random() * (b - a);
  let svg = null, last = null;
  const isDark = () => {
    const t = document.documentElement.dataset.theme;
    if (t === "dark") return true;
    if (t === "light") return false;
    return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  };
  const MOTIFS = {
    net: (c) => { const L = [[-24, -18], [-24, 0], [-24, 18], [0, -24], [0, -8], [0, 8], [0, 24], [24, -10], [24, 10]];
      let e = ""; for (const a of L.slice(0, 3)) for (const b of L.slice(3, 7)) e += `<path d="M${a[0]} ${a[1]}L${b[0]} ${b[1]}"/>`;
      for (const a of L.slice(3, 7)) for (const b of L.slice(7)) e += `<path d="M${a[0]} ${a[1]}L${b[0]} ${b[1]}"/>`;
      return `<g stroke="${c}" stroke-width=".8" opacity=".6">${e}</g>` + L.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="2.6" fill="${c}"/>`).join(""); },
    atom: (c) => `<g fill="none" stroke="${c}" stroke-width="1.6"><ellipse rx="22" ry="8"/><ellipse rx="22" ry="8" transform="rotate(60)"/><ellipse rx="22" ry="8" transform="rotate(-60)"/></g><circle r="3.2" fill="${c}"/>`,
    galaxy: (c) => `<ellipse rx="26" ry="9" fill="${c}" opacity=".18"/><path d="M0 0C10-8 24-4 26 4M0 0C-10 8-24 4-26-4" stroke="${c}" stroke-width="1.6" fill="none"/><circle r="3" fill="#fff"/>`,
    planet: (c) => `<circle r="11" fill="${c}" opacity=".7"/><ellipse rx="21" ry="5" fill="none" stroke="${c}" stroke-width="2" transform="rotate(-20)"/>`,
    gp: (c) => `<path d="M-30 6C-18-10-6-12 6-2C18 8 24 4 30-6L30 4C24 14 16 18 6 10C-6 0-18 2-30 16Z" fill="${c}" opacity=".22"/><path d="M-30 11C-18-3-6-5 6 4C18 12 24 9 30-1" stroke="${c}" stroke-width="1.6" fill="none"/>`,
    wave: (c) => `<path d="M-30 0C-22-12-14-12-6 0S10 12 18 0 26-12 30-6" stroke="${c}" stroke-width="1.6" fill="none"/>`,
    star: (c) => `<path d="M0-9L2.4-2.4 9 0 2.4 2.4 0 9-2.4 2.4-9 0-2.4-2.4Z" fill="${c}"/>`,
  };
  const EQS = ["p(θ|D) ∝ p(D|θ) p(θ)", "softmax(QKᵀ/√d)·V", "k(x,x′) = σ²·exp(−‖x−x′‖²/2ℓ²)", "iħ ∂ψ/∂t = Ĥψ", "E = mc²", "θ ← θ − η∇L",
    "∇·E = ρ/ε₀", "H(p) = −Σ p log p", "f ~ GP(m, k)", "Gμν = 8πG Tμν"];
  const FLY_CSS = `<style>
    #flyers .w{position:absolute;left:0;top:0;will-change:transform;animation:cw var(--d) ease-in-out infinite alternate;animation-delay:var(--dl)}
    @keyframes cw{0%{transform:translate(var(--x0),var(--y0))}25%{transform:translate(var(--x1),var(--y1))}
      50%{transform:translate(var(--x2),var(--y2))}75%{transform:translate(var(--x3),var(--y3))}100%{transform:translate(var(--x4),var(--y4))}}
    #flyers .spin{animation:cspin var(--s) linear infinite}@keyframes cspin{to{transform:rotate(360deg)}}
    #flyers .ff{display:block;width:11px;height:11px;border-radius:50%;
      background:radial-gradient(circle,#fff 0 14%,var(--c) 30%,transparent 70%);
      animation:cblink var(--b) ease-in-out infinite;animation-delay:var(--bd)}
    @keyframes cblink{0%,100%{opacity:.05}45%,60%{opacity:1}}
  </style>`;
  function route() {
    let s = "";
    for (let k = 0; k < 5; k++) s += `--x${k}:${rnd(1, 97).toFixed(1)}vw;--y${k}:${rnd(4, 94).toFixed(1)}vh;`;
    return s;
  }
  function moon(i) {
    const w = Math.round(rnd(14, 22)), c = COLS[i % COLS.length];
    if (i % 3 === 0) {          // a little ringed planet
      return `<svg width="${w + 10}" height="${w}" viewBox="-17 -11 34 22" aria-hidden="true"><circle r="7" fill="${c}"/><circle cx="-2" cy="-2.5" r="2.2" fill="#fff" opacity=".5"/>` +
        `<ellipse rx="15" ry="4" fill="none" stroke="#FFD166" stroke-width="1.6" transform="rotate(-18)"/></svg>`;
    }
    return `<svg width="${w}" height="${w}" viewBox="-10 -10 20 20" aria-hidden="true"><circle r="8" fill="#D9DCE8"/><circle r="8" fill="url(#)" opacity="0"/>` +
      `<circle cx="-3" cy="-2" r="2" fill="#B8BCCD"/><circle cx="3" cy="3" r="1.4" fill="#B8BCCD"/><circle cx="2.5" cy="-3.5" r="1" fill="#C6CADA"/>` +
      `<path d="M-8 0A8 8 0 0 0 8 0" fill="none" stroke="${c}" stroke-width="1.2" opacity=".7"/></svg>`;
  }
  function drawFlyers(dark, still) {
    let host = document.getElementById("flyers");
    if (!host) {
      host = document.createElement("div");
      host.id = "flyers";
      host.setAttribute("aria-hidden", "true");
      host.style.cssText = "position:fixed;inset:0;pointer-events:none;z-index:45;overflow:hidden";
      document.body.appendChild(host);
    }
    if (still) { host.innerHTML = ""; host.dataset.count = "0"; return; }
    let out = FLY_CSS;
    if (dark) {
      for (let i = 0; i < FIREFLIES; i++) {
        out += `<div class="w" style="${route()}--d:${rnd(50, 110).toFixed(0)}s;--dl:-${rnd(0, 60).toFixed(0)}s">` +
          `<i class="ff" style="--c:${COLS[i % COLS.length]};--b:${rnd(2.2, 5).toFixed(1)}s;--bd:${rnd(0, 5).toFixed(1)}s"></i></div>`;
      }
    } else {
      for (let i = 0; i < DAY_FLYERS; i++) {
        out += `<div class="w moon" style="${route()}--d:${rnd(50, 90).toFixed(0)}s;--dl:-${rnd(0, 40).toFixed(0)}s">` +
          `<div class="spin" style="--s:${rnd(18, 40).toFixed(0)}s">${moon(i)}</div></div>`;
      }
    }
    host.innerHTML = out;
    host.dataset.count = String(dark ? FIREFLIES : DAY_FLYERS);
    host.dataset.mode = dark ? "fireflies" : "moons";
  }
  function render(opts) {
    if (opts) last = opts;
    const host = document.getElementById("bg");
    if (!host) return;
    const weight = (last && last.weight) || (() => 50);
    const dark = isDark();
    const still = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    const W = 1600, H = 1000, ml = weight("ml") || 50, sci = weight("sci") || 40;
    const pool = [["net", 10 + ml / 6], ["gp", 6 + ml / 12], ["wave", 6], ["atom", 6 + sci / 10], ["galaxy", 5 + sci / 12], ["planet", 7], ["star", 10]];
    const pick = () => { let r = Math.random() * pool.reduce((s, [, w]) => s + w, 0); for (const [k, w] of pool) if ((r -= w) <= 0) return k; return "star"; };
    let out = `<style>
      .dr{animation:dr var(--d) ease-in-out infinite alternate}@keyframes dr{to{transform:translate(var(--x),var(--y)) rotate(var(--r))}}
      .tw{animation:tw 3s ease-in-out infinite}@keyframes tw{0%,100%{opacity:.15}50%{opacity:1}}
      .eq{font:500 15px "Space Grotesk",Menlo,monospace;fill:currentColor;opacity:${dark ? ".2" : ".22"}}
      ${still ? "*{animation:none!important}" : ""}</style>`;
    if (dark) {
      for (let i = 0; i < 90; i++) {
        out += `<circle class="tw" style="animation-delay:${rnd(0, 4).toFixed(1)}s" cx="${rnd(0, W).toFixed(0)}" cy="${rnd(0, H).toFixed(0)}" r="${rnd(.6, 1.8).toFixed(1)}" fill="${Math.random() < .75 ? "#fff" : COLS[i % 5]}"/>`;
      }
    }
    for (let i = 0; i < 22; i++) {
      const m = pick(), c = COLS[(Math.random() * COLS.length) | 0];
      out += `<g transform="translate(${rnd(30, W - 30).toFixed(0)} ${rnd(30, H - 30).toFixed(0)}) scale(${rnd(.9, 1.8).toFixed(2)}) rotate(${rnd(-30, 30).toFixed(0)})" opacity="${dark ? ".4" : ".38"}">` +
        `<g class="dr" style="--d:${rnd(8, 16).toFixed(1)}s;--x:${rnd(-30, 30).toFixed(0)}px;--y:${rnd(-30, 30).toFixed(0)}px;--r:${rnd(-15, 15).toFixed(0)}deg">${MOTIFS[m](c)}</g></g>`;
    }
    EQS.slice().sort(() => Math.random() - .5).slice(0, 6).forEach((e, i) => {
      out += `<text class="eq" x="${rnd(40, W - 380).toFixed(0)}" y="${(120 + i * 150 + rnd(-30, 30)).toFixed(0)}" transform="rotate(${rnd(-8, 8).toFixed(0)} 800 500)">${e}</text>`;
    });
    if (!svg) { svg = document.createElementNS(NS, "svg"); svg.setAttribute("preserveAspectRatio", "xMidYMid slice"); host.appendChild(svg); }
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.innerHTML = out;
    host.dataset.motifs = String(svg.querySelectorAll(".dr").length);
    host.dataset.mode = dark ? "fireflies" : "moons";
    drawFlyers(dark, still);
  }
  if (typeof MutationObserver !== "undefined") {
    new MutationObserver(() => render()).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  }
  if (window.matchMedia) {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    if (mq && mq.addEventListener) mq.addEventListener("change", () => render());
  }
  window.PPBackground = { render };
})();
