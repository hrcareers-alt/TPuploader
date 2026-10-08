"""Map a candidate location to a Teleperformance Philippines site.

Teleperformance endorsements in this project use two requisitions: Luzon and
VisMin (Visayas and Mindanao). Province, city/municipality, and barangay names
come from the PSGC tables in ``data/``.
"""

import csv
import re
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

# PSGC region codes. 17 is MIMAROPA, which Teleperformance treats as Luzon.
VISMIN_REGION_CODES = {"06", "07", "08", "09", "10", "11", "12", "15", "16"}

# Spoken aliases that are not official PSGC names.
MANUAL_SITES = {
    "CDO": "vismin",
    "GENSAN": "vismin",
    "NCR": "luzon",
    "METRO MANILA": "luzon",
    "MINDANAO": "vismin",
    "VISAYAS": "vismin",
    "VISMIN": "vismin",
    "LUZON": "luzon",
}

_SKIP_ALIASES = {
    "CITY",
    "CAPITAL",
    "OF",
    "THE",
    "POB",
    "POBLACION",
    "BARANGAY",
    "BRGY",
    "BGY",
}


def site_for_region(reg_code):
    if str(reg_code).zfill(2) in VISMIN_REGION_CODES:
        return "vismin"
    return "luzon"


def normalize_place(value):
    text = str(value or "").upper().replace("Ñ", "N")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _aliases(description):
    raw = str(description or "")
    without_notes = re.sub(r"\([^)]*\)", " ", raw)
    names = {normalize_place(raw), normalize_place(without_notes)}
    names.update(normalize_place(part) for part in re.findall(r"\(([^)]+)\)", raw))

    expanded = set(names)
    for name in names:
        if name.startswith("CITY OF "):
            rest = name[len("CITY OF ") :].strip()
            expanded.add(rest)
            expanded.add(f"{rest} CITY".strip())
        if name.endswith(" CITY"):
            rest = name[: -len(" CITY")].strip()
            expanded.add(rest)
            expanded.add(f"CITY OF {rest}".strip())
    return {name for name in expanded if name and name not in _SKIP_ALIASES and len(name) >= 3}


class _PlaceIndex:
    def __init__(self):
        # phrase -> {"sites": set, "province_sites": set, "city_word_sites": set}
        self.places = {}
        self.barangays = {}

    def add_place(self, phrase, site, kind, official_name, exact_province=False):
        entry = self.places.setdefault(
            phrase,
            {
                "sites": set(),
                "exact_province_sites": set(),
                "province_sites": set(),
                "city_word_sites": set(),
            },
        )
        entry["sites"].add(site)
        if exact_province:
            entry["exact_province_sites"].add(site)
        if kind == "province":
            entry["province_sites"].add(site)
        if kind == "city" and "CITY" in official_name.upper():
            entry["city_word_sites"].add(site)

    def add_barangay(self, phrase, site):
        self.barangays.setdefault(phrase, set()).add(site)


def _load_index():
    index = _PlaceIndex()
    with (DATA_DIR / "Province.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            site = site_for_region(row["regCode"])
            official = row["provDesc"]
            without_notes = re.sub(r"\([^)]*\)", " ", official)
            exact = {normalize_place(official), normalize_place(without_notes)}
            for alias in _aliases(official):
                index.add_place(
                    alias, site, "province", official, exact_province=alias in exact
                )

    with (DATA_DIR / "Municipalities.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            site = site_for_region(row["regDesc"])
            official = row["citymunDesc"]
            for alias in _aliases(official):
                index.add_place(alias, site, "city", official)

    for phrase, site in MANUAL_SITES.items():
        index.add_place(phrase, site, "province", phrase)

    with (DATA_DIR / "Barangay.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            site = site_for_region(row["regCode"])
            for alias in _aliases(row["brgyDesc"]):
                if alias in index.places or alias in MANUAL_SITES:
                    continue
                index.add_barangay(alias, site)
    return index


@lru_cache(maxsize=1)
def _index():
    return _load_index()


def _phrases(text):
    words = text.split()
    for length in range(len(words), 0, -1):
        for start in range(len(words) - length + 1):
            yield " ".join(words[start : start + length])


def _site_for_phrase(entry):
    if len(entry["sites"]) == 1:
        return next(iter(entry["sites"]))
    if len(entry["exact_province_sites"]) == 1:
        return next(iter(entry["exact_province_sites"]))
    if len(entry["province_sites"]) == 1:
        return next(iter(entry["province_sites"]))
    if len(entry["city_word_sites"]) == 1:
        return next(iter(entry["city_word_sites"]))
    return None


def explain_tp_site(location):
    """Return ``(site, matched_name)`` for a free-text location.

    Unknown and ambiguous locations stay on the Luzon requisition, which is
    the endorsing default when no VisMin place can be identified.
    """
    text = normalize_place(location)
    if not text:
        return "luzon", ""

    index = _index()
    for phrase in _phrases(text):
        entry = index.places.get(phrase)
        if entry is None:
            continue
        site = _site_for_phrase(entry)
        if site:
            return site, phrase

    for phrase in _phrases(text):
        sites = index.barangays.get(phrase)
        if sites and len(sites) == 1:
            return next(iter(sites)), phrase

    return "luzon", ""


def resolve_tp_site(location):
    return explain_tp_site(location)[0]
