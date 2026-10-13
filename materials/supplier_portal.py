# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""The supplier's portal: the orders addressed to it, what each line must be, and
the certificate it sends before loading (Design 55 MA-01, board M1).

Opened through ``worgify.utils.supplier_portal.require_portal_supplier`` — a
supplier sees its own orders and nothing else, and what the buyer told it. The
certificate is read and judged at once; the supplier sees whether it can ship,
and why not, in the words the buyer will use.
"""

from __future__ import annotations

import frappe
from frappe import _

from materials import conformity, orders

MPO = "Material Purchase Order"


def _mine():
	from worgify.utils.supplier_portal import require_portal_supplier

	return require_portal_supplier()


def _open_orders(supplier):
	if not frappe.db.exists("DocType", MPO):
		return []
	return frappe.get_all(MPO, filters={"supplier": supplier, "docstatus": 1,
										 "status": ["not in", ["Completed", "Closed", "Cancelled"]]},
						  fields=["name", "order_date", "delivery_date", "per_received"], order_by="delivery_date asc",
						  ignore_permissions=True)


@frappe.whitelist()
def my_orders() -> dict:
	supplier = _mine()
	out = []
	for o in _open_orders(supplier):
		doc = frappe.get_doc(MPO, o.name)
		certs = {}
		for c in orders.certificates_of(o.name):
			cert, j = orders._judged(doc, c)
			certs.setdefault(str(c.order_line or ""), []).append({
				"number": c.certificate_number or c.name, "heat": orders._heat_of(c.name),
				"ok": j["verdict"] != conformity.NO, "why": ", ".join(j["short"])})
		reqs = [{"what": conformity.requirement_word(r.requirement), "value": conformity.requirement_value(r),
				 "line": r.order_line or None} for r in doc.get("technical_requirements") or []]
		lines = [{"line": str(r.idx), "item": r.item_name or r.item_code, "qty": r.qty, "uom": r.stock_uom,
				  "due": frappe.utils.formatdate(r.required_by_date or doc.delivery_date) if (r.required_by_date or doc.delivery_date) else "",
				  "certificates": certs.get(str(r.idx), []),
				  "asks_certificate": bool(r.certificate_required) or bool(reqs)} for r in doc.items]
		told = frappe.get_all("Communication", filters={"reference_doctype": MPO, "reference_name": o.name,
														"sent_or_received": "Sent"},
							  fields=["creation", "content"], order_by="creation desc", limit=3, ignore_permissions=True)
		out.append({"name": o.name, "due": frappe.utils.formatdate(o.delivery_date) if o.delivery_date else "",
					"requirements": reqs, "lines": lines,
					"told": [{"on": frappe.utils.format_datetime(t.creation, "d MMMM HH:mm"),
							  "text": frappe.utils.strip_html(t.content or "")} for t in told]})
	return {"supplier": frappe.db.get_value("Supplier", supplier, "supplier_name") or supplier, "orders": out}


@frappe.whitelist(methods=["POST"])
def send_certificate(order: str, line: str, file_url: str) -> dict:
	"""The supplier's 3.1 for one line of one of its orders: read, kept, judged."""
	supplier = _mine()
	if frappe.db.get_value(MPO, order, "supplier") != supplier:
		frappe.throw(_("This order is not addressed to you."), frappe.PermissionError)
	owner = frappe.db.get_value("File", {"file_url": file_url}, "owner")
	if owner != frappe.session.user:
		frappe.throw(_("Send a file you uploaded."), frappe.PermissionError)
	got = orders.receive_certificate(order, line, file_url, before_shipping=True, supplier_user=frappe.session.user)
	j = got["judgement"]
	if j["verdict"] == conformity.NO:
		said = _("Do not ship heat {0}: {1}.").format(got["heat"] or "?", ", ".join(j["short"]))
	elif j["verdict"] == conformity.ASK:
		said = _("Received. Your customer will ask for: {0}.").format(
			", ".join(r["out"].lstrip("! ") for r in j["rows"] if r["outcome"] == conformity.ASK))
	else:
		said = _("Heat {0} can ship: everything within the standard and the order.").format(got["heat"] or "?")
	return {"ok": j["verdict"] != conformity.NO, "message": said}
