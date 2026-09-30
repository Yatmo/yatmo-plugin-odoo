# Hermetic tests: Yatmo is never called, requests.get is replaced by canned answers.
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from odoo.tests import TransactionCase, tagged

SUMMARY = {
    "Paragraphs": [
        {
            "IconId": "shopping",
            "Title": {"FR": "Commerces", "EN": "Shops", "NL": "Winkels"},
            "TitleBis": {"FR": "Commerces près de la Rue de la Loi", "EN": "Shops near Rue de la Loi", "NL": "Winkels bij de Wetstraat"},
            "TitleTer": {"FR": "Commerces à Bruxelles", "EN": "Shops in Brussels", "NL": "Winkels in Brussel"},
            "Sentences": [{"FR": "Un [STRONG]Carrefour[/STRONG] à 3 minutes.", "EN": "A [STRONG]Carrefour[/STRONG] 3 minutes away.", "NL": "Een [STRONG]Carrefour[/STRONG] op 3 minuten."}],
            "List": [],
        },
        {
            "IconId": "education",
            "Title": {"FR": "Écoles", "EN": "Schools", "NL": "Scholen"},
            "TitleBis": {"FR": "Écoles près de la Rue de la Loi", "EN": "Schools near Rue de la Loi", "NL": "Scholen bij de Wetstraat"},
            "TitleTer": {"FR": "Écoles à Bruxelles", "EN": "Schools in Brussels", "NL": "Scholen in Brussel"},
            "Sentences": [{"FR": "Deux écoles <primaires> à moins de 10 minutes.", "EN": "Two <primary> schools within 10 minutes.", "NL": "Twee <basisscholen> binnen 10 minuten."}],
            "List": [{"FR": "École A", "EN": "School A", "NL": "School A"}],
        },
        {
            "IconId": "cities",
            "Title": {"FR": "Villes", "EN": "Cities", "NL": "Steden"},
            "Sentences": [],
            "List": [],
        },
    ]
}

GEOCODE = {"type": "FeatureCollection", "features": [{"geometry": {"coordinates": [4.3664, 50.8461]}}]}


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


