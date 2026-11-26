import time

import common as C


def test_dates_in_the_formats_boards_use():
    cases = {"30 Dec 2026 - 22:00 (UTC)": "2026-12-30", "Last Date: 2026-06-16": "2026-06-16",
             "13.08.2026": "2026-08-13", "10/03/2026": "2026-03-10", "21st November 2026": "2026-11-21",
             "November 21, 2026": "2026-11-21", "3 Sept 2027": "2027-09-03",
             "2026-11-05T10:00:00-05:00": "2026-11-05", "2026-11-10T17:00:00.000+00:00": "2026-11-10"}
    for text, want in cases.items():
        assert C.parse_date(text) == want, text


def test_epoch_milliseconds_and_struct_time():
    assert C.parse_date(1794009600000) == "2026-11-07"
    assert C.parse_date(time.strptime("2026-11-20", "%Y-%m-%d")) == "2026-11-20"


def test_deadline_needs_a_cue_and_a_future_date():
    assert C.deadline_from_text("Last date for receipt of applications: 15.12.2026") == "2026-12-15"
    assert C.deadline_from_text("Closing date: 5 January 2027") == "2027-01-05"
    assert C.deadline_from_text("Posted on 12 Dec 2026") is None
    assert C.deadline_from_text("The deadline was 1 Jan 2020") is None


def test_canonical_urls_and_stable_ids():
    assert C.canonical_url("https://www.Example.org/jobs/123/?utm_source=x&gh_src=y&id=5#top") == \
        "https://example.org/jobs/123?id=5"
    assert C.job_id("https://example.org/jobs/123?id=5") == \
        C.job_id("https://www.example.org/jobs/123/?id=5&utm_medium=li")


def test_text_helpers():
    assert C.html_text("&lt;p&gt;Hello &amp;amp; &lt;b&gt;world&lt;/b&gt;&lt;/p&gt;") == "Hello & world"
    assert C.fold("Münster UMC") == "munster umc"
    assert C.truncate("one two three four", 9) == "one two…"
