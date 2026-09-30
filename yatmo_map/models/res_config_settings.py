# Site-wide defaults of the module, in Website > Configuration > Settings > Yatmo. Stored as the
# system parameters yatmo_map.*, read back by yatmo.map.config(). Every block, template or
# JSON call can override them.
from odoo import api, fields, models

from .yatmo_map import COUNTRIES, HEADINGS, LANGUAGES, MODES, PARAGRAPHS


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    yatmo_license_key = fields.Char(
        "Yatmo licence key", config_parameter="yatmo_map.license_key",
        help="Your Yatmo frontend key, the one locked to your domains. Never enter your backend key here.")
    yatmo_country = fields.Selection(
        COUNTRIES, "Country", config_parameter="yatmo_map.country", default="BE",
        help="Country of your properties. A block or template can set another one.")
    yatmo_language = fields.Selection(
        [("auto", "Same as the page (recommended)")] + [(code, "%s (%s)" % (code, label)) for code, label in LANGUAGES],
        "Language", config_parameter="yatmo_map.language", default="auto")

    yatmo_mode = fields.Selection(
        [(mode, mode) for mode in MODES], "Layout", config_parameter="yatmo_map.mode", default="overlay")
    yatmo_height = fields.Char(
        "Height", config_parameter="yatmo_map.height", default="560",
        help="In pixels (560) or any CSS length (70vh). The width always fills the content column.")
    yatmo_zoom = fields.Integer("Zoom", config_parameter="yatmo_map.zoom", default=15, help="7 to 20.")
    yatmo_map_style = fields.Integer(
        "Map style", config_parameter="yatmo_map.map_style", default=1,
        help="1 to 7. Compare the styles in the Yatmo playground: https://yatmo.com/#map-playground")
    yatmo_accent_color = fields.Char(
        "Accent colour", config_parameter="yatmo_map.accent_color", default="#428BFF",
        help="Hex colour of the pin and highlights.")
    yatmo_rounded = fields.Integer(
        "Rounded corners", config_parameter="yatmo_map.rounded", default=0, help="Radius in pixels, 0 to 15.")
    yatmo_marker = fields.Selection(
        [("pin", "Pin (exact location)"), ("circle", "Circle (hides the exact address)")],
        "Property marker", config_parameter="yatmo_map.marker", default="pin")
    yatmo_circle_radius = fields.Integer(
        "Circle radius (m)", config_parameter="yatmo_map.circle_radius", default=500, help="50 to 2000 metres.")

    yatmo_isochrone = fields.Selection(
        [("off", "Off"), ("left", "On, panel on the left"), ("right", "On, panel on the right")],
        "Isochrones", config_parameter="yatmo_map.isochrone", default="off",
        help="Areas reachable in 5, 10 and 20 minutes from the property.")
    yatmo_route_from = fields.Selection(
        [("off", "Off"), ("left", "On, panel on the left"), ("right", "On, panel on the right"),
         ("popup", "Travel times in the place popup only")],
        "Routes", config_parameter="yatmo_map.route_from", default="off",
        help="Route from the property to the place the visitor clicks.")
    yatmo_favorites = fields.Boolean(
        "Favourite addresses", config_parameter="yatmo_map.favorites",
        help="Let logged-in visitors save their own places (home, work, school) and see their commute "
             "from every property. Each visitor is identified by a hash of their Odoo user id; nothing else is sent.")

    yatmo_text_education = fields.Boolean("Education")
    yatmo_text_shopping = fields.Boolean("Shopping")
    yatmo_text_publictransports = fields.Boolean("Public transport")
    yatmo_text_transports = fields.Boolean("Roads, stations and airports")
    yatmo_text_tourism = fields.Boolean("Leisure and tourism")
    yatmo_text_cities = fields.Boolean("Nearby cities")
    yatmo_text_heading = fields.Selection(
        [(h, h.upper()) for h in HEADINGS], "Heading level", config_parameter="yatmo_map.text_heading", default="h3",
        help="Pick the level that fits under the headings of your property page.")
    yatmo_text_hide_street = fields.Boolean(
        "Hide the street name", config_parameter="yatmo_map.text_hide_street",
        help="The first heading names the street. Tick this when the exact address of a property must stay private.")
    yatmo_text_hide_city = fields.Boolean(
        "Hide the city name", config_parameter="yatmo_map.text_hide_city",
        help="The second heading names the city.")

    @api.model
    def get_values(self):
        res = super().get_values()
        enabled = self.env["yatmo.map"].config()["text_paragraphs"]
        for paragraph in PARAGRAPHS:
            res["yatmo_text_" + paragraph] = paragraph in enabled
        return res

    def set_values(self):
        super().set_values()
        # None ticked = all, like the module default.
        enabled = [p for p in PARAGRAPHS if self["yatmo_text_" + p]]
        self.env["ir.config_parameter"].sudo().set_param(
            "yatmo_map.text_paragraphs", ",".join(enabled or PARAGRAPHS))
