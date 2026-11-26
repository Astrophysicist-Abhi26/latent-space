from sources_ats import fetch_company, probe
from sources_feeds import fetch_rss
from sources_manual import fetch_issues, parse_issue_form
from sources_web import fetch_euraxess, fetch_links, fetch_listing


def test_euraxess_cards(fake_http):
    jobs = fetch_euraxess({"name": "EURAXESS", "urls": ["https://euraxess.ec.europa.eu/jobs/search?keywords=x"], "max_pages": 5})
    assert [j["url"].rsplit("/", 1)[-1] for j in jobs] == ["470001", "470002", "470005", "470003", "470004", "468900"]
    assert [j["hints"].get("kind") for j in jobs if j["url"].endswith(("470002", "470005"))] == ["phd", "phd"]   # R1 = PhD
    j = jobs[0]
    assert (j["org"], j["location"], j["posted"], j["deadline"]) == \
        ("Amsterdam UMC", "Amsterdam, Netherlands", "2026-11-18", "2027-01-15")
    assert j["hints"]["kind"] == "postdoc" and "Biological sciences" in j["fields_text"]
    assert "carbapenemase-producing" in j["description"]
    assert sum("page=1" in u for _, u in fake_http.calls) == 1          # stopped at the empty page


def test_madgex_feed(fake_http):
    jobs = fetch_rss({"name": "Nature", "parser": "madgex", "queries": ["a", "b"],
                      "url": "https://www.nature.com/naturecareers/jobsrss/?keywords={q}"})
    assert len(jobs) == 3                                               # same items from two queries
    j = jobs[0]
    assert (j["org"], j["location"], j["deadline"], j["posted"]) == \
        ("Example University", "Bristol, United Kingdom", "2027-01-12", "2026-11-20")


def test_other_feed_parsers(fake_http):
    mpg = fetch_rss({"name": "MPG", "parser": "mpg", "url": "https://www.mpg.de/feeds/jobs.rss"})
    assert mpg[0]["org"] == "Max Planck Institute for Infection Biology" and mpg[0]["deadline"] == "2026-12-31"
    rx = fetch_rss({"name": "jobRxiv", "parser": "jobrxiv", "url": "https://jobrxiv.org/?feed=job_feed&search_keywords={q}",
                    "queries": ["phage"]})
    assert (rx[0]["org"], rx[0]["location"], rx[0]["deadline"]) == ("University of Copenhagen", "Copenhagen, Denmark", "2026-12-20")
    ac = fetch_rss({"name": "jobs.ac.uk", "parser": "labelled", "url": "https://www.jobs.ac.uk/jobs/biological-sciences/?format=rss"})
    assert (ac[0]["org"], ac[0]["location"], ac[0]["deadline"]) == ("Example University", "Norwich", "2027-01-08")
    wp = fetch_rss({"name": "Biotecnika", "parser": "wordpress", "url": "https://www.biotecnika.org/category/jobs/feed/"})
    assert wp[1]["org"] == "CSIR-IMTECH" and wp[1]["deadline"] == "2026-12-10" and wp[0]["deadline"] == "2027-01-15"


def test_job_link_boards(fake_http):
    ap = fetch_links({"name": "AP", "url": "https://academicpositions.com/jobs/position/post-doc/field/microbiology",
                      "href": "/ad/[^/]+/\\d{4}/[^/]+/\\d+", "org_from_href": "/ad/([^/]+)/"})
    assert [(j["org"], j["location"], j["deadline"], j["posted"]) for j in ap] == [
        ("University of Copenhagen", "Denmark", "2027-01-07", "2026-11-12"),
        ("Karolinska Institutet", "Sweden", "2026-12-15", "2026-11-10")]
    ib = fetch_links({"name": "IBS", "url": "https://indiabioscience.org/jobs", "href": "indiabioscience\\.org/orgs/[^/]+/jobs/[^/?#]+",
                      "org_from_href": "/orgs/([^/]+)/jobs"})
    assert [(j["org"], j["deadline"]) for j in ib] == [("NCBS", "2026-12-15"), ("THSTI", "2026-11-30")]
    assert "Vaccine" not in ib[0]["description"]                       # each card keeps to itself


