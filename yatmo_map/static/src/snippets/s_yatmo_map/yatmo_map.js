/*
 * Front end of the Yatmo Map block (Odoo 19 and 20 interactions): asks the server for the iframe
 * URL (settings, geocoding and the licence key stay on the server) and mounts the iframe. The edit
 * variant (yatmo_map.edit.js) runs the same code in the builder; the builder restarts it whenever
 * a data-yatmo-* attribute changes, and everything inserted is removed on destroy, so nothing
 * generated is ever saved in the page.
 */
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export function yatmoValues(el) {
    const values = {};
    for (const [key, value] of Object.entries(el.dataset)) {
        if (key.startsWith("yatmo") && value !== "") {
            values[key] = value;
        }
    }
    values.pageLang = el.ownerDocument.documentElement.lang || "";
    return values;
}

export class YatmoMap extends Interaction {
    static selector = ".s_yatmo_map";

    setup() {
        this.editMode = false;
        this.result = {};
    }

    async willStart() {
        try {
            this.result = await this.waitFor(rpc("/yatmo_map/embed", { values: yatmoValues(this.el) }));
        } catch (error) {
            this.result = { notice: this.editMode ? String(error.message || error) : "" };
        }
    }

    start() {
        const host = this.el.querySelector(".s_yatmo_map_embed") || this.el;
        if (this.result.url) {
            const iframe = document.createElement("iframe");
            iframe.src = this.result.url;
            iframe.title = this.result.title || "";
            iframe.loading = "lazy";
            iframe.setAttribute("allow", "fullscreen");
            iframe.style.cssText = "display:block;width:100%;height:" + this.result.height + ";border:0";
            this.insert(iframe, host);
        } else if (this.result.notice) {
            const notice = document.createElement("div");
            notice.className = "yatmo-map-notice";
            notice.textContent = "Yatmo: " + this.result.notice;
            this.insert(notice, host);
        }
    }
}

registry.category("public.interactions").add("yatmo_map.map", YatmoMap);
