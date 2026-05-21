// Copyright (c) 2025, WeldTrack and contributors
// For license information, please see license.txt

frappe.ui.form.on("Base Material Specification", {
	refresh(frm) {
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
