// Copyright (c) 2025, WeldTrack and contributors
// For license information, please see license.txt

frappe.ui.form.on("Material Specification", {
	refresh(frm) {
		// Supersedes self-Link: never offer the record itself (multi-hop cycle
		// guard is enforced in validate → _guard_supersedes_cycle; see guide 29).
		frm.set_query("supersedes", () => ({
			filters: { name: ["!=", frm.doc.name || ""] },
		}));

		if (!frm.is_new() && frm.doc.spec_status !== "Withdrawn") {
			frm.add_custom_button(__("Withdraw"), function () {
				frappe.confirm(
					__("Are you sure you want to withdraw specification {0}?", [frm.doc.name]),
					function () {
						frm.call("withdraw").then(() => {
							frm.reload_doc();
						});
					}
				);
			}, __("Actions"));
		}
	}
});
