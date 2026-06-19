"""
MRB section: Material Certificates (EN 10204 3.1).

Embeds the full certificate for every material heat in scope: header facts,
chemical composition, and mechanical properties, each value flagged in/out of
spec. This is the dossier's documentary material evidence.
"""

from __future__ import annotations

import frappe

from materials.book._common import badge, empty_section, esc, fmtdate, section_title
from materials.book.scope import all_certs, certs_for_heats, heats_in_scope

_VAL_SEV = {"Validated": "success", "Rejected": "danger", "Conditional": "warning", "Pending Review": "muted"}
_STATUS_SEV = {"Valid": "success", "Expired": "warning", "Revoked": "danger"}


def build(book, scope, section_row=None) -> dict:
	if scope.scope_type == "Organization":
		cert_names = all_certs()
	else:
		cert_names = certs_for_heats(heats_in_scope(scope))

	if not cert_names:
		return empty_section("No material certificates traced to this scope.")

	blocks = [_cert_block(frappe.get_doc("Material Certificate", cn)) for cn in cert_names]
	html = (
		section_title("Material Certificates", f"{len(cert_names)} certificate(s) — EN 10204 traceability")
		+ "".join(blocks)
	)
	return {
		"html": html,
		"metadata": {
			"empty": False,
			"warnings": [],
			"snapshot": {"certificates": cert_names},
			"builder_version": "1.0",
			"estimated_pages": max(1, len(cert_names)),
		},
	}


def _facts(doc) -> str:
	facts = [
		("Certificate No.", doc.certificate_number),
		("Type", doc.certificate_type),
		("Date", fmtdate(doc.certificate_date)),
		("Supplier", doc.supplier),
		("Issuing Body", doc.issuing_body),
		("Applicable Standard", doc.applicable_standard),
	]
	cells = "".join(
		f"<div style='min-width:160px'><label class='text-muted' style='display:block;font-size:11px'>{esc(label)}</label>"
		f"<div>{esc(value) or '—'}</div></div>"
		for label, value in facts
	)
	return f"<div style='display:flex;flex-wrap:wrap;gap:6px 28px;margin:6px 0 10px'>{cells}</div>"


def _chemical(doc) -> str:
	if not doc.chemical_results:
		return ""
	rows = "".join(
		"<tr>"
		f"<td>{esc(r.element_other if r.element == 'Other' else r.element)}</td>"
		f"<td class='text-right'>{esc(r.value_percent)}</td>"
		f"<td class='text-right'>{esc(r.spec_min)}</td>"
		f"<td class='text-right'>{esc(r.spec_max)}</td>"
		f"<td>{badge('OK', 'success') if r.within_spec else badge('OUT', 'danger')}</td>"
		"</tr>"
		for r in doc.chemical_results
	)
	return (
		"<div class='section-label'><strong>Chemical Composition (%)</strong></div>"
		"<table class='table table-bordered mrb-tight'><thead><tr>"
		"<th>Element</th><th>Value</th><th>Min</th><th>Max</th><th>Spec</th>"
		f"</tr></thead><tbody>{rows}</tbody></table>"
	)


def _mechanical(doc) -> str:
	if not doc.mechanical_results:
		return ""
	rows = "".join(
		"<tr>"
		f"<td>{esc(r.test_type_other if r.test_type == 'Other' else r.test_type)}</td>"
		f"<td class='text-right'>{esc(r.value)} {esc(r.unit)}</td>"
		f"<td class='text-right'>{esc(r.spec_min)}</td>"
		f"<td class='text-right'>{esc(r.spec_max)}</td>"
		f"<td>{esc(r.temperature) or '—'}</td>"
		f"<td>{badge('OK', 'success') if r.within_spec else badge('OUT', 'danger')}</td>"
		"</tr>"
		for r in doc.mechanical_results
	)
	return (
		"<div class='section-label'><strong>Mechanical Properties</strong></div>"
		"<table class='table table-bordered mrb-tight'><thead><tr>"
		"<th>Test</th><th>Value</th><th>Min</th><th>Max</th><th>Temp</th><th>Spec</th>"
		f"</tr></thead><tbody>{rows}</tbody></table>"
	)


def _cert_block(doc) -> str:
	status = badge(doc.status, _STATUS_SEV.get(doc.status, "muted")) if doc.status else ""
	val = badge(doc.validation_status, _VAL_SEV.get(doc.validation_status, "muted")) if doc.validation_status else ""
	tpv = badge("3rd-party verified", "success") if doc.third_party_verified else ""
	heats = ", ".join(esc(h.heat) for h in (doc.heats_covered or [])) or "—"
	return (
		"<div style='margin-bottom:18px;padding-bottom:12px;border-bottom:1px solid #ddd'>"
		f"<h3 style='margin:0 0 2px'>{esc(doc.certificate_number or doc.name)} {status} {val} {tpv}</h3>"
		f"<div class='text-muted' style='margin-bottom:4px'>Heats covered: {heats}</div>"
		f"{_facts(doc)}{_chemical(doc)}{_mechanical(doc)}"
		"</div>"
	)
