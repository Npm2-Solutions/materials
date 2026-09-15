# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt

"""Material certificates for the Worgify assistant (worgify Design 36 §23).

A mill certificate arrives as a PDF. The person drops it in the chat; the model
reads it; the record gets written from it. The model reads, and here the
application checks, before a card is ever drawn:

* the certificate number is not already recorded (one of two would be forged, or
  a copy);
* each heat is known, and of the grade the certificate states;
* each chemical and mechanical result is inside the limits printed beside it —
  with the certificate's own rule (`MaterialCertificate._check_within_spec`);
* when a lot is named, the certificate covers the lot's heats and supplies a
  certificate type the lot still needs.

What stays the person's: that the certificate is verified, and the specification
limits when the certificate does not print them — marked as decisions.
"""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import flt

from worgify.agent.proposals import propose
from worgify.agent.registry import AgentRefused, agent_tool, load

AGENT_GUIDES = {
	"Material Certificate": (
		"One inspection document (EN 10204 2.2/3.1/3.2, a mill test report, a PMI report) for one or "
		"more heats. From a PDF in the chat: read it, then call check_material_certificate with what "
		"you read — it checks the number is not already recorded, the heats and their grade, every "
		"result against its printed limits, and the lot. Heats not in the system are created with "
		"create_material_heat first (heats_covered links to existing heats). Then prepare_new_record "
		"with heats_covered, chemical_results (element, value_percent, spec_min, spec_max) and "
		"mechanical_results (test_type, value, unit, spec_min, spec_max, temperature), sources with the "
		"page of every value, and attach_file with attach_field \"attachment\" so the PDF goes with the "
		"record. within_spec is computed by the record itself. Never tick verified. Spec limits the "
		"certificate does not print are not yours to supply. After it is saved, "
		"link_certificate_to_batch attaches it to a lot."
	),
	"Material Heat": (
		"A heat (cast) of steel, named by its heat number, with its grade. Certificates cover heats; "
		"lots (Batch) carry heats. Create one with create_material_heat."
	),
}

AGENT_JUDGEMENT = {
	"Material Certificate": [
		"verified", "verification_remarks", "third_party_verified",
		"chemical_results.spec_min", "chemical_results.spec_max",
		"mechanical_results.spec_min", "mechanical_results.spec_max",
	],
}

AGENT_SUGGESTIONS = {
	"Material Certificate": {"list": ["Record a certificate from a PDF I attach"]},
	"Batch": {"form": ["Is this lot's certificate complete and within spec?"]},
	"Material Heat": {"form": ["Which certificates cover this heat?"]},
}


def _options(doctype: str, fieldname: str) -> list[str]:
	df = frappe.get_meta(doctype).get_field(fieldname)
	return [o for o in (df.options or "").split("\n") if o] if df else []


def _grade_candidates(grade: str) -> list[str]:
	"""Material Grades whose name carries the same numbers and letters groups — "SA-516 Gr.70"
	finds "ASME-SA-516--70". A lead for the model, never a match it may assume."""
	tokens = [t for t in re.findall(r"[A-Za-z]*\d+[A-Za-z]*", grade or "") if t]
	if not tokens:
		return []
	pattern = "%" + "%".join(tokens) + "%"
	return frappe.get_list("Material Grade", filters={"name": ["like", pattern]}, pluck="name", limit=5)


def _result_rows(rows, value_key: str, label_key: str, label: str) -> tuple[list, list]:
	from materials.material_certifications.doctype.material_certificate.material_certificate import MaterialCertificate

	checked, findings = [], []
	for n, row in enumerate(rows or [], 1):
		if not isinstance(row, dict):
			findings.append({"severity": "block", "text": _("{0} row {1} is not an object.").format(label, n)})
			continue
		name = row.get(label_key) or row.get("element") or row.get("test_type")
		value = row.get(value_key, row.get("value"))
		spec_min, spec_max = row.get("spec_min"), row.get("spec_max")
		inverted = spec_min not in (None, "") and spec_max not in (None, "") and flt(spec_min) > flt(spec_max)
		if inverted:
			findings.append({"severity": "block", "text": _("{0} {1}: minimum {2} is above maximum {3} — misread?").format(label, name, spec_min, spec_max)})
		within = MaterialCertificate._check_within_spec(value, spec_min, spec_max) if value not in (None, "") and not inverted else None
		if within == 0:
			findings.append({"severity": "warn", "text": _("{0} {1} = {2} is outside {3} – {4}").format(
				label, name, value, spec_min if spec_min not in (None, "") else "-", spec_max if spec_max not in (None, "") else "-")})
		if spec_min in (None, "") and spec_max in (None, ""):
			findings.append({"severity": "info", "text": _("{0} {1}: no limits printed — the person supplies them, or leaves them empty").format(label, name)})
		checked.append({"name": name, "value": value, "spec_min": spec_min, "spec_max": spec_max, "within_spec": within})
	return checked, findings