def test_institute_pages(fake_http):
    ncbs = fetch_listing({"name": "NCBS", "url": "https://ncbs.res.in/jobportal"})
    assert ncbs[0]["title"] == "Project Scientist-I in Microbial Genomics on contract basis"
    assert ncbs[0]["deadline"] == "2026-12-15" and len(ncbs) == 2      # one per row ("View" + "Apply")
    iisc = fetch_listing({"name": "IISc", "url": "https://www.iisc.ac.in/careers/contract-project-staff",
                          "title_cells": 2, "skip_if": "\\bClosed\\b"})
    assert [(j["title"], j["deadline"]) for j in iisc] == \
        [("Research Associate/Postdoc — Microbiology and Cell Biology (MCB)", "2026-12-18")]
    thsti = fetch_listing({"name": "THSTI", "url": "https://thsti.res.in/public/en/Jobs"})
    assert [(j["title"], j["deadline"]) for j in thsti] == [("Research Associate-I (Bacterial pathogenesis)", "2026-12-08")]


def test_company_boards(fake_http):
    gh = fetch_company({"name": "Anthropic", "ats": "greenhouse", "slug": "anthropic", "group": "ai-bio"})
    assert len(gh) == 6 and gh[0]["posted"] == "2026-11-16" and "We do sponsor visas!" in gh[0]["description"]
    assert gh[0]["hints"]["sector"] == "ai-bio"
    ash = fetch_company({"name": "Adaptyv", "ats": "ashby", "slug": "adaptyv", "group": "ai-bio"})
    assert len(ash) == 3 and ash[0]["location"] == "Lausanne, Switzerland"         # unlisted role skipped
    lev = fetch_company({"name": "Convergent", "ats": "lever", "slug": "convergentresearch", "group": "nonprofit"})
    assert lev[0]["location"] == "Alameda, California" and "animal handling" in lev[0]["description"]
    wk = fetch_company({"name": "LabGenius", "ats": "workable", "slug": "labgenius", "group": "ai-bio"})
    assert wk[0]["location"] == "London, England, United Kingdom"
    wd = fetch_company({"name": "Novartis", "ats": "workday", "host": "novartis.wd3.myworkdayjobs.com",
                        "tenant": "novartis", "site": "Novartis_Careers", "queries": ["microbiology", "antibacterial"],
                        "group": "pharma"})
    assert len(wd) == 1 and wd[0]["posted"] == "2026-11-19" and "susceptibility testing" in wd[0]["description"]


def test_probe_finds_the_board(fake_http):
    assert dict(probe("anthropic"))["greenhouse"] == 6


def test_add_a_position_issues(fake_http):
    jobs = fetch_issues()
    assert len(jobs) == 1                                               # the issue without a link is skipped
    j = jobs[0]
    assert j["pinned"] and j["deadline"] == "2027-01-31" and j["hints"]["kind"] == "postdoc"
    assert j["url"] == "https://www.linkedin.com/jobs/view/4100000001/" and j["issue"].endswith("/5")
    assert parse_issue_form("### Notes\n\n_No response_\n\n### Location\n\nPune") == {"location": "Pune"}


def test_hn_who_is_hiring(fake_http):
    from sources_feeds import fetch_hn_hiring
    jobs = fetch_hn_hiring({"name": "HN"})
    assert len(jobs) == 5 and jobs[0]["org"] == "Sarvam AI" and jobs[0]["title"].startswith("ML Research Engineer")
    assert "Bengaluru" in jobs[0]["location"] and jobs[0]["url"].endswith("45000011") and jobs[1]["location"] == "Remote"
