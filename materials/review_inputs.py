# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""The suppliers in the management review (Design 55 QU-03): the heats recalled
in the period, by the mill that made them — and the proposal to requalify a
mill whose heat was recalled."""

from __future__ import annotations

import frappe
from frappe import _


def _recalls(start, end):
	if not frappe.db.exists("DocType", "Material Recall"):
		return {}
	by = {}
	for r in frappe.get_all("Material Recall", filters={"notice_date": ["between", [str(start), str(end)]]}, fields=["heat"]):
		mill = frappe.db.get_value("Material Heat", r.heat, "mill") if r.heat else None
		by.setdefault(mill or _("unknown mill"), []).append(r.heat)
	return by


def inputs(start, end):
	by = _recalls(start, end)
	if not by:
		return [{"area": _("Suppliers"), "source": _("materials"), "order": 60,
				 "lines": [{"text": _("no heat recalled"), "tone": "ok"}]}]
	lines = [{"text": _("{0}: heat {1} recalled").format(mill, ", ".join(heats)), "tone": "bad"} for mill, heats in by.items()]
	return [{"area": _("Suppliers"), "source": _("materials"), "order": 60, "lines": lines,
			 "route": {"name": "materials-lots"}}]


def proposals(start, end):
	return [{"key": f"materials:requalify:{mill}", "text": _("Requalify {0}, or move its orders to another mill.").format(mill)}
			for mill in _recalls(start, end)]
