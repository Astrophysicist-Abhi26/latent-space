"""
Where is a position?  locate(text, extra) -> {country, region, remote}

Reads a free-text location first and the organisation name second: country names,
then US / Canadian / Indian states, then a city list, then Indian institute
acronyms. Regions are the site's filter buckets; Europe includes the UK,
Switzerland and Norway.
"""

import re

REGIONS = {
    "europe": "Europe (incl. UK, CH, NO)",
    "india": "India",
    "north-america": "North America",
    "asia-pacific": "Asia–Pacific",
    "middle-east": "Middle East",
    "africa": "Africa",
    "latin-america": "Latin America",
    "remote": "Remote",
    "unknown": "Not stated",
}

# ISO-2 -> (name, region, aliases). All-caps aliases of <= 4 letters match case-sensitively.
COUNTRIES = {
    "GB": ("United Kingdom", "europe", ["United Kingdom", "UK", "U.K.", "England", "Scotland", "Wales",
                                       "Northern Ireland", "Great Britain", "Britain"]),
    "IE": ("Ireland", "europe", ["Ireland", "Éire"]),
    "FR": ("France", "europe", ["France"]),
    "DE": ("Germany", "europe", ["Germany", "Deutschland"]),
    "NL": ("Netherlands", "europe", ["Netherlands", "The Netherlands", "Holland", "Nederland"]),
    "BE": ("Belgium", "europe", ["Belgium", "Belgique", "België"]),
    "LU": ("Luxembourg", "europe", ["Luxembourg"]),
    "CH": ("Switzerland", "europe", ["Switzerland", "Schweiz", "Suisse", "Svizzera"]),
    "AT": ("Austria", "europe", ["Austria", "Österreich"]),
    "IT": ("Italy", "europe", ["Italy", "Italia"]),
    "ES": ("Spain", "europe", ["Spain", "España"]),
    "PT": ("Portugal", "europe", ["Portugal"]),
    "DK": ("Denmark", "europe", ["Denmark", "Danmark"]),
    "SE": ("Sweden", "europe", ["Sweden", "Sverige"]),
    "NO": ("Norway", "europe", ["Norway", "Norge"]),
    "FI": ("Finland", "europe", ["Finland", "Suomi"]),
    "IS": ("Iceland", "europe", ["Iceland"]),
    "PL": ("Poland", "europe", ["Poland", "Polska"]),
    "CZ": ("Czechia", "europe", ["Czech Republic", "Czechia"]),
    "SK": ("Slovakia", "europe", ["Slovakia"]),
    "HU": ("Hungary", "europe", ["Hungary"]),
    "SI": ("Slovenia", "europe", ["Slovenia"]),
    "HR": ("Croatia", "europe", ["Croatia"]),
    "RO": ("Romania", "europe", ["Romania"]),
    "BG": ("Bulgaria", "europe", ["Bulgaria"]),
    "GR": ("Greece", "europe", ["Greece"]),
    "CY": ("Cyprus", "europe", ["Cyprus"]),
    "MT": ("Malta", "europe", ["Malta"]),
    "EE": ("Estonia", "europe", ["Estonia"]),
    "LV": ("Latvia", "europe", ["Latvia"]),
    "LT": ("Lithuania", "europe", ["Lithuania"]),
    "RS": ("Serbia", "europe", ["Serbia"]),
    "UA": ("Ukraine", "europe", ["Ukraine"]),
    "TR": ("Türkiye", "europe", ["Türkiye", "Turkey"]),
    "IN": ("India", "india", ["India", "Bharat"]),
    "US": ("United States", "north-america", ["United States", "United States of America", "USA", "U.S.A.",
                                              "U.S.", "US"]),
    "CA": ("Canada", "north-america", ["Canada"]),
    "MX": ("Mexico", "latin-america", ["Mexico", "México"]),
    "BR": ("Brazil", "latin-america", ["Brazil", "Brasil"]),
    "AR": ("Argentina", "latin-america", ["Argentina"]),
    "CL": ("Chile", "latin-america", ["Chile"]),
    "CO": ("Colombia", "latin-america", ["Colombia"]),
    "PE": ("Peru", "latin-america", ["Peru"]),
    "CN": ("China", "asia-pacific", ["China", "PRC"]),
    "HK": ("Hong Kong", "asia-pacific", ["Hong Kong"]),
    "TW": ("Taiwan", "asia-pacific", ["Taiwan"]),
    "JP": ("Japan", "asia-pacific", ["Japan"]),
    "KR": ("South Korea", "asia-pacific", ["South Korea", "Republic of Korea", "Korea"]),
    "SG": ("Singapore", "asia-pacific", ["Singapore"]),
    "MY": ("Malaysia", "asia-pacific", ["Malaysia"]),
    "TH": ("Thailand", "asia-pacific", ["Thailand"]),
    "VN": ("Vietnam", "asia-pacific", ["Vietnam", "Viet Nam"]),
    "ID": ("Indonesia", "asia-pacific", ["Indonesia"]),
    "PH": ("Philippines", "asia-pacific", ["Philippines"]),
    "AU": ("Australia", "asia-pacific", ["Australia"]),
    "NZ": ("New Zealand", "asia-pacific", ["New Zealand"]),
    "BD": ("Bangladesh", "asia-pacific", ["Bangladesh"]),
    "LK": ("Sri Lanka", "asia-pacific", ["Sri Lanka"]),
    "NP": ("Nepal", "asia-pacific", ["Nepal"]),
    "PK": ("Pakistan", "asia-pacific", ["Pakistan"]),
    "AE": ("United Arab Emirates", "middle-east", ["United Arab Emirates", "UAE", "Abu Dhabi", "Dubai"]),
    "SA": ("Saudi Arabia", "middle-east", ["Saudi Arabia", "KSA"]),
    "QA": ("Qatar", "middle-east", ["Qatar"]),
    "OM": ("Oman", "middle-east", ["Oman"]),
    "IL": ("Israel", "middle-east", ["Israel"]),
    "JO": ("Jordan", "middle-east", ["Jordan"]),
    "ZA": ("South Africa", "africa", ["South Africa"]),
    "EG": ("Egypt", "africa", ["Egypt"]),
    "NG": ("Nigeria", "africa", ["Nigeria"]),
    "KE": ("Kenya", "africa", ["Kenya"]),
    "GH": ("Ghana", "africa", ["Ghana"]),
    "GA": ("Gabon", "africa", ["Gabon"]),
    "MA": ("Morocco", "africa", ["Morocco"]),
    "TN": ("Tunisia", "africa", ["Tunisia"]),
    "ET": ("Ethiopia", "africa", ["Ethiopia"]),
    "UG": ("Uganda", "africa", ["Uganda"]),
    "TZ": ("Tanzania", "africa", ["Tanzania"]),
    "RW": ("Rwanda", "africa", ["Rwanda"]),
    "MW": ("Malawi", "africa", ["Malawi"]),
}

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}
CA_PROVINCES = {"ON": "Ontario", "QC": "Quebec", "BC": "British Columbia", "AB": "Alberta",
                "MB": "Manitoba", "NS": "Nova Scotia", "SK": "Saskatchewan", "NB": "New Brunswick"}
