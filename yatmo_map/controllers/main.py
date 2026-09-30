# JSON routes of the building blocks. The map block asks for its iframe URL at page load (the
# licence key thus never sits in the saved page); the text block asks, in the editor only, for
# the HTML it writes into the page.
from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request


class YatmoMapController(http.Controller):

    @http.route("/yatmo_map/embed", type="jsonrpc", auth="public", website=True)
    def embed(self, values=None, **kwargs):
        return request.env["yatmo.map"].embed_json(values or {})

    @http.route("/yatmo_map/text", type="jsonrpc", auth="user", website=True)
    def text(self, values=None, **kwargs):
        if not request.env["yatmo.map"].is_editor():
            raise AccessError("Only website editors can generate the Yatmo text.")
        return request.env["yatmo.map"].text_json(values or {})
