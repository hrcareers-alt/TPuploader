"""Pick the Teleperformance Philippines branch nearest a candidate.

The questionnaire asks for a preferred site. The branch list below is the
endorsement list, with approximate WGS84 landmarks. Candidate text is matched
to a PSGC city or province, then the closest landmark wins. A named landmark
in the address (Fairview, Lanang, Clark, MOA, and the other hints) wins before
that distance check.
"""

import csv
import math
from functools import lru_cache

from tp_locations import DATA_DIR, _aliases, _phrases, normalize_place, resolve_tp_site

# Canonical labels, in endorsement order. Coordinates are branch landmarks.
TP_BRANCHES = (
    {"name": "Antipolo", "lat": 14.625, "lon": 121.122},  # SM Masinag
    {"name": "Baguio", "lat": 16.408, "lon": 120.596},  # Harrison / Session
    {"name": "Bacolod", "lat": 10.676, "lon": 122.951},  # Magsaysay
    {"name": "Cagayan de Oro / CDO", "lat": 8.482, "lon": 124.645},  # Centrio
    {"name": "Cebu", "lat": 10.330, "lon": 123.906},  # IT Park, Apas
    {"name": "Clark", "lat": 15.186, "lon": 120.560},  # Clark Freeport
    {"name": "Davao", "lat": 7.049, "lon": 125.588},  # SM Ecoland, Matina
    {"name": "Davao Uprise / Felcris Centrale", "lat": 7.100, "lon": 125.633},  # Lanang
    {"name": "General Santos", "lat": 6.116, "lon": 125.172},
    {"name": "Laoag", "lat": 18.197, "lon": 120.593},
    {"name": "Makati / Southgate", "lat": 14.541, "lon": 121.019},  # Alphaland Southgate
    {"name": "Mandaluyong / EDSA Greenfield", "lat": 14.577, "lon": 121.049},
    {"name": "McKinley West", "lat": 14.530, "lon": 121.044},
    {"name": "Aura", "lat": 14.547, "lon": 121.054},  # SM Aura, McKinley Parkway
    {"name": "Fairview", "lat": 14.701, "lon": 121.064},  # SM Fairview, Greater Lagro
    {"name": "Fairview Terraces", "lat": 14.736, "lon": 121.060},  # Quirino Highway
    {"name": "Vertis North", "lat": 14.653, "lon": 121.035},  # EDSA–Mindanao Ave
    # Separate from Greenfield. Cubao / Araneta is the EDSA landmark used here.
    {"name": "EDSA", "lat": 14.619, "lon": 121.051},
    {"name": "Silver City", "lat": 14.588, "lon": 121.080},  # Frontera Verde, Pasig
    {"name": "Rockwell", "lat": 14.586, "lon": 121.061},  # Rockwell Business Center, Ortigas
    {"name": "Sucat", "lat": 14.476, "lon": 121.048},  # Parañaque
    {"name": "MOA", "lat": 14.535, "lon": 120.982},
    {"name": "Pasay", "lat": 14.545, "lon": 121.001},
)

# Longer phrases first so Fairview Terraces is not read as Fairview.
_HINTS = (
    ("FAIRVIEW TERRACES", "Fairview Terraces"),
    ("FELCRIS CENTRALE", "Davao Uprise / Felcris Centrale"),
    ("GREATER LAGRO", "Fairview"),
    ("MALL OF ASIA", "MOA"),
    ("MCKINLEY WEST", "McKinley West"),
    ("FORT BONIFACIO", "Aura"),
    ("SILVER CITY", "Silver City"),
    ("VERTIS NORTH", "Vertis North"),
    ("SOUTH GATE", "Makati / Southgate"),
    ("SOUTHGATE", "Makati / Southgate"),
    ("GREENFIELD", "Mandaluyong / EDSA Greenfield"),
    ("FAIRVIEW", "Fairview"),
    ("FELCRIS", "Davao Uprise / Felcris Centrale"),
    ("MCKINLEY", "McKinley West"),
    ("LANANG", "Davao Uprise / Felcris Centrale"),
    ("UPRISE", "Davao Uprise / Felcris Centrale"),
    ("VERTIS", "Vertis North"),
    ("ROCKWELL", "Rockwell"),
    ("ORTIGAS", "Rockwell"),
    ("ALABANG", "Sucat"),
    ("SUCAT", "Sucat"),
    ("CLARK", "Clark"),
    ("CUBAO", "EDSA"),
    ("AURA", "Aura"),
    ("BGC", "Aura"),
    ("MOA", "MOA"),
)

