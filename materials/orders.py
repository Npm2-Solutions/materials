# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""The order with its technical requirements, and its certificates checked before
the truck leaves (Design 55 MA-01, board M1).

A wrong certificate found at receiving costs a return; found before shipping it
costs an e-mail. So the order carries what the job's review asks of the metal
(``technical_requirements``, a field materials adds to stock's order), the
supplier uploads each 3.1 from its portal before loading, and the certificate is
read and judged at once (``materials.conformity``, proposal 17). The buyer sees
the verdict and sends one sentence the supplier can act on.

The order is stock's; nothing here writes it except its requirements. The
requirements are proposed from the job's material requirements (the review,
proposal 13, writes those); the buyer can add one, with where it comes from.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate

from materials import certificate_reader, conformity

MPO = "Material Purchase Order"
CERT = conformity.CERT


def _order(name, ptype="read"):
	if not frappe.db.exists("DocType", MPO):
		frappe.throw(_("Orders live in the warehouse app, which is not installed."))
	doc = frappe.get_doc(MPO, name)
	doc.check_permission(ptype)
	return doc


def _lines(doc):
	return {str(r.idx): r for r in doc.get("items") or []}


def _requirement_rows(doc):
	rows = []
	for r in doc.get("technical_requirements") or []:
		rows.append({"name": r.name, "kind": r.requirement, "what": conformity.requirement_word(r.requirement),
					 "value": conformity.requirement_value(r), "line": r.order_line or None,
					 "source": r.source or "", "added_on": frappe.utils.formatdate(r.added_on, "d MMMM") if r.added_on else None})
	return rows


def certificates_of(order):
	"""The certificates that name this order, newest first."""
	return frappe.get_all(CERT, filters={"order_reference": order}, fields=["name", "certificate_number", "order_line",
																		  "sent_before_shipping", "contested", "creation",
																		  "attachment", "certificate_type"],
						  order_by="creation desc")


def _heat_of(cert_name):
	return frappe.db.get_value("Material Heat Coverage", {"parent": cert_name, "parenttype": CERT}, "heat")


def _judged(doc_order, c):
	cert = frappe.get_doc(CERT, c.name)
	reqs = conformity.requirements_of_order(doc_order.name, c.order_line)
	thickness = cert.get("product_thickness") or conformity._thickness_of_order_line(doc_order.name, c.order_line)
	return cert, conformity.judge(cert, reqs, thickness)


def _check_line(j):
	"""The check in one line, as the board says it."""
	if j["verdict"] == conformity.NO:
		return " · ".join(j["brief"])
	asks = [r["out"].lstrip("! ") for r in j["rows"] if r["outcome"] == conformity.ASK]
	if asks:
		return _("within the standard and the order") + " · " + "; ".join(asks)
	return " · ".join([_("everything within the standard and the order")] + j["notes"])


