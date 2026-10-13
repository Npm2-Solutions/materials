# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""The metal a customer's change touches (Design 55 JO-02, board J4; the change
is the projects app's ``projects.change_impact``).

For each part the change adds: the grade, and **what the job asks of it** — the
job's material requirement (the inspection certificate, the impact the
specification asks), so the order says it and the certificate proves it (P13);
its **price** from the last order of that grade (per kg, when the order or the
item says what a piece weighs) and its **lead time**, the days that order took.
Without an order that states a price, the amount is a person's to write.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt

JMR = "Job Material Requirement"


def _requirement(project):
	rows = frappe.get_all(JMR, filters={"project": project}, fields=["grade", "certificate_type", "impact_energy",
																	  "impact_temperature", "delivery_condition"],
						  order_by="modified desc", limit=1) if project else []
	return rows[0] if rows else None


def _last_order(grade):
	"""The latest order line of an item of this grade: price per kg, days, who ordered."""
	rows = frappe.db.sql("""
		select i.rate, i.uom, i.stock_uom, it.unit_weight, o.order_date, o.delivery_date, o.supplier_name, o.owner
		from `tabMaterial Purchase Order Item` i
		join `tabMaterial Purchase Order` o on o.name = i.parent
		join `tabItem` it on it.name = i.item_code
		where it.material_grade like %s and o.docstatus < 2
		order by o.order_date desc limit 1
	""", (f"%{grade}%",), as_dict=True) if grade and frappe.db.exists("DocType", "Material Purchase Order") else []
	if not rows:
		return None
	r = rows[0]
	per_kg = None
	if flt(r.rate):
		if (r.uom or r.stock_uom or "").lower() == "kg":
			per_kg = flt(r.rate)
		elif flt(r.unit_weight):
			per_kg = flt(r.rate) / flt(r.unit_weight)
	buyer = frappe.db.get_value("Personnel", {"user": r.owner}, "name") if r.owner else None
	days = date_diff(r.delivery_date, r.order_date) if r.delivery_date and r.order_date else None
	return frappe._dict(per_kg=per_kg, days=days, supplier=r.supplier_name, buyer=buyer)


def impacts(change):
	parts = [i for i in change["items"] if i.kind == "Part"]
	if not parts:
		return []
	req = _requirement(change.project)
	out = []
	for i in parts:
		grade = (i.material or (req.grade.split("--")[-1] if req and req.grade else "")).strip()
		last = _last_order(grade)
		kg = flt(i.weight) * (flt(i.quantity) or 1)
		amount = round(last.per_kg * kg, 2) if last and last.per_kg and kg else None
		out.append({
			"key": f"part:{i.idx}", "area": "materials", "who": last.buyer if last else None, "amount": amount,
			"lead_days": last.days if last else None,
			"facts": {"label": i.description, "grade": grade, "kg": kg or None,
					  "certificate": req.certificate_type if req else None,
					  "impact_j": flt(req.impact_energy) if req and req.impact_energy else None,
					  "impact_t": flt(req.impact_temperature) if req and req.impact_energy else None,
					  "supplier": last.supplier if last else None, "priced": bool(amount)},
		})
	return out


def describe(row):
	if row.area != "materials":
		return None
	f = row.facts
	what = _("{0} in {1}").format(f.label, f.grade) if f.grade else (f.label or "")
	asks = []
	if f.certificate:
		asks.append(_("with certificate {0}").format(f.certificate))
	if f.impact_j:
		asks.append(_("impact {0} J at {1} °C").format(round(f.impact_j), str(round(f.impact_t)).replace("-", "−")))
	if asks:
		what += ", " + " " .join([asks[0]] + [_("and {0}").format(a) for a in asks[1:]])
	days = cint(row.lead_days)
	if days:
		weeks = max(1, round(days / 7))
		what += " · " + (_("1 week from the last order") if weeks == 1 else _("{0} weeks from the last order").format(weeks))
	if not f.priced and not flt(row.amount):
		what += " · " + _("no order states a price: the amount is to write")
	return {"area": _("Materials"), "what": what}
