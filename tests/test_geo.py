import pytest

from geo import locate

CASES = [
    ("Cambridge, MA", "", "US"), ("Cambridge, UK", "", "GB"), ("Cambridge", "", "GB"),
    ("South San Francisco, California, United States", "", "US"), ("San Francisco Bay Area", "", "US"),
    ("Number of offers: 1, Netherlands, Amsterdam UMC, Amsterdam", "", "NL"),
    ("Lausanne, or willing to relocate", "", "CH"), ("Hybrid · London", "", "GB"),
    ("", "National Centre for Biological Sciences (NCBS)", "IN"), ("Bengaluru, Karnataka", "", "IN"),
    ("", "CSIR-IMTECH", "IN"), ("Durham, NC", "", "US"), ("Durham", "", "GB"), ("Washington, DC", "", "US"),
    ("Münster, Germany", "", "DE"), ("Basel, Switzerland", "", "CH"), ("Faridabad", "", "IN"),
]


@pytest.mark.parametrize("loc,org,cc", CASES)
def test_country(loc, org, cc):
    assert locate(loc, org)["country"] == cc


def test_regions_and_remote():
    assert locate("Amsterdam")["region"] == "europe"
    assert locate("Chennai")["region"] == "india"
    assert locate("Remote")["region"] == "remote"
    assert locate("Remote - US") == {"country": "US", "region": "north-america", "remote": True}
    assert locate("somewhere")["region"] == "unknown"
