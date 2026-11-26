# Latent Space ✦ AI/ML internships, jobs & M.Tech for Kartik Khurana

**Live site:** https://astrophysicist-abhi26.github.io/latent-space/ · **Android app:** the *Android app* button on the site

Every morning at 07:00 IST a GitHub Action reads AI-company job boards and job feeds and keeps the machine-learning,
data-science and quant openings that suit Kartik (BS-MS Physics + Data Science, IISER Pune, graduating 2027):

| Tab | What it shows |
|---|---|
| **Top picks** | Every opening, best match first |
| **Internships** | Three columns: **India**, **Remote & abroad**, **Frontier AI labs** — plus schemes, flagged when only enrolled students can apply |
| **Jobs & fellowships** | Entry-level ML / research-engineer / data / quant roles, research-fellow programmes and residencies; PhD-only roles can be hidden |
| **AI labs** | Anthropic, OpenAI, Google DeepMind, xAI, Mistral, Cohere, Hugging Face, Scale, Databricks, NVIDIA, Axiom … |
| **M.Tech & programmes** | GATE 2027 (checked dates), IISc / IIT M.Tech in AI, CMI, ISI, IIIT-H; Microsoft Research India RF, Anthropic Fellows, Google pre-doc, OpenAI Residency |
| **My tracker** | Applications (saved → applied → interview → offer), notes, documents, calendar export |
| **Search elsewhere** | Ready-made LinkedIn / Google / Indeed searches from his profile |
| **Sources** | Health of every source, refreshed daily |

Sources: the labs' own job boards (Greenhouse, Ashby, Lever, Workable, Workday APIs), the monthly Hacker News
"Who is hiring?" thread, Times Higher Education and Nature Careers, and IISc project roles. Only roles that involve
machine learning, data science or quant work are kept (`scraper/site.yaml`: `domain: ai`); PhD, postdoc and
faculty posts are dropped. Each posting is compared with his CV (`scraper/cv/kartik.txt`) and scored 0–100 per
ranking profile (`scraper/profiles.yaml`); every card says why.

The look: deep space with colourful fireflies at night, a dawn sky with tiny drifting moons by day, floating
equations, neural-network constellations and his own Gaussian-process plot beside his avatar.

## Make it yours

| To change … | edit |
|---|---|
| name, person, which position types are dropped | `scraper/site.yaml` |
| how positions are ranked (topics, regions, “near Bengaluru” bonus, PhD-required penalty) | `scraper/profiles.yaml` — or live in the site’s **Tune** panel |
| PhD programmes and internship schemes | `scraper/programmes.yaml` (only checked dates are shown) |
| job boards, institutes, companies | `scraper/sources.yaml`, `institutes.yaml`, `companies.yaml` (test with `python scraper/doctor.py`) |
| the avatar, icon and launcher icon | `tools/make_art.py`, then `python tools/make_art.py` |

## Run it locally

```bash
pip install -r requirements.txt
python scraper/scrape.py --offline --out docs/jobs.json   # fixtures, no network
python scraper/scrape.py --out docs/jobs.json             # live run
cd docs && python -m http.server 8000                     # open http://localhost:8000
python -m pytest -q                                       # 58 tests
```

Deploying from scratch: **[RUNBOOK.md](RUNBOOK.md)**. Everything is plain Python and plain JavaScript; there is no
database and no build step. Data comes only from public adverts and official job-board APIs, respecting robots.txt.

Built for Kartik by his senior Abhishek.
