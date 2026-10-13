# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt

"""The supplier inside Worgify (guide 33 P1, D-9; level-up pass, phase 5).

What /supplier-certificates did, in the supplier's own space: the open orders we sent
them, line by line, with what each line asks (the 3.1 certificate, the requirements of
the order) and the certificates already sent — read and judged at once: a heat that may
ship, one we will ask about, one not to ship. The order stays closed to them at the API:
its page is its only door, asking first whether it is theirs (``gate``); the certificate
is the portal's own write (``materials.supplier_portal.send_certificate``).
"""

from __future__ import annotations

import frappe
from frappe import _

from worgify.utils.supplier_portal import get_user_supplier, require_portal_supplier

MPO = "Material Purchase Order"


def order_is_theirs(doc) -> bool:
	supplier = get_user_supplier()
	return bool(supplier and doc.supplier == supplier and doc.docstatus == 1)


def _waiting(o) -> int:
	return sum(1 for ln in o["lines"] if ln["asks_certificate"] and not ln["certificates"])


def orders() -> list[dict]:
	"""The open orders, the ones still owing a certificate first."""
	from materials.supplier_portal import my_orders

	out = []
	for o in my_orders()["orders"]:
		owed = _waiting(o)
		out.append({"title": o["name"], "doctype": MPO, "name": o["name"],
					"line": " · ".join(filter(None, [_("due {0}").format(o["due"]) if o["due"] else None,
													 _("{0} lines").format(len(o["lines"]))])),
					"state": _("{0} certificates to send").format(owed) if owed else _("Certificates sent"),
					"theme": "orange" if owed else "green", "owed": bool(owed)})
	out.sort(key=lambda r: not r.pop("owed"))
	return out


def today() -> dict:
	from materials.supplier_portal import my_orders

	rows = [o for o in my_orders()["orders"] if _waiting(o)]
	if not rows:
		return {"bands": []}
	return {"bands": [{"verb": _("Send"), "count": len(rows), "rows": [{
		"title": o["name"], "subtitle": _("due {0}").format(o["due"]) if o["due"] else "",
		"why": _("{0} certificates to send before shipping").format(_waiting(o)),
		"link": {"doctype": MPO, "name": o["name"]}} for o in rows]}]}


def order_page(doc) -> dict:
	"""An order as the supplier reads it: its lines, what each asks, the certificates
	sent and how they were judged — and the one act, sending a certificate."""
	from materials.supplier_portal import my_orders

	require_portal_supplier()
	o = next((x for x in my_orders()["orders"] if x["name"] == doc.name), None)
	if not o:
		frappe.throw(_("This order is not open any more."), frappe.PermissionError)
	owed = _waiting(o)
	lines = {"type": "table", "title": _("The lines"), "columns": [
		{"key": "line", "label": _("Line")}, {"key": "item", "label": _("Item")}, {"key": "qty", "label": _("Quantity")},
		{"key": "due", "label": _("Due")}, {"key": "certs", "label": _("Certificates")}],
		"rows": [{"line": ln["line"], "item": ln["item"], "qty": f"{ln['qty']:g} {ln['uom'] or ''}".strip(), "due": ln["due"],
				  "certs": "; ".join(f"{c['number']} · {_('heat')} {c['heat'] or '?'} · {_('can ship') if c['ok'] else c['why']}"
									 for c in ln["certificates"]) or (_("to send") if ln["asks_certificate"] else "")}
				 for ln in o["lines"]]}
	blocks = [lines]
	if o["requirements"]:
		blocks.append({"type": "table", "title": _("What the order asks"), "columns": [
			{"key": "what", "label": _("Requirement")}, {"key": "value", "label": _("Value")}],
			"rows": [{"what": r["what"], "value": r["value"]} for r in o["requirements"]]})
	page = {"title": doc.name, "kind": _("Our order"),
			"headline": ({"text": _("{0} certificates to send before shipping: each is read and judged when it arrives.").format(owed),
						  "theme": "orange"} if owed else {"text": _("Every certificate it asks has been sent."), "theme": "green"}),
			"facts": [{"label": _("Due"), "value": o["due"]}], "overview": blocks}
	asking = [ln for ln in o["lines"] if ln["asks_certificate"]]
	if asking:
		page["primary"] = {"id": "send_certificate", "label": _("Send a certificate"), "icon": "upload",
						   "method": "materials.supplier_portal.send_certificate", "args": {"order": doc.name},
						   "fields": [{"fieldname": "line", "label": _("Line"), "fieldtype": "Select", "reqd": 1,
									   "options": "\n".join(ln["line"] for ln in asking)},
									  {"fieldname": "file_url", "label": _("The certificate (PDF)"), "fieldtype": "Attach", "reqd": 1}]}
	return page
