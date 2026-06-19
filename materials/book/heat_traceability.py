"""
MRB section: Material & Heat Traceability matrix.

One row per heat used in scope, mapped to its mill certificate(s). Flags heats
with no certificate (error) and Recalled heats (error) — the auditor's proof
that every heat used traces to a valid EN 10204 certificate.
"""

from __future__ import annotations

import frappe

from materials.book._common import badge, empty_section, esc, fmtdate, section_title
from materials.book.scope import heats_in_scope

_HEAT_STATUS_SEV = {
	"Active": "success",
	"Released": "success",
	"Quarantined": "warning",
	"Recalled": "danger",
}


def build(book, scope, section_row=None) -> dict:
	heat_names = heats_in_scope(scope)
	if not heat_names:
		return empty_section("No material heats traced to this scope.")

	heats = frappe.get_all(
		"Material Heat",
		filters={"name": ["in", heat_names]},
		fields=["name", "heat_number", "cast_number", "mill", "grade", "production_date", "status"],
		order_by="grade asc, heat_number asc",
	)

	coverage = frappe.get_all(
		"Material Heat Coverage",
		filters={"heat": ["in", heat_names], "parenttype": "Material Certificate"},
		fields=["heat", "parent"],
	)
	cert_names = sorted({c.parent for c in coverage if c.parent})
	cert_meta = {
		c.name: c
		for c in frappe.get_all(
			"Material Certificate",
			filters={"name": ["in", cert_names or [""]]},
			fields=["name", "certificate_number", "certificate_type", "status"],
		)
	}
	heat_certs: dict[str, list[str]] = {}
	for c in coverage:
		heat_certs.setdefault(c.heat, []).append(c.parent)

	rows_html = []
	n_with_cert = 0
	recalled = []
	for h in heats:
		certs = heat_certs.get(h.name, [])
		if certs:
			n_with_cert += 1
		if h.status == "Recalled":
			recalled.append(h.heat_number or h.name)
		cert_cell = (
			"<br>".join(
				f"{esc(cert_meta[cn].certificate_number or cn)} "
				f"<span class='text-muted'>({esc(cert_meta[cn].certificate_type or '')})</span>"
				for cn in certs
				if cn in cert_meta
			)
			or badge("MISSING", "danger")
		)
		status_cell = badge(h.status, _HEAT_STATUS_SEV.get(h.status, "muted")) if h.status else "—"
		rows_html.append(
			"<tr>"
			f"<td><strong>{esc(h.heat_number or h.name)}</strong></td>"
			f"<td>{esc(h.grade)}</td>"
			f"<td>{esc(h.mill)}</td>"
			f"<td>{esc(fmtdate(h.production_date))}</td>"
			f"<td>{status_cell}</td>"
			f"<td>{cert_cell}</td>"
			"</tr>"
		)

	missing = len(heats) - n_with_cert
	subtitle = f"{len(heats)} heat(s) · {n_with_cert} certified · {missing} missing certificate"
	html = (
		section_title("Material & Heat Traceability", subtitle)
		+ "<table class='table table-bordered mrb-tight'><thead><tr>"
		+ "<th>Heat No.</th><th>Grade</th><th>Mill</th><th>Prod. Date</th><th>Status</th><th>Certificate(s)</th>"
		+ "</tr></thead><tbody>"
		+ "".join(rows_html)
		+ "</tbody></table>"
	)

	warnings = []
	if missing:
		warnings.append(
			{
				"severity": "warning",
				"code": "heats-missing-cert",
				"message": f"{missing} heat(s) in scope have no material certificate.",
			}
		)
	if recalled:
		warnings.append(
			{
				"severity": "error",
				"code": "recalled-heat",
				"message": "Recalled heat(s) in scope: " + ", ".join(recalled),
			}
		)

	return {
		"html": html,
		"metadata": {
			"empty": False,
			"warnings": warnings,
			"snapshot": {"heats": [dict(h) for h in heats], "heat_certs": heat_certs},
			"builder_version": "1.0",
			"estimated_pages": max(1, len(heats) // 30 + 1),
		},
	}