IN_STATES = ["Karnataka", "Tamil Nadu", "Tamilnadu", "Kerala", "Maharashtra", "Telangana",
             "Andhra Pradesh", "Delhi", "NCR", "Haryana", "Punjab", "Gujarat", "West Bengal", "Odisha",
             "Uttar Pradesh", "Madhya Pradesh", "Rajasthan", "Assam", "Bihar", "Chandigarh",
             "Puducherry", "Pondicherry", "Goa", "Himachal Pradesh", "Uttarakhand", "Jharkhand",
             "Chhattisgarh", "Jammu", "Kashmir", "Sikkim", "Meghalaya", "Manipur", "Mizoram",
             "Tripura", "Nagaland", "Arunachal Pradesh"]

# City -> ISO-2. Ambiguous names (Cambridge, Birmingham, Manchester) default to the UK
# and are overridden by a US state found in the same text.
CITIES = {
    # UK & Ireland
    "London": "GB", "Cambridge": "GB", "Oxford": "GB", "Edinburgh": "GB", "Glasgow": "GB",
    "Manchester": "GB", "Birmingham": "GB", "Liverpool": "GB", "Leeds": "GB", "Sheffield": "GB",
    "Bristol": "GB", "Norwich": "GB", "Nottingham": "GB", "Newcastle": "GB", "Dundee": "GB",
    "Aberdeen": "GB", "Cardiff": "GB", "Belfast": "GB", "Southampton": "GB", "Exeter": "GB",
    "Leicester": "GB", "York": "GB", "Hinxton": "GB", "Harwell": "GB", "Brighton": "GB",
    "St Andrews": "GB", "Durham": "GB", "Dublin": "IE", "Cork": "IE", "Galway": "IE",
    # France
    "Paris": "FR", "Lyon": "FR", "Marseille": "FR", "Montpellier": "FR", "Toulouse": "FR",
    "Strasbourg": "FR", "Grenoble": "FR", "Bordeaux": "FR", "Lille": "FR", "Nantes": "FR",
    "Rennes": "FR", "Villejuif": "FR", "Gif-sur-Yvette": "FR",
    # Germany
    "Berlin": "DE", "Munich": "DE", "München": "DE", "Heidelberg": "DE", "Hamburg": "DE",
    "Frankfurt": "DE", "Cologne": "DE", "Köln": "DE", "Tübingen": "DE", "Tuebingen": "DE",
    "Münster": "DE", "Muenster": "DE", "Braunschweig": "DE", "Jena": "DE", "Göttingen": "DE",
    "Freiburg": "DE", "Leipzig": "DE", "Dresden": "DE", "Würzburg": "DE", "Mainz": "DE",
    "Bonn": "DE", "Düsseldorf": "DE", "Hannover": "DE", "Hanover": "DE", "Kiel": "DE",
    "Saarbrücken": "DE", "Greifswald": "DE", "Bremen": "DE", "Martinsried": "DE", "Marburg": "DE",
    "Giessen": "DE", "Gießen": "DE", "Regensburg": "DE", "Erlangen": "DE", "Ulm": "DE",
    "Konstanz": "DE", "Potsdam": "DE", "Rostock": "DE", "Halle": "DE", "Magdeburg": "DE",
    # Benelux
    "Amsterdam": "NL", "Utrecht": "NL", "Leiden": "NL", "Rotterdam": "NL", "Groningen": "NL",
    "Nijmegen": "NL", "Delft": "NL", "Wageningen": "NL", "Maastricht": "NL", "Eindhoven": "NL",
    "Bilthoven": "NL", "Brussels": "BE", "Bruxelles": "BE", "Leuven": "BE", "Ghent": "BE",
    "Gent": "BE", "Antwerp": "BE", "Liège": "BE", "Louvain-la-Neuve": "BE",
    # Nordics
    "Copenhagen": "DK", "Aarhus": "DK", "Odense": "DK", "Lyngby": "DK", "Aalborg": "DK",
    "Stockholm": "SE", "Uppsala": "SE", "Lund": "SE", "Gothenburg": "SE", "Göteborg": "SE",
    "Umeå": "SE", "Linköping": "SE", "Solna": "SE", "Huddinge": "SE",
    "Oslo": "NO", "Bergen": "NO", "Trondheim": "NO", "Tromsø": "NO",
    "Helsinki": "FI", "Turku": "FI", "Kuopio": "FI", "Oulu": "FI", "Tampere": "FI",
    "Reykjavik": "IS",
    # Alpine & south
    "Zurich": "CH", "Zürich": "CH", "Basel": "CH", "Geneva": "CH", "Genève": "CH",
    "Lausanne": "CH", "Bern": "CH", "Epalinges": "CH", "Allschwil": "CH",
    "Vienna": "AT", "Wien": "AT", "Graz": "AT", "Innsbruck": "AT", "Salzburg": "AT",
    "Klosterneuburg": "AT",
    "Madrid": "ES", "Barcelona": "ES", "Valencia": "ES", "Seville": "ES", "Sevilla": "ES",
    "Bilbao": "ES", "Granada": "ES", "Salamanca": "ES", "Santander": "ES",
    "Lisbon": "PT", "Lisboa": "PT", "Porto": "PT", "Coimbra": "PT", "Oeiras": "PT",
    "Milan": "IT", "Milano": "IT", "Rome": "IT", "Roma": "IT", "Turin": "IT", "Torino": "IT",
    "Bologna": "IT", "Padua": "IT", "Padova": "IT", "Pisa": "IT", "Florence": "IT",
    "Naples": "IT", "Napoli": "IT", "Trieste": "IT", "Siena": "IT", "Pavia": "IT",
    "Prague": "CZ", "Brno": "CZ", "Warsaw": "PL", "Kraków": "PL", "Krakow": "PL",
    "Gdańsk": "PL", "Wrocław": "PL", "Budapest": "HU", "Szeged": "HU", "Athens": "GR",
    "Heraklion": "GR", "Thessaloniki": "GR", "Ljubljana": "SI", "Zagreb": "HR",
    "Tallinn": "EE", "Tartu": "EE", "Riga": "LV", "Vilnius": "LT", "Bratislava": "SK",
    "Belgrade": "RS", "Bucharest": "RO", "Sofia": "BG", "Nicosia": "CY",
    # India
    "Bengaluru": "IN", "Bangalore": "IN", "Chennai": "IN", "Coimbatore": "IN", "Hyderabad": "IN",
    "Pune": "IN", "Mumbai": "IN", "New Delhi": "IN", "Kolkata": "IN", "Faridabad": "IN",
    "Gurugram": "IN", "Gurgaon": "IN", "Noida": "IN", "Lucknow": "IN", "Bhubaneswar": "IN",
    "Thiruvananthapuram": "IN", "Trivandrum": "IN", "Kochi": "IN", "Cochin": "IN", "Mysuru": "IN",
    "Mysore": "IN", "Vellore": "IN", "Manipal": "IN", "Mohali": "IN", "Ahmedabad": "IN",
    "Gandhinagar": "IN", "Kanpur": "IN", "Kharagpur": "IN", "Guwahati": "IN", "Bhopal": "IN",
    "Indore": "IN", "Jaipur": "IN", "Jodhpur": "IN", "Varanasi": "IN", "Patna": "IN",
    "Ranchi": "IN", "Raipur": "IN", "Nagpur": "IN", "Madurai": "IN", "Tiruchirappalli": "IN",
    "Trichy": "IN", "Salem": "IN", "Puducherry": "IN", "Visakhapatnam": "IN", "Tirupati": "IN",
    "Kalyani": "IN", "Shillong": "IN", "Dehradun": "IN", "Srinagar": "IN", "Jammu": "IN",
    "Kasauli": "IN", "Izatnagar": "IN", "Karnal": "IN", "Ludhiana": "IN", "Dharwad": "IN",
    "Mangaluru": "IN", "Mangalore": "IN", "Calicut": "IN", "Kozhikode": "IN", "Thrissur": "IN",
    "Berhampur": "IN", "Bareilly": "IN", "Chandigarh": "IN",
    # North America
    "Boston": "US", "San Francisco": "US", "South San Francisco": "US", "Emeryville": "US",
    "Berkeley": "US", "Redwood City": "US", "Palo Alto": "US", "Menlo Park": "US", "Stanford": "US",
    "Mountain View": "US", "Alameda": "US", "Oakland": "US", "San Diego": "US", "La Jolla": "US",
    "Los Angeles": "US", "Seattle": "US", "New York": "US", "Bethesda": "US", "Baltimore": "US",
    "Philadelphia": "US", "Pittsburgh": "US", "Chicago": "US", "Houston": "US", "Atlanta": "US",
    "Madison": "US", "Denver": "US", "Boulder": "US", "Salt Lake City": "US",
    "Chapel Hill": "US", "Nashville": "US", "St. Louis": "US", "Saint Louis": "US", "Ann Arbor": "US",
    "Minneapolis": "US", "Pasadena": "US", "Princeton": "US", "New Haven": "US", "Providence": "US",
    "Rockville": "US", "Gaithersburg": "US", "Research Triangle": "US", "Watertown": "US",
    "Toronto": "CA", "Montreal": "CA", "Montréal": "CA", "Vancouver": "CA", "Ottawa": "CA",
    "Calgary": "CA", "Edmonton": "CA",
    # Asia-Pacific, Middle East, Africa, Latin America
    "Beijing": "CN", "Shanghai": "CN", "Shenzhen": "CN", "Suzhou": "CN", "Hangzhou": "CN",
    "Tokyo": "JP", "Kyoto": "JP", "Osaka": "JP", "Seoul": "KR", "Melbourne": "AU",
    "Sydney": "AU", "Brisbane": "AU", "Perth": "AU", "Adelaide": "AU", "Canberra": "AU",
    "Auckland": "NZ", "Kuala Lumpur": "MY", "Bangkok": "TH", "Dhaka": "BD", "Kathmandu": "NP",
    "Doha": "QA", "Riyadh": "SA", "Jeddah": "SA", "Thuwal": "SA", "Rehovot": "IL",
    "Jerusalem": "IL", "Tel Aviv": "IL", "Haifa": "IL", "Cape Town": "ZA", "Johannesburg": "ZA",
    "Nairobi": "KE", "Kampala": "UG", "Lambaréné": "GA", "Accra": "GH", "Cairo": "EG",
    "São Paulo": "BR", "Sao Paulo": "BR", "Rio de Janeiro": "BR", "Buenos Aires": "AR",
    "Santiago": "CL", "Bogotá": "CO", "Lima": "PE", "Mexico City": "MX",
}

