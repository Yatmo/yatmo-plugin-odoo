/*
 * The Yatmo Map interaction inside the website builder: same behaviour, plus the server error
 * text when the call fails (editors see it, visitors never do).
 */
import { registry } from "@web/core/registry";
import { YatmoMap } from "./yatmo_map";

const YatmoMapEdit = (I) =>
    class extends I {
        setup() {
            super.setup();
            this.editMode = true;
        }
    };

registry.category("public.interactions.edit").add("yatmo_map.map", {
    Interaction: YatmoMap,
    mixin: YatmoMapEdit,
});
