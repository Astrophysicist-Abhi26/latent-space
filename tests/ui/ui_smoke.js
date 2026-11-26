// Clicks through the whole site in a headless DOM and fails on any script error.
//   npm install jsdom@24
//   python scraper/scrape.py --offline --out /tmp/jobs.json
//   node tests/ui/ui_smoke.js /tmp/jobs.json
const fs = require("fs"), path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");
const DOCS = path.join(__dirname, "..", "..", "docs");
const data = JSON.parse(fs.readFileSync(process.argv[2] || path.join(DOCS, "jobs.json"), "utf8"));
const errors = [];
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => { if (!/Not implemented: (navigation|HTMLCanvasElement)/.test(e.message)) errors.push("jsdomError: " + e.message); });
vc.on("error", (e) => errors.push("console.error: " + e));
const html = fs.readFileSync(path.join(DOCS, "index.html"), "utf8").replace(/<script src="[^"]+"><\/script>/g, "");
const dom = new JSDOM(html, { url: "https://example.org/latent-space/", runScripts: "outside-only", pretendToBeVisual: true, virtualConsole: vc });
const w = dom.window, d = w.document;
w.fetch = async () => ({ ok: true, json: async () => JSON.parse(JSON.stringify(data)) });
for (const f of ["score.js", "bg.js", "app.js"]) w.eval(fs.readFileSync(path.join(DOCS, f), "utf8"));
const tick = () => new Promise((r) => setTimeout(r, 30));
const check = (cond, msg) => { if (!cond) errors.push("FAIL: " + msg); else console.log("  ok  " + msg); };
const cards = () => [...d.querySelectorAll("#list article.job")];
const job = (el) => data.jobs.find((j) => j.id === el.dataset.id);
const click = (el) => el.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
const change = (el) => el.dispatchEvent(new w.Event("change", { bubbles: true }));
const tab = async (t) => { click(d.querySelector(`.tabs [data-tab="${t}"]`)); await tick(); };
const reset = async () => { click(d.querySelector('#filters [data-act="reset"]')); await tick(); };
const LABS = ["ai-lab", "tech", "quant", "ai-bio"];
(async () => {
  await tick(); await tick();
  // ── Top picks ──
  const n0 = cards().length;
  check(n0 === data.jobs.length, `top picks show every opening (${n0})`);
  check(["internship", "fellowship"].includes(job(cards()[0]).kind), `best match is an internship or fellowship (${job(cards()[0]).title})`);
  check(/Sample data/.test(d.querySelector("#status").textContent), "sample banner shown for offline data");
  check(d.querySelector("#profile").options.length === data.profiles.list.length, "profile picker lists all profiles");
  check(/Kartik/.test(d.querySelector("#hello").textContent), "hero greets Kartik");
  check(/Latent Space found \d+ openings? for you today: \d+ internships?/.test(d.querySelector("#today").textContent), "hero summarises the day");
  check(d.querySelectorAll("#bg svg g").length > 20 && Number(d.querySelector("#bg").dataset.motifs) > 10, "space background drawn with physics and ML motifs");
  const fl = d.querySelector("#flyers");
  check(fl && fl.style.position === "fixed" && fl.style.pointerEvents === "none", "flyers float over the page and let clicks through");
  check(fl.dataset.mode === "moons" && d.querySelectorAll("#flyers .moon").length === 9, "tiny moons and planets drift by in the light theme");
  d.documentElement.dataset.theme = "dark"; await tick();
  check(fl.dataset.mode === "fireflies" && d.querySelectorAll("#flyers .ff").length > 20 && !d.querySelector("#flyers .moon"), "colourful fireflies in the dark theme");
  d.documentElement.dataset.theme = "light"; await tick();
  const q = d.querySelector("#q"); q.value = "Gaussian"; q.dispatchEvent(new w.Event("input", { bubbles: true })); await new Promise((r) => setTimeout(r, 250));
  check(cards().length >= 1 && cards().every((c) => /gaussian/i.test(c.textContent)), `search "Gaussian" (${cards().length})`);
  q.value = ""; q.dispatchEvent(new w.Event("input", { bubbles: true })); await new Promise((r) => setTimeout(r, 250));
  const chip = cards()[0].querySelector(".chip"); const sub = chip.dataset.sub; click(chip); await tick();
  check(cards().length > 0 && w.location.search.includes("sub=" + sub), `topic chip filters to ${sub} (${cards().length})`);
  await reset();
  check(cards().length === n0, "reset restores everything");
  check(/Internship|Fellowship|Frontier AI lab/.test(cards()[0].querySelector(".why").textContent), "score explanation lists the reasons");
  const first = cards()[0]; const id = first.dataset.id;
  click(first.querySelector('[data-act="track"]')); await tick();
  check(d.querySelector("#tcount").textContent === "1", "tracking updates the tab count");
  check(JSON.parse(w.localStorage.getItem("lh.tracker"))[id].status === "saved", "tracker saved in localStorage");
  // ── quick search: frontier labs ──
  click(d.querySelector('#discs [data-preset="labs"]')); await tick();
  check(/Frontier AI labs/.test(d.querySelector("#listhead").textContent) && cards().length > 0 && cards().every((c) => job(c).sector === "ai-lab"),
        `"Anthropic, OpenAI, DeepMind & co." opens the AI-labs tab (${cards().length})`);
  await reset();
  check(cards().every((c) => LABS.includes(job(c).sector)), `AI-labs tab lists lab, tech and quant roles (${cards().length})`);
  // ── Jobs & fellowships ──
  await tab("jobs");
  check(/Jobs, research-fellow roles/.test(d.querySelector("#listhead").textContent), "jobs tab has its own heading");
  check(cards().length > 3 && cards().every((c) => ["technician", "scientist", "other", "fellowship"].includes(job(c).kind)), `jobs tab excludes internships (${cards().length})`);
  const nophd = d.querySelector('#filters input[data-f="nophd"]'); nophd.checked = true; change(nophd); await tick();
  check(cards().length > 0 && cards().every((c) => !job(c).needs_phd), `"Hide jobs that need a PhD" works (${cards().length})`);
  nophd.checked = false; change(nophd); await tick();
  const sel = d.querySelector("#profile"); sel.value = "labs"; change(sel); await tick();
  check(job(cards()[0]).sector === "ai-lab", `frontier-labs profile puts a lab first (${job(cards()[0]).title})`);
  sel.value = "kartik"; change(sel); await tick();
  click(d.querySelector("#tune-btn")); await tick();
  const rank = () => cards().findIndex((c) => job(c).region === "india");
  const before = rank();
  const slider = d.querySelector('#tune input[data-tune="regions.india"]'); slider.value = "40"; slider.dispatchEvent(new w.Event("input", { bubbles: true })); await tick();
  check(before >= 0 && rank() === 0, `tuning India +40 lifts the first Indian role from #${before + 1} to #${rank() + 1}`);
  click(d.querySelector("#tune-reset")); await tick();
  // ── Internships: three columns ──
  await tab("internships");
  check(d.querySelectorAll("#internships .icol").length === 3, "internships tab shows three columns");
  check(/Microsoft Research India internships/.test(d.querySelector("#col-india").textContent), "India column lists Indian schemes");
  check(/Machine Learning Intern \(weather forecasting\)/.test(d.querySelector("#col-abroad").textContent), "remote internship sits in the remote & abroad column");
  check(/Research Engineer Intern, Machine Learning/.test(d.querySelector("#col-ai").textContent), "frontier-lab internship sits in the AI-labs column");
  click(d.querySelector('#col-ai .mini [data-act="track"]')); await tick();
  check(d.querySelector("#tcount").textContent === "2", "tracking from an internship card works");
  click(d.querySelector('#internships [data-fid="msr-india-intern"]')); await tick();
  check(JSON.parse(w.localStorage.getItem("lh.tracker"))["f-msr-india-intern"] !== undefined, "tracking a scheme stores it");
  click(d.querySelector('#internships [data-goto="jobs"]')); await tick();
  check(/Jobs, research-fellow roles/.test(d.querySelector("#listhead").textContent), "the enrolment note links to Jobs & fellowships");
  // ── M.Tech & programmes ──
  await tab("programmes");
  const pt = d.querySelector("#programmes").textContent;
  check(/GATE 2027/.test(pt) && /Chennai Mathematical Institute/.test(pt), "M.Tech routes listed, GATE and non-GATE");
  check(/Microsoft Research India — Research Fellows Program/.test(pt) && /Anthropic Fellows Program/.test(pt), "research-fellow and residency programmes listed");
  click(d.querySelector('#programmes [data-fid="gate-2027"]')); await tick();
  check(JSON.parse(w.localStorage.getItem("lh.tracker"))["f-gate-2027"] !== undefined, "tracking a programme works");
  // ── Tracker, search, sources ──
  await tab("tracker");
  check(d.querySelectorAll("#board .tcard").length === 4, "tracker shows everything tracked");
  const st = d.querySelector('#board select[data-t="status"]'); st.value = "applied"; change(st); await tick();
  check([...d.querySelectorAll("#board .col")].some((c) => /Applied/.test(c.querySelector("h3").textContent) && c.querySelector(".tcard")), "status change moves the card to Applied");
  const form = d.querySelector("#add-form"); form.querySelector('[name="title"]').value = "Referral: ML intern, Sarvam";
  form.querySelector('[name="deadline"]').value = "2027-01-15"; form.dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true })); await tick();
  check(d.querySelectorAll("#board .tcard").length === 5, "manual add works");
  await tab("search");
  const li = [...d.querySelectorAll("#search a.lcard")].find((a) => /LinkedIn Jobs/.test(a.textContent));
  check(li && /keywords=machine%20learning%20intern/.test(li.href) && /location=India/.test(li.href), "LinkedIn saved search uses his profile");
  await tab("sources");
  check(d.querySelectorAll("#sources table.health tbody tr").length === data.health.length, "sources tab lists every source");
  let icsText = ""; w.URL.createObjectURL = (b) => { const r = new w.FileReader(); r.onload = () => (icsText = r.result); r.readAsText(b); return "blob:x"; }; w.URL.revokeObjectURL = () => {};
  await tab("tracker"); click(d.querySelector("#ics")); await new Promise((r) => setTimeout(r, 60));
  check(/BEGIN:VEVENT/.test(icsText) && /DTSTART;VALUE=DATE:20270221/.test(icsText), "calendar export contains the deadlines (GATE 21 Feb 2027)");
  console.log(errors.length ? "\nPROBLEMS:\n" + errors.join("\n") : "\nAll UI checks passed, no script errors.");
  process.exit(errors.length ? 1 : 0);
})();
