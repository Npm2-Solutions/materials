# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""Stainless kept apart from carbon steel (Design 55 MA-11): a warehouse location
may declare that it keeps only stainless steel, or only carbon and low-alloy
steel; a movement or a receipt that would put the other kind there is refused,
with the reason. Iron picked up from carbon steel spoils a stainless surface —
the separation is a rule of the shop, not a preference.

The family of a line is its metal's: the lot's heat's grade, its standard's
category (``Material Specification.material_category``). A line whose metal is
not known is not refused — nothing is guessed.
"""

from __future__ import annotations

import frappe
from frappe import _

STAINLESS_ONLY = "Stainless steel only"
CARBON_ONLY = "Carbon and low-alloy steel only"
STAINLESS = ("Stainless Steel", "Duplex Stainless Steel", "Super Duplex Stainless Steel")


def family_of(item_code=None, lot=None):
	"""'stainless', 'carbon' or None."""
	grade = None
	if lot:
		heat = frappe.db.get_value("Batch", lot, "heat_number")
		grade = frappe.db.get_value("Material Heat", heat, "grade") if heat else None
	if not grade and item_code:
		text = frappe.db.get_value("Item", item_code, "material_grade")
		if text:
			grade = frappe.db.get_value("Material Grade", {"display_name": text}) or frappe.db.get_value(
				"Material Grade", {"grade": text.split(" +")[0].strip()})
	if not grade:
		return None
	spec = frappe.db.get_value("Material Grade", grade, "specification")
	category = frappe.db.get_value("Material Specification", spec, "material_category") if spec else None
	if not category:
		return None
	return "stainless" if category in STAINLESS or "Stainless" in category else "carbon"


def refusal(warehouse, item_code, lot, row_label):
	if not warehouse or not frappe.get_meta("Warehouse").has_field("steel_kept"):
		return None
	kept = frappe.db.get_value("Warehouse", warehouse, "steel_kept")
	if not kept:
		return None
	family = family_of(item_code, lot)
	if kept == STAINLESS_ONLY and family == "carbon":
		return _("{0}: {1} keeps only stainless steel, and {2} is carbon steel. Carbon steel next to stainless leaves iron on its surface.").format(
			row_label, warehouse, lot or item_code)
	if kept == CARBON_ONLY and family == "stainless":
		return _("{0}: {1} keeps only carbon and low-alloy steel; {2} is stainless and goes to a stainless area.").format(
			row_label, warehouse, lot or item_code)
	return None


def check_stock_entry(doc, method=None):
	errors = [refusal(r.t_warehouse, r.item_code, r.batch_no, _("Row {0}").format(r.idx)) for r in doc.get("items") or []
			  if r.get("t_warehouse")]
	errors = [e for e in errors if e]
	if errors:
		frappe.throw("<br>".join(errors), title=_("Stainless and carbon steel are kept apart"))


def check_goods_receipt(doc, method=None):
	errors = []
	for r in doc.get("items") or []:
		wh = r.get("warehouse") or doc.get("warehouse")
		lot = r.get("created_batch")
		heat_grade = None
		if not lot and r.get("heat_number"):
			heat_grade = frappe.db.get_value("Material Heat", r.heat_number, "grade")
		msg = refusal(wh, r.item_code, lot, _("Row {0}").format(r.idx)) if not heat_grade else _refusal_by_grade(wh, heat_grade, r)
		if msg:
			errors.append(msg)
	if errors:
		frappe.throw("<br>".join(errors), title=_("Stainless and carbon steel are kept apart"))


def _refusal_by_grade(warehouse, grade, r):
	if not warehouse or not frappe.get_meta("Warehouse").has_field("steel_kept"):
		return None
	kept = frappe.db.get_value("Warehouse", warehouse, "steel_kept")
	spec = frappe.db.get_value("Material Grade", grade, "specification")
	category = frappe.db.get_value("Material Specification", spec, "material_category") if spec else None
	if not kept or not category:
		return None
	family = "stainless" if "Stainless" in category else "carbon"
	if (kept == STAINLESS_ONLY and family == "carbon") or (kept == CARBON_ONLY and family == "stainless"):
		return refusal(warehouse, r.item_code, None, _("Row {0}").format(r.idx)) or _(
			"Row {0}: {1} keeps {2}; heat {3} is not.").format(r.idx, warehouse, _(kept).lower(), r.heat_number)
	return None
