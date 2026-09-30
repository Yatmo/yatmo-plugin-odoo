# Yatmo Neighbourhood Map for Odoo. Odoo 17.0 and 18.0 share this code: the version below has no
# series prefix (each Odoo adds its own), the build script (Plugins/Odoo/build-yatmo-map.ps1)
# writes "<series>.1.0.0" in each package.
{
    "name": "Yatmo Neighbourhood Map",
    "summary": "Neighbourhood map, points of interest, travel times and an indexable "
               "neighbourhood text on your property pages",
    "description": "See static/description/index.html",
    "version": "17.0.1.0.0",
    "category": "Website/Website",
    "author": "Yatmo SRL",
    "website": "https://yatmo.com",
    "support": "support@yatmo.com",
    "license": "LGPL-3",
    "depends": ["website"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/res_config_settings_views.xml",
        "views/templates.xml",
        "views/snippets.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "yatmo_map/static/src/snippets/s_yatmo_map/000.js",
            "yatmo_map/static/src/snippets/s_yatmo_map/000.scss",
        ],
        "website.assets_wysiwyg": [
            "yatmo_map/static/src/snippets/s_yatmo_map/options.js",
            "yatmo_map/static/src/snippets/s_yatmo_text/options.js",
        ],
    },
    "images": ["static/description/banner.png"],
    "application": False,
    "installable": True,
}
