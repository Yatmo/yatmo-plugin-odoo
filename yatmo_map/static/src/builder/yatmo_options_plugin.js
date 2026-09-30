/*
 * Builder plugin of the Yatmo blocks (Odoo 19 and 20):
 *  - yatmoRefreshText action: fetches the neighbourhood text from the server and writes it into
 *    the Yatmo Text section, so the saved page carries it as plain HTML (indexable). Triggered by
 *    the location and text options, by the "Refresh the text" button, and when the block is dropped.
 *  - the editor notice (missing key, unknown address...) is dropped on save.
 * The Yatmo Map block needs no action: the builder restarts its interaction when an attribute changes.
 *
 * The option templates are in yatmo_options.xml; they are attached to the blocks by
 * yatmo_options_register.xml (Odoo 20) or yatmo_options_register.js (Odoo 19).
 */
import { Plugin } from "@html_editor/plugin";
import { BuilderAction } from "@html_builder/core/builder_action";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

function yatmoValues(el) {
    const values = {};
    for (const [key, value] of Object.entries(el.dataset)) {
        if (key.startsWith("yatmo") && value !== "") {
            values[key] = value;
        }
    }
    values.pageLang = el.ownerDocument.documentElement.lang || "";
    return values;
}

/**
 * Writes the text (or the notice) into the section.
 */
export async function refreshYatmoText(el) {
    const body = el.querySelector(".s_yatmo_text_body");
    if (!body) {
        return;
    }
    let notice = el.querySelector(".s_yatmo_text_notice");
    if (!notice) {
        notice = el.ownerDocument.createElement("div");
        notice.className = "s_yatmo_text_notice o_not_editable d-none";
        notice.style.cssText = "padding:1em;border:1px dashed #d63638;color:#1d2327;background:#fff";
        body.parentNode.insertBefore(notice, body);
    }
    let result;
    try {
        result = await rpc("/yatmo_map/text", { values: yatmoValues(el) });
    } catch (error) {
        result = { html: "", notice: String(error.message || error) };
    }
    if (result.html) {
        body.innerHTML = result.html;
        el.dataset.yatmoFetched = new Date().toISOString().slice(0, 10);
    }
    notice.textContent = result.notice ? _t("Yatmo: %s", result.notice) : "";
    notice.classList.toggle("d-none", !result.notice);
}

export class YatmoRefreshTextAction extends BuilderAction {
    static id = "yatmoRefreshText";

    async apply({ editingElement, isPreviewing }) {
        if (isPreviewing) {
            return;
        }
        await refreshYatmoText(editingElement);
    }
}

export class YatmoOptionPlugin extends Plugin {
    static id = "yatmoOption";

    resources = {
        builder_actions: { YatmoRefreshTextAction },
        on_snippet_dropped_handlers: ({ snippetEl }) => {
            if (snippetEl && snippetEl.matches && snippetEl.matches(".s_yatmo_text")) {
                refreshYatmoText(snippetEl);
            }
        },
        // Odoo 19 (handlers receive { root }) and Odoo 20 (processors receive and return root).
        clean_for_save_handlers: ({ root }) => this.cleanForSave(root),
        clean_for_save_processors: (root) => {
            this.cleanForSave(root);
            return root;
        },
    };

    cleanForSave(root) {
        for (const notice of root.querySelectorAll(".s_yatmo_text_notice")) {
            notice.remove();
        }
    }
}

registry.category("website-plugins").add(YatmoOptionPlugin.id, YatmoOptionPlugin);