# Indian institutions recognisable from the organisation name alone
_IN_ORGS = re.compile(r"\b(IISc|IISER|IITs?|AIIMS|ICMR|CSIR|DBT|NCBS|THSTI|inStem|CCMB|IGIB|IMTECH|RGCB|"
                      r"NIBMG|CDFD|NCCS|JNCASR|TIFR|PGIMER|JIPMER|BRIC|NIRT|NICED|NIRBI|Indian Institute)\b")


def _alias_rx(aliases):
    ci, cs = [], []
    for a in sorted(aliases, key=len, reverse=True):
        (cs if re.fullmatch(r"[A-Z.]{2,5}", a) else ci).append(re.escape(a))
    parts = []
    if ci:
        parts.append(re.compile(r"(?<![\w-])(?:" + "|".join(ci) + r")(?![\w-])", re.I))
    if cs:
        parts.append(re.compile(r"(?<![\w.-])(?:" + "|".join(cs) + r")(?![\w-])"))
    return parts


_COUNTRY_RX = [(cc, rx) for cc, (_, _, al) in COUNTRIES.items() for rx in _alias_rx(al)]
_US_NAME_RX = re.compile(r"(?<![\w-])(" + "|".join(sorted(map(re.escape, US_STATES.values()), key=len, reverse=True)) + r")(?![\w-])")
_US_ABBR_RX = re.compile(r",\s*(" + "|".join(US_STATES) + r")\b(?![\w-])")
_CA_RX = re.compile(r"(?<![\w-])(" + "|".join(map(re.escape, CA_PROVINCES.values())) + r")(?![\w-])|,\s*(" +
                    "|".join(CA_PROVINCES) + r")\b(?![\w-])")
