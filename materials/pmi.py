# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""PMI with readings (Design 55 MA-07, board M7): the analyser's reading of each
alloy element against the grade's limits from the library's standard, the
instrument named and checked, a photo of the spot, the result proposed.

*Found 316L* is a claim; *Mo 2,05 % (2,00–2,50)* is evidence. A reading on the
product is judged on the cast limits widened by the standard's product-analysis
tolerances (EN 10216-5 Table 5, EN 10028-4 Table 2) — that is what the standard
allows a product to show. What a handheld XRF cannot read (carbon, and the light
elements) is said, with where the answer comes from instead: the certificate.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from materials import conformity, grade_limits as gl

PMI = "PMI Check"
#: what a handheld XRF reads; carbon, silicon below ~0,1 %, phosphorus, sulphur,
#: nitrogen, aluminium and boron are beyond it
XRF_READS = ("Cr", "Ni", "Mo", "Mn", "Cu", "Ti", "Nb", "V", "W", "Co")


def _grade_of_lot(lot):
	heat = frappe.db.get_value("Batch", lot, "heat_number") if frappe.db.exists("DocType", "Batch") else None
	grade = conformity.grade_of_heat(heat) if heat else None
	return heat, grade


def limits_for(grade):
	standard, name, label = conformity.standard_and_name(grade)
	cast = gl.limits(standard, name) if standard and name else None
	product = gl.limits(standard, name, product=True) if cast else None
	return standard, name, label, cast, product


@frappe.whitelist(methods=["POST"])
def start(lot: str, piece: str | None = None, inspection_request: str | None = None) -> dict:
	"""A PMI on one piece of a lot: the grade is the lot's heat's."""
	frappe.has_permission(PMI, "create", throw=True)
	heat, grade = _grade_of_lot(lot)
	if not grade:
		frappe.throw(_("Lot {0} has no heat with a grade: the limits cannot be known.").format(lot))
	doc = frappe.get_doc({"doctype": PMI, "subject_doctype": "Batch", "subject": lot, "piece": piece, "heat": heat,
						  "grade": grade, "inspection_request": inspection_request, "tested_on": now_datetime(),
						  "operator": _me()})
	doc.insert()
	return {"name": doc.name}


def _me():
	try:
		from worgify.personnel.api import get_personnel_for_user

		return get_personnel_for_user(frappe.session.user)
	except Exception:
		return None


def _title(doc):
	return " · ".join(x for x in [doc.subject, doc.piece] if x)


def judge(doc) -> dict:
	"""Each reading against the product limits; the proposal."""
	standard, name, label, cast, product = limits_for(doc.grade)
	if not cast:
		return {"rows": [], "proposal": "Incomplete", "source": None, "unread": [],
				"said": _("The limits of {0} are not transcribed yet: the reading is recorded, not judged.").format(label or doc.grade)}
	read = {r.element: r.read_percent for r in doc.readings or [] if r.read_percent is not None and flt(r.read_percent) > 0}
	rows = []
	for el in [e for e in XRF_READS if e in cast["chemistry"]]:
		low, high = product["chemistry"][el]
		c_low, c_high = cast["chemistry"][el]
		v = read.get(el)
		within = v is not None and (low is None or v >= low - 1e-9) and (high is None or v <= high + 1e-9)
		rows.append({"element": el, "read": v, "read_text": conformity.pct(v) if v is not None else "",
					 "limit": conformity._range(c_low, c_high), "low": low, "high": high,
					 "tolerance": conformity._range(low, high) if (low, high) != (c_low, c_high) else "",
					 "within": within if v is not None else None})
	unread = [e for e in cast["chemistry"] if e not in XRF_READS]
	if any(r["within"] is False for r in rows):
		proposal = "Alloy not confirmed"
	elif rows and all(r["within"] for r in rows):
		proposal = "Alloy confirmed"
	else:
		proposal = "Incomplete"
	source = ", ".join([cast["source"]["title"], _("tables {0} and {1}").format(
		cast["chemistry_clause"].replace("Table ", ""), product["chemistry_clause"].replace("Table ", ""))])
	return {"rows": rows, "proposal": proposal, "source": source, "unread": unread, "said": _said(doc, rows, proposal, unread)}


