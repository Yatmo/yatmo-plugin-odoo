# Yatmo Neighbourhood Map for Odoo 19.0 and 20.0 (new website builder). The version below has no
# series prefix (each Odoo adds its own); the build script (Plugins/Odoo/build-yatmo-map.ps1) writes
# "<series>.1.0.0" in each package and, for 19.0, swaps yatmo_options_register.js (20: options
# attached through website.BuilderOptions) for yatmo_options_register.js (19: builder_options resource).
{
    "name": "Yatmo Neighbourhood Map",
    "summary": "Neighbourhood map, points of interest, travel times and an indexable "
               "neighbourhood text on your property pages",
    "description": "See static/description/index.html",
    "version": "19.0.1.0.0",
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
            "yatmo_map/static/src/snippets/s_yatmo_map/yatmo_map.js",
            "yatmo_map/static/src/snippets/s_yatmo_map/000.scss",
        ],
        "website.assets_inside_builder_iframe": [
            "yatmo_map/static/src/snippets/s_yatmo_map/yatmo_map.edit.js",
        ],
        "website.website_builder_assets": [
            "yatmo_map/static/src/builder/yatmo_options.xml",
            "yatmo_map/static/src/builder/yatmo_options_plugin.js",
            "yatmo_map/static/src/builder/yatmo_options_register.js",
        ],
    },
    "images": ["static/description/banner.png"],
    "application": False,
    "installable": True,
}