# Whole-country words are not a city. They only apply when no place matched.
_BROAD_POINTS = {
    "NCR": (14.590, 120.982, "MANILA"),
    "METRO MANILA": (14.590, 120.982, "MANILA"),
    "LUZON": (14.590, 120.982, "MANILA"),
    "MINDANAO": (7.070, 125.610, "DAVAO CITY"),
    "VISAYAS": (10.307, 123.893, "CEBU CITY"),
    "VISMIN": (10.307, 123.893, "CEBU CITY"),
}

_MANILA = (14.590, 120.982)
_CEBU_CITY = (10.307, 123.893)

# Provincial capitals, keyed by PSGC provCode.
_PROVINCE_POINTS = {
    "0128": (18.197, 120.593),  # Laoag
    "0129": (17.575, 120.387),  # Vigan
    "0133": (16.616, 120.317),  # San Fernando, La Union
    "0155": (16.022, 120.232),  # Lingayen
    "0209": (20.448, 121.970),  # Basco
    "0215": (17.613, 121.727),  # Tuguegarao
    "0231": (17.149, 121.889),  # Ilagan
    "0250": (16.481, 121.150),  # Bayombong
    "0257": (16.511, 121.526),  # Cabarroguis
    "0308": (14.676, 120.536),  # Balanga
    "0314": (14.853, 120.816),  # Malolos
    "0349": (15.541, 121.084),  # Palayan
    "0354": (15.034, 120.685),  # San Fernando, Pampanga
    "0369": (15.476, 120.598),  # Tarlac City
    "0371": (15.333, 119.978),  # Iba
    "0377": (15.759, 121.562),  # Baler
    "0410": (13.757, 121.058),  # Batangas City
    "0421": (14.430, 120.937),  # Imus
    "0434": (14.281, 121.417),  # Santa Cruz, Laguna
    "0456": (13.938, 121.617),  # Lucena
    "0458": (14.588, 121.176),  # Antipolo
    "1740": (13.446, 121.842),  # Boac
    "1751": (13.226, 120.596),  # Mamburao
    "1752": (13.411, 121.180),  # Calapan
    "1753": (9.739, 118.735),  # Puerto Princesa
    "1759": (12.577, 122.270),  # Romblon
    "0505": (13.139, 123.744),  # Legazpi
    "0516": (14.113, 122.955),  # Daet
    "0517": (13.584, 123.275),  # Pili
    "0520": (13.584, 124.206),  # Virac
    "0541": (12.369, 123.619),  # Masbate City
    "0562": (12.974, 124.005),  # Sorsogon City
    "0604": (11.707, 122.365),  # Kalibo
    "0606": (10.745, 121.941),  # San Jose, Antique
    "0619": (11.586, 122.751),  # Roxas City
    "0630": (10.720, 122.562),  # Iloilo City
    "0645": (10.676, 122.951),  # Bacolod
    "0679": (10.597, 122.599),  # Jordan
    "0712": (9.650, 123.853),  # Tagbilaran
    "0722": (10.307, 123.893),  # Cebu City
    "0746": (9.307, 123.308),  # Dumaguete
    "0761": (9.215, 123.515),  # Siquijor
    "0826": (11.608, 125.436),  # Borongan
    "0837": (11.245, 125.000),  # Tacloban
    "0848": (12.499, 124.638),  # Catarman
    "0860": (11.776, 124.886),  # Catbalogan
    "0864": (10.133, 124.845),  # Maasin
    "0878": (11.561, 124.397),  # Naval
    "0972": (8.588, 123.341),  # Dipolog
    "0973": (7.825, 123.437),  # Pagadian
    "0983": (7.777, 122.586),  # Ipil
    "0997": (6.704, 121.971),  # Isabela City
    "1013": (8.157, 125.128),  # Malaybalay
    "1018": (9.253, 124.719),  # Mambajao
    "1035": (8.068, 123.842),  # Tubod
    "1042": (8.486, 123.805),  # Oroquieta
    "1043": (8.454, 124.632),  # Cagayan de Oro
    "1123": (7.448, 125.806),  # Tagum
    "1124": (6.750, 125.357),  # Digos
    "1125": (6.953, 126.217),  # Mati
    "1182": (7.601, 126.084),  # Nabunturan
    "1186": (6.415, 125.612),  # Malita
    "1247": (7.008, 125.090),  # Kidapawan
    "1263": (6.503, 124.847),  # Koronadal
    "1265": (6.629, 124.605),  # Isulan
    "1280": (5.757, 125.530),  # Alabel
    "1298": (7.204, 124.247),  # Cotabato City
    "1339": (14.590, 120.982),  # Manila
    "1374": (14.630, 121.050),  # NCR second district
    "1375": (14.670, 120.970),  # NCR third district
    "1376": (14.500, 121.020),  # NCR fourth district
    "1401": (17.597, 120.621),  # Bangued
    "1411": (16.459, 120.588),  # La Trinidad
    "1427": (16.800, 121.120),  # Lagawe
    "1432": (17.419, 121.444),  # Tabuk
    "1444": (17.087, 120.976),  # Bontoc
    "1481": (18.022, 121.184),  # Kabugao
    "1507": (6.704, 121.971),  # Isabela City
    "1536": (8.000, 124.292),  # Marawi
    "1538": (6.864, 124.442),  # Shariff Aguak
    "1566": (6.052, 121.002),  # Jolo
    "1570": (5.029, 119.773),  # Bongao
    "1602": (8.948, 125.543),  # Butuan
    "1603": (8.606, 125.916),  # Prosperidad
    "1667": (9.789, 125.495),  # Surigao City
    "1668": (9.078, 126.199),  # Tandag
    "1685": (10.095, 125.609),  # San Jose, Dinagat
}