@frappe.whitelist()
def order_metal(order: str) -> dict:
	"""What the order's page shows beside stock's lines: the requirements the supplier
	received, each line's certificate state, the certificates sent before shipping
	with their check, what to tell the supplier, and the supplier in one box."""
	doc = _order(order)
	lines = _lines(doc)
	certs = []
	by_line = {}
	for c in certificates_of(order):
		cert, j = _judged(doc, c)
		heat = _heat_of(c.name)
		row = {"name": c.name, "number": c.certificate_number or c.name, "heat": heat, "line": c.order_line,
			   "verdict": j["verdict"], "short": j["short"], "said": j["said"], "file": c.attachment,
			   "before_shipping": bool(c.sent_before_shipping),
			   "line_text": _check_line(j)}
		certs.append(row)
		by_line.setdefault(str(c.order_line or ""), []).append(row)
	line_rows = []
	to_redo = 0
	for idx, r in lines.items():
		mine = by_line.get(idx, [])
		good = [c for c in mine if c["verdict"] != conformity.NO]
		bad = [c for c in mine if c["verdict"] == conformity.NO]
		if bad and not good:
			state, theme = _("certificate to redo"), "red"
			to_redo += 1
		elif good:
			state, theme = (_("certificate compliant") if any(c["verdict"] == conformity.OK for c in good)
							else _("certificate: values to ask")), "green" if any(c["verdict"] == conformity.OK for c in good) else "amber"
		elif any(x.requirement for x in doc.get("technical_requirements") or []):
			state, theme = _("certificate not sent yet"), "gray"
		else:
			state, theme = "", "gray"
		line_rows.append({"line": idx, "item": r.item_name or r.item_code, "qty": flt(r.qty), "uom": r.stock_uom,
						  "due": frappe.utils.formatdate(r.required_by_date or doc.delivery_date, "d MMMM")
						  if (r.required_by_date or doc.delivery_date) else None, "state": state, "theme": theme})
	message = None
	bad_certs = [c for c in certs if c["verdict"] == conformity.NO]
	if bad_certs:
		c = bad_certs[0]
		alt = next((x["heat"] for x in certs if x["verdict"] == conformity.OK and x["heat"] != c["heat"]
					and str(x["line"] or "") in ("", str(c["line"] or ""))), None)
		message = conformity.message_to_supplier(c["line"], c["heat"], c["short"], alt)
	told = frappe.get_all("Communication", filters={"reference_doctype": MPO, "reference_name": order,
													"sent_or_received": "Sent", "communication_type": "Communication"},
						  fields=["name", "creation", "content", "subject"], order_by="creation desc", limit=1)
	return {
		"requirements": _requirement_rows(doc), "lines": line_rows, "certificates": certs, "to_redo": to_redo,
		"message": message, "told": {"on": frappe.utils.format_datetime(told[0].creation, "d MMMM HH:mm"),
									 "text": frappe.utils.strip_html(told[0].content or "")} if told else None,
		"supplier": supplier_box(doc.supplier), "may_edit": bool(frappe.has_permission(MPO, "write", doc=doc)),
		"may_tell": bool(frappe.has_permission(MPO, "write", doc=doc)),
		"job_requirements": _job_requirement_offer(doc),
		"portal": "/supplier-certificates",
		"job": (frappe.db.get_value("Project", doc.project, "project_name") or "").split(" · ")[0] if doc.get("project") else None,
	}


def _job_requirement_offer(doc):
	"""The job's material requirements not yet on the order — what the buyer can add in one click."""
	if not doc.get("project"):
		return []
	have = {(r.requirement, r.grade, r.certificate_type, flt(r.impact_energy), flt(r.impact_temperature), flt(r.cev_max))
			for r in doc.get("technical_requirements") or []}
	out = []
	for jr in conformity.job_requirements(doc.project):
		for row in _rows_from_job_requirement(jr):
			key = (row["requirement"], row.get("grade"), row.get("certificate_type"), flt(row.get("impact_energy")),
				   flt(row.get("impact_temperature")), flt(row.get("cev_max")))
			if key not in have:
				out.append({**row, "value": conformity.requirement_value(row), "what": conformity.requirement_word(row["requirement"])})
	return out


def _rows_from_job_requirement(jr):
	source = jr.source or _("review of job {0}").format(jr.project)
	rows = [{"requirement": "Material", "grade": jr.grade, "delivery_condition": jr.delivery_condition, "source": source}]
	if jr.certificate_type:
		rows.append({"requirement": "Document", "certificate_type": jr.certificate_type, "source": source})
	if flt(jr.impact_energy):
		rows.append({"requirement": "Impact", "impact_energy": jr.impact_energy, "impact_temperature": jr.impact_temperature,
					 "impact_direction": jr.impact_direction or "Transverse", "source": source})
	if flt(jr.cev_max):
		rows.append({"requirement": "Carbon equivalent", "cev_max": jr.cev_max, "cev_elements": jr.cev_elements, "source": source})
	if jr.pmi_required:
		rows.append({"requirement": "PMI", "text": _("PMI on every piece"), "source": source})
	return rows


@frappe.whitelist(methods=["POST"])
def add_requirements(order: str, rows: str | list) -> dict:
	"""Add requirements to the order — at writing or after it was signed, when the
	review changed (the board's *added on 7 October*). The order's history keeps it."""
	doc = _order(order, "write")
	rows = frappe.parse_json(rows) if isinstance(rows, str) else rows
	for r in rows or []:
		if not r.get("requirement"):
			continue
		doc.append("technical_requirements", {k: r.get(k) for k in (
			"requirement", "order_line", "grade", "delivery_condition", "certificate_type", "impact_energy",
			"impact_temperature", "impact_direction", "cev_max", "cev_elements", "text", "source")}
				   | {"added_on": nowdate()})
	doc.flags.ignore_validate_update_after_submit = True
	doc.save()
	return {"message": _("{0} requirements on the order.").format(len(doc.get("technical_requirements") or []))}


