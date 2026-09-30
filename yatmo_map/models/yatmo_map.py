# The Yatmo service of the module: site defaults, iframe URL (https://map.yatmo.com/plugin.html),
# neighbourhood text (https://<country>.yatmo.com/Summary/text) and geocoder
# (https://<country>.yatmo.com/Geolocation). The building blocks, the QWeb templates and the
# JSON routes all end up here, so the rules are written once.
#
# Parameter reference of the iframe: https://documentation.yatmo.com/plugins/iframe
import hashlib
import hmac
import logging
import re
from urllib.parse import urlencode

import requests
from markupsafe import Markup, escape

from odoo import _, api, models
from odoo.http import request

_logger = logging.getLogger(__name__)

IFRAME_URL = "https://map.yatmo.com/plugin.html"

# Countries served by Yatmo (country parameter of the iframe).
COUNTRIES = [
    ("AL", "Albania"), ("AT", "Austria"), ("AU", "Australia"), ("BA", "Bosnia and Herzegovina"),
    ("BE", "Belgium"), ("BG", "Bulgaria"), ("CA", "Canada"), ("CH", "Switzerland"),
    ("CY", "Cyprus"), ("DE", "Germany"), ("ES", "Spain"), ("FR", "France"), ("GR", "Greece"),
    ("HR", "Croatia"), ("IE", "Ireland"), ("IT", "Italy"), ("LU", "Luxembourg"),
    ("MA", "Morocco"), ("ME", "Montenegro"), ("MT", "Malta"), ("NL", "Netherlands"),
    ("PT", "Portugal"), ("RS", "Serbia"), ("SI", "Slovenia"), ("UK", "United Kingdom"),
]
COUNTRY_CODES = [code for code, _label in COUNTRIES]

# Languages of the widget, with their native names.
LANGUAGES = [
    ("EN", "English"), ("FR", "Français"), ("NL", "Nederlands"), ("DE", "Deutsch"),
    ("IT", "Italiano"), ("ES", "Español"), ("PT", "Português"), ("CA", "Català"),
    ("EL", "Ελληνικά"), ("HR", "Hrvatski"), ("MT", "Malti"), ("SL", "Slovenščina"),
    ("SR", "Srpski"), ("BS", "Bosanski"), ("CNR", "Crnogorski"), ("SQ", "Shqip"),
    ("BG", "Български"), ("TR", "Türkçe"), ("AR", "العربية"), ("RU", "Русский"),
    ("ZH", "汉语"), ("JA", "日本語"), ("HI", "हिन्दी"),
]
LANGUAGE_CODES = [code for code, _label in LANGUAGES]

MODES = ["overlay", "overlay-scores", "map-top", "map", "summary", "summary-tabs"]
MARKERS = ["pin", "circle", "custom"]
SIDE_MODULES = ["", "left", "right"]
ROUTE_FROM = ["", "left", "right", "popup"]
HEADINGS = ["h2", "h3", "h4", "h5", "h6"]

# Paragraph types of the Yatmo summary, in display order (IconId of Summary/text).
PARAGRAPHS = ["education", "shopping", "publictransports", "transports", "tourism", "cities"]

TEXT_TTL = 30 * 24 * 3600
GEOCODE_FOUND_TTL = 90 * 24 * 3600
GEOCODE_MISS_TTL = 3600

# Keys accepted by the templates, the blocks and the JSON routes. Block data attributes are
# camelCase with a "yatmo" prefix (data-yatmo-accent-color); everything is normalized to these.
VALUE_KEYS = [
    "address", "latitude", "longitude", "country", "language", "mode", "marker",
    "circle_radius", "custom_marker_url", "custom_marker_width", "custom_marker_height",
    "map_style", "accent_color", "zoom", "height", "rounded", "isochrone", "route_from",
    "summary_background_color", "summary_line_color", "title", "css_class",
    "paragraphs", "heading", "street_in_title", "city_in_title", "page_lang",
]


class YatmoMapError(Exception):
    """Something is missing (key, location...): explained to editors, hidden from visitors."""


