import unittest

from tp_locations import explain_tp_site, resolve_tp_site


class TeleperformanceSiteTests(unittest.TestCase):
    def assert_site(self, location, site):
        resolved, matched = explain_tp_site(location)
        self.assertEqual(resolved, site, f"{location!r} matched {matched!r}")

    def test_vismin_provinces_and_cities(self):
        for location in [
            "Cebu",
            "Cebu City",
            "Davao",
            "Davao del Sur",
            "Iloilo",
            "Bacolod City",
            "Cagayan de Oro",
            "CDO",
            "Zamboanga City",
            "General Santos",
            "Gensan",
            "Butuan",
            "Tacloban",
            "Tagbilaran",
            "Dumaguete",
            "City of Naga, Cebu",
        ]:
            self.assert_site(location, "vismin")

    def test_luzon_provinces_and_cities(self):
        for location in [
            "Manila",
            "Quezon City",
            "Makati",
            "Pasig City",
            "Baguio",
            "City of Calamba",
            "Calamba",
            "Puerto Princesa",
            "Palawan",
            "Pampanga",
            "Naga City",
            "Isabela",
            "Metro Manila",
            "NCR",
        ]:
            self.assert_site(location, "luzon")

    def test_city_of_isabela_is_mindanao(self):
        self.assert_site("Isabela City", "vismin")
        self.assert_site("City of Isabela", "vismin")

    def test_barangay_used_when_city_is_absent(self):
        site, matched = explain_tp_site("Lahug")
        self.assertEqual(site, "vismin")
        self.assertEqual(matched, "LAHUG")

    def test_barangay_does_not_override_city(self):
        site, matched = explain_tp_site("Brgy. Lahug, Cebu City")
        self.assertEqual(site, "vismin")
        self.assertEqual(matched, "CEBU CITY")

    def test_unknown_location_defaults_to_luzon(self):
        self.assertEqual(resolve_tp_site(""), "luzon")
        self.assertEqual(resolve_tp_site("Atlantis"), "luzon")
        self.assertEqual(resolve_tp_site(None), "luzon")


if __name__ == "__main__":
    unittest.main()