@frappe.whitelist(methods=["POST"])
def remove_requirement(order: str, row: str) -> dict:
	doc = _order(order, "write")
	keep = [r for r in doc.get("technical_requirements") or [] if r.name != row]
	doc.set("technical_requirements", keep)
	doc.flags.ignore_validate_update_after_submit = True
	doc.save()
	return {"message": _("Requirement removed.")}


def grade_from_reading(reading):
	"""The Material Grade a certificate names: its grade («13MnNi6-3 +N») under its standard («EN 10028-4»)."""
	f = reading.get("fields") or {}
	name = ((f.get("grade") or {}).get("value") or "").split("+")[0].split("(")[0].strip()
	standard = ((f.get("standard") or {}).get("value") or "").replace(" ", "-")
	if not name:
		return None
	if standard:
		g = frappe.db.get_value("Material Grade", {"grade": name, "specification": standard})
		if g:
			return g
	rows = frappe.get_all("Material Grade", filters={"grade": name}, pluck="name", limit=2)
	return rows[0] if len(rows) == 1 else None


def _ensure_heat(heat_number, grade, supplier):
	"""The heat in the register; a heat with no known grade is not invented — None."""
	if not heat_number:
		return None
	if frappe.db.exists("Material Heat", heat_number):
		return heat_number
	if not grade:
		return None
	h = frappe.get_doc({"doctype": "Material Heat", "heat_number": heat_number, "grade": grade, "mill": supplier})
	h.insert(ignore_permissions=True)
	return h.name


def receive_certificate(order: str, line: str | None, file_url: str, before_shipping: bool = True,
						supplier_user: str | None = None) -> dict:
	"""Read a certificate PDF for an order line, keep it as a Material Certificate
	and judge it. Shared by the supplier's portal and the buyer's page."""
	doc = frappe.get_doc(MPO, order)
	reading = certificate_reader.read(file_url)
	if reading["scanned"]:
		frappe.throw(_("This PDF is a scan: there are no words to read. Send the certificate as the mill's system printed it."))
	f = reading["fields"]
	number = (f.get("certificate_number") or {}).get("value")
	if number and frappe.db.exists(CERT, {"certificate_number": number, "supplier": doc.supplier}):
		existing = frappe.db.get_value(CERT, {"certificate_number": number, "supplier": doc.supplier}, "name")
		frappe.throw(_("Certificate {0} was already received ({1}).").format(number, existing))
	reqs = conformity.requirements_of_order(order, line)
	grade = next((r.grade for r in reqs if r.requirement == "Material" and r.grade), None) or grade_from_reading(reading)
	heat = _ensure_heat((f.get("heat") or {}).get("value"), grade, doc.supplier)
	cert = frappe.new_doc(CERT)
	cert.supplier = doc.supplier
	cert.attachment = file_url
	cert.order_line = str(line) if line else None
	cert.sent_before_shipping = 1 if before_shipping else 0
	certificate_reader.apply(cert, reading, heat)
	cert.order_reference = order
	cert.status = "Valid"
	cert.flags.ignore_permissions = bool(supplier_user)
	cert.insert()
	if supplier_user:
		frappe.db.set_value("File", {"file_url": file_url}, {"attached_to_doctype": CERT, "attached_to_name": cert.name})
	j = conformity.judge(cert, reqs, cert.product_thickness or conformity._thickness_of_order_line(order, line))
	return {"name": cert.name, "number": cert.certificate_number, "heat": heat, "verdict": j["verdict"], "judgement": j,
			"not_read": reading["not_read"]}


@frappe.whitelist(methods=["POST"])
def upload_certificate(order: str, file_url: str, line: str | None = None) -> dict:
	"""The buyer adds a certificate the supplier e-mailed instead of uploading it."""
	_order(order, "write")
	frappe.has_permission(CERT, "create", throw=True)
	return receive_certificate(order, line, file_url, before_shipping=True)