def param_get(icp, key):
    """System parameter as a string ("" when unset). Odoo 20 replaced get_param by typed getters."""
    if hasattr(icp, "get_str"):
        return icp.get_str(key, "") or ""
    return icp.get_param(key) or ""


def param_set(icp, key, value):
    """Stores a system parameter as a string (Odoo 19: set_param, Odoo 20: set_str)."""
    if hasattr(icp, "set_str"):
        return icp.set_str(key, value)
    return icp.set_param(key, value)


class YatmoMap(models.AbstractModel):
    _name = "yatmo.map"
    _description = "Yatmo neighbourhood map"

    # ------------------------------------------------------------------ settings

    @api.model
    def defaults(self):
        return {
            "license_key": "",
            "country": "BE",
            "language": "auto",
            "mode": "overlay",
            "map_style": 1,
            "accent_color": "#428BFF",
            "marker": "pin",
            "circle_radius": 500,
            "zoom": 15,
            "height": "560",
            "rounded": 0,
            "isochrone": "",
            "route_from": "",
            "favorites": False,
            "text_paragraphs": list(PARAGRAPHS),
            "text_heading": "h3",
            "text_hide_street": False,
            "text_hide_city": False,
        }

    @api.model
    def config(self):
        """Site defaults: the system parameters yatmo_map.* over the defaults, validated."""
        icp = self.env["ir.config_parameter"].sudo()
        d = self.defaults()
        raw = {key: param_get(icp, "yatmo_map." + key) for key in d}

        def pick(key, allowed):
            value = (raw[key] or "").strip()
            if value == "off":
                value = ""  # the settings selections store "off", the iframe wants nothing
            return value if value in allowed else d[key]

        def clamp(key, low, high):
            return self._int_between(raw[key], low, high, d[key])

        def flag(key):
            return (raw[key] or "").strip().lower() in ("true", "1", "yes", "on")

        paragraphs = self.paragraph_list(raw["text_paragraphs"] or "")
        color = self._hex_color(raw["accent_color"] or "")
        height = self.sanitize_height(raw["height"] or "")
        return {
            "license_key": re.sub(r"[^A-Za-z0-9]", "", raw["license_key"] or ""),
            "country": pick("country", COUNTRY_CODES),
            "language": pick("language", ["auto"] + LANGUAGE_CODES),
            "mode": pick("mode", MODES),
            "map_style": clamp("map_style", 1, 7),
            "accent_color": color or d["accent_color"],
            "marker": pick("marker", ["pin", "circle"]),
            "circle_radius": clamp("circle_radius", 50, 2000),
            "zoom": clamp("zoom", 7, 20),
            "height": height or d["height"],
            "rounded": clamp("rounded", 0, 15),
            "isochrone": pick("isochrone", SIDE_MODULES),
            "route_from": pick("route_from", ROUTE_FROM),
            "favorites": flag("favorites"),
            "text_paragraphs": paragraphs or d["text_paragraphs"],
            "text_heading": pick("text_heading", HEADINGS),
            "text_hide_street": flag("text_hide_street"),
            "text_hide_city": flag("text_hide_city"),
        }

    @api.model
    def mode_labels(self):
        return {
            "overlay": _("Map + summary (summary over the map)"),
            "overlay-scores": _("Map + Yatmo scores"),
            "map-top": _("Map above the summary"),
            "map": _("Map only"),
            "summary": _("Summary only"),
            "summary-tabs": _("Summary only, in tabs"),
        }

    @api.model
    def paragraph_labels(self):
        return {
            "education": _("Education"),
            "shopping": _("Shopping"),
            "publictransports": _("Public transport"),
            "transports": _("Roads, stations and airports"),
            "tourism": _("Leisure and tourism"),
            "cities": _("Nearby cities"),
        }

    # ------------------------------------------------------------------ rendering

    @api.model
    def render_map(self, values=None):
        """HTML of the iframe (a Markup), or the editor notice, or "" for visitors."""
        try:
            return self._map_markup(self.normalize(values))
        except YatmoMapError as error:
            return self.editor_notice(str(error))

    @api.model
    def render_text(self, values=None):
        """HTML of the neighbourhood text (a Markup), or the editor notice, or "" for visitors."""
        try:
            return self._text_markup(self.normalize(values))
        except YatmoMapError as error:
            return self.editor_notice(str(error))

    @api.model
    def embed_json(self, values=None):
        """For the map block: the iframe URL and its size, or a notice for editors."""
        values = self.normalize(values)
        try:
            params = self.build_params(values)
        except YatmoMapError as error:
            return {"notice": str(error) if self.is_editor() else ""}
        return {
            "url": IFRAME_URL + "?" + urlencode(params),
            "height": self._css_height(values),
            "title": values.get("title") or _("Map and neighbourhood of the property"),
        }

    @api.model
    def text_json(self, values=None):
        """For the text block (editors only): the HTML to write in the page, or a notice."""
        try:
            return {"html": str(self._text_markup(self.normalize(values))), "notice": ""}
        except YatmoMapError as error:
            return {"html": "", "notice": str(error)}

    def _map_markup(self, values):
        params = self.build_params(values)
        src = IFRAME_URL + "?" + urlencode(params)
        title = values.get("title") or _("Map and neighbourhood of the property")
        css_class = " ".join(c for c in ["yatmo-map-embed", self._css_class(values)] if c)
        return Markup(
            '<div class="%s"><iframe src="%s" title="%s" style="display:block;width:100%%;'
            'height:%s;border:0" loading="lazy" allow="fullscreen"></iframe></div>'
        ) % (css_class, src, title, self._css_height(values))

    def _text_markup(self, values):
        context = self.context(values)
        cfg = context["settings"]
        summary = self.fetch_summary(context["country"], context["location"], cfg["license_key"])

        wanted = self.paragraph_list(values.get("paragraphs")) or cfg["text_paragraphs"]
        heading = (values.get("heading") or "").lower()
        if heading not in HEADINGS:
            heading = cfg["text_heading"]
        street = self._flag(values.get("street_in_title"), not cfg["text_hide_street"])
        city = self._flag(values.get("city_in_title"), not cfg["text_hide_city"])

        html = Markup("")
        shown = 0
        for paragraph in summary.get("Paragraphs") or []:
            icon = paragraph.get("IconId")
            if not icon or icon not in wanted:
                continue
            language = self._pick_language(paragraph.get("Title") or {}, context["language"])
            if not language:
                continue

            # First heading names the street, second the city, the others stay generic: this is
            # what reads naturally. Off for discreet listings.
            title_key = "Title"
            if shown == 0 and street and (paragraph.get("TitleBis") or {}).get(language):
                title_key = "TitleBis"
            elif shown == 1 and city and (paragraph.get("TitleTer") or {}).get(language):
                title_key = "TitleTer"

            sentences = [
                self._format_sentence(s[language])
                for s in paragraph.get("Sentences") or []
                if isinstance(s, dict) and s.get(language)
            ]
            items = [
                Markup("<li>%s</li>") % self._format_sentence(i[language])
                for i in paragraph.get("List") or []
                if isinstance(i, dict) and i.get(language)
            ]
            if not sentences and not items:
                continue

            html += Markup("<%s>%s</%s>") % (heading, paragraph[title_key][language], heading)
            if sentences:
                html += Markup("<p>%s</p>") % Markup(" ").join(sentences)
            if items:
                html += Markup("<ul>%s</ul>") % Markup("").join(items)
            shown += 1

        if not html:
            raise YatmoMapError(_("Yatmo has no text for this location with the selected paragraphs."))

        css_class = " ".join(c for c in ["yatmo-text", self._css_class(values)] if c)
        return Markup('<div class="%s">%s</div>') % (css_class, html)

    # ------------------------------------------------------------------ iframe parameters

    @api.model
    def build_params(self, values):
        """Iframe query parameters, or YatmoMapError explaining why the widget cannot be shown."""
        context = self.context(values)
        cfg = context["settings"]
        location = context["location"]

        params = {
            "licenseKey": cfg["license_key"],
            "country": context["country"],
            "language": context["language"],
            "latitude": self.format_coordinate(location["lat"]),
            "longitude": self.format_coordinate(location["lng"]),
            "mode": self._allowed(values.get("mode"), MODES, cfg["mode"]),
            "zoom": str(self._int_between(values.get("zoom"), 7, 20, cfg["zoom"])),
            "mapStyle": str(self._int_between(values.get("map_style"), 1, 7, cfg["map_style"])),
        }
        params["accentColor"] = self._hex_color(values.get("accent_color")) or cfg["accent_color"]

        marker = self._allowed(values.get("marker"), MARKERS, cfg["marker"])
        custom = (values.get("custom_marker_url") or "").strip()
        if not custom.lower().startswith("https://"):
            custom = ""
        if marker == "custom" and not custom:
            marker = "pin"
        params["marker"] = marker
        if marker == "circle":
            params["circleRadiusInMeters"] = str(
                self._int_between(values.get("circle_radius"), 50, 2000, cfg["circle_radius"]))
        elif marker == "custom":
            params["customMarkerUrl"] = custom
            params["customMarkerWidth"] = str(self._int_between(values.get("custom_marker_width"), 8, 200, 50))
            params["customMarkerHeight"] = str(self._int_between(values.get("custom_marker_height"), 8, 200, 45))

        rounded = self._int_between(values.get("rounded"), 0, 15, cfg["rounded"])
        if rounded > 0:
            params["rounded"] = "%dpx" % rounded

        isochrone = self._allowed(values.get("isochrone"), ["off", "left", "right"], cfg["isochrone"])
        if isochrone in ("left", "right"):
            params["isochrone"] = isochrone

        route_from = self._allowed(values.get("route_from"), ["off", "left", "right", "popup"], cfg["route_from"])
        if route_from in ("left", "right", "popup"):
            params["routeFrom"] = route_from

        for key, param in (("summary_background_color", "summaryBackgroundColor"),
                           ("summary_line_color", "summaryLineColor")):
            color = self._hex_color(values.get(key))
            if color:
                params[param] = color

        user_id = self._favorites_user_id(cfg)
        if user_id:
            params["userId"] = user_id

        return params

    @api.model
    def context(self, values):
        """What both blocks need before calling Yatmo: the settings, the country, the language and
        the property location. Raises YatmoMapError when something is missing."""
        cfg = self.config()
        if not cfg["license_key"]:
            raise YatmoMapError(_(
                "Enter your Yatmo licence key in Website > Configuration > Settings > Yatmo."))

        country = (values.get("country") or "").strip().upper()
        if country not in COUNTRY_CODES:
            country = cfg["country"]

        location = self._resolve_location(values, country, cfg)

        language = (values.get("language") or "").strip().upper()
        if language not in LANGUAGE_CODES:
            language = self.site_language(values.get("page_lang")) if cfg["language"] == "auto" else cfg["language"]

        return {"settings": cfg, "country": country, "language": language, "location": location}

    def _resolve_location(self, values, country, cfg):
        """Explicit coordinates first, then the address through the geocoder."""
        location = self.parse_coordinates(values.get("latitude"), values.get("longitude"))
        if not location:
            address = (values.get("address") or "").strip()
            if address:
                location = self.geocode(address, country, cfg["license_key"])
                if not location:
                    raise YatmoMapError(_(
                        'Yatmo could not find the address "%(address)s" in %(country)s. Check the '
                        "address and the country, or enter the latitude and longitude.",
                        address=address, country=country))
        if not location:
            raise YatmoMapError(_("No property location: give an address or coordinates."))
        return location

    def _favorites_user_id(self, cfg):
        """Stable per visitor and per database, not reversible to the Odoo user id."""
        if not cfg["favorites"] or not request:
            return ""
        user = request.env.user
        if not user or user._is_public():
            return ""
        secret = param_get(self.env["ir.config_parameter"].sudo(), "database.secret")
        digest = hmac.new(secret.encode(), b"yatmo-map|%d" % user.id, hashlib.sha256).hexdigest()
        return digest[:32]

    # ------------------------------------------------------------------ Yatmo calls

    @api.model
    def fetch_summary(self, country, location, license_key):
        """Summary of a location (every language of the country), from the cache or from Yatmo."""
        lat = self.format_coordinate(location["lat"])
        lng = self.format_coordinate(location["lng"])
        cache = self.env["yatmo.map.cache"]
        key = "text|" + hashlib.md5(("%s|%s|%s" % (country, lat, lng)).encode()).hexdigest()

        cached = cache.get_value(key)
        if isinstance(cached, dict) and isinstance(cached.get("Paragraphs"), list):
            return cached

        url = "https://%s.yatmo.com/Summary/text?%s" % (
            country.lower(), urlencode({"latitude": lat, "longitude": lng, "licenseKey": license_key}))
        # A never-seen location takes about two seconds to generate, a known one is instant.
        try:
            response = requests.get(url, timeout=15, headers={"User-Agent": "yatmo-map-odoo"})
        except requests.RequestException as error:
            _logger.warning("Yatmo Summary/text unreachable: %s", error)
            raise YatmoMapError(_("Yatmo could not be reached, the text will appear on a later attempt."))

        if response.status_code in (401, 403):
            raise YatmoMapError(_(
                "Your Yatmo licence does not include the neighbourhood text, or does not cover this "
                "country. Contact Yatmo."))
        if response.status_code == 400:
            raise YatmoMapError(_(
                "Yatmo refused this location: check that it lies in %(country)s, or choose the "
                "right country.", country=country))
        if response.status_code != 200:
            raise YatmoMapError(_(
                "Yatmo answered with an error (%(code)s), the text will be retried on a later "
                "attempt.", code=response.status_code))

        try:
            summary = response.json()
        except ValueError:
            summary = None
        if not isinstance(summary, dict) or not isinstance(summary.get("Paragraphs"), list):
            raise YatmoMapError(_(
                "Yatmo returned an unexpected answer, the text will be retried on a later attempt."))

        cache.set_value(key, summary, TEXT_TTL)
        return summary

    @api.model
    def geocode(self, address, country, license_key):
        """Coordinates of an address in a country ({"lat", "lng"}), or None. The geocoder only
        answers inside the requested country; results are cached, misses for an hour only."""
        address = re.sub(r"<[^>]*>", "", address or "").strip(" \t\n\r\0\x0b'\"“”")
        if not address:
            return None

        cache = self.env["yatmo.map.cache"]
        key = "geo|" + hashlib.md5(("%s|%s" % (country, address.lower())).encode()).hexdigest()
        cached = cache.get_value(key)
        if isinstance(cached, dict):
            return cached if "lat" in cached and "lng" in cached else None

        url = "https://%s.yatmo.com/Geolocation?%s" % (
            country.lower(), urlencode({"language": "EN", "address": address, "LicenseKey": license_key}))
        try:
            response = requests.get(url, timeout=5, headers={"User-Agent": "yatmo-map-odoo"})
        except requests.RequestException as error:
            _logger.warning("Yatmo Geolocation unreachable: %s", error)
            return None
        if response.status_code != 200:
            # Outage or refused key: do not remember it as "address not found".
            return None

        location = None
        try:
            coordinates = response.json()["features"][0]["geometry"]["coordinates"]
            location = self.parse_coordinates(coordinates[1], coordinates[0])
        except (ValueError, KeyError, IndexError, TypeError):
            location = None

        cache.set_value(key, location or {"miss": 1}, GEOCODE_FOUND_TTL if location else GEOCODE_MISS_TTL)
        return location

    # ------------------------------------------------------------------ helpers

    @api.model
    def normalize(self, values):
        """Accepted keys only, as trimmed strings; camelCase and data-yatmo-* names converted."""
        out = {}
        for key, value in (values or {}).items():
            if value is None or isinstance(value, (dict, list, tuple)):
                continue
            name = str(key)
            if name.startswith("yatmo") and len(name) > 5:
                name = name[5].lower() + name[6:]
            name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower().replace("-", "_")
            if name == "class":
                name = "css_class"
            if name in VALUE_KEYS:
                if isinstance(value, bool):
                    value = "1" if value else "0"
                out[name] = str(value).strip()
        return out

    @api.model
    def is_editor(self):
        """People who can edit the website see the notices; visitors get nothing."""
        return self.env.user.has_group("website.group_website_restricted_editor")

    @api.model
    def editor_notice(self, message):
        if not self.is_editor():
            return Markup("")
        return Markup(
            '<div class="yatmo-map-notice" style="padding:1em;border:1px dashed #d63638;'
            'color:#1d2327;background:#fff"><strong>%s</strong> %s <em>%s</em></div>'
        ) % (_("Yatmo:"), message, _("(Only people who can edit the website see this message.)"))

    @api.model
    def site_language(self, page_lang=None):
        """Language used when the setting is "auto": the language of the page being rendered."""
        locale = (page_lang or self.env.lang or "en").lower().replace("-", "_")
        # Yatmo calls Montenegrin CNR (it has no ISO 639-1 code).
        if locale.startswith("cnr") or locale.startswith("me_"):
            return "CNR"
        code = locale[:2].upper()
        return code if code in LANGUAGE_CODES else "EN"

    @api.model
    def parse_coordinates(self, lat, lng):
        """Valid coordinates or None. Accepts a decimal comma ("50,85")."""
        try:
            lat = float(str(lat if lat is not None else "").strip().replace(",", "."))
            lng = float(str(lng if lng is not None else "").strip().replace(",", "."))
        except ValueError:
            return None
        if abs(lat) > 90 or abs(lng) > 180 or (lat == 0.0 and lng == 0.0):
            return None
        return {"lat": lat, "lng": lng}

    @api.model
    def format_coordinate(self, value):
        """Coordinate with a dot and without locale surprises."""
        return ("%.7f" % float(value)).rstrip("0").rstrip(".")

    @api.model
    def sanitize_height(self, height):
        """Height as a number of pixels ("560") or a CSS length ("70vh"), else ""."""
        height = str(height or "").strip().lower()
        match = re.match(r"^(\d{2,4})(px)?$", height)
        if match:
            return match.group(1)
        return height if re.match(r"^\d{1,4}(\.\d+)?(vh|svh|dvh|rem|em)$", height) else ""

    @api.model
    def paragraph_list(self, value):
        """Known paragraph types from a comma-separated string or a list, in display order."""
        items = value if isinstance(value, (list, tuple)) else str(value or "").split(",")
        items = [str(item).strip().lower() for item in items]
        return [p for p in PARAGRAPHS if p in items]

    def _css_height(self, values):
        height = self.sanitize_height(values.get("height")) or self.config()["height"]
        return height + "px" if height.isdigit() else height

    @staticmethod
    def _css_class(values):
        return re.sub(r"[^A-Za-z0-9_\- ]", "", values.get("css_class") or "").strip()

    @staticmethod
    def _allowed(value, allowed, fallback):
        value = (value or "").strip().lower()
        return value if value in allowed else str(fallback)

    @staticmethod
    def _int_between(value, low, high, fallback):
        try:
            number = int(float(str(value).strip()))
        except (TypeError, ValueError):
            return int(fallback)
        return max(low, min(high, number))

    @staticmethod
    def _hex_color(value):
        value = (value or "").strip()
        return value if re.match(r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$", value) else ""

    @staticmethod
    def _flag(value, fallback):
        value = (value or "").strip().lower()
        if not value:
            return bool(fallback)
        return value in ("1", "true", "yes", "on")

    @staticmethod
    def _pick_language(titles, language):
        """Requested language when the text exists in it, else English, else the first one."""
        if not isinstance(titles, dict) or not titles:
            return ""
        for candidate in (language, "EN"):
            if titles.get(candidate):
                return candidate
        return next(iter(titles))

    @staticmethod
    def _format_sentence(sentence):
        """Escapes a sentence and turns the [STRONG] markers of Yatmo into <strong>."""
        text = str(escape(str(sentence).strip()))
        return Markup(text.replace("[STRONG]", "<strong>").replace("[/STRONG]", "</strong>"))
