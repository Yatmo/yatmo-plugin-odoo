/*
 * Odoo 19: options are attached to their blocks through the builder_options resource (Odoo 20
 * does it in XML, see yatmo_options_register.xml). The build script puts this file in the 19.0
 * package in place of the XML one and updates the manifest accordingly.
 */
import { BaseOptionComponent } from "@html_builder/core/utils";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

export class YatmoMapOption extends BaseOptionComponent {
    static template = "yatmo_map.YatmoMapOption";
    static selector = ".s_yatmo_map";
}

export class YatmoTextOption extends BaseOptionComponent {
    static template = "yatmo_map.YatmoTextOption";
    static selector = ".s_yatmo_text";
}

export class YatmoOptionRegisterPlugin extends Plugin {
    static id = "yatmoOptionRegister";
    resources = {
        builder_options: [YatmoMapOption, YatmoTextOption],
    };
}

registry.category("website-plugins").add(YatmoOptionRegisterPlugin.id, YatmoOptionRegisterPlugin);
