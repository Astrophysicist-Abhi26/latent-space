/* Latent Space — the ranking formula, shared by the site and the tests.
   A line-for-line mirror of score() in scraper/profiles.py: tests/test_profiles.py runs
   both on the same postings and fails if a single score or reason differs. */
(function (root) {
  "use strict";

  function fold(s) {
    return String(s || "").normalize("NFKD").replace(/[^\x00-\x7f]/g, "")
      .toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  }

  function makeContext(d) {
    const tax = d.taxonomy || { fields: {}, subfields: {} };
    return {
      fieldOf: (t) => String(t).split(".")[0],
      label: (t) => (tax.subfields[t] && tax.subfields[t].label) || tax.fields[t] || t,
      labels: d.labels || {},
      softCap: d.soft_cap || 75,
      pinFloor: d.pin_floor || 60,
    };
  }

  const TABLES = [["kinds", "kind"], ["sectors", "sector"], ["labs", "lab"], ["regions", "region"], ["visa", "visa"]];
  const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

  function weightFor(topic, interests, ctx) {
    if (has(interests, topic)) return interests[topic];
    const f = ctx.fieldOf(topic);
    return has(interests, f) ? interests[f] : null;
  }

  function scoreJob(job, prof, ctx) {
    const interests = prof.interests || {};
    const weighted = [];
    for (const t of job.topics || []) {
      const w = weightFor(t, interests, ctx);
      if (w !== null && w !== undefined) weighted.push([w, ctx.fieldOf(t), t]);
    }
    const pos = weighted.filter((x) => x[0] > 0).sort((a, b) => b[0] - a[0]);
    if (!pos.length) return { score: 0, reasons: [] };
    const best = pos[0];
    let raw = best[0];
    const reasons = [[ctx.label(best[2]), best[0]]];
    const second = pos.slice(1).find((x) => x[1] !== best[1]);
    if (second && prof.cross_field) {
      const pts = prof.cross_field * second[0];
      raw += pts;
      reasons.push([ctx.label(second[2]) + " (second field)", pts]);
    }
    const negs = weighted.filter((x) => x[0] < 0).map((x) => x[0]);
    const neg = negs.length ? Math.min(...negs) : 0;
    if (neg) { raw += neg; reasons.push(["Topic you avoid", neg]); }
    for (const [table, key] of TABLES) {
      const tab = prof[table] || {};
      const k = job[key] || "";
      const v = has(tab, k) ? tab[k] : 0;
      if (v) {
        raw += v;
        const labels = ctx.labels[table] || {};
        reasons.push([has(labels, job[key]) ? labels[job[key]] : job[key], v]);
      }
    }
    if (job.coding && prof.coding) { raw += prof.coding; reasons.push(["Coding-heavy role", prof.coding]); }
    if (job.level === "senior" && prof.senior) { raw += prof.senior; reasons.push(["Senior role", prof.senior]); }
    if (job.needs_phd && prof.needs_phd) { raw += prof.needs_phd; reasons.push(["Needs a PhD", prof.needs_phd]); }
    const cv = job.cv || 0;
    if (prof.cv && cv) { const pts = prof.cv * cv; raw += pts; reasons.push(["Similar to the CV", pts]); }
    const fit = job.llm ? job.llm.fit : null;
    if (prof.llm && fit !== null && fit !== undefined) {
      const pts = prof.llm * (fit - 50) / 50;
      raw += pts;
      reasons.push(["Claude fit check", pts]);
    }
    if (prof.network && prof.network.length) {
      const hay = fold((job.org || "") + " " + (job.location || ""));
      for (const [pat, bonus] of prof.network) {
        if (new RegExp(pat).test(hay)) { raw += bonus; reasons.push([prof.network_label || "Network bonus", bonus]); break; }
      }
    }
    let s = Math.floor(100 * (1 - Math.exp(-Math.max(raw, 0) / ctx.softCap)) + 0.5);
    if (job.pinned) s = Math.max(s, ctx.pinFloor);
    return { score: Math.min(s, 100), reasons };
  }

  const api = { scoreJob, makeContext, fold, weightFor };
  root.LHScore = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