@tagged("post_install", "-at_install")
class TestYatmoMap(TransactionCase):

    def setUp(self):
        super().setUp()
        self.icp = self.env["ir.config_parameter"].sudo()
        self.icp.set_param("yatmo_map.license_key", "abc123")
        self.icp.set_param("yatmo_map.country", "BE")
        # The dev database may hold real texts and geocodes for the same coordinates.
        self.env["yatmo.map.cache"].search([]).unlink()
        self.calls = []
        patcher = patch("odoo.addons.yatmo_map.models.yatmo_map.requests.get", side_effect=self._fake_get)
        self.fake_get = patcher.start()
        self.addCleanup(patcher.stop)
        # An editor, so the notices are visible in the tests.
        self.editor = self.env["res.users"].create({
            "name": "Editor", "login": "yatmo_editor",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id, self.env.ref("website.group_website_designer").id])],
        })
        self.yatmo = self.env["yatmo.map"].with_user(self.editor)

    def _fake_get(self, url, **kwargs):
        self.calls.append(url)
        if "/Summary/text" in url:
            return FakeResponse(200, SUMMARY)
        if "/Geolocation" in url:
            query = parse_qs(urlparse(url).query)
            if "nowhere" in query.get("address", [""])[0].lower():
                return FakeResponse(200, {"type": "FeatureCollection", "features": []})
            return FakeResponse(200, GEOCODE)
        return FakeResponse(404)

    @staticmethod
    def _params(html):
        src = html.split('src="', 1)[1].split('"', 1)[0].replace("&amp;", "&")
        return {k: v[0] for k, v in parse_qs(urlparse(src).query).items()}

    def test_map_from_coordinates_and_defaults(self):
        html = str(self.yatmo.render_map({"latitude": "50,8461", "longitude": "4.3664", "language": "fr"}))
        self.assertIn('class="yatmo-map-embed"', html)
        self.assertIn("height:560px", html)
        params = self._params(html)
        self.assertEqual(params["licenseKey"], "abc123")
        self.assertEqual(params["country"], "BE")
        self.assertEqual(params["language"], "FR")
        self.assertEqual(params["latitude"], "50.8461")
        self.assertEqual(params["mode"], "overlay")
        self.assertEqual(params["marker"], "pin")
        self.assertNotIn("isochrone", params)
        self.assertNotIn("rounded", params)
        self.assertEqual(self.calls, [])

    def test_map_options_and_settings(self):
        self.icp.set_param("yatmo_map.isochrone", "right")
        self.icp.set_param("yatmo_map.rounded", "8")
        self.icp.set_param("yatmo_map.height", "70vh")
        html = str(self.yatmo.render_map({
            "latitude": 50.8461, "longitude": 4.3664, "mode": "map-top", "marker": "circle",
            "circle_radius": "9999", "zoom": "3", "accent_color": "#123456", "route_from": "popup",
            "summary_line_color": "nope", "css_class": "my-map", "title": "Around the flat",
        }))
        params = self._params(html)
        self.assertEqual(params["mode"], "map-top")
        self.assertEqual(params["marker"], "circle")
        self.assertEqual(params["circleRadiusInMeters"], "2000")
        self.assertEqual(params["zoom"], "7")
        self.assertEqual(params["accentColor"], "#123456")
        self.assertEqual(params["isochrone"], "right")
        self.assertEqual(params["routeFrom"], "popup")
        self.assertEqual(params["rounded"], "8px")
        self.assertNotIn("summaryLineColor", params)
        self.assertIn('class="yatmo-map-embed my-map"', html)
        self.assertIn('title="Around the flat"', html)
        self.assertIn("height:70vh", html)
        # "off" on the block disables a module the settings enable.
        params = self._params(str(self.yatmo.render_map({"latitude": 50.8461, "longitude": 4.3664, "isochrone": "off"})))
        self.assertNotIn("isochrone", params)

    def test_map_from_address_is_geocoded_once(self):
        values = {"address": "Rue de la Loi 16, 1000 Bruxelles"}
        first = self._params(str(self.yatmo.render_map(values)))
        second = self._params(str(self.yatmo.render_map(values)))
        self.assertEqual(first["latitude"], "50.8461")
        self.assertEqual(first["longitude"], "4.3664")
        self.assertEqual(first, second)
        self.assertEqual(len([c for c in self.calls if "/Geolocation" in c]), 1)
        self.assertIn("be.yatmo.com/Geolocation", self.calls[0])

    def test_notices_for_editors_only(self):
        html = str(self.yatmo.render_map({"address": "Nowhere street"}))
        self.assertIn("yatmo-map-notice", html)
        self.assertIn("could not find the address", html)
        self.assertEqual(str(self.env["yatmo.map"].with_user(self.env.ref("base.public_user")).render_map({"address": "Nowhere street"})), "")

        self.assertIn("No property location", str(self.yatmo.render_map({})))
        self.icp.set_param("yatmo_map.license_key", "")
        self.assertIn("licence key", str(self.yatmo.render_map({"latitude": 50.8461, "longitude": 4.3664})))

    def test_embed_json(self):
        result = self.yatmo.embed_json({"yatmoLatitude": "50.8461", "yatmoLongitude": "4.3664", "yatmoMode": "map", "pageLang": "nl-BE"})
        self.assertTrue(result["url"].startswith("https://map.yatmo.com/plugin.html?"))
        params = {k: v[0] for k, v in parse_qs(urlparse(result["url"]).query).items()}
        self.assertEqual(params["mode"], "map")
        self.assertEqual(params["language"], "NL")
        self.assertEqual(result["height"], "560px")
        self.assertEqual(self.yatmo.embed_json({}), {"notice": "No property location: give an address or coordinates."})
        self.assertEqual(self.env["yatmo.map"].with_user(self.env.ref("base.public_user")).embed_json({}), {"notice": ""})

    def test_text(self):
        html = str(self.yatmo.render_text({"latitude": 50.8461, "longitude": 4.3664, "language": "FR"}))
        self.assertIn('<div class="yatmo-text">', html)
        # Paragraphs in the order Yatmo sends them, street in the first heading, city in the second.
        self.assertLess(html.index("Commerces près de la Rue de la Loi"), html.index("Écoles à Bruxelles"))
        self.assertIn("<h3>Commerces près de la Rue de la Loi</h3>", html)
        self.assertIn("<h3>Écoles à Bruxelles</h3>", html)
        self.assertIn("<p>Deux écoles &lt;primaires&gt; à moins de 10 minutes.</p>", html)
        self.assertIn("<ul><li>École A</li></ul>", html)
        self.assertIn("<strong>Carrefour</strong>", html)
        self.assertNotIn("Villes", html)  # empty paragraph skipped
        self.assertIn("be.yatmo.com/Summary/text", self.calls[0])

        # Cached: no second call. Options: paragraphs, heading, no street name.
        html = str(self.yatmo.render_text({
            "latitude": 50.8461, "longitude": 4.3664, "language": "EN",
            "paragraphs": "shopping", "heading": "h2", "street_in_title": "0",
        }))
        self.assertEqual(len(self.calls), 1)
        self.assertIn("<h2>Shops</h2>", html)
        self.assertNotIn("Schools", html)

        # A language the country does not have falls back to English.
        html = str(self.yatmo.render_text({"latitude": 50.8461, "longitude": 4.3664, "language": "DE"}))
        self.assertIn("Shops near Rue de la Loi", html)

    def test_text_settings(self):
        self.icp.set_param("yatmo_map.text_paragraphs", "shopping")
        self.icp.set_param("yatmo_map.text_heading", "h4")
        self.icp.set_param("yatmo_map.text_hide_street", "True")
        html = str(self.yatmo.render_text({"latitude": 50.8461, "longitude": 4.3664, "language": "EN"}))
        self.assertIn("<h4>Shops</h4>", html)
        self.assertNotIn("Schools", html)

    def test_text_json_and_errors(self):
        result = self.yatmo.text_json({"yatmoLatitude": "50.8461", "yatmoLongitude": "4.3664", "pageLang": "en"})
        self.assertIn("<h3>Shops near Rue de la Loi</h3>", result["html"])
        self.assertEqual(result["notice"], "")
        result = self.yatmo.text_json({})
        self.assertEqual(result["html"], "")
        self.assertIn("No property location", result["notice"])

        self.fake_get.side_effect = lambda url, **kw: FakeResponse(403)
        result = self.yatmo.text_json({"yatmoLatitude": "51.2", "yatmoLongitude": "4.4"})
        self.assertIn("does not include the neighbourhood text", result["notice"])
        self.fake_get.side_effect = lambda url, **kw: FakeResponse(200, {"oops": 1})
        result = self.yatmo.text_json({"yatmoLatitude": "51.3", "yatmoLongitude": "4.4"})
        self.assertIn("unexpected answer", result["notice"])

    def test_settings_roundtrip(self):
        settings = self.env["res.config.settings"].create({
            "yatmo_license_key": " key-with-dash ",
            "yatmo_country": "FR",
            "yatmo_mode": "summary-tabs",
            "yatmo_isochrone": "left",
            "yatmo_favorites": True,
            # The form starts with every paragraph ticked (the default): untick four.
            "yatmo_text_education": True,
            "yatmo_text_shopping": False,
            "yatmo_text_publictransports": False,
            "yatmo_text_transports": False,
            "yatmo_text_tourism": False,
            "yatmo_text_cities": True,
            "yatmo_text_hide_city": True,
        })
        settings.execute()
        cfg = self.env["yatmo.map"].config()
        self.assertEqual(cfg["license_key"], "keywithdash")
        self.assertEqual(cfg["country"], "FR")
        self.assertEqual(cfg["mode"], "summary-tabs")
        self.assertEqual(cfg["isochrone"], "left")
        self.assertTrue(cfg["favorites"])
        self.assertEqual(cfg["text_paragraphs"], ["education", "cities"])
        self.assertTrue(cfg["text_hide_city"])
        self.assertFalse(cfg["text_hide_street"])
        values = self.env["res.config.settings"].default_get(["yatmo_text_education", "yatmo_text_shopping", "yatmo_isochrone"])
        self.assertTrue(values["yatmo_text_education"])
        self.assertFalse(values["yatmo_text_shopping"])
        self.assertEqual(values["yatmo_isochrone"], "left")

    def test_cache_expiry(self):
        cache = self.env["yatmo.map.cache"]
        cache.set_value("k", {"a": 1}, 60)
        self.assertEqual(cache.get_value("k"), {"a": 1})
        cache.set_value("k", {"a": 2}, -1)
        self.assertIsNone(cache.get_value("k"))
        cache._purge_expired()
        self.assertFalse(cache.sudo().search([("key", "=", "k")]))

    def test_templates(self):
        view = self.env["ir.ui.view"]
        html = view.with_user(self.editor)._render_template("yatmo_map.map", {"yatmo": {"latitude": 50.8461, "longitude": 4.3664}})
        self.assertIn("map.yatmo.com/plugin.html", str(html))
        html = view.with_user(self.editor)._render_template("yatmo_map.text", {"yatmo": {"latitude": 50.8461, "longitude": 4.3664, "language": "EN"}})
        self.assertIn("<h3>Shops near Rue de la Loi</h3>", str(html))
        self.assertIn("No property location", str(view.with_user(self.editor)._render_template("yatmo_map.map", {})))