# Cities and municipalities that should not use the provincial capital.
_CITY_POINTS = {
    "137401": (14.579, 121.035),  # Mandaluyong
    "137402": (14.650, 121.102),  # Marikina
    "137403": (14.576, 121.085),  # Pasig
    "137404": (14.676, 121.044),  # Quezon City
    "137405": (14.604, 121.030),  # San Juan
    "137501": (14.648, 120.983),  # Caloocan
    "137502": (14.662, 120.957),  # Malabon
    "137503": (14.666, 120.941),  # Navotas
    "137504": (14.701, 120.983),  # Valenzuela
    "137601": (14.448, 120.982),  # Las Piñas
    "137602": (14.555, 121.024),  # Makati
    "137603": (14.408, 121.041),  # Muntinlupa
    "137604": (14.479, 121.027),  # Parañaque
    "137605": (14.537, 121.001),  # Pasay
    "137606": (14.545, 121.068),  # Pateros
    "137607": (14.517, 121.050),  # Taguig
    "112402": (7.070, 125.610),  # Davao City
    "112319": (7.448, 125.806),  # Tagum
    "112403": (6.750, 125.357),  # Digos
    "112315": (7.308, 125.684),  # Panabo
    "126303": (6.116, 125.172),  # General Santos
    "104305": (8.454, 124.632),  # Cagayan de Oro
    "072217": (10.307, 123.893),  # Cebu City
    "072226": (10.311, 123.949),  # Lapu-Lapu
    "072230": (10.323, 123.922),  # Mandaue
    "063022": (10.720, 122.562),  # Iloilo City
    "064501": (10.676, 122.951),  # Bacolod
    "141102": (16.411, 120.593),  # Baguio
    "035401": (15.145, 120.584),  # Angeles
    "035409": (15.223, 120.584),  # Mabalacat
    "045802": (14.588, 121.176),  # Antipolo
    "045805": (14.586, 121.123),  # Cainta municipal hall
    "045813": (14.567, 121.133),  # Taytay, Rizal
    "045808": (14.736, 121.145),  # Rodriguez
    "045811": (14.698, 121.122),  # San Mateo, Rizal
    "043405": (14.212, 121.165),  # Calamba
    "043428": (14.312, 121.111),  # Santa Rosa, Laguna
    "043403": (14.339, 121.084),  # Biñan
    "043404": (14.278, 121.125),  # Cabuyao
    "043425": (14.358, 121.057),  # San Pedro, Laguna
    "042103": (14.459, 120.964),  # Bacoor
    "042106": (14.330, 120.937),  # Dasmariñas
    "042109": (14.430, 120.937),  # Imus
    "097332": (6.921, 122.079),  # Zamboanga City
    "103504": (8.228, 124.245),  # Iligan
    "160202": (8.948, 125.543),  # Butuan
    "129804": (7.204, 124.247),  # Cotabato City
    "175316": (9.739, 118.735),  # Puerto Princesa
    "045624": (13.938, 121.617),  # Lucena
    "037107": (14.829, 120.283),  # Olongapo
    "031410": (14.853, 120.816),  # Malolos
    "031412": (14.736, 120.960),  # Meycauayan
    "031420": (14.814, 121.045),  # San Jose del Monte
    "041005": (13.757, 121.058),  # Batangas City
    "041014": (13.941, 121.163),  # Lipa
    "074610": (9.307, 123.308),  # Dumaguete
    "071242": (9.650, 123.853),  # Tagbilaran
    "083747": (11.245, 125.000),  # Tacloban
    "083738": (11.006, 124.608),  # Ormoc
    "051724": (13.621, 123.181),  # Naga City, Camarines Sur
    "072234": (10.209, 123.758),  # City of Naga, Cebu
    "099701": (6.704, 121.971),  # City of Isabela
}

