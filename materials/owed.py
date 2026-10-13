# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""What a supplier owes, for the kernel's «who owes what» (Design 55 DO-02): the
order lines still to deliver once their date passed or a delivery came short,
with how the supplier keeps time."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

MPO = "Material Purchase Order"


def owed():
	if not frappe.db.exists("DocType", MPO) or not frappe.has_permission(MPO, "read"):
		return []
	from materials.orders import punctuality

	today = getdate(nowdate())
	out, paces = [], {}
	for o in frappe.get_list(MPO, filters={"docstatus": 1, "status": ["not in", ["Completed", "Closed", "Cancelled"]]},
							 fields=["name", "supplier", "supplier_name", "delivery_date", "project"], limit_page_length=200):
		short = {r.purchase_order_item: r.receipt_date for r in frappe.db.sql("""
			SELECT gri.purchase_order_item, gr.receipt_date FROM `tabGoods Receipt` gr
			JOIN `tabGoods Receipt Item` gri ON gri.parent = gr.name
			WHERE gr.docstatus = 1 AND gr.purchase_order = %s AND gr.has_discrepancy = 1""", o.name, as_dict=True)}
		for r in frappe.get_all("Material Purchase Order Item", filters={"parent": o.name}, fields=["name", "idx", "item_name", "qty",
																										 "received_qty", "stock_uom", "required_by_date"]):
			left = flt(r.qty) - flt(r.received_qty)
			due = getdate(r.required_by_date or o.delivery_date) if (r.required_by_date or o.delivery_date) else None
			if left <= 0 or not (r.name in short or (due and due < today)):
				continue
			if o.supplier not in paces:
				p = punctuality(o.supplier)
				paces[o.supplier] = _("on time {0} %").format(p) if p is not None else None
			out.append({"holder": ("Supplier", o.supplier), "label": o.supplier_name,
						"what": _("Order {0}, line {1}: {2} {3} of {4} still to deliver").format(o.name, r.idx, f"{left:g}",
																								  _(r.stock_uom) if r.stock_uom else "", r.item_name),
						"since": short.get(r.name) or due, "due": due, "project": o.project, "pace": paces[o.supplier],
						"route": {"name": "materials-order", "params": {"name": o.name}}})
	return out
