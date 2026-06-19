"""
Resolve which Material Heats / Certificates fall within a book's scope.

Material Certificate and Material Heat have no `project` field (they are a
shared catalogue). The link to a project is structural:

  Project ─▶ Assembly Part.project  ─▶ Assembly Part.heat_number ─▶ Material Heat
  Project ─▶ Batch.project          ─▶ Batch.heat_number         ─▶ Material Heat
  Material Heat ◀─ Material Heat Coverage.heat ◀─ Material Certificate

So: heats used in scope = parts' + batches' heats; certs = the certificates
whose `heats_covered` table references any of those heats.
"""

from __future__ import annotations

import frappe


def _has(doctype: str) -> bool:
	return bool(frappe.db.exists("DocType", doctype))


def _part_filters(scope):
	"""Filters for Assembly Part rows in scope, or None when not applicable."""
	if scope.scope_type == "Organization":
		return {}
	if scope.scope_type == "Project" and scope.project:
		return {"project": scope.project}
	if scope.scope_type == "Assembly" and scope.assembly:
		return {"assembly": scope.assembly}
	if scope.is_joint_scope() and scope.joint_names and _has("Assembly Joint"):
		assemblies = sorted(
			{
				a
				for a in frappe.get_all(
					"Assembly Joint", filters={"name": ["in", scope.joint_names]}, pluck="assembly"
				)
				if a
			}
		)
		return {"assembly": ["in", assemblies]} if assemblies else None
	return None


def heats_in_scope(scope) -> list[str]:
	"""Material Heat names used within the book's scope."""
	heats: set[str] = set()

	part_filters = _part_filters(scope)
	if part_filters is not None and _has("Assembly Part"):
		for row in frappe.get_all("Assembly Part", filters=part_filters, fields=["heat_number"]):
			if row.heat_number:
				heats.add(row.heat_number)

	# Stock batches received against the project carry their own heat link.
	if scope.project and _has("Batch"):
		for row in frappe.get_all("Batch", filters={"project": scope.project}, fields=["heat_number"]):
			if row.heat_number:
				heats.add(row.heat_number)

	return sorted(heats)


def certs_for_heats(heat_names: list[str]) -> list[str]:
	"""Material Certificate names whose heats_covered references any heat."""
	if not heat_names:
		return []
	rows = frappe.get_all(
		"Material Heat Coverage",
		filters={"heat": ["in", heat_names], "parenttype": "Material Certificate"},
		fields=["parent"],
	)
	return sorted({r.parent for r in rows if r.parent})


def all_certs() -> list[str]:
	"""Every Material Certificate (used for Organization scope)."""
	return frappe.get_all("Material Certificate", pluck="name", order_by="certificate_date asc")