_MANUAL_POINTS = {
    "CDO": (8.454, 124.632),
    "GENSAN": (6.116, 125.172),
}

# Option text that must not be selected for a similarly named branch.
_OPTION_EXCLUSIONS = {
    "Davao": ("UPRISE", "FELCRIS"),
    "Fairview": ("TERRACES",),
    "EDSA": ("GREENFIELD", "MANDALUYONG", "VERTIS"),
    "Pasay": ("MOA", "MALL OF ASIA"),
    "MOA": ("PASAY",),
    "Makati / Southgate": ("MCKINLEY", "AURA"),
    "Mandaluyong / EDSA Greenfield": ("VERTIS",),
}

_OPTION_ALIASES = {
    "Antipolo": ("ANTIPOLO",),
    "Baguio": ("BAGUIO",),
    "Bacolod": ("BACOLOD",),
    "Cagayan de Oro / CDO": ("CAGAYAN DE ORO", "CDO"),
    "Cebu": ("CEBU",),
    "Clark": ("CLARK",),
    "Davao": ("DAVAO",),
    "Davao Uprise / Felcris Centrale": ("DAVAO UPRISE", "FELCRIS CENTRALE", "FELCRIS", "UPRISE"),
    "General Santos": ("GENERAL SANTOS", "GENSAN"),
    "Laoag": ("LAOAG",),
    "Makati / Southgate": ("MAKATI", "SOUTHGATE", "SOUTH GATE"),
    "Mandaluyong / EDSA Greenfield": ("MANDALUYONG", "EDSA GREENFIELD", "GREENFIELD"),
    "McKinley West": ("MCKINLEY",),
    "Aura": ("AURA",),
    "Fairview": ("FAIRVIEW",),
    "Fairview Terraces": ("FAIRVIEW TERRACES",),
    "Vertis North": ("VERTIS",),
    "EDSA": ("EDSA",),
    "Silver City": ("SILVER CITY",),
    "Rockwell": ("ROCKWELL",),
    "Sucat": ("SUCAT",),
    "MOA": ("MOA", "MALL OF ASIA"),
    "Pasay": ("PASAY",),
}

_CLOSE_KM = 40.0
# Manila-area province codes. A duplicated municipality name here is the
# one candidates mean when they do not name another province.
_METRO_PROVINCES = {"0458", "1339", "1374", "1375", "1376"}


def branch_names():
    return tuple(branch["name"] for branch in TP_BRANCHES)


def haversine_km(origin, destination):
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    half = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(half))


def _contains_phrase(text, phrase):
    words = text.split()
    target = phrase.split()
    size = len(target)
    if size == 0 or size > len(words):
        return False
    return any(words[index : index + size] == target for index in range(len(words) - size + 1))


def _spread_km(places):
    points = [place["point"] for place in places]
    widest = 0.0
    for origin in points:
        for destination in points:
            widest = max(widest, haversine_km(origin, destination))
    return widest


def _choose_place(places, phrase):
    if len(places) == 1:
        return places[0]

    provinces = [
        place
        for place in places
        if place["kind"] == "province" and phrase in place["exact"]
    ]
    if len(provinces) == 1:
        return provinces[0]

    city_named = [place for place in places if place["has_city_word"]]
    official_hits = [place for place in places if place["official_norm"] == phrase]
    if len(official_hits) == 1:
        hit = official_hits[0]
        others = [place for place in city_named if place["id"] != hit["id"]]
        if hit["has_city_word"] or not others:
            return hit
        if len(others) == 1:
            return others[0]
    elif len(city_named) == 1:
        return city_named[0]

    metro = [place for place in places if place["prov_code"] in _METRO_PROVINCES]
    if len(metro) == 1:
        return metro[0]

    if _spread_km(places) <= _CLOSE_KM:
        if len(city_named) == 1:
            return city_named[0]
        return places[0]
    return None


def _add_place(index, phrase, place):
    bucket = index.setdefault(phrase, [])
    if all(existing["id"] != place["id"] for existing in bucket):
        bucket.append(place)