@frappe.whitelist(methods=["POST"])
def tell_supplier(order: str, message: str) -> dict:
	"""The sentence goes to the supplier: on its portal, and by e-mail when the
	site can send one (said plainly when it cannot)."""
	doc = _order(order, "write")
	message = (message or "").strip()
	if not message:
		frappe.throw(_("Write what to tell the supplier."))
	recipients = _supplier_emails(doc.supplier)
	subject = _("Order {0}: certificates before shipping").format(doc.name)
	sent = False
	if recipients and _can_send():
		# Frappe's own e-mail act: the Communication is written and the mail queued
		from frappe.core.doctype.communication.email import make

		try:
			make(doctype=MPO, name=doc.name, content=message, subject=subject, recipients=", ".join(recipients),
				 send_email=True)
			sent = True
		except frappe.OutgoingEmailError:
			frappe.local.message_log = []
	if not sent:
		# no outgoing mail on this site: the sentence is still kept, and the portal shows it
		frappe.get_doc({
			"doctype": "Communication", "communication_type": "Communication", "communication_medium": "Other",
			"sent_or_received": "Sent", "subject": subject, "content": message, "reference_doctype": MPO,
			"reference_name": doc.name, "recipients": ", ".join(recipients), "sender": frappe.session.user,
		}).insert(ignore_permissions=True)
	where = _("on its portal and by e-mail") if sent else _("on its portal (no outgoing mail on this site)")
	return {"message": _("Told {0} {1}.").format(doc.supplier_name or doc.supplier, where), "sent": sent}


def _can_send():
	"""Does the site have the outgoing account Frappe would send with?"""
	try:
		from frappe.email.doctype.email_account.email_account import EmailAccount

		return bool(EmailAccount.find_outgoing(_raise_error=False))
	except Exception:
		return False


def _supplier_emails(supplier):
	users = []
	if frappe.db.exists("DocType", "Supplier Portal User"):
		users = frappe.get_all("Supplier Portal User", filters={"parent": supplier, "parenttype": "Supplier", "enabled": 1},
							   pluck="user")
	return [u for u in users if u and "@" in u]


def supplier_box(supplier) -> dict | None:
	"""The supplier in one box: its standing, the certificates it got wrong this
	year, and its deliveries on time — written from what happened, never filled in."""
	if not supplier:
		return None
	start = getdate(f"{getdate(nowdate()).year}-01-01")
	status = frappe.db.get_value("Supplier", supplier, "avl_status") if frappe.get_meta("Supplier").has_field("avl_status") else None
	certs = frappe.get_all(CERT, filters={"supplier": supplier, "creation": [">=", start]}, fields=["name", "contested"])
	defective = 0
	for c in certs:
		if c.contested:
			defective += 1
			continue
		doc = frappe.get_doc(CERT, c.name)
		order = doc.get("order_reference")
		if order and frappe.db.exists(MPO, order):
			if conformity.judge(doc, conformity.requirements_of_order(order, doc.get("order_line")),
								doc.get("product_thickness"))["verdict"] == conformity.NO:
				defective += 1
	return {"name": frappe.db.get_value("Supplier", supplier, "supplier_name") or supplier, "status": status,
			"status_label": _(status) if status else None, "defective": defective, "certificates": len(certs),
			"punctuality": punctuality(supplier)}


def punctuality(supplier) -> int | None:
	"""Order lines received by their date, over the last twelve months, in %
	(from the Goods Receipts: a delivery is the receipt, not a movement)."""
	if not frappe.db.exists("DocType", "Goods Receipt"):
		return None
	rows = frappe.db.sql("""
		SELECT gr.receipt_date, COALESCE(poi.required_by_date, po.delivery_date) AS due
		FROM `tabGoods Receipt` gr
		JOIN `tabGoods Receipt Item` gri ON gri.parent = gr.name
		JOIN `tabMaterial Purchase Order` po ON po.name = gr.purchase_order
		LEFT JOIN `tabMaterial Purchase Order Item` poi ON poi.name = gri.purchase_order_item
		WHERE gr.docstatus = 1 AND gr.supplier = %s AND gr.receipt_date >= %s
	""", (supplier, add_days(nowdate(), -365)), as_dict=True)
	judged = [r for r in rows if r.due and r.receipt_date]
	if not judged:
		return None
	on_time = sum(1 for r in judged if getdate(r.receipt_date) <= getdate(r.due))
	return round(100 * on_time / len(judged))