@agent_tool(kind="explain")
def check_material_certificate(certificate_number: str | None = None, certificate_type: str | None = None,
							   supplier: str | None = None, issuing_body: str | None = None, grade: str | None = None,
							   heats: list | None = None, chemical: list | None = None, mechanical: list | None = None,
							   batch: str | None = None):
	"""Check what you read from a material certificate before preparing its record: duplicates, heats and grade, every result against its limits, the lot.

	Call this after reading a certificate PDF and before prepare_new_record. Pass what the
	certificate prints; the checks are the application's. Report every block and warning
	to the person.

	Args:
		certificate_number: As printed, e.g. "MTR-BW-2026-0453".
		certificate_type: One of the Conformity Certificate Types, e.g. "EN 10204 3.1".
		supplier: The Supplier record, if known.
		issuing_body: The issuer as printed (mill or laboratory).
		grade: The material grade as printed, e.g. "SA-516 Gr.70".
		heats: Heat numbers as printed: ["H-2026-0142"], or [{"heat_number": ..., "grade": ...}].
		chemical: [{"element": "C", "value_percent": 0.18, "spec_min": null, "spec_max": 0.27}].
		mechanical: [{"test_type": "Tensile Strength", "value": 485, "unit": "MPa", "spec_min": 485, "spec_max": 620}].
		batch: A lot (Batch) this certificate should cover.
	"""
	frappe.has_permission("Material Certificate", "read", throw=True)
	findings: list[dict] = []

	types = frappe.get_all("Conformity Certificate Type", pluck="name")
	if certificate_type and certificate_type not in types:
		findings.append({"severity": "block", "text": _("Certificate type {0} is not one of: {1}").format(certificate_type, ", ".join(types))})

	if certificate_number:
		filters = {"certificate_number": certificate_number}
		same = frappe.get_list("Material Certificate", filters=filters, fields=["name", "issuing_body", "supplier"], limit=5)
		for s in same:
			same_issuer = not (issuing_body or supplier) or s.issuing_body == issuing_body or s.supplier == supplier
			findings.append({
				"severity": "block" if same_issuer else "warn",
				"text": _("Certificate number {0} is already recorded as {1}{2}").format(
					certificate_number, s.name, "" if same_issuer else _(" from another issuer — one of the two may be forged")),
			})

	grade_known = bool(grade and frappe.db.exists("Material Grade", grade))
	candidates = [] if grade_known or not grade else _grade_candidates(grade)
	if grade and not grade_known:
		findings.append({"severity": "info", "text": _("Grade {0} as printed is not a Material Grade name; candidates: {1}").format(
			grade, ", ".join(candidates) or _("none found"))})

	heat_rows = []
	for item in heats or []:
		number = item.get("heat_number") if isinstance(item, dict) else item
		printed_grade = (item.get("grade") if isinstance(item, dict) else None) or grade
		number = str(number or "").strip()
		if not number:
			continue
		existing = frappe.db.get_value("Material Heat", number, ["name", "grade", "status"], as_dict=True)
		row = {"heat_number": number, "exists": bool(existing)}
		if not existing:
			findings.append({"severity": "warn", "text": _("Heat {0} is not in the system: create it with create_material_heat before the certificate").format(number)})
		else:
			row.update({"grade": existing.grade, "status": existing.status})
			if printed_grade and existing.grade and printed_grade != existing.grade and existing.grade not in (candidates or [printed_grade]):
				findings.append({"severity": "block", "text": _("Heat {0} is recorded as grade {1}; the certificate says {2}").format(number, existing.grade, printed_grade)})
			covering = frappe.get_all("Material Heat Coverage", filters={"heat": existing.name, "parenttype": "Material Certificate"}, pluck="parent")
			if covering:
				row["already_covered_by"] = covering
		heat_rows.append(row)

	chem, chem_findings = _result_rows(chemical, "value_percent", "element", _("Chemical"))
	mech, mech_findings = _result_rows(mechanical, "value", "test_type", _("Mechanical"))
	findings += chem_findings + mech_findings
	elements = _options("Certificate Chemical Result", "element")
	tests = _options("Certificate Mechanical Result", "test_type")
	for r in chem:
		if r["name"] and r["name"] not in elements:
			findings.append({"severity": "info", "text": _("Element {0} is not in the list: use element \"Other\" with element_other").format(r["name"])})
	for r in mech:
		if r["name"] and r["name"] not in tests:
			findings.append({"severity": "info", "text": _("Test {0} is not in the list ({1}): use \"Other\" with test_type_other").format(r["name"], ", ".join(tests))})

	lot = None
	if batch:
		b = load("Batch", batch, "read")
		from materials.material_certifications.doctype.material_certificate.material_certificate import _batch_heat_names

		lot_heats = _batch_heat_names(b)
		cert_heats = {h["heat_number"] for h in heat_rows}
		match = "exact" if lot_heats and lot_heats <= cert_heats else "partial" if lot_heats & cert_heats else "none"
		lot = {"batch": batch, "item": b.item, "lot_heats": sorted(lot_heats), "match": match}
		if match == "none":
			findings.append({"severity": "block", "text": _("The certificate covers none of lot {0}'s heats ({1})").format(batch, ", ".join(sorted(lot_heats)) or "—")})
		elif match == "partial":
			findings.append({"severity": "warn", "text": _("The certificate covers only some of lot {0}'s heats").format(batch)})
		if "stock" in frappe.get_installed_apps():
			from stock.certificates import missing_types

			missing = missing_types(batch, b.item, b.get("project"))
			lot["missing_certificate_types"] = missing
			if missing and certificate_type and certificate_type not in missing:
				findings.append({"severity": "warn", "text": _("Lot {0} still needs {1}; this certificate is {2}").format(batch, ", ".join(missing), certificate_type)})

	order = {"block": 0, "warn": 1, "info": 2}
	findings.sort(key=lambda f: order.get(f["severity"], 3))
	return {
		"findings": findings,
		"blocking": sum(1 for f in findings if f["severity"] == "block"),
		"heats": heat_rows,
		"chemical": chem,
		"mechanical": mech,
		"grade_candidates": candidates,
		"lot": lot,
		"decided_by": "materials certificate checks (MaterialCertificate._check_within_spec, heat and lot registers)",
	}


