// Copyright (c) 2026, NPM2 Solutions Srl and contributors
// For license information, please see license.txt

frappe.ui.form.on("Material Certificate", {
	refresh: function(frm) {
		// Status indicator colors
		if (frm.doc.status) {
			let color = {
				"Valid": "green",
				"Expired": "red",
				"Revoked": "darkgrey"
			}[frm.doc.status] || "blue";

			if (frm.page && frm.page.set_indicator) {
				frm.page.set_indicator(frm.doc.status, color);
			}
		}

		// Action buttons
		if (!frm.is_new() && frm.add_custom_button) {
			if (frm.doc.status !== "Revoked") {
				frm.add_custom_button(__("Revoke"), () => {
					frappe.confirm(
						__("Are you sure you want to revoke this certificate? This cannot be undone."),
						() => {
							frm.call("revoke").then(() => {
								frm.reload_doc();
							});
						}
					);
				}, __("Actions"));
			}
			if (frm.doc.validation_status !== "Rejected") {
				frm.add_custom_button(__("Reject"), () => {
					frappe.confirm(
						__("Are you sure you want to reject this certificate?"),
						() => {
							frm.call("reject").then(() => {
								frm.reload_doc();
							});
						}
					);
				}, __("Actions"));
			}
		}

		// Extract from PDF button
		if (frm.doc.attachment && !frm.is_new()) {
			frappe.xcall(
				"frappe.client.get_value",
				{ doctype: "Stock Settings", fieldname: "enable_certificate_extraction" }
			).then(function(r) {
				if (r && r.enable_certificate_extraction) {
					frm.add_custom_button(__("Extract from PDF"), function() {
						extract_certificate_data(frm);
					});
				}
			});
		}

		// Find Matching Batches button
		if (frm.doc.heat_numbers_covered && !frm.is_new()) {
			frm.add_custom_button(__("Find Matching Batches"), function() {
				find_matching_batches(frm);
			});
		}
	},

	setup: function(frm) {
		if (frm.set_query) {
			frm.set_query("batch", function() {
				return {};
			});

			frm.set_query("issuing_organization", function() {
				return {};
			});

			frm.set_query("applicable_standard", function() {
				return {};
			});
		}
	},

	batch: function(frm) {
		if (frm.doc.batch) {
			frappe.db.get_value("Batch", frm.doc.batch, "item").then(r => {
				if (r.message) {
					frm.set_value("item_code", r.message.item);
				}
			});
		} else {
			frm.set_value("item_code", "");
		}
	},

	verified: function(frm) {
		if (frm.doc.verified) {
			frm.set_value("verified_by", frappe.session.user);
			frm.set_value("verification_date", frappe.datetime.nowdate());
		}
	}
});


function extract_certificate_data(frm) {
	frappe.call({
		method: "materials.materials.material_certifications.doctype.material_certificate.material_certificate.extract_certificate_data",
		args: { certificate_name: frm.doc.name },
		freeze: true,
		freeze_message: __("Extracting data from PDF..."),
		callback: function(r) {
			if (!r.message) return;
			let data = r.message;

			let fields = [];
			if (data.heat_numbers && data.heat_numbers.length) {
				fields.push({
					fieldname: "heat_numbers",
					fieldtype: "Small Text",
					label: __("Heat Numbers Found"),
					default: data.heat_numbers.join("\n"),
				});
			}
			if (data.chemical && data.chemical.length) {
				fields.push({
					fieldname: "chemical_html",
					fieldtype: "HTML",
					options: "<b>" + __("Chemical Composition") + "</b><br>" +
						data.chemical.map(c =>
							`${c.element}: ${c.value_percent}% (confidence: ${c.confidence}%)`
						).join("<br>"),
				});
			}
			if (data.mechanical && data.mechanical.length) {
				fields.push({
					fieldname: "mechanical_html",
					fieldtype: "HTML",
					options: "<b>" + __("Mechanical Properties") + "</b><br>" +
						data.mechanical.map(m =>
							`${m.test_type}: ${m.value} ${m.unit || ''} (confidence: ${m.confidence}%)`
						).join("<br>"),
				});
			}

			if (!fields.length) {
				frappe.msgprint(__("No data could be extracted from the PDF."));
				return;
			}

			let d = new frappe.ui.Dialog({
				title: __("Review Extracted Data"),
				fields: fields,
				size: "large",
				primary_action_label: __("Apply"),
				primary_action() {
					// Apply heat numbers
					if (data.heat_numbers && data.heat_numbers.length) {
						let heat_val = d.get_value("heat_numbers");
						frm.set_value("heat_numbers_covered", heat_val);
					}
					// Apply chemical results
					if (data.chemical && data.chemical.length) {
						data.chemical.forEach(c => {
							let row = frm.add_child("chemical_results");
							row.element = c.element;
							row.value_percent = c.value_percent;
						});
					}
					// Apply mechanical results
					if (data.mechanical && data.mechanical.length) {
						data.mechanical.forEach(m => {
							let row = frm.add_child("mechanical_results");
							row.test_type = m.test_type;
							row.value = m.value;
							row.unit = m.unit || "";
						});
					}
					frm.refresh_fields();
					frm.dirty();
					d.hide();
					frappe.show_alert({ message: __("Data applied. Review and save."), indicator: "green" });
				}
			});
			d.show();
		}
	});
}


function find_matching_batches(frm) {
	// Parse heat numbers from this certificate
	let heats = (frm.doc.heat_numbers_covered || "").split("\n").filter(h => h.trim());
	if (!heats.length) {
		frappe.msgprint(__("No heat numbers to search for."));
		return;
	}

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Batch",
			or_filters: heats.map(h => ({ heat_number: h.trim() })),
			fields: ["name", "batch_id", "item", "heat_number", "lot_status"],
			limit_page_length: 20,
		},
		callback: function(r) {
			if (!r.message || !r.message.length) {
				frappe.msgprint(__("No matching batches found."));
				return;
			}

			let d = new frappe.ui.Dialog({
				title: __("Matching Batches"),
				fields: [{
					fieldname: "batches_html",
					fieldtype: "HTML",
					options: r.message.map(b =>
						`<div class="mb-2">
							<a href="/app/batch/${b.name}">${b.batch_id || b.name}</a>
							— ${b.item} — Heat: ${b.heat_number || ''} — ${b.lot_status}
							<button class="btn btn-xs btn-primary ml-2 link-batch-btn"
								data-batch="${b.name}">${__("Link")}</button>
						</div>`
					).join(""),
				}],
			});

			d.$wrapper.on("click", ".link-batch-btn", function() {
				let batch_no = $(this).data("batch");
				frappe.xcall(
					"materials.materials.material_certifications.doctype.material_certificate.material_certificate.auto_link_certificate",
					{ batch_no: batch_no, certificate_name: frm.doc.name }
				).then(function() {
					frappe.show_alert({ message: __("Linked to batch {0}", [batch_no]), indicator: "green" });
					frm.reload_doc();
				});
			});

			d.show();
		}
	});
}
