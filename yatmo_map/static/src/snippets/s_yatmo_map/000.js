/** @odoo-module **/
/*
 * Front end of the Yatmo Map block: asks the server for the iframe URL (settings, geocoding and
 * the licence key stay on the server) and mounts the iframe. Also runs in the editor, so the
 * preview follows the options; the iframe is removed on destroy so it is never saved in the page.
 */
import publicWidget from "@web/legacy/js/public/public_widget";

async function jsonCall(route, params) {
    const response = await fetch(route, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method: "call", id: Date.now(), params }),
    });
    const body = await response.json();
    if (body.error) {
        throw new Error(body.error.data && body.error.data.message ? body.error.data.message : body.error.message);
    }
    return body.result;
}

export function yatmoValues(el) {
    const values = {};
    for (const [key, value] of Object.entries(el.dataset)) {
        if (key.startsWith("yatmo") && value !== "") {
            values[key] = value;
        }
    }
    values.pageLang = document.documentElement.lang || "";
    return values;
}

publicWidget.registry.YatmoMap = publicWidget.Widget.extend({
    selector: ".s_yatmo_map",
    disabledInEditableMode: false,

    /**
     * @override
     */
    async start() {
        await this._super(...arguments);
        const host = this.el.querySelector(".s_yatmo_map_embed") || this.el;
        host.replaceChildren();
        let result;
        try {
            result = await jsonCall("/yatmo_map/embed", { values: yatmoValues(this.el) });
        } catch (error) {
            result = { notice: this.editableMode ? String(error.message || error) : "" };
        }
        if (this.isDestroyed()) {
            return;
        }
        if (result.url) {
            const iframe = document.createElement("iframe");
            iframe.src = result.url;
            iframe.title = result.title || "";
            iframe.loading = "lazy";
            iframe.setAttribute("allow", "fullscreen");
            iframe.style.cssText = "display:block;width:100%;height:" + result.height + ";border:0";
            host.appendChild(iframe);
        } else if (result.notice) {
            const notice = document.createElement("div");
            notice.className = "yatmo-map-notice";
            notice.textContent = "Yatmo: " + result.notice;
            host.appendChild(notice);
        }
    },

    /**
     * @override
     */
    destroy() {
        const host = this.el.querySelector(".s_yatmo_map_embed");
        if (host) {
            host.replaceChildren();
        }
        this._super(...arguments);
    },
});

export default publicWidget.registry.YatmoMap;
