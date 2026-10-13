# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""What the metal proves when a job is billed (Design 55 JO-03; the engine is
the kernel's ``worgify.jobs.closeout``): *the material in the shop* — every
order of the job received, with the certificate of each line registered."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, formatdate

MPO = "Material Purchase Order"


def evidence_kinds():
	return [{"key": "materials_in", "label": _("The material in the shop")}]


def evidence(key, project, scope=None):
	if key != "materials_in":
		return None
	if not frappe.db.exists("DocType", MPO):
		return {"ok": False, "what": _("no purchasing on this site")}
	orders = frappe.get_all(MPO, filters={"project": project, "docstatus": 1}, fields=["name", "per_received"])
	if not orders:
		return {"ok": False, "what": _("no order of material on the job")}
	short = [o for o in orders if flt(o.per_received) < 100]
	if short:
		return {"ok": False, "what": _("order {0} received at {1} %").format(short[0].name, round(flt(short[0].per_received)))}
	receipts = frappe.get_all("Goods Receipt", filters={"purchase_order": ["in", [o.name for o in orders]], "docstatus": 1},
							  fields=["name", "receipt_date"], order_by="receipt_date asc")
	lines = frappe.get_all("Goods Receipt Item", filters={"parent": ["in", [r.name for r in receipts] or ["—"]]},
						   fields=["certificate_reference"])
	certified = lines and all(line.certificate_reference for line in lines)
	names = ", ".join(r.name for r in receipts)
	last = receipts[-1].receipt_date if receipts else None
	what = (_("receipts {0}, certificates registered") if certified else _("receipts {0}, certificates still to register")).format(names)
	return {"ok": bool(certified), "what": what, "on": last}
