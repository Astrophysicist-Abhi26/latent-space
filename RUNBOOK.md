# Latent Space — runbook

## 1. First deployment (about 15 minutes)

1. **Create the repository.** On GitHub: **+ → New repository**, name it `latent-space`, *Public*, and leave
   "Add a README" unticked.
2. **Push the code** from the folder you unzipped (Terminal on the Mac):
   ```bash
   cd ~/Desktop/latent-space
   git init -b main
   git add -A
   git commit -m "Latent Space: AI/ML internships, jobs and M.Tech for Kartik"
   git remote add origin https://github.com/Astrophysicist-Abhi26/latent-space.git
   git push -u origin main
   ```
   If the push is refused with a *workflow* scope error, create a new personal access token with the
   `repo` and `workflow` scopes and use it as the password.
3. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
4. **Settings → Actions → General:** *Allow all actions*.
5. **Actions → "Update positions and publish" → Run workflow.** The first live run takes 10–15 minutes;
   the site then appears at `https://astrophysicist-abhi26.github.io/latent-space/`.
6. **Actions → "Build Android app" → Run workflow.** It publishes `LatentSpace.apk` on the Releases page;
   the site's *Android app* button always points to the newest one.
7. Optional: **Settings → Secrets and variables → Actions → New secret** `ANTHROPIC_API_KEY` turns on the
   Claude fit check for the best matches (a few cents a day). Without it the site works the same, minus that note.

## 2. Installing the app on her phone

Open the site on the phone → **Android app** → download `LatentSpace.apk` → allow installing from the browser when
Android asks. The app is the same site in a window of its own, with an offline page and downloads of the tracker backup.

## 3. Daily care

* The **Sources** tab shows each source as green, amber or red. A failing source keeps its last good postings for
  10 days, so nothing vanishes overnight.
* Red source? Run `python scraper/doctor.py --only "<name>"` on the Mac to see what the site returns, and
  `python scraper/doctor.py --probe <company>` to find a company's job-board name.
* To add a position seen on LinkedIn or by e-mail: **Add a position** in the footer (opens a GitHub issue form);
  it appears on the next run.
* Watch the **digest** issue on GitHub to receive each day's new matches by e-mail.

## 4. Things to check with Kartik

* She is happy with the avatar (`docs/kartik.svg`) appearing on a public site.
* The ranking: open **Tune**, adjust topics and regions, and copy the numbers she likes into `scraper/profiles.yaml`.
* Programme details marked "not yet checked" in `scraper/programmes.yaml` — confirm dates each autumn, since most
  European PhD programmes recruit between October and February.