def _said(doc, rows, proposal, unread):
	if proposal == "Alloy not confirmed":
		out = [r for r in rows if r["within"] is False]
		return _("Outside the grade: {0}.").format(", ".join(f"{r['element']} {r['read_text']} % ({r['limit']})" for r in out))
	if proposal != "Alloy confirmed":
		return _("Read every element to propose a result.")
	words = ", ".join(_(conformity.ELEMENT_WORDS.get(r["element"], r["element"])) for r in rows if r["low"] is not None)
	said = _("{0}: within the grade.").format(words.capitalize()) if words else _("Within the grade.")
	if "C" in unread:
		c = _certificate_carbon(doc)
		said += " " + (_("The carbon the analyser cannot read is the certificate's: {0} %.").format(conformity.pct(c)) if c is not None
					   else _("The analyser cannot read carbon: the certificate says it, and it does not print it here."))
	return said


def _certificate_carbon(doc):
	if not doc.heat:
		return None
	for c in frappe.get_all("Material Heat Coverage", filters={"heat": doc.heat, "parenttype": conformity.CERT}, pluck="parent"):
		v = frappe.db.get_value("Certificate Chemical Result", {"parent": c, "element": "C"}, "value_percent")
		if v:
			return flt(v)
	return None


def _is_instrument(name):
	return bool(name and frappe.db.exists("DocType", "Instrument") and frappe.db.exists("Instrument", name))


def _usable(doc):
	"""May the analyser be used now? The fleet answers (Design 43); without the
	instruments app, the check ticked on the PMI is the only word there is."""
	if not doc.instrument:
		return False
	if _is_instrument(doc.instrument):
		from worgify.readiness import EXPIRING, USABLE, can_use

		a = can_use("Instrument", doc.instrument)
		return bool(a.known and a.status in (USABLE, EXPIRING))
	return bool(doc.instrument_checked)


def _instrument(doc):
	if not doc.instrument:
		return None
	out = {"name": doc.instrument, "checked": _usable(doc), "label": doc.instrument}
	if frappe.db.exists("DocType", "Instrument") and frappe.db.exists("Instrument", doc.instrument):
		out["label"] = frappe.db.get_value("Instrument", doc.instrument, "instrument_name") or doc.instrument
		try:
			from worgify.readiness import can_use, word

			a = can_use("Instrument", doc.instrument)
			if a.known:
				out["status"] = a.status
				out["status_label"] = word(a.status)
				out["reason"] = "; ".join(f.reason for f in a.findings if f.status == a.status)
		except Exception:
			pass
	return out


@frappe.whitelist()
def workspace(name: str) -> dict:
	doc = frappe.get_doc(PMI, name)
	doc.check_permission("read")
	standard, gname, label, cast, product = limits_for(doc.grade)
	j = judge(doc)
	item = None
	if doc.subject_doctype == "Batch" and frappe.db.exists("Batch", doc.subject):
		b = frappe.db.get_value("Batch", doc.subject, ["item", "item_name", "received_qty", "stock_uom"], as_dict=True)
		item = {"name": b.item_name or b.item, "qty": flt(b.received_qty), "uom": b.stock_uom}
	number = (cast or {}).get("number")
	return {
		"name": doc.name, "lot": doc.subject, "piece": doc.piece, "heat": doc.heat, "grade": label or doc.grade,
		"number": number if not (item and number and number in (item["name"] or "")) else None, "item": item, "inspection_request": doc.inspection_request,
		"operator": frappe.db.get_value("Personnel", doc.operator, "full_name") if doc.operator else None,
		"limits_from": j["source"], "rows": j["rows"], "proposal": j["proposal"],
		"proposal_label": _(j["proposal"]) if j["proposal"] else "", "said": j["said"],
		"instrument": _instrument(doc), "photo": doc.photo, "result": doc.result, "remarks": doc.remarks,
		"may_write": bool(frappe.has_permission(PMI, "write", doc=doc)) and not doc.result,
		"next_piece": _next_piece(doc.piece),
	}


def _next_piece(piece):
	"""«tube 3 of 12» → «tube 4 of 12»; None at the last."""
	import re

	m = re.search(r"(\d+)\D+(\d+)\s*$", piece or "")
	if not m or int(m.group(1)) >= int(m.group(2)):
		return None
	return piece[:m.start(1)] + str(int(m.group(1)) + 1) + piece[m.end(1):]


