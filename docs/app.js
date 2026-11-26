/* Latent Space — Kartik's PhD, project and internship site. Plain JavaScript, no framework and no build step.
   Data: jobs.json, written daily by scraper/scrape.py. Ranking: score.js (shared with the tests).
   Everything personal (tracker, hidden posts, tuning) stays in this browser's localStorage. */
(function () {
  "use strict";

  // ── helpers ──────────────────────────────────────────────────────────────
  const $ = (s, r = document) => r.querySelector(s);
  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ESC[c]);
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode: keep going */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* ignore */ } },
  };
  const DAY = 86400000;
  const pad = (n) => String(n).padStart(2, "0");
  function todayDate() { const d = new Date(); d.setHours(0, 0, 0, 0); return d; }
  function isoToday() { const d = todayDate(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }
  function parseISO(s) {
    if (!s) return null;
    const [y, m, d] = String(s).slice(0, 10).split("-").map(Number);
    return y ? new Date(y, (m || 1) - 1, d || 1) : null;
  }
  function daysUntil(s) { const d = parseISO(s); return d ? Math.round((d - todayDate()) / DAY) : null; }
  function fmtDate(s) { const d = parseISO(s); return d ? d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : ""; }
  function ago(s) {
    const d = daysUntil(s);
    if (d === null) return "";
    const n = -d;
    if (n <= 0) return "today";
    if (n === 1) return "yesterday";
    if (n < 45) return `${n} days ago`;
    return `${Math.round(n / 30)} months ago`;
  }
  const flag = (cc) => (/^[A-Z]{2}$/.test(cc || "") ? String.fromCodePoint(...[...cc].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65)) : "");
  const signed = (p) => (p > 0 ? "+" : p < 0 ? "−" : "") + Math.abs(Math.round(p));
  function download(name, text, type) {
    // inside the Android app, files go to Downloads through the app's bridge
    if (window.AndroidBridge && window.AndroidBridge.saveFile) { window.AndroidBridge.saveFile(name, type, text); return; }
    if (!window.URL || !URL.createObjectURL) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type }));
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

  // ── state ────────────────────────────────────────────────────────────────
  const ARR = ["kind", "sector", "lab", "region", "field", "sub"];
  const BOOL = ["wet", "nocode", "novisa", "nosenior", "notech", "fresh", "hidden"];
  const DEFAULTS = { near: false, nophd: false, kind: [], sector: [], lab: [], region: [], field: [], sub: [], country: "", deadline: "any",
                     posted: "any", min: 0, wet: false, nocode: false, novisa: false, nosenior: false, notech: false,
                     fresh: false, hidden: false };
  const S = {
    data: null, jobs: [], byId: new Map(), ctx: null, profiles: {}, profileId: null, prof: null,
    f: JSON.parse(JSON.stringify(DEFAULTS)), q: "", sort: "match", tab: "positions", shown: 40,
    tracker: store.get("lh.tracker", {}), hidden: new Set(store.get("lh.hidden", [])),
    prevVisit: store.get("lh.lastVisit", null), openFields: new Set(), term: 0, place: 0, preset: null,
  };

  function readURL() {
    const u = new URLSearchParams(location.search);
    S.profileId = u.get("p");
    S.q = u.get("q") || "";
    S.sort = u.get("sort") || "match";
    S.tab = u.get("tab") || "positions";
    for (const k of ARR) S.f[k] = (u.get(k) || "").split(",").filter(Boolean);
    for (const k of BOOL) S.f[k] = u.get(k) === "1";
    S.f.country = u.get("country") || "";
    S.f.deadline = u.get("deadline") || "any";
    S.f.posted = u.get("posted") || "any";
    S.f.min = +u.get("min") || 0;
  }
  function writeURL() {
    const u = new URLSearchParams();
    if (S.data && S.profileId !== S.data.profiles.default) u.set("p", S.profileId);
    if (S.q) u.set("q", S.q);
    if (S.sort !== "match") u.set("sort", S.sort);
    if (S.tab !== "positions") u.set("tab", S.tab);
    for (const k of ARR) if (S.f[k].length) u.set(k, S.f[k].join(","));
    for (const k of BOOL) if (S.f[k]) u.set(k, "1");
    if (S.f.country) u.set("country", S.f.country);
    if (S.f.deadline !== "any") u.set("deadline", S.f.deadline);
    if (S.f.posted !== "any") u.set("posted", S.f.posted);
    if (S.f.min) u.set("min", String(S.f.min));
    const qs = u.toString();
    try { history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "")); } catch (e) { /* file:// */ }
  }

  // ── ranking ──────────────────────────────────────────────────────────────
  function tunedProfile(id) {
    const p = JSON.parse(JSON.stringify(S.profiles[id]));
    const t = store.get("lh.tune." + id, null);
    if (!t) return p;
    for (const [path, val] of Object.entries(t.set || {})) {
      const [a, b] = path.split(".");
      if (b) { p[a] = p[a] || {}; p[a][b] = val; } else p[a] = val;
    }
    for (const [field, factor] of Object.entries(t.scale || {})) {
      for (const node of Object.keys(p.interests)) {
        if (node.split(".")[0] === field && p.interests[node] > 0) p.interests[node] *= factor;
      }
    }
    return p;
  }
  function rescore() {
    S.prof = tunedProfile(S.profileId);
    for (const j of S.jobs) {
      const r = LHScore.scoreJob(j, S.prof, S.ctx);
      j._s = r.score;
      j._r = r.reasons;
    }
  }

  // ── filtering ────────────────────────────────────────────────────────────
  const L = () => S.data.labels;
  const subLabel = (t) => (S.data.taxonomy.subfields[t] || {}).label || t;
  function isNew(j) { return !!(S.prevVisit && j.first_seen && j.first_seen > S.prevVisit.slice(0, 10)); }
  function haystack(j) {
    if (!j._hay) {
      j._hay = [j.title, j.org, j.location, j.summary, (L().countries || {})[j.country], (L().kinds || {})[j.kind],
                ...(j.topics || []).map(subLabel)].join(" ").toLowerCase();
    }
    return j._hay;
  }
  function open(j) { const d = daysUntil(j.deadline); return d === null || d >= 0; }
  function passes(j, skip) {
    if (S.scope && S.scope.kinds && !S.scope.kinds.includes(j.kind)) return false;
    if (S.scope && S.scope.sectors && !S.scope.sectors.includes(j.sector)) return false;
    if (S.f.near && !NEAR.test(((j.org || "") + " " + (j.location || "") + " " + (j.title || "")).toLowerCase())) return false;
    if (S.f.nophd && j.needs_phd) return false;
    const f = S.f;
    if (!f.hidden && S.hidden.has(j.id)) return false;
    if (!open(j)) return false;
    for (const k of ["kind", "sector", "lab", "region"]) if (skip !== k && f[k].length && !f[k].includes(j[k])) return false;
    if (skip !== "country" && f.country && j.country !== f.country) return false;
    const topics = j.topics || [];
    if (skip !== "field" && f.field.length && !topics.some((t) => f.field.includes(t.split(".")[0]))) return false;
    if (skip !== "sub" && f.sub.length && !topics.some((t) => f.sub.includes(t))) return false;
    if (f.wet && !(j.lab === "wet" || j.lab === "hybrid")) return false;
    if (f.nocode && j.coding) return false;
    if (f.novisa && j.visa === "no-sponsorship") return false;
    if (f.nosenior && j.level === "senior") return false;
    if (f.notech && j.kind === "technician") return false;
    if (f.fresh && !isNew(j)) return false;
    const d = daysUntil(j.deadline);
    if (f.deadline === "has" && d === null) return false;
    if (f.deadline === "none" && d !== null) return false;
    if (/^\d+$/.test(f.deadline) && !(d !== null && d <= +f.deadline)) return false;
    if (f.posted !== "any") {
      const age = daysUntil(j.posted || j.first_seen);
      if (age !== null && -age > +f.posted) return false;
    }
    if (f.min && j._s < f.min) return false;
    if (S.q) {
      const h = haystack(j);
      for (const w of S.q.toLowerCase().split(/\s+/).filter(Boolean)) if (!h.includes(w)) return false;
    }
    return true;
  }
  const byDeadline = (a, b) => String(a.deadline || "9999").localeCompare(String(b.deadline || "9999"));
  const SORTS = {
    match: (a, b) => (b._s - a._s) || byDeadline(a, b) || a.title.localeCompare(b.title),
    deadline: (a, b) => byDeadline(a, b) || (b._s - a._s),
    newest: (a, b) => String(b.posted || b.first_seen || "").localeCompare(String(a.posted || a.first_seen || "")) || (b._s - a._s),
    org: (a, b) => String(a.org || "~").localeCompare(String(b.org || "~")) || (b._s - a._s),
  };
  function counts(skip, values) {
    const c = {};
    for (const j of S.jobs) {
      if (!passes(j, skip)) continue;
      for (const v of values(j)) c[v] = (c[v] || 0) + 1;
    }
    return c;
  }

  // ── header, profile, theme ──────────────────────────────────────────────
  function applyTheme(mode) {
    if (mode === "light" || mode === "dark") document.documentElement.dataset.theme = mode;
    else delete document.documentElement.dataset.theme;
    const btn = $("#theme-btn");
    if (btn) btn.title = "Theme: " + (mode === "light" || mode === "dark" ? mode : "automatic") + " (click to change)";
  }
  function renderHeader() {
    const d = S.data;
    const sel = $("#profile");
    sel.innerHTML = d.profiles.list.map((p) => `<option value="${esc(p.id)}">${esc(p.label)}</option>`).join("");
    sel.value = S.profileId;
    const gen = d.generated ? new Date(d.generated) : null;
    const stale = gen && (Date.now() - gen.getTime()) > 2.5 * DAY;
    const ok = (d.health || []).filter((h) => h.status === "ok" || h.status === "low").length;
    $("#status").innerHTML = (d.sample ? '<span class="banner">Sample data from the test fixtures; the live site updates every morning.</span> ' : "") +
      `Updated ${gen ? esc(gen.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })) : "recently"}. ` +
      `${ok} of ${(d.health || []).length} sources healthy.` +
      (stale ? ' <span class="banner">The data is more than two days old: check the Actions tab on GitHub.</span>' : "");
    $("#blurb").innerHTML = `<span>${esc(S.profiles[S.profileId].blurb || "")}</span>`;
    const repo = (d.site || {}).repo;
    if (repo) {
      const gh = "https://github.com/" + repo;
      const apk = gh + "/releases/latest/download/LatentSpace.apk";
      const inApp = /LatentSpaceApp/.test(navigator.userAgent || "");
      $("#repo-link").href = gh;
      $("#addpos-link").href = $("#addpos-foot").href = gh + "/issues/new?template=add-position.yml";
      $("#appbtn").href = $("#app-link").href = apk;
      $("#appbtn").hidden = $("#app-link").hidden = inApp;
    }
    renderHero();
  }

  // ── hero: greeting, today's plate, quick searches ───────────────────────
  const NEAR = /bengal?uru|bangalore|pune/;
  const LAB_SECTORS = ["ai-lab", "tech", "quant", "ai-bio"];
  const SCOPES = { top: null, jobs: { kinds: ["technician", "scientist", "other", "fellowship"] },
                   internships: { kinds: ["internship"] }, labs: { sectors: LAB_SECTORS } };
  const PRESETS = [
    { id: "labs", label: "Anthropic, OpenAI, DeepMind & co.", k: "p", tab: "labs", f: { sector: ["ai-lab"] } },
    { id: "intern-in", label: "Internships in India", k: "a", tab: "internships", f: {}, col: "india" },
    { id: "intern-ab", label: "Remote & abroad internships", k: "c", tab: "internships", f: {}, col: "abroad" },
    { id: "fellows", label: "Fellowships & residencies", k: "v", tab: "jobs", f: { kind: ["fellowship"] } },
    { id: "science", label: "AI for climate & physics", k: "g", tab: "top", f: { sub: ["sci.climate", "sci.physics", "ml.prob", "ds.ts"] } },
    { id: "entry", label: "Entry-level ML jobs", k: "y", tab: "jobs", f: { nophd: true, nosenior: true } },
    { id: "soon", label: "Closing in 2 weeks", k: "r", tab: "top", f: { deadline: "14" } },
    { id: "new", label: "New since last visit", k: "y", tab: "top", f: { fresh: true } },
  ];
  function withFilters(f, fn, tab) {
    const saved = [S.f, S.q, S.scope];
    S.f = Object.assign(JSON.parse(JSON.stringify(DEFAULTS)), JSON.parse(JSON.stringify(f)));
    S.q = "";
    S.scope = tab ? SCOPES[tab] : null;
    try { return fn(); } finally { S.f = saved[0]; S.q = saved[1]; S.scope = saved[2]; }
  }
  const countWith = (f, tab) => withFilters(f, () => S.jobs.filter((j) => passes(j)).length, tab);
  const firstName = () => ((S.data && S.data.site) || {}).first_name || "Kartik";
  function greeting() {
    const h = new Date().getHours(), n = firstName();
    if (h < 5) return `Night owl, ${n}? The fireflies are out.`;
    if (h < 12) return `Good morning, ${n}!`;
    if (h < 17) return `Good afternoon, ${n}!`;
    return `Good evening, ${n}!`;
  }
  function renderHero() {
    $("#hello").textContent = greeting();
    const all = countWith({}), intern = countWith({}, "internships"), jobs = countWith({ nophd: true }, "jobs");
    const labs = countWith({ sector: ["ai-lab"] }, "labs"), india = countWith({ region: ["india"] });
    const fresh = countWith({ fresh: true }), week = countWith({ deadline: "7" });
    const pl = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
    let text = `Latent Space found ${pl(all, "opening")} for you today: ${pl(intern, "internship")}, ${pl(jobs, "job and fellowship")} open ` +
      `without a PhD, ${labs} at frontier AI labs and ${india} in India.`;
    if (fresh) text += ` ${fresh} ${fresh === 1 ? "is" : "are"} new since your last visit.`;
    if (week) text += ` ${week} close${week === 1 ? "s" : ""} within a week.`;
    $("#today").textContent = text;
    $("#discs").innerHTML = PRESETS.map((p) => [p, countWith(p.f, p.tab)]).filter(([, n]) => n > 0).map(([p, n]) =>
      `<button class="disc ${p.k}" data-preset="${p.id}" aria-pressed="${S.preset === p.id}"><i aria-hidden="true"></i>${esc(p.label)} <small>${n}</small></button>`).join("");
  }
  function markPreset() {
    for (const b of document.querySelectorAll("#discs .disc")) b.setAttribute("aria-pressed", String(b.dataset.preset === S.preset));
  }
  function applyPreset(id) {
    const p = PRESETS.find((x) => x.id === id);
    if (!p) return;
    S.f = Object.assign(JSON.parse(JSON.stringify(DEFAULTS)), JSON.parse(JSON.stringify(p.tab === "internships" ? {} : p.f)));
    S.q = "";
    $("#q").value = "";
    S.preset = id;
    showTab(p.tab);
    if (p.tab !== "internships") update();
    const v = p.col ? document.getElementById("col-" + p.col) : $("#view-positions");
    if (v && v.scrollIntoView) v.scrollIntoView({ behavior: "smooth", block: "start" });
    if (p.col && v) { v.classList.remove("flash"); void v.offsetWidth; v.classList.add("flash"); }
  }
  function fieldWeight(field) {
    let w = 0;
    for (const [node, v] of Object.entries((S.prof || {}).interests || {})) if (node.split(".")[0] === field && v > w) w = v;
    return w;
  }
  function paintBackground(reseed) {
    if (window.PPBackground) window.PPBackground.render({ weight: fieldWeight, reseed: !!reseed });
  }

  // ── filters panel ───────────────────────────────────────────────────────
  function options(key, labels, c, order) {
    const keys = (order || Object.keys(labels)).filter((k) => c[k] || S.f[key].includes(k));
    return keys.map((k) => `<label class="opt"><input type="checkbox" data-f="${key}" value="${esc(k)}"${S.f[key].includes(k) ? " checked" : ""}>` +
      `<span>${esc(labels[k] || k)}</span><small>${c[k] || 0}</small></label>`).join("") || '<p class="muted">None</p>';
  }
  function toggle(key, text) {
    return `<label class="opt"><input type="checkbox" data-f="${key}"${S.f[key] ? " checked" : ""}><span>${text}</span></label>`;
  }
  function radios(key, items) {
    return items.map(([v, t]) => `<label class="opt"><input type="radio" name="${key}" data-f="${key}" value="${v}"${S.f[key] === v ? " checked" : ""}><span>${t}</span></label>`).join("");
  }
  function renderFilters() {
    const d = S.data, tax = d.taxonomy;
    const cKind = counts("kind", (j) => [j.kind]);
    const cRegion = counts("region", (j) => [j.region]);
    const cCountry = counts("country", (j) => (j.country ? [j.country] : []));
    const cSector = counts("sector", (j) => [j.sector]);
    const cLab = counts("lab", (j) => [j.lab]);
    const cField = counts("field", (j) => [...new Set((j.topics || []).map((t) => t.split(".")[0]))]);
    const cSub = counts("sub", (j) => j.topics || []);
    const fields = Object.keys(tax.fields).filter((f) => cField[f] || S.f.field.includes(f));
    const fieldHtml = fields.map((f) => {
      const subs = Object.keys(tax.subfields).filter((s) => tax.subfields[s].field === f && (cSub[s] || S.f.sub.includes(s)));
      const isOpen = S.openFields.has(f) || subs.some((s) => S.f.sub.includes(s));
      return `<details class="fld" data-field="${f}"${isOpen ? " open" : ""}><summary><label class="opt"><input type="checkbox" data-f="field" value="${f}"${S.f.field.includes(f) ? " checked" : ""}>` +
        `<span>${esc(tax.fields[f])}</span><small>${cField[f] || 0}</small></label></summary>` +
        subs.map((s) => `<label class="opt sub"><input type="checkbox" data-f="sub" value="${s}"${S.f.sub.includes(s) ? " checked" : ""}>` +
          `<span>${esc(tax.subfields[s].label)}</span><small>${cSub[s] || 0}</small></label>`).join("") + "</details>";
    }).join("");
    const countries = Object.keys(cCountry).sort((a, b) => cCountry[b] - cCountry[a]);
    if (S.f.country && !countries.includes(S.f.country)) countries.unshift(S.f.country);
    $("#filters").innerHTML = `
      <div class="fhead"><b>Filters</b><button class="link" data-act="reset">Reset all</button></div>
      <fieldset><legend>Quick picks for ${esc(firstName())}</legend>
        ${toggle("nophd", "Hide jobs that need a PhD")}${toggle("near", "Around Pune / Bengaluru only")}
        ${toggle("wet", "Wet lab, or wet + dry")}${toggle("nocode", "Hide coding-heavy roles")}
        ${toggle("novisa", "Hide roles that refuse visa sponsorship")}${toggle("fresh", "New since my last visit")}</fieldset>
      <fieldset><legend>Position type</legend>${options("kind", L().kinds, cKind)}</fieldset>
      <fieldset><legend>Region</legend>${options("region", L().regions, cRegion)}
        <select data-f="country" aria-label="Country"><option value="">All countries</option>${countries.map((cc) =>
          `<option value="${cc}"${S.f.country === cc ? " selected" : ""}>${flag(cc)} ${esc((L().countries || {})[cc] || cc)} (${cCountry[cc] || 0})</option>`).join("")}</select></fieldset>
      <fieldset><legend>Field</legend>${fieldHtml || '<p class="muted">None</p>'}</fieldset>
      <fieldset><legend>Sector</legend>${options("sector", L().sectors, cSector)}</fieldset>
      <fieldset><legend>Lab work</legend>${options("lab", L().labs, cLab)}</fieldset>
      <fieldset><legend>Deadline</legend>${radios("deadline", [["any", "Any"], ["14", "Closes within 2 weeks"], ["30", "Within a month"],
        ["60", "Within 2 months"], ["has", "Has a deadline"], ["none", "No deadline listed"]])}</fieldset>
      <fieldset><legend>Posted</legend>${radios("posted", [["any", "Any time"], ["7", "Last 7 days"], ["30", "Last 30 days"]])}</fieldset>
      <fieldset><legend>Minimum match <output id="minout">${S.f.min}</output></legend>
        <input type="range" min="0" max="90" step="5" data-f="min" value="${S.f.min}" aria-label="Minimum match score"></fieldset>
      ${toggle("hidden", `Show positions I hid (${S.hidden.size})`)}`;
  }

  // ── position cards ──────────────────────────────────────────────────────
  function card(j) {
    const t = S.tracker[j.id];
    const d = daysUntil(j.deadline);
    const where = [flag(j.country), j.location || (L().countries || {})[j.country] || ""].filter(Boolean).join(" ");
    const via = (j.sources || [j.source]).filter(Boolean).join(", ");
    const badges = [`<span class="b">${esc(L().kinds[j.kind] || j.kind)}</span>`];
    if (j.sector === "ai-lab") badges.push('<span class="b ai">Frontier AI lab</span>');
    if (j.sector === "quant") badges.push('<span class="b ai">Quant</span>');
    if (j.sector === "ai-bio") badges.push('<span class="b ai">AI × biology</span>');
    else if (j.sector && j.sector !== "academic") badges.push(`<span class="b">${esc(L().sectors[j.sector] || j.sector)}</span>`);
    if (j.lab === "wet") badges.push('<span class="b wet">Wet lab</span>');
    if (j.lab === "hybrid") badges.push('<span class="b hyb">Wet + dry</span>');
    if (j.lab === "dry") badges.push('<span class="b dry">Computational</span>');
    if (j.coding) badges.push('<span class="b warn">Coding-heavy</span>');
    if (j.needs_phd) badges.push('<span class="b warn">Needs a PhD</span>');
    if (j.visa === "sponsors") badges.push('<span class="b ok">Mentions visa support</span>');
    if (j.visa === "no-sponsorship") badges.push('<span class="b bad">No visa sponsorship</span>');
    if (j.level === "senior") badges.push('<span class="b">Senior</span>');
    if (isNew(j)) badges.push('<span class="b new">New</span>');
    if (j.pinned) badges.push('<span class="b ok">Added by hand</span>');
    if (j.carried) badges.push('<span class="b warn">Source down today — last known</span>');
    const chips = (j.topics || []).slice(0, 4).map((s) => `<button class="chip" data-sub="${esc(s)}" title="Show only this field">${esc(subLabel(s))}</button>`).join("");
    const dl = j.deadline
      ? `<span class="dl ${d <= 7 ? "urgent" : d <= 21 ? "soon" : ""}">Closes ${esc(fmtDate(j.deadline))}, ${d === 0 ? "today" : d + " days left"}</span>`
      : '<span class="dl none">No deadline listed</span>';
    const posted = j.posted ? `<span>Posted ${esc(ago(j.posted))}</span>` : j.first_seen ? `<span>Found ${esc(ago(j.first_seen))}</span>` : "";
    const reasons = (j._r || []).map((r, i) => `<li>${esc(r[0])} <span>${i === 0 ? Math.round(r[1]) : signed(r[1])}</span></li>`).join("");
    const tier = j._s >= 80 ? "hi" : j._s >= 60 ? "mid" : "lo";
    return `<article class="job${S.hidden.has(j.id) ? " dim" : ""}" data-id="${esc(j.id)}" data-lab="${esc(j.lab || "unknown")}">
      <div class="score ${tier}" style="--s:${j._s}" title="Match for this ranking profile"><b>${j._s}</b><small>match</small></div>
      <div class="body">
        <h3><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a></h3>
        <p class="meta">${j.org ? `<span class="org">${esc(j.org)}</span>` : ""}${where ? `<span class="where">${esc(where)}</span>` : ""}<span class="via">via ${esc(via)}</span></p>
        <p class="badges">${badges.join("")}</p>
        ${chips ? `<p class="topics">${chips}</p>` : ""}
        ${j.summary ? `<p class="summary">${esc(j.summary)}</p>` : ""}
        ${j.llm && j.llm.why ? `<p class="ai-note"><b>Claude:</b> ${esc(j.llm.why)} <span class="muted">(fit ${esc(j.llm.fit)})</span></p>` : ""}
        <p class="dates">${dl}${posted}</p>
        ${reasons ? `<details class="why"><summary>Why this score?</summary><ul>${reasons}</ul></details>` : ""}
      </div>
      <div class="actions">
        <button data-act="track" class="${t ? "on" : ""}">${t ? "★ " + esc(statusLabel(t.status)) : "☆ Track"}</button>
        <button data-act="hide">${S.hidden.has(j.id) ? "Unhide" : "Hide"}</button>
        <a class="open" href="${esc(j.apply || j.url)}" target="_blank" rel="noopener">Open advert</a>
      </div>
    </article>`;
  }
  function renderList() {
    const list = S.jobs.filter((j) => passes(j)).sort(SORTS[S.sort] || SORTS.match);
    const total = S.jobs.filter(open).length;
    $("#count").textContent = `${list.length} of ${total} open positions` + (S.q ? ` matching “${S.q}”` : "") +
      `, ranked for ${S.profiles[S.profileId].label}.`;
    $("#list").innerHTML = list.length ? list.slice(0, S.shown).map(card).join("")
      : '<p class="empty">No colonies grew on this plate. Remove a filter or two (or press “Reset all”), shorten the search, or try another ranking.</p>';
    const more = $("#more");
    more.hidden = list.length <= S.shown;
    more.textContent = `Show more (${list.length - S.shown} more)`;
  }
  function update() { S.shown = 40; writeURL(); renderFilters(); renderList(); markPreset(); }

  // ── tracker ─────────────────────────────────────────────────────────────
  const STATUS = [["saved", "Saved"], ["preparing", "Preparing"], ["applied", "Applied"], ["interview", "Interview"],
                  ["offer", "Offer"], ["closed", "Closed / not selected"]];
  const DOCS = [["cv", "CV"], ["letter", "Cover letter"], ["statement", "Research statement"], ["refs", "Referees asked"]];
  const statusLabel = (k) => (STATUS.find((s) => s[0] === k) || STATUS[0])[1];
  function saveTracker() { store.set("lh.tracker", S.tracker); updateTabCounts(); }
  function trackJob(j) {
    S.tracker[j.id] = { id: j.id, title: j.title, org: j.org || "", url: j.url, deadline: j.deadline || "",
      location: j.location || (L().countries || {})[j.country] || "", kind: j.kind || "", status: "saved",
      added: isoToday(), applied: "", followup: "", notes: "", docs: {} };
    saveTracker();
  }
  function trackCard(t) {
    const d = daysUntil(t.deadline);
    const dl = t.deadline ? (d < 0 ? `Closed ${fmtDate(t.deadline)}` : `Closes ${fmtDate(t.deadline)}, ${d} days left`) : "No deadline set";
    return `<article class="tcard" data-tid="${esc(t.id)}">
      <a href="${esc(t.url)}" target="_blank" rel="noopener"><b>${esc(t.title)}</b></a>
      <p class="meta">${esc(t.org)}${t.org && t.location ? ", " : ""}${esc(t.location || "")}</p>
      <p class="dl ${d !== null && d < 0 ? "past" : d !== null && d <= 7 ? "urgent" : ""}">${esc(dl)}</p>
      <div class="row"><label>Status <select data-t="status">${STATUS.map(([k, l]) => `<option value="${k}"${t.status === k ? " selected" : ""}>${l}</option>`).join("")}</select></label>
        <label>Deadline <input type="date" data-t="deadline" value="${esc(t.deadline || "")}"></label></div>
      <div class="row"><label>Applied on <input type="date" data-t="applied" value="${esc(t.applied || "")}"></label>
        <label>Follow up on <input type="date" data-t="followup" value="${esc(t.followup || "")}"></label></div>
      <div class="docs">${DOCS.map(([k, l]) => `<label><input type="checkbox" data-doc="${k}"${t.docs && t.docs[k] ? " checked" : ""}> ${l}</label>`).join("")}</div>
      <textarea data-t="notes" rows="2" placeholder="Notes: PI, contact, what to emphasise…">${esc(t.notes || "")}</textarea>
      <button class="link danger" data-act="untrack">Remove</button>
    </article>`;
  }
  function renderTracker() {
    const items = Object.values(S.tracker);
    $("#board").innerHTML = items.length ? STATUS.map(([k, label]) => {
      const its = items.filter((t) => (t.status || "saved") === k).sort(byDeadline);
      return `<section class="col"><h3>${label} <small>${its.length}</small></h3>${its.map(trackCard).join("") || '<p class="muted">—</p>'}</section>`;
    }).join("") : '<p class="empty">Nothing tracked yet. Press <b>☆ Track</b> on any position, or add one by hand below.</p>';
  }
  function ics() {
    const out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Latent Space//Applications//EN", "CALSCALE:GREGORIAN"];
    const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+/, "");
    const e = (s) => String(s || "").replace(/\\/g, "\\\\").replace(/[,;]/g, (c) => "\\" + c).replace(/\r?\n/g, "\\n");
    for (const t of Object.values(S.tracker)) {
      for (const [field, what] of [["deadline", "Deadline"], ["followup", "Follow up"]]) {
        if (!t[field]) continue;
        out.push("BEGIN:VEVENT", `UID:${t.id}-${field}@latent-space`, `DTSTAMP:${stamp}`,
          `DTSTART;VALUE=DATE:${t[field].replace(/-/g, "")}`, `SUMMARY:${e(`${what}: ${t.title}${t.org ? " — " + t.org : ""}`)}`,
          `URL:${t.url || ""}`, `DESCRIPTION:${e(`Status: ${statusLabel(t.status)}${t.notes ? "\n" + t.notes : ""}`)}`, "END:VEVENT");
      }
    }
    out.push("END:VCALENDAR");
    return out.join("\r\n");
  }
  function updateTabCounts() { const n = Object.keys(S.tracker).length; $("#tcount").textContent = n ? String(n) : ""; }

  // ── fellowships ─────────────────────────────────────────────────────────
  function windowState(w) {
    const o = daysUntil(w.opens), d = daysUntil(w.deadline);
    if (o !== null && o > 0) return ["upcoming", `opens ${fmtDate(w.opens)} (in ${o} days); deadline ${fmtDate(w.deadline)}`];
    if (d !== null && d >= 0) return ["open", `open now, closes ${fmtDate(w.deadline)} (${d} days left)`];
    return ["closed", `closed ${fmtDate(w.deadline)}`];
  }
  const REGION_NAMES = { europe: "Europe", india: "India", global: "Global", "north-america": "USA", "asia-pacific": "Asia–Pacific" };
  function progCard(f) {
    const wins = (f.windows || []).map((w) => {
      const [cls, text] = windowState(w);
      return `<p class="window ${cls}">${esc(w.label)}: ${esc(text)}<br><small class="muted">Dates checked ${esc(w.checked)}</small></p>`;
    }).join("") || `<p class="window muted">Dates: see the official page${f.verified ? "" : " (details not yet checked)"}</p>`;
    const enrol = f.enrolled_only === true ? '<span class="b warn">Enrolled students only — apply before graduating</span>'
      : f.enrolled_only === false ? '<span class="b ok">Graduates can apply</span>' : "";
    const tracked = !!S.tracker["f-" + f.id];
    return `<article class="fcard"><h3><a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.name)}</a></h3>
      <p class="meta">${esc(f.funder)}, ${esc(REGION_NAMES[f.region] || f.region)}</p>${enrol ? `<p class="badges">${enrol}</p>` : ""}${wins}
      <p><b>Who:</b> ${esc(f.who)}</p><p><b>For ${esc(firstName())}:</b> ${esc(f.fit)}</p>
      <button class="btn ghost" data-act="track-f" data-fid="${esc(f.id)}">${tracked ? "★ Tracked" : "☆ Track"}</button></article>`;
  }
  const progs = (kind) => (S.data.programmes || []).filter((f) => f.kind === kind);
  function renderProgrammes() {
    const live = S.jobs.filter((j) => j.kind === "fellowship" && open(j) && !S.hidden.has(j.id)).sort(byDeadline);
    $("#programmes").innerHTML = `<h2>M.Tech &amp; master's routes</h2>
      <p class="muted">Curated in <code>scraper/programmes.yaml</code>. GATE 2027 dates were checked; other programmes link to their official pages.</p>
      <div class="fgrid">${progs("mtech").map(progCard).join("")}</div>
      <h2>Research-fellow programmes &amp; residencies (no PhD needed)</h2><div class="fgrid">${progs("residency").map(progCard).join("")}</div>
      <h2>Live fellowship and residency postings</h2><p class="muted">Collected daily from the labs' own job boards.</p>
      <div class="live">${live.slice(0, 30).map(card).join("") || '<p class="muted">None open right now.</p>'}</div>`;
  }
  function mini(j) {
    const d = daysUntil(j.deadline), t = S.tracker[j.id];
    const where = [flag(j.country), j.location || (L().countries || {})[j.country] || ""].filter(Boolean).join(" ");
    const due = j.deadline ? `<span class="due${d !== null && d <= 7 ? " soon" : ""}">⏳ ${d === 0 ? "closes today" : d === 1 ? "1 day left" : d + " days left"}</span>` : "";
    return `<article class="mini" data-id="${esc(j.id)}"><div class="score" style="--s:${j._s || 0}" title="Match ${j._s || 0} of 100"><b>${j._s || 0}</b></div>
      <div><h4><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a></h4>
      <p class="meta">${esc(j.org || "")}${where ? " · " + esc(where) : ""}</p>${due}</div>
      <button class="btn ghost sm" data-act="track" aria-label="Track">${t ? "★" : "☆"}</button></article>`;
  }
  function renderInternships() {
    const all = S.jobs.filter((j) => j.kind === "internship" && open(j) && !S.hidden.has(j.id)).sort((a, b) => (b._s || 0) - (a._s || 0));
    const near = (j) => NEAR.test(((j.org || "") + " " + (j.location || "") + " " + (j.title || "")).toLowerCase());
    const cols = [
      ["india", "India (Pune, Bengaluru …)", "🇮🇳", all.filter((j) => j.region === "india").sort((a, b) => near(b) - near(a)), progs("internship").filter((f) => f.area === "india")],
      ["abroad", "Remote & abroad (startups, companies, labs)", "🌍", all.filter((j) => j.region !== "india" && j.sector !== "ai-lab"), progs("internship").filter((f) => f.area === "abroad")],
      ["ai", "Frontier AI labs (Anthropic, OpenAI, DeepMind …)", "🧠", all.filter((j) => j.sector === "ai-lab" && j.region !== "india"), []],
    ];
    $("#internships").innerHTML = `<div class="note fun"><b>Good to know:</b> most internships take only <em>currently enrolled</em> students, so apply while he is
      still at IISER (the BS-MS ends in 2027). After graduating, the same doors open as research-fellow programmes (Microsoft Research India,
      Anthropic Fellows) and entry-level roles — see <button class="link" data-goto="jobs">Jobs &amp; fellowships</button>.</div>
      <div class="cols3">${cols.map(([id, label, icon, jobs, schemes]) => `<section class="icol" id="col-${id}">
        <h3><span aria-hidden="true">${icon}</span> ${label} <small>${jobs.length}</small></h3>
        ${jobs.slice(0, 25).map(mini).join("") || '<p class="muted">No live postings right now — Latent Space looks again tomorrow morning.</p>'}
        ${schemes.length ? `<h4 class="sub">Schemes to apply to</h4>${schemes.map(progCard).join("")}` : ""}
      </section>`).join("")}</div>`;
  }
  function trackFellowship(id) {
    const f = (S.data.programmes || []).find((x) => x.id === id);
    if (!f) return;
    const key = "f-" + id;
    if (S.tracker[key]) delete S.tracker[key];
    else {
      const next = (f.windows || []).map((w) => w.deadline).filter((dd) => daysUntil(dd) >= 0).sort()[0] || "";
      S.tracker[key] = { id: key, title: f.name, org: f.funder, url: f.url, deadline: next, location: "", kind: "fellowship",
        status: "saved", added: isoToday(), applied: "", followup: "", notes: "", docs: {} };
    }
    saveTracker();
    if (S.tracker[key]) confetti();
    (S.tab === "internships" ? renderInternships : renderProgrammes)();
  }

  // ── search elsewhere ────────────────────────────────────────────────────
  function renderSearch() {
    const s = (S.prof && S.prof.search) || {};
    const terms = s.terms && s.terms.length ? s.terms : ["postdoc biology"];
    const places = s.places && s.places.length ? s.places : ["Europe"];
    const term = terms[S.term] || terms[0], place = places[S.place] || places[0];
    const e = encodeURIComponent;
    const links = [
      ["LinkedIn Jobs", `https://www.linkedin.com/jobs/search/?keywords=${e(term)}&location=${e(place)}&f_TPR=r2592000`, "Job ads from the last month"],
      ["LinkedIn posts", `https://www.linkedin.com/search/results/content/?keywords=${e(term + " hiring")}&sortBy=%22date_posted%22`, "PIs announcing openings in posts"],
      ["Google Jobs", `https://www.google.com/search?q=${e(term + " " + place)}&ibp=htl;jobs`, "Google's search across many job boards"],
      ["EURAXESS", `https://euraxess.ec.europa.eu/jobs/search?keywords=${e(term)}`, "EU research jobs and funding"],
      ["Nature Careers", `https://www.nature.com/naturecareers/searchjobs/?keywords=${e(term)}`, "Academic and industry science jobs"],
      ["X (Twitter)", `https://x.com/search?q=${e(term)}&f=live`, "Latest posts, e.g. #postdoc announcements"],
      ["Bluesky", `https://bsky.app/search?q=${e(term)}`, "Many academics post openings here now"],
      ["IndiaBioscience jobs", "https://indiabioscience.org/jobs", "Indian institutes and companies"],
    ];
    $("#search").innerHTML = `<h2>Search elsewhere</h2>
      <div class="note">LinkedIn and X do not allow automated collection and hide most posts behind a login, so Latent Space
      cannot read them for you. These buttons open ready-made searches instead. When you find something, add it to your
      tracker (Tracker tab) or open an “Add a position” issue on GitHub to put it on the site.</div>
      <h3>What</h3><div class="chips">${terms.map((t, i) => `<button data-term="${i}" aria-pressed="${t === term}">${esc(t)}</button>`).join("")}</div>
      <h3>Where</h3><div class="chips">${places.map((p, i) => `<button data-place="${i}" aria-pressed="${p === place}">${esc(p)}</button>`).join("")}</div>
      <div class="links">${links.map(([n, u, d]) => `<a class="lcard" href="${esc(u)}" target="_blank" rel="noopener"><b>${esc(n)} ↗</b><small>${esc(d)}</small></a>`).join("")}</div>
      <p class="muted">Search terms and places come from the ranking profile (<code>search:</code> in <code>scraper/profiles.yaml</code>).</p>`;
  }

  // ── sources ─────────────────────────────────────────────────────────────
  const STAT = { ok: "OK", low: "Fewer than usual", empty: "Nothing found", error: "Error", robots: "Blocked by robots.txt",
                 unverified: "Unconfirmed URL failing" };
  function renderSources() {
    const groups = {};
    for (const h of S.data.health || []) (groups[h.group] = groups[h.group] || []).push(h);
    const cls = S.data.classifiers || {};
    const line = (k, label) => cls[k] ? `<li>${label}: <b>${esc(cls[k].status)}</b> — ${esc(cls[k].detail || "")}</li>` : "";
    $("#sources").innerHTML = `<h2>Where positions come from</h2>
      <p class="muted">${(S.data.health || []).length} sources, read once a day. A source that fails keeps its last good
      positions for up to 10 days. “Unconfirmed” sources follow a site's usual pattern but have not been checked live yet.</p>
      <ul class="muted">${line("cv", "CV match")}${line("enrich", "Full-text reading of short postings")}${line("llm", "Claude fit check")}</ul>` +
      Object.entries(groups).map(([g, hs]) => `<h3>${esc(g)}</h3><div class="tablewrap"><table class="health">
        <thead><tr><th>Source</th><th>Status</th><th>Kept</th><th>Notes</th></tr></thead><tbody>${hs.map((h) => `<tr>
          <td>${/^https?:/.test(h.url || "") ? `<a href="${esc(h.url)}" target="_blank" rel="noopener">${esc(h.name)}</a>` : esc(h.name)}${h.verified ? "" : ` <small class="muted">(${esc(h.verification || "unconfirmed")})</small>`}</td>
          <td><span class="st ${esc(h.status)}">${esc(STAT[h.status] || h.status)}</span></td>
          <td>${h.kept}${h.carried ? ` <small class="muted">(${h.carried} from last run)</small>` : ""}</td>
          <td class="muted">${esc(h.error || h.note || "")}</td></tr>`).join("")}</tbody></table></div>`).join("");
  }

  // ── tune ────────────────────────────────────────────────────────────────
  const TUNE = [["regions.europe", "Europe"], ["regions.india", "India"], ["regions.north-america", "North America"],
                ["labs.wet", "Wet-lab roles"], ["labs.dry", "Computational roles"], ["coding", "Coding-heavy roles"],
                ["kinds.postdoc", "Postdocs"], ["kinds.scientist", "Scientist roles"], ["kinds.fellowship", "Fellowships"],
                ["kinds.technician", "Technician-level roles"], ["sectors.ai-lab", "Frontier AI labs"],
                ["sectors.industry", "Industry"], ["visa.no-sponsorship", "Roles refusing visa sponsorship"]];
  function baseValue(path) {
    const p = S.profiles[S.profileId];
    const [a, b] = path.split(".");
    return b ? ((p[a] || {})[b] || 0) : (p[a] || 0);
  }
  function renderTune() {
    const t = store.get("lh.tune." + S.profileId, { set: {}, scale: {} });
    const bonus = TUNE.map(([path, label]) => {
      const v = path in (t.set || {}) ? t.set[path] : baseValue(path);
      return `<label>${esc(label)} <output>${signed(v)}</output><input type="range" min="-60" max="40" step="1" data-tune="${path}" value="${v}"></label>`;
    }).join("");
    const fields = Object.entries(S.data.taxonomy.fields).map(([f, label]) => {
      const v = Math.round(100 * ((t.scale || {})[f] == null ? 1 : t.scale[f]));
      return `<label>${esc(label)} <output>${v}%</output><input type="range" min="0" max="200" step="10" data-scale="${f}" value="${v}"></label>`;
    }).join("");
    $("#tune-body").innerHTML = `<h4>Bonuses and penalties (points)</h4><div class="tune-grid">${bonus}</div>
      <h4>Field emphasis</h4><div class="tune-grid">${fields}</div>`;
  }
  function setTune(kind, key, value) {
    const id = "lh.tune." + S.profileId;
    const t = store.get(id, { set: {}, scale: {} });
    t.set = t.set || {};
    t.scale = t.scale || {};
    if (kind === "set") t.set[key] = value; else t.scale[key] = value;
    store.set(id, t);
    rescore();
    renderList();
  }

  // ── confetti ────────────────────────────────────────────────────────────
  function confetti() {
    const c = $("#confetti");
    if (!c || !c.getContext || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches)) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const W = (c.width = innerWidth), H = (c.height = innerHeight);
    const cols = ["#38E1FF", "#9B7BFF", "#FF6AD5", "#B6FF5C", "#FFD166", "#FFFFFF"];
    const bits = Array.from({ length: 90 }, () => ({ x: W / 2, y: H * 0.35, vx: (Math.random() - 0.5) * 14, vy: -Math.random() * 12 - 4,
      r: 3 + Math.random() * 5, c: cols[(Math.random() * cols.length) | 0], a: Math.random() * 6, s: Math.random() < 0.5 }));
    let t = 0;
    (function step() {
      ctx.clearRect(0, 0, W, H);
      for (const b of bits) {
        b.x += b.vx; b.y += b.vy; b.vy += 0.35; b.vx *= 0.99; b.a += 0.2;
        ctx.save(); ctx.translate(b.x, b.y); ctx.rotate(b.a); ctx.fillStyle = b.c;
        ctx.beginPath();
        if (b.s) { ctx.ellipse(0, 0, b.r, b.r / 2.2, 0, 0, 7); ctx.fill(); }          // petals
        else { ctx.arc(0, 0, b.r / 1.2, 0, 7); ctx.lineWidth = 2; ctx.strokeStyle = b.c; ctx.stroke(); }   // little vesicles
        ctx.restore();
      }
      if (++t < 80) requestAnimationFrame(step); else ctx.clearRect(0, 0, W, H);
    })();
  }

  // ── tabs ────────────────────────────────────────────────────────────────
  const listView = () => { renderFilters(); renderList(); };
  const RENDER = { top: listView, jobs: listView, internships: renderInternships, labs: listView, programmes: renderProgrammes,
                   tracker: renderTracker, search: renderSearch, sources: renderSources };
  const VIEW = { top: "positions", jobs: "positions", labs: "positions" };
  const HEADS = { top: "Top picks — every AI/ML internship, job and fellowship, best match first",
                  jobs: "Jobs, research-fellow roles and residencies — no PhD needed",
                  labs: "Frontier AI labs, AI companies and quant firms" };
  function showTab(tab) {
    if (!RENDER[tab]) tab = "top";
    S.tab = tab;
    S.scope = SCOPES[tab] && tab !== "internships" ? SCOPES[tab] : null;
    for (const b of document.querySelectorAll(".tabs button")) b.setAttribute("aria-selected", String(b.dataset.tab === tab));
    const shown = VIEW[tab] || tab;
    for (const v of document.querySelectorAll(".view")) v.hidden = v.id !== "view-" + shown;
    const lh = $("#listhead");
    if (lh) lh.textContent = HEADS[tab] || HEADS.phd;
    RENDER[tab]();
    writeURL();
  }

  // ── events ──────────────────────────────────────────────────────────────
  function onJobAction(e) {
    const sub = e.target.closest("[data-sub]");
    if (sub) { S.f.sub = [sub.dataset.sub]; showTab(["jobs", "labs"].includes(S.tab) ? S.tab : "top"); update(); return; }
    const go = e.target.closest("[data-goto]");
    if (go) { showTab(go.dataset.goto); return; }
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    if (btn.dataset.act === "track-f") { trackFellowship(btn.dataset.fid); return; }
    const art = btn.closest("[data-id]");
    const j = art && S.byId.get(art.dataset.id);
    if (!j) return;
    if (btn.dataset.act === "track") {
      if (S.tracker[j.id]) delete S.tracker[j.id]; else { trackJob(j); confetti(); }
      saveTracker();
    } else if (btn.dataset.act === "hide") {
      if (S.hidden.has(j.id)) S.hidden.delete(j.id); else S.hidden.add(j.id);
      store.set("lh.hidden", [...S.hidden]);
      renderFilters();
    }
    art.outerHTML = art.classList.contains("mini") ? mini(j) : card(j);
    if (btn.dataset.act === "hide" && !S.f.hidden) renderList();
  }
  function bind() {
    document.querySelector(".tabs").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-tab]");
      if (b) showTab(b.dataset.tab);
    });
    $("#discs").addEventListener("click", (e) => {
      const b = e.target.closest("[data-preset]");
      if (b) applyPreset(b.dataset.preset);
    });
    $("#profile").addEventListener("change", (e) => {
      S.profileId = e.target.value;
      rescore();
      renderHeader();
      paintBackground();
      if (!$("#tune").hidden) renderTune();
      RENDER[S.tab]();
      writeURL();
    });
    $("#theme-btn").addEventListener("click", () => {
      const order = ["auto", "light", "dark"];
      const next = order[(order.indexOf(store.get("lh.theme", "auto")) + 1) % 3];
      store.set("lh.theme", next);
      applyTheme(next);
    });
    $("#tune-btn").addEventListener("click", () => {
      const panel = $("#tune");
      panel.hidden = !panel.hidden;
      $("#tune-btn").setAttribute("aria-expanded", String(!panel.hidden));
      if (!panel.hidden) renderTune();
    });
    $("#tune-close").addEventListener("click", () => { $("#tune").hidden = true; $("#tune-btn").setAttribute("aria-expanded", "false"); });
    $("#tune-reset").addEventListener("click", () => { store.del("lh.tune." + S.profileId); rescore(); renderTune(); renderList(); });
    $("#tune").addEventListener("input", (e) => {
      const el = e.target;
      if (el.dataset.tune) { el.previousElementSibling.textContent = signed(+el.value); setTune("set", el.dataset.tune, +el.value); }
      if (el.dataset.scale) { el.previousElementSibling.textContent = el.value + "%"; setTune("scale", el.dataset.scale, +el.value / 100); }
    });
    const filters = $("#filters");
    filters.addEventListener("change", (e) => {
      const el = e.target, key = el.dataset.f;
      if (!key) return;
      S.preset = null;
      if (ARR.includes(key)) {
        const set = new Set(S.f[key]);
        if (el.checked) set.add(el.value); else set.delete(el.value);
        S.f[key] = [...set];
      } else if (BOOL.includes(key)) S.f[key] = el.checked;
      else if (key === "min") S.f.min = +el.value;
      else S.f[key] = el.value;
      update();
    });
    filters.addEventListener("input", (e) => {
      if (e.target.dataset.f === "min") { S.f.min = +e.target.value; $("#minout").textContent = e.target.value; renderList(); }
    });
    filters.addEventListener("click", (e) => {
      if (e.target.closest("[data-act=reset]")) { S.f = JSON.parse(JSON.stringify(DEFAULTS)); S.q = ""; $("#q").value = ""; S.preset = null; update(); return; }
      const summary = e.target.closest("summary");
      if (summary && !e.target.closest("input")) {
        const f = summary.parentElement.dataset.field;
        if (S.openFields.has(f)) S.openFields.delete(f); else S.openFields.add(f);
      }
    });
    $("#ftoggle").addEventListener("click", () => filters.classList.toggle("open"));
    const onSearch = debounce(() => { S.shown = 40; writeURL(); renderList(); }, 150);
    $("#q").addEventListener("input", (e) => { S.q = e.target.value.trim(); onSearch(); });
    $("#sort").addEventListener("change", (e) => { S.sort = e.target.value; writeURL(); renderList(); });
    $("#more").addEventListener("click", () => { S.shown += 40; renderList(); });
    $("#list").addEventListener("click", onJobAction);
    $("#programmes").addEventListener("click", onJobAction);
    $("#internships").addEventListener("click", onJobAction);
    document.addEventListener("keydown", (e) => {
      if (e.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || "")) {
        e.preventDefault();
        showTab("positions");
        $("#q").focus();
      }
    });
    // tracker
    const board = $("#board");
    board.addEventListener("change", (e) => {
      const el = e.target, art = el.closest("[data-tid]");
      const t = art && S.tracker[art.dataset.tid];
      if (!t) return;
      if (el.dataset.t) t[el.dataset.t] = el.value;
      if (el.dataset.doc) { t.docs = t.docs || {}; t.docs[el.dataset.doc] = el.checked; }
      saveTracker();
      if (el.dataset.t === "status" || el.dataset.t === "deadline") renderTracker();
    });
    board.addEventListener("input", (e) => {
      const el = e.target, art = el.closest("[data-tid]");
      if (el.dataset.t === "notes" && art && S.tracker[art.dataset.tid]) { S.tracker[art.dataset.tid].notes = el.value; saveTracker(); }
    });
    board.addEventListener("click", (e) => {
      const b = e.target.closest("[data-act=untrack]");
      if (!b) return;
      const art = b.closest("[data-tid]");
      delete S.tracker[art.dataset.tid];
      saveTracker();
      renderTracker();
    });
    $("#add-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const title = String(fd.get("title") || "").trim();
      if (!title) return;
      const id = "m-" + Date.now();
      S.tracker[id] = { id, title, org: String(fd.get("org") || ""), url: String(fd.get("url") || ""),
        location: String(fd.get("location") || ""), deadline: String(fd.get("deadline") || ""), kind: "",
        status: "saved", added: isoToday(), applied: "", followup: "", notes: String(fd.get("notes") || ""), docs: {} };
      saveTracker();
      e.target.reset();
      renderTracker();
    });
    $("#ics").addEventListener("click", () => download("latent-space-deadlines.ics", ics(), "text/calendar"));
    $("#export").addEventListener("click", () => download(`latent-space-tracker-${isoToday()}.json`,
      JSON.stringify({ tracker: S.tracker, hidden: [...S.hidden], exported: new Date().toISOString() }, null, 1), "application/json"));
    $("#import").addEventListener("change", async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      try {
        const data = JSON.parse(await file.text());
        Object.assign(S.tracker, data.tracker || {});
        for (const id of data.hidden || []) S.hidden.add(id);
        store.set("lh.hidden", [...S.hidden]);
        saveTracker();
        renderTracker();
      } catch (err) {
        alert("That file is not a Latent Space backup.");
      }
      e.target.value = "";
    });
    $("#search").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-term],button[data-place]");
      if (!b) return;
      if (b.dataset.term !== undefined) S.term = +b.dataset.term; else S.place = +b.dataset.place;
      renderSearch();
    });
  }

  function noData(err) {
    $("#status").textContent = "";
    $("#list").innerHTML = `<div class="note"><b>No positions to show yet.</b> The daily GitHub Action writes <code>jobs.json</code>;
      the first run takes about ten minutes after GitHub Pages is switched on (see RUNBOOK.md).<br>
      To preview locally: <code>python scraper/scrape.py --offline</code>, then <code>python -m http.server -d docs</code>
      and open http://localhost:8000. <span class="muted">(${esc(err && err.message)})</span></div>`;
  }

  async function init() {
    applyTheme(store.get("lh.theme", "auto"));
    if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("sw.js").catch(() => {});
    readURL();
    bind();
    $("#q").value = S.q;
    $("#sort").value = S.sort;
    let data;
    try {
      const r = await fetch("jobs.json?v=" + Date.now(), { cache: "no-store" });
      if (!r.ok) throw new Error("jobs.json: HTTP " + r.status);
      data = await r.json();
    } catch (err) {
      noData(err);
      return;
    }
    S.data = data;
    S.jobs = data.jobs || [];
    S.byId = new Map(S.jobs.map((j) => [j.id, j]));
    S.ctx = LHScore.makeContext({ taxonomy: data.taxonomy, labels: data.labels,
                                  soft_cap: data.profiles.soft_cap, pin_floor: data.profiles.pin_floor });
    for (const p of data.profiles.list) S.profiles[p.id] = p;
    if (!S.profiles[S.profileId]) S.profileId = data.profiles.default;
    rescore();
    renderHeader();
    paintBackground(true);
    updateTabCounts();
    showTab(S.tab);
    store.set("lh.lastVisit", new Date().toISOString());
    window.LatentSpace = { state: S, rescore, renderList };           // handy in the browser console
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
