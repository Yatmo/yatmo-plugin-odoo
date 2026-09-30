/** @odoo-module **/
/*
 * Editor side of the Yatmo blocks (Odoo 17 and 18 website builder).
 *  - YatmoLocation: address, coordinates, country and language, shared by both blocks.
 *  - YatmoMap: after any option change, restart the public widget so the preview follows.
 */
import options from "@web_editor/js/editor/snippets.options";

options.registry.YatmoLocation = options.Class.extend({
    /**
     * @override
     */
    async selectDataAttribute(previewMode, widgetValue, params) {
        await this._super(...arguments);
        if (!previewMode) {
            this.$target.trigger("yatmo_changed");
        }
    },
});

options.registry.YatmoMap = options.Class.extend({
    /**
     * @override
     */
    start() {
        this.$target.on("yatmo_changed.yatmo_map", () => this._refreshPublicWidgets());
        return this._super(...arguments);
    },
    /**
     * @override
     */
    destroy() {
        this.$target.off(".yatmo_map");
        this._super(...arguments);
    },
    /**
     * @override
     */
    onBuilt() {
        this._refreshPublicWidgets();
    },
    /**
     * @override
     */
    async selectDataAttribute(previewMode, widgetValue, params) {
        await this._super(...arguments);
        if (!previewMode) {
            await this._refreshPublicWidgets();
        }
    },
});

export default options.registry.YatmoMap;
