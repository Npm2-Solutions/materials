# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""The metal's line on a job (Design 55 JO-05; the engine is the kernel's
``worgify.jobs.lines``): the lines received with their certificate, the ones
still on their way — and the materials stage, done when every order of the job
is received."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

MPO = "Material Purchase Order"


def line(project):
	if not frappe.db.exists("DocType", MPO):
		return None
	orders = frappe.get_all(MPO, filters={"project": project, "docstatus": 1}, fields=["name", "per_received"])
	if not orders:
		return None
	receipts = frappe.get_all("Goods Receipt", filters={"purchase_order": ["in", [o.name for o in orders]], "docstatus": 1},
							  pluck="name")
	lines = frappe.get_all("Goods Receipt Item", filters={"parent": ["in", receipts or ["—"]]}, fields=["certificate_reference"])
	pending = frappe.db.sql("""select count(*) from `tabMaterial Purchase Order Item`
		where parent in %s and ifnull(received_qty, 0) < qty""", (tuple(o.name for o in orders),))[0][0]
	without = sum(1 for x in lines if not x.certificate_reference)
	parts = [{"text": _("{0} lines received").format(len(lines))}]
	if lines:
		parts.append({"text": _("all with their certificate")} if not without else
					 {"text": _("{0} without a certificate").format(without), "tone": "warn"})
	if pending:
		parts.append({"text": _("{0} on their way").format(pending)})
	return {"space": _("Materials"), "icon": "lucide-package", "order": 40, "parts": parts,
			"route": {"name": "materials-orders", "query": {"project": project}},
			"stages": {"materials": {"started": bool(lines), "done": all(flt(o.per_received) >= 100 for o in orders)}}}