@frappe.whitelist(methods=["POST"])
def save(name: str, readings: str | dict | None = None, instrument: str | None = None, instrument_checked: int | None = None,
		 photo: str | None = None) -> dict:
	doc = frappe.get_doc(PMI, name)
	doc.check_permission("write")
	if doc.result:
		frappe.throw(_("This PMI is decided: start a new one for another piece."))
	if readings is not None:
		readings = frappe.parse_json(readings) if isinstance(readings, str) else readings
		have = {r.element: r for r in doc.readings or []}
		for el, v in (readings or {}).items():
			v = None if v in (None, "") else flt(v)
			if el in have:
				have[el].read_percent = v
			elif v is not None:
				doc.append("readings", {"element": el, "read_percent": v})
	if instrument is not None:
		doc.instrument = instrument or None
	if instrument_checked is not None:
		if cint(instrument_checked) and _is_instrument(doc.instrument):
			# the check on today's sample is the instrument's fact: it is recorded where
			# the fleet keeps it (instruments' one door), and read back from there
			try:
				frappe.get_attr("instruments.instruments.equipment_service.log_verification")(
					doc.instrument, "Pass", reference_used=_("today's sample"), notes=_("PMI {0}").format(doc.name))
			except frappe.PermissionError:
				frappe.throw(_("You may not record the check of {0}: ask who keeps the instruments.").format(doc.instrument))
		doc.instrument_checked = cint(instrument_checked)
	if photo is not None:
		doc.photo = photo or None
	_stamp(doc)
	doc.save()
	return workspace(name)


def _stamp(doc):
	j = judge(doc)
	limits = {r["element"]: r for r in j["rows"]}
	for r in doc.readings or []:
		lim = limits.get(r.element)
		r.low = lim["low"] if lim else None
		r.high = lim["high"] if lim else None
		r.within = 1 if lim and lim["within"] else 0
	doc.proposal = j["proposal"]
	doc.limits_from = j["source"]
	doc.title = _title(doc)


@frappe.whitelist(methods=["POST"])
def decide(name: str, result: str, remarks: str | None = None) -> dict:
	"""The person decides; the proposal is only a proposal. Without the instrument
	checked on today's sample and a photo of the spot, nothing is decided."""
	doc = frappe.get_doc(PMI, name)
	doc.check_permission("write")
	if result not in ("Pass", "Fail", "Inconclusive"):
		frappe.throw(_("Pass, Fail or Inconclusive."))
	if result == "Pass":
		if not doc.instrument or not _usable(doc):
			frappe.throw(_("Name the analyser and say it was checked on today's sample."))
		if not doc.photo:
			frappe.throw(_("Take a photo of the spot that was read."))
		if judge(doc)["proposal"] != "Alloy confirmed":
			frappe.throw(_("The readings do not confirm the alloy: it cannot pass."))
	doc.result = result
	doc.remarks = remarks
	_stamp(doc)
	doc.save()
	out = {"message": _("PMI {0}: {1}.").format(_title(doc), _(result).lower())}
	nxt = _next_piece(doc.piece)
	if nxt:
		out["next"] = start(doc.subject, nxt, doc.inspection_request)["name"]
	return out


@frappe.whitelist()
def queue(view: str = "recent") -> dict:
	"""The PMI checks, the newest first, with what they found."""
	frappe.has_permission(PMI, "read", throw=True)
	rows = frappe.get_list(PMI, fields=["name", "subject", "piece", "grade", "proposal", "result", "tested_on", "operator"],
						   order_by="tested_on desc", limit_page_length=100)
	grades = {g.name: g.display_name or g.grade for g in frappe.get_all("Material Grade", filters={"name": ["in", [r.grade for r in rows] or [""]]},
																	   fields=["name", "grade", "display_name"])}
	return {"rows": [{"name": r.name, "title": " · ".join(x for x in [r.subject, r.piece] if x), "grade": grades.get(r.grade, r.grade),
					  "result": r.result, "result_label": _(r.result) if r.result else _("to decide"),
					  "proposal": _(r.proposal) if r.proposal else "", "on": frappe.utils.format_datetime(r.tested_on, "d MMM HH:mm")}
					 for r in rows],
			"may_create": bool(frappe.has_permission(PMI, "create"))}
