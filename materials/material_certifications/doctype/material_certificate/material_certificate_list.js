// Copyright (c) 2026, NPM2 Solutions Srl and contributors
// For license information, please see license.txt

frappe.listview_settings["Material Certificate"] = {
	add_fields: ["status", "verified"],

	get_indicator: function(doc) {
		const indicators = {
			"Valid": ["Valid", "green", "status,=,Valid"],
			"Expired": ["Expired", "red", "status,=,Expired"],
			"Revoked": ["Revoked", "grey", "status,=,Revoked"],
		};
		return indicators[doc.status] || ["Unknown", "grey"];
	},

	formatters: {
		status: function(value) {
			const colors = {
				"Valid": "green",
				"Expired": "red",
				"Revoked": "grey",
			};
			let color = colors[value] || "grey";
			return `<span class="indicator-pill ${color}">${__(value)}</span>`;
		}
	}
};
