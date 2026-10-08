import unittest

from tp_branches import branch_names, explain_tp_branch, match_site_option, nearest_tp_branch


class NearestTeleperformanceBranchTests(unittest.TestCase):
    def assert_branch(self, location, branch):
        resolved, matched = explain_tp_branch(location)
        self.assertEqual(resolved, branch, f"{location!r} matched {matched!r} -> {resolved!r}")

    def test_canonical_site_list(self):
        self.assertEqual(
            branch_names(),
            (
                "Antipolo",
                "Baguio",
                "Bacolod",
                "Cagayan de Oro / CDO",
                "Cebu",
                "Clark",
                "Davao",
                "Davao Uprise / Felcris Centrale",
                "General Santos",
                "Laoag",
                "Makati / Southgate",
                "Mandaluyong / EDSA Greenfield",
                "McKinley West",
                "Aura",
                "Fairview",
                "Fairview Terraces",
                "Vertis North",
                "EDSA",
                "Silver City",
                "Rockwell",
                "Sucat",
                "MOA",
                "Pasay",
            ),
        )

    def test_vismin_cities(self):
        cases = {
            "Cebu": "Cebu",
            "Cebu City": "Cebu",
            "Davao": "Davao",
            "Davao city": "Davao",
            "Davao City": "Davao",
            "City of Digos": "Davao",
            "Tagum": "Davao Uprise / Felcris Centrale",
            "Lanang, Davao City": "Davao Uprise / Felcris Centrale",
            "Felcris Centrale": "Davao Uprise / Felcris Centrale",
            "The Uprise, Davao": "Davao Uprise / Felcris Centrale",
            "Cagayan de Oro": "Cagayan de Oro / CDO",
            "CDO": "Cagayan de Oro / CDO",
            "General Santos": "General Santos",
            "Gensan": "General Santos",
            "Bacolod": "Bacolod",
            "Bacolod City": "Bacolod",
            "Iloilo": "Bacolod",
            "Iloilo City": "Bacolod",
        }
        for location, branch in cases.items():
            self.assert_branch(location, branch)

    def test_luzon_and_ncr(self):
        cases = {
            "Baguio": "Baguio",
            "Baguio City": "Baguio",
            "Laoag": "Laoag",
            "Ilocos Norte": "Laoag",
            "Cagayan": "Laoag",
            "Clark": "Clark",
            "Angeles": "Clark",
            "Angeles City": "Clark",
            "Mabalacat": "Clark",
            "Pampanga": "Clark",
            "Antipolo": "Antipolo",
            "Marikina": "Antipolo",
            "Cainta": "Antipolo",
            "Taytay": "Silver City",
            "Taytay, Rizal": "Silver City",
            "Taytay, Palawan": "Bacolod",
            "San Mateo": "Fairview",
            "San Mateo, Rizal": "Fairview",
            "Makati": "Makati / Southgate",
            "Makati City": "Makati / Southgate",
            "Mandaluyong": "Mandaluyong / EDSA Greenfield",
            "Quezon City": "Vertis North",
            "Fairview, Quezon City": "Fairview",
            "Fairview Terraces": "Fairview Terraces",
            "Greater Lagro": "Fairview",
            "Vertis North": "Vertis North",
            "Cubao, Quezon City": "EDSA",
            "Pasig": "Silver City",
            "Pasig City": "Silver City",
            "Taguig": "McKinley West",
            "McKinley West": "McKinley West",
            "BGC, Taguig": "Aura",
            "SM Aura": "Aura",
            "Rockwell": "Rockwell",
            "Ortigas, Pasig": "Rockwell",
            "Sucat": "Sucat",
            "Paranaque": "Sucat",
            "Parañaque": "Sucat",
            "MOA": "MOA",
            "Mall of Asia": "MOA",
            "Pasay": "Pasay",
            "Pasay City": "Pasay",
            "Manila": "Pasay",
            "Calamba": "Sucat",
            "City of Calamba": "Sucat",
        }
        for location, branch in cases.items():
            self.assert_branch(location, branch)

    def test_shared_names_keep_their_own_branch(self):
        self.assert_branch("Isabela", "Baguio")
        self.assert_branch("City of Isabela", "Cagayan de Oro / CDO")
        self.assert_branch("Naga City", "Antipolo")
        self.assert_branch("Davao de Oro", "Davao Uprise / Felcris Centrale")
        self.assert_branch("San Mateo, Isabela", "Baguio")
        self.assert_branch("City of Naga, Cebu", "Cebu")
        self.assert_branch("Quezon", "Sucat")
        self.assert_branch("Quezon City", "Vertis North")

    def test_unknown_location_uses_manila(self):
        self.assert_branch("", "Pasay")
        self.assert_branch("Atlantis", "Pasay")
        self.assert_branch(None, "Pasay")

    def test_option_labels_match_exactly(self):
        options = ["", "Select", *branch_names()]
        for name in branch_names():
            self.assertEqual(match_site_option(name, options), name)

    def test_option_labels_do_not_collapse_similar_sites(self):
        self.assertEqual(
            match_site_option("Davao", ["Select", "TP Davao Uprise", "TP Davao"]),
            "TP Davao",
        )
        self.assertEqual(
            match_site_option(
                "Davao Uprise / Felcris Centrale",
                ["Davao", "Felcris Centrale"],
            ),
            "Felcris Centrale",
        )
        self.assertEqual(
            match_site_option("Fairview", ["Fairview Terraces", "SM Fairview"]),
            "SM Fairview",
        )
        self.assertEqual(
            match_site_option("Fairview Terraces", ["Fairview", "Fairview Terraces"]),
            "Fairview Terraces",
        )
        self.assertEqual(match_site_option("Cagayan de Oro / CDO", ["CDO"]), "CDO")
        self.assertEqual(
            match_site_option("EDSA", ["EDSA Greenfield", "EDSA Cubao"]),
            "EDSA Cubao",
        )
        self.assertEqual(match_site_option("MOA", ["Pasay", "MOA"]), "MOA")
        self.assertEqual(
            match_site_option("Pasay", ["MOA Annex Pasay", "Pasay"]),
            "Pasay",
        )
        self.assertEqual(
            match_site_option("Mandaluyong / EDSA Greenfield", ["EDSA", "Greenfield"]),
            "Greenfield",
        )

    def test_review_candidate_davao_city(self):
        self.assertEqual(nearest_tp_branch("Davao city"), "Davao")


if __name__ == "__main__":
    unittest.main()