@agent_tool(kind="act", doctype="Material Heat", action="insert", reversible=True)
def create_material_heat(heat_number: str, grade: str, mill: str | None = None, cast_number: str | None = None):
	"""Propose creating a Material Heat a certificate covers — the heat number as printed and its grade.

	Call this when check_material_certificate says a heat is not in the system.

	Args:
		heat_number: As printed on the certificate.
		grade: The Material Grade record, e.g. "ASME-SA-516--70" (see grade_candidates).
		mill: The Supplier that melted it, if it is recorded.
		cast_number: The cast number, if printed separately.
	"""
	heat_number = (heat_number or "").strip()
	if not heat_number:
		raise AgentRefused(_("Give the heat number."))
	if frappe.db.exists("Material Heat", heat_number):
		raise AgentRefused(_("Heat {0} already exists.").format(heat_number))
	if not frappe.db.exists("Material Grade", grade):
		raise AgentRefused(_("{0} is not a Material Grade. Candidates: {1}").format(grade, ", ".join(_grade_candidates(grade)) or "—"))
	if mill and not frappe.db.exists("Supplier", mill):
		raise AgentRefused(_("Supplier {0} does not exist.").format(mill))
	frappe.has_permission("Material Heat", "create", throw=True)

	def run():
		doc = frappe.get_doc({"doctype": "Material Heat", "heat_number": heat_number, "grade": grade,
							  "mill": mill, "cast_number": cast_number, "status": "Active"})
		doc.insert()
		return {"message": _("Heat {0} created").format(doc.name), "name": doc.name}

	return propose(
		_("Create heat {0}, grade {1}").format(heat_number, grade),
		run,
		doctype="Material Heat",
		details=[_("Mill: {0}").format(mill) if mill else _("Mill not recorded")] + ([_("Cast: {0}").format(cast_number)] if cast_number else []),
		reversible=True,
	)


@agent_tool(kind="act", doctype="Batch", action="auto_link_certificate", reversible=True)
def link_certificate_to_batch(batch: str, certificate: str):
	"""Propose linking a saved Material Certificate to a lot (Batch) — the link lives on the lot.

	Args:
		batch: The Batch name.
		certificate: The Material Certificate name, e.g. "MCERT-2026-00017".
	"""
	from materials.material_certifications.doctype.material_certificate.material_certificate import auto_link_certificate

	b = load("Batch", batch, "write")
	cert = load("Material Certificate", certificate, "read")
	if certificate in {r.certificate for r in b.get("certificates") or []}:
		raise AgentRefused(_("{0} is already linked to {1}.").format(certificate, batch))
	return propose(
		_("Link certificate {0} ({1}) to lot {2}").format(certificate, cert.certificate_type, batch),
		lambda: auto_link_certificate(batch, certificate) | {"name": batch},
		doctype="Batch",
		name=batch,
		details=[_("Certificate number: {0}").format(cert.certificate_number)],
		reversible=True,
	)
