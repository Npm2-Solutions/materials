# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""What materials says about a supplier, for its evaluation (Design 55 OR-01,
board O3, the kernel's ``supplier_evaluation_providers``).

* **Certificates conforming** — each 3.1 of the period read against its standard
  and its order (``conformity.judge``, MA-03) or contested by a person: a
  defective certificate weighs, because the material behind it is used on its word.
  Points: 100 minus five times the share found defective (a fifth defective is 0).
* **Recalls** — the heats recalled in the period that came from them (MA-06):
  each costs 60 points.
* **Responses and documents** — the certificates sent before the material
  shipped (the supplier portal, MA-01), over all of the period's.

A failed impact test proposes repeating it on a sample of each delivery; any
defective certificate proposes checking the certificate before shipping.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate

from materials import conformity

CERT = "Material Certificate"
RECALL = "Material Recall"
KEYS = ("materials:certificates", "materials:recalls", "materials:documents")


def certificates_of(supplier, start, end) -> list:
	"""The period's certificates of a supplier, each with what the check found."""
	out = []
	for c in frappe.get_all(CERT, filters={"supplier": supplier, "certificate_date": ["between", [start, end]]},
							fields=["name", "certificate_number", "contested", "contested_reason", "sent_before_shipping",
									"order_reference"], order_by="certificate_date asc"):
		found = {"name": c.name, "number": c.certificate_number or c.name, "before": bool(c.sent_before_shipping),
				 "defective": False, "short": [], "impact": False}
		if c.contested:
			found.update(defective=True, short=[c.contested_reason] if c.contested_reason else [])
		order = c.order_reference
		if order and frappe.db.exists("Material Purchase Order", order):
			doc = frappe.get_doc(CERT, c.name)
			j = conformity.judge(doc, conformity.requirements_of_order(order, doc.get("order_line")),
								 doc.get("product_thickness"))
			if j["verdict"] == conformity.NO:
				found["defective"] = True
				found["short"] = found["short"] or j.get("short") or []
			found["impact"] = any(r.get("key") == "KV" and r.get("outcome") == conformity.NO for r in j.get("rows") or [])
		reason = (c.contested_reason or "").lower() if c.contested else ""
		if "impact" in reason or "resilien" in reason or "kv" in reason.split():
			found["impact"] = True
		out.append(found)
	return out


def _recalls(supplier, start, end):
	if not frappe.db.exists("DocType", RECALL):
		return []
	rows = frappe.db.sql("""
		SELECT r.name, r.heat, r.cause, r.notice_date, h.heat_number
		FROM `tabMaterial Recall` r
		LEFT JOIN `tabMaterial Heat` h ON h.name = r.heat
		LEFT JOIN `tabMaterial Certificate` c ON c.name = r.certificate
		WHERE (h.mill = %(s)s OR c.supplier = %(s)s) AND COALESCE(r.notice_date, DATE(r.creation)) BETWEEN %(a)s AND %(b)s
		ORDER BY COALESCE(r.notice_date, DATE(r.creation)) DESC
	""", {"s": supplier, "a": start, "b": end}, as_dict=True)
	for r in rows:
		r["welded"] = bool(frappe.db.exists("Material Recall Branch", {"parent": r.name, "branch": "Welded into joints"}))
	return rows


def criteria(supplier, start, end) -> list:
	certs = certificates_of(supplier, start, end)
	recalls = _recalls(supplier, start, end)
	out = []

	bad = [c for c in certs if c["defective"]]
	row = {"key": KEYS[0], "label": _("Certificates conforming"), "reads": _("the 3.1 checks"), "weight": 40,
		   "refs": [{"doctype": CERT, "name": c["name"], "label": c["number"]} for c in bad]}
	if not certs:
		out.append({**row, "score": None, "happened": _("No certificate in the period.")})
	else:
		said = "; ".join(f"{', '.join(c['short'][:2])} ({c['number']})" if c["short"] else c["number"] for c in bad[:3])
		happened = (_("{0} defective of {1}: {2}").format(len(bad), len(certs), said) if bad
					else _("All {0} conforming.").format(len(certs)))
		suggests = []
		if bad:
			suggests.append(_("the certificate checked before shipping"))
		if any(c["impact"] for c in bad):
			suggests.append(_("the impact test repeated by us on a sample of each delivery"))
		out.append({**row, "score": max(0, round(100 - 500 * len(bad) / len(certs))), "happened": happened,
					"suggests": suggests})

	row = {"key": KEYS[1], "label": _("Recalls"), "reads": _("materials"), "weight": 20,
		   "refs": [{"doctype": RECALL, "name": r.name, "label": r.heat_number or r.heat} for r in recalls]}
	if not recalls:
		out.append({**row, "score": 100 if certs else None,
					"happened": _("No heat recalled.") if certs else _("Nothing received in the period.")})
	else:
		bits = []
		for r in recalls[:3]:
			who = _("by the mill") if r.cause == "The mill's notice" else _("by our check")
			bit = _("heat {0} recalled {1}").format(r.heat_number or r.heat, who)
			bits.append(bit + (", " + _("already welded") if r.welded else ""))
		out.append({**row, "score": max(0, 100 - 60 * len(recalls)), "happened": "; ".join(bits)})

	row = {"key": KEYS[2], "label": _("Responses and documents"), "reads": _("orders and portal"), "weight": 15, "refs": []}
	if not certs:
		out.append({**row, "score": None, "happened": _("No certificate in the period.")})
	else:
		before = sum(1 for c in certs if c["before"])
		out.append({**row, "score": round(100 * before / len(certs)),
					"happened": _("{0} of {1} certificates came before the material").format(before, len(certs))})
	return out


criteria.keys = KEYS
