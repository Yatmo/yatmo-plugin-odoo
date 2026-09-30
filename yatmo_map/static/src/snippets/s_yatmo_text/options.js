/** @odoo-module **/
/*
 * Editor side of the Yatmo Text block: fetches the neighbourhood text from the server and writes
 * it into the section, so the saved page carries it as plain HTML (indexable). The editor notice
 * (missing key, unknown address...) is shown in the editor only and dropped on save.
 */
import options from "@web_editor/js/editor/snippets.options";
import { _t } from "@web/core/l10n/translation";

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

options.registry.YatmoText = options.Class.extend({
    /**
     * @override
     */
    start() {
        this.$target.on("yatmo_changed.yatmo_text", () => this._refreshText());
        return this._super(...arguments);
    },
    /**
     * @override
     */
    destroy() {
        this.$target.off(".yatmo_text");
        this._super(...arguments);
    },
    /**
     * @override
     */
    onBuilt() {
        this._refreshText();
    },
    /**
     * @override
     */
    cleanForSave() {
        const notice = this.$target[0].querySelector(".s_yatmo_text_notice");
        if (notice) {
            notice.remove();
        }
    },
    /**
     * @override
     */
    async selectDataAttribute(previewMode, widgetValue, params) {
        await this._super(...arguments);
        if (!previewMode) {
            await this._refreshText();
        }
    },
    /**
     * "Refresh the text" button.
     */
    async refreshText() {
        await this._refreshText();
    },

    /**
     * Writes the text (or the notice) into the section.
     */
    async _refreshText() {
        const el = this.$target[0];
        const body = el.querySelector(".s_yatmo_text_body");
        let notice = el.querySelector(".s_yatmo_text_notice");
        if (!notice) {
            notice = document.createElement("div");
            notice.className = "s_yatmo_text_notice o_not_editable d-none";
            notice.style.cssText = "padding:1em;border:1px dashed #d63638;color:#1d2327;background:#fff";
            body.parentNode.insertBefore(notice, body);
        }
        const values = {};
        for (const [key, value] of Object.entries(el.dataset)) {
            if (key.startsWith("yatmo") && value !== "") {
                values[key] = value;
            }
        }
        values.pageLang = el.ownerDocument.documentElement.lang || "";

        let result;
        try {
            result = await jsonCall("/yatmo_map/text", { values });
        } catch (error) {
            result = { html: "", notice: String(error.message || error) };
        }
        if (result.html) {
            body.innerHTML = result.html;
            el.dataset.yatmoFetched = new Date().toISOString().slice(0, 10);
        }
        notice.textContent = result.notice ? _t("Yatmo: %s", result.notice) : "";
        notice.classList.toggle("d-none", !result.notice);
    },
});

export default options.registry.YatmoText;
