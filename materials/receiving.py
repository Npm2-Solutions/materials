# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""The certificates read with the delivery note (Design 55 MA-02, board M2): each
PDF that came with the truck is read and judged against its standard and the
order — or recognised as the one already checked before shipping (MA-01) — and,
once the receipt is booked, tied to the lots born from it, by heat.

The receipt is stock's; this is the metal's half, called by the receiving screen
where materials is installed.
"""

from __future__ import annotations

import frappe
from frappe import _

from materials import certificate_reader, conformity, orders

CERT = conformity.CERT


@frappe.whitelist(methods=["POST"])
def read_certificates(files: str | list, order: str | None = None, heats: str | list | None = None) -> dict:
	"""{heat: {certificate, number, verdict, line_text, before_shipping, read}} for
	each PDF: a certificate already received (by its number) is not read twice.
	``heats``: the heats the delivery note names — kept in the register, so the
	receipt's lines can carry them even before a certificate covers them."""
	frappe.has_permission(CERT, "read", throw=True)
	files = frappe.parse_json(files) if isinstance(files, str) else (files or [])
	heats = frappe.parse_json(heats) if isinstance(heats, str) else (heats or [])
	grade = None
	if order and frappe.db.exists("Material Purchase Order", order):
		grade = next((r.grade for r in conformity.requirements_of_order(order) if r.requirement == "Material" and r.grade), None)
		supplier = frappe.db.get_value("Material Purchase Order", order, "supplier")
		for h in heats:
			if h and frappe.has_permission("Material Heat", "create"):
				orders._ensure_heat(h, grade, supplier)
	out, notes = {}, []
	for url in files:
		reading = certificate_reader.read(url)
		if reading["scanned"]:
			notes.append(_("{0} is a scan: it could not be read.").format(url.rsplit("/", 1)[-1]))
			continue
		f = reading["fields"]
		number = (f.get("certificate_number") or {}).get("value")
		heat = (f.get("heat") or {}).get("value")
		existing = frappe.db.get_value(CERT, {"certificate_number": number}, "name") if number else None
		if existing:
			name, before = existing, bool(frappe.db.get_value(CERT, existing, "sent_before_shipping"))
		else:
			if not frappe.has_permission(CERT, "create"):
				notes.append(_("{0} read, not kept: you may not add certificates.").format(number or url))
				continue
			mpo = order or (f.get("order") or {}).get("value")
			try:
				if mpo and frappe.db.exists("Material Purchase Order", mpo):
					got = orders.receive_certificate(mpo, _line_for(mpo, heat, reading), url, before_shipping=False)
					name = got["name"]
				else:
					cert = frappe.new_doc(CERT)
					cert.attachment = url
					certificate_reader.apply(cert, reading, orders._ensure_heat(heat, orders.grade_from_reading(reading), None))
					cert.status = "Valid"
					cert.insert()
					name = cert.name
			except frappe.MandatoryError:
				# what the paper does not print is not invented: it is kept by hand
				frappe.local.message_log = []
				notes.append(_("{0} read, not kept: it does not print {1}. Add it by hand from the paper.").format(
					number or url.rsplit("/", 1)[-1], ", ".join(_missing(reading))))
				continue
			before = False
		doc = frappe.get_doc(CERT, name)
		mpo = doc.get("order_reference")
		j = conformity.judge(doc, conformity.requirements_of_order(mpo, doc.get("order_line")) if mpo else [],
							 doc.get("product_thickness"))
		heat = heat or orders._heat_of(name)
		out[heat or name] = {"certificate": name, "number": doc.certificate_number or name, "heat": heat,
							 "verdict": j["verdict"], "line_text": orders._check_line(j), "before_shipping": before,
							 "file": url, "said": j["said"],
							 "at": {"heat": (f.get("heat") or {}).get("at"), "number": (f.get("certificate_number") or {}).get("at")}}
	for h in heats:
		if h and h not in out:
			out[h] = {"certificate": None, "number": None, "heat": h, "verdict": None, "before_shipping": False,
					  "line_text": _("no certificate for heat {0}").format(h)}
	return {"by_heat": out, "notes": notes}


def _missing(reading):
	words = {"certificate_number": _("its number"), "heat": _("its heat"), "date": _("its date")}
	return [w for k, w in words.items() if k not in reading["fields"]] or [_("a required value")]


def _line_for(order, heat, reading):
	"""The order line a certificate is for: by thickness, when the lines differ in it."""
	t = (reading["fields"].get("thickness") or {}).get("value")
	if not t:
		return None
	for r in frappe.get_all("Material Purchase Order Item", filters={"parent": order}, fields=["idx", "item_code"]):
		if frappe.db.get_value("Item", r.item_code, "thickness") == t:
			return str(r.idx)
	return None


@frappe.whitelist(methods=["POST"])
def tie_certificates(receipt: str) -> dict:
	"""After booking: each lot born from the receipt carries the certificates of its heat."""
	gr = frappe.get_doc("Goods Receipt", receipt)
	gr.check_permission("read")
	from materials.material_certifications.doctype.material_certificate.material_certificate import auto_link_certificate

	tied = 0
	for r in gr.items:
		if not r.created_batch or not r.heat_number:
			continue
		for c in frappe.get_all("Material Heat Coverage", filters={"heat": r.heat_number, "parenttype": CERT}, pluck="parent"):
			try:
				auto_link_certificate(r.created_batch, c)
				tied += 1
			except Exception:
				frappe.log_error(title=f"materials: tie {c} to {r.created_batch} failed")
	return {"tied": tied}