_IN_RX = re.compile(r"(?<![\w-])(" + "|".join(sorted(map(re.escape, IN_STATES), key=len, reverse=True)) + r")(?![\w-])", re.I)
_CITY_RX = re.compile(r"(?<![\w-])(" + "|".join(sorted(map(re.escape, CITIES), key=len, reverse=True)) + r")(?![\w-])", re.I)
_CITY_KEYS = {k.lower(): v for k, v in CITIES.items()}
_REMOTE = re.compile(r"\b(remote|work from home|anywhere|telecommut\w*)\b", re.I)


def _first_country(text):
    best = None
    for cc, rx in _COUNTRY_RX:
        m = rx.search(text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), cc)
    return best[1] if best else None


def _from_text(text):
    if not text:
        return None
    # "Washington, DC" must not become the state; "Georgia" in the US list wins over the country
    if re.search(r"\bWashington,?\s*D\.?C\b", text):
        return "US"
    cc = _first_country(text)
    if cc:
        return cc
    if _US_ABBR_RX.search(text) or _US_NAME_RX.search(text):
        return "US"
    if _CA_RX.search(text):
        return "CA"
    if _IN_RX.search(text):
        return "IN"
    m = _CITY_RX.search(text)
    if m:
        return _CITY_KEYS[m.group(1).lower()]
    return None


def locate(location, org="", title=""):
    """-> dict(country='GB', region='europe', remote=False). Unknown country -> ''."""
    loc = location or ""
    remote = bool(_REMOTE.search(loc))
    cc = _from_text(loc) or _from_text(org) or (_IN_ORGS.search(org or "") and "IN") or None
    if not cc and title:
        cc = _from_text(title)
    if cc:
        return {"country": cc, "region": COUNTRIES[cc][1], "remote": remote}
    return {"country": "", "region": "remote" if remote else "unknown", "remote": remote}


def country_name(cc):
    return COUNTRIES.get(cc, ("",))[0]