def _load_geo_index():
    index = {}
    with (DATA_DIR / "Province.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            code = row["provCode"]
            if code not in _PROVINCE_POINTS:
                raise KeyError(f"Missing coordinates for province {row['provDesc']} ({code})")
            official = row["provDesc"]
            without_notes = official.split("(")[0]
            exact = {normalize_place(official), normalize_place(without_notes)}
            place = {
                "id": f"province:{code}:{normalize_place(official)}",
                "kind": "province",
                "prov_code": code,
                "official_norm": normalize_place(without_notes),
                "exact": exact,
                "has_city_word": "CITY" in official.upper(),
                "point": _PROVINCE_POINTS[code],
                "label": normalize_place(official),
            }
            for alias in _aliases(official):
                _add_place(index, alias, place)
            if code == "1182":
                # The PSGC extract still uses the former province name.
                _add_place(index, "DAVAO DE ORO", place)

    with (DATA_DIR / "Municipalities.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            code = row["citymunCode"]
            prov = row["provCode"]
            point = _CITY_POINTS.get(code) or _PROVINCE_POINTS.get(prov)
            if point is None:
                continue
            official = row["citymunDesc"]
            without_notes = official.split("(")[0]
            place = {
                "id": f"city:{code}",
                "kind": "city",
                "prov_code": prov,
                "official_norm": normalize_place(without_notes),
                "exact": {normalize_place(official), normalize_place(without_notes)},
                "has_city_word": "CITY" in official.upper(),
                "point": point,
                "label": normalize_place(without_notes),
            }
            for alias in _aliases(official):
                _add_place(index, alias, place)

    for phrase, point in _MANUAL_POINTS.items():
        place = {
            "id": f"manual:{phrase}",
            "kind": "city",
            "prov_code": "",
            "official_norm": phrase,
            "exact": {phrase},
            "has_city_word": False,
            "point": point,
            "label": phrase,
        }
        _add_place(index, phrase, place)
    return index


@lru_cache(maxsize=1)
def _geo_index():
    return _load_geo_index()


def _nearest_name(point):
    branch = min(
        TP_BRANCHES,
        key=lambda item: (haversine_km(point, (item["lat"], item["lon"])), item["name"]),
    )
    return branch["name"]


def _places_in_named_province(index, places, text):
    """Keep places whose province is actually named in the location text."""
    named = set()
    for phrase in _phrases(text):
        for place in index.get(phrase, []):
            if place["kind"] == "province" and phrase in place["exact"]:
                named.add(place["prov_code"])
    if not named:
        return places
    filtered = [place for place in places if place["prov_code"] in named]
    return filtered or places


def _hint(text):
    for phrase, branch in _HINTS:
        if _contains_phrase(text, phrase):
            return branch, phrase
    return None


def explain_tp_branch(location):
    """Return ``(branch_name, matched_label)`` for a free-text location."""
    text = normalize_place(location)
    hinted = _hint(text)
    if hinted:
        return hinted

    if text:
        index = _geo_index()
        for phrase in _phrases(text):
            places = index.get(phrase)
            if not places:
                continue
            chosen = _choose_place(_places_in_named_province(index, places, text), phrase)
            if chosen:
                return _nearest_name(chosen["point"]), chosen["label"]
        for phrase, point in _BROAD_POINTS.items():
            if _contains_phrase(text, phrase):
                lat, lon, label = point
                return _nearest_name((lat, lon)), label

    if resolve_tp_site(location) == "vismin":
        return _nearest_name(_CEBU_CITY), "CEBU CITY"
    return _nearest_name(_MANILA), "MANILA"


def nearest_tp_branch(location):
    return explain_tp_branch(location)[0]


def match_site_option(branch_name, options):
    """Return the dropdown label for ``branch_name``.

    ``options`` are the visible ``q_prefer_site`` choices. Davao does not
    match Davao Uprise, and Fairview does not match Fairview Terraces.
    """
    if branch_name not in _OPTION_ALIASES:
        raise KeyError(branch_name)

    cleaned = []
    for option in options:
        text = " ".join(str(option or "").split())
        norm = normalize_place(text)
        if norm and norm not in {"SELECT", "PLEASE SELECT", "CHOOSE"}:
            cleaned.append((text, norm))

    target = normalize_place(branch_name)
    for text, norm in cleaned:
        if norm == target:
            return text

    aliases = _OPTION_ALIASES[branch_name]
    exclusions = _OPTION_EXCLUSIONS.get(branch_name, ())
    usable = [
        (text, norm)
        for text, norm in cleaned
        if not any(_contains_phrase(norm, excluded) for excluded in exclusions)
    ]
    for alias in aliases:
        for text, norm in usable:
            if norm == alias:
                return text
    best = None
    best_len = -1
    for alias in aliases:
        for text, norm in usable:
            if _contains_phrase(norm, alias) and len(alias) > best_len:
                best = text
                best_len = len(alias)
    return best
