# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""The data of the Materials place in the Worgify interface (/w/materials): its
Today and its counts, and the metal's own screens — the heats and the mill
certificates.

The place is materials' and leads with the warehouse wherever `stock` is
installed (owner 5/10: a real warehouse first, traceability on top, the metal
as a module of its own). So the home survives where a tenant runs the metal
register without a warehouse: the warehouse's bands and counts are asked of
`stock.screens` only when stock is there. Every answer is built as the person
may read it (`frappe.get_list`, `check_permission`).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate
from frappe.utils.translations import N_

CERT = "Material Certificate"
HEAT = "Material Heat"
COVER = "Material Heat Coverage"
BATCH = "Batch"

HEAT_THEME = {"Active": "gray", "Released": "green", "Quarantined": "red", "Recalled": "red"}
CERT_STATUS_THEME = {"Valid": "green", "Expired": "red", "Revoked": "red"}
LOT_THEME = {"Pending Inspection": "amber", "Released": "green", "Quarantine": "red",
			 "Returned Pending Re-Inspection": "amber", "Rejected": "gray"}
HELD = ("Quarantined", "Recalled")
# the register's own transitions (MaterialHeat.ALLOWED_STATUS_TRANSITIONS), as acts
HEAT_ACTS = (
	("Released", N_("Release the heat"), "circle-check", None),
	("Quarantined", N_("Quarantine the heat"), "shield-alert", "red"),
	("Active", N_("Back to active"), "rotate-ccw", None),
	("Recalled", N_("Recall the heat"), "ban", "red"),
)


# ── small helpers ────────────────────────────────────────────────────────────


def _w(value, context=None):
	return _(value, context=context) if value else ""


def _d(value):
	return str(value) if value else None


def _join(*bits):
	return " · ".join(str(b) for b in bits if b not in (None, ""))


def _can(doctype, ptype="read", doc=None):
	try:
		return bool(frappe.db.exists("DocType", doctype)) and bool(frappe.has_permission(doctype, ptype, doc=doc))
	except Exception:
		return False


def _stock():
	"""Whether the warehouse is installed: lots exist only there."""
	return "stock" in frappe.get_installed_apps() and bool(frappe.db.exists("DocType", BATCH))


def _row(title, subtitle, doctype, name, **extra):
	out = {"name": name, "title": title or name, "subtitle": subtitle or "", "link": {"doctype": doctype, "name": name}}
	out.update({k: v for k, v in extra.items() if v not in (None, "", [], False)})
	return out


def _band(key, label, verb, theme, rows, more=None):
	return {"key": key, "label": label, "verb": verb, "theme": theme, "count": len(rows), "rows": rows[:6], "more": more}


def _num(value):
	v = flt(value, 3)
	return f"{v:g}"


def _supplier_names(names):
	names = [n for n in set(names or []) if n]
	if not names:
		return {}
	return dict(frappe.get_all("Supplier", filters={"name": ["in", names]}, fields=["name", "supplier_name"], as_list=True))


def _grade_names(grades):
	"""{grade: what people call it} — the grade's display name, not its key."""
	grades = [g for g in set(grades or []) if g]
	if not grades or not frappe.db.exists("DocType", "Material Grade"):
		return {}
	return dict(frappe.get_all("Material Grade", filters={"name": ["in", grades]}, fields=["name", "display_name"],
							   as_list=True))


def _range(low, high):
	"""A requirement as it is read: a band, at least, at most — a missing bound is no bound."""
	low = flt(low) or None
	high = flt(high) or None
	if low and high:
		return f"{_num(low)} – {_num(high)}"  # noqa: RUF001
	if low:
		return f"≥ {_num(low)}"
	if high:
		return f"≤ {_num(high)}"
	return None


def _coverage(certificates):
	"""{certificate: [heat, …]} for the certificates given."""
	out = {}
	if certificates:
		for r in frappe.get_all(COVER, filters={"parenttype": CERT, "parent": ["in", list(certificates)]},
								fields=["parent", "heat"], order_by="idx asc"):
			if r.heat:
				out.setdefault(r.parent, []).append(r.heat)
	return out


def _carrying(certificates):
	"""{certificate: {lot, …}} — the lots whose certificate list names it (stock's side)."""
	out = {}
	if certificates and _stock():
		for r in frappe.get_all("Mill Test Certificate", filters={"parenttype": BATCH, "certificate": ["in", list(certificates)]},
								fields=["parent", "certificate"]):
			out.setdefault(r.certificate, set()).add(r.parent)
	return out


def _lots_of_heats(heats):
	"""{heat: [lot, …]} — the lots that name the heat, as their primary heat or in
	their list of heats, as the person may read them."""
	out = {}
	if not heats or not _stock() or not _can(BATCH):
		return out
	heats = list(set(heats))
	rows = frappe.get_list(BATCH, filters={"heat_number": ["in", heats]}, fields=["name", "heat_number"],
						   limit_page_length=0)
	for r in rows:
		out.setdefault(r.heat_number, set()).add(r.name)
	extra = frappe.get_all("Batch Heat Number", filters={"parenttype": BATCH, "heat_number": ["in", heats]},
						   fields=["parent", "heat_number"])
	if extra:
		readable = set(frappe.get_list(BATCH, filters={"name": ["in", list({r.parent for r in extra})]}, pluck="name",
									   limit_page_length=0))
		for r in extra:
			if r.parent in readable:
				out.setdefault(r.heat_number, set()).add(r.parent)
	return out


def _unlinked(certificates, coverage=None, carrying=None):
	"""{certificate: {lot, …}} — lots of the heats it covers that do not carry it."""
	coverage = coverage if coverage is not None else _coverage(certificates)
	carrying = carrying if carrying is not None else _carrying(certificates)
	heats = {h for hs in coverage.values() for h in hs}
	by_heat = _lots_of_heats(heats)
	out = {}
	for c in certificates:
		lots = set()
		for h in coverage.get(c, []):
			lots |= by_heat.get(h, set())
		lots -= carrying.get(c, set())
		if lots:
			out[c] = lots
	return out


def _held_heats_on_the_shelf():
	"""Heats the register holds (quarantined, recalled) whose lots are still
	Released with material on the shelf — what a recall has not stopped yet."""
	if not _can(HEAT) or not _stock() or not _can(BATCH):
		return []
	held = frappe.get_list(HEAT, filters={"status": ["in", HELD]}, fields=["name", "status", "grade", "mill"],
						   limit_page_length=200)
	if not held:
		return []
	by_heat = _lots_of_heats([h.name for h in held])
	lots = {b.name: b for b in frappe.get_list(BATCH, filters={"name": ["in", list({x for s in by_heat.values() for x in s}) or [""]]},
											   fields=["name", "lot_status", "available_qty", "stock_uom"], limit_page_length=0)}
	out = []
	for h in held:
		live = [lots[n] for n in by_heat.get(h.name, set()) if n in lots and lots[n].lot_status == "Released"
				and flt(lots[n].available_qty) > 0]
		if live:
			h.live = live
			out.append(h)
	return out


# ── Today and the counts: the place's own answers ────────────────────────────

QUALITY = ("STK Material Inspector", "STK Quality Manager", "Material Record Author", "System Manager")


def _matches():
	"""Whose work it is to tie a certificate to its lots: the quality side who may
	write the lots (the store keeper writes lots too, but judges no paperwork)."""
	return _stock() and _can(BATCH, "write") and bool(set(QUALITY) & set(frappe.get_roles()))


def _heats_text(heats):
	heats = heats or []
	if not heats:
		return None
	if len(heats) == 1:
		return _("heat {0}").format(heats[0])
	return _("heats {0}").format(", ".join(heats[:3]) + ("…" if len(heats) > 3 else ""))


@frappe.whitelist()
def today() -> dict:
	"""What waits on whoever opens Materials, by verb: the warehouse's bands where
	stock is installed (stock.screens.today_bands), and the metal's — heats held
	but still on the shelf, certificates to tie to their lots, certificates to
	verify. A band the person cannot act on is not there."""
	bands = []
	held = _held_heats_on_the_shelf() if _can(BATCH, "write") else []
	if held:
		bands.append(_band("held_heats", _("Held heats still on the shelf"), _("Hold it"), "red", [
			_row(h.name, _join(_w(h.status, HEAT), h.grade,
							   _("1 lot on the shelf") if len(h.live) == 1 else _("{0} lots on the shelf").format(len(h.live))),
				 HEAT, h.name) for h in held], {"route": {"name": "materials-heats", "query": {"view": "held"}}}))
	if _stock():
		bands += frappe.get_attr("stock.screens.today_bands")()
	if _can(CERT):
		certs = frappe.get_list(CERT, filters={"status": "Valid"},
								fields=["name", "certificate_number", "certificate_type", "issuing_body", "supplier",
										"attachment", "verified", "certificate_date"],
								order_by="certificate_date asc", limit_page_length=500)
		coverage = _coverage([c.name for c in certs])
		matched = set()
		if certs and _matches():
			unlinked = _unlinked([c.name for c in certs], coverage)
			rows = []
			for c in certs:
				lots = unlinked.get(c.name)
				if lots:
					matched.add(c.name)
					rows.append(_row(c.certificate_number or c.name, _join(c.issuing_body, _heats_text(coverage.get(c.name))),
									 CERT, c.name, when=_d(c.certificate_date), code=c.certificate_type,
									 why=_("1 lot of its heats does not carry it") if len(lots) == 1
									 else _("{0} lots of its heats do not carry it").format(len(lots))))
			if rows:
				bands.append(_band("match", _("Certificates to tie to their lots"), _("Tie"), "blue", rows,
								   {"route": {"name": "materials-certificates", "query": {"view": "match"}}}))
		if certs and _can(CERT, "write"):
			# one row per certificate: one still to tie to its lots is met there first;
			# verifying compares the transcription with the PDF, so the PDF comes first
			waiting = [c for c in certs if not c.verified and c.name not in matched]
			for key, label, verb, rows in (
				("attach", _("Certificates without their PDF"), _("Attach"), [c for c in waiting if not c.attachment]),
				("verify", _("Certificates to verify"), _("Verify"), [c for c in waiting if c.attachment]),
			):
				if rows:
					bands.append(_band(key, label, verb, "blue", [
						_row(c.certificate_number or c.name, _join(c.issuing_body, _heats_text(coverage.get(c.name))), CERT,
							 c.name, when=_d(c.certificate_date), code=c.certificate_type) for c in rows],
						{"route": {"name": "materials-certificates", "query": {"view": "verify"}}}))
	return {"bands": bands}


@frappe.whitelist()
def nav_counts() -> dict:
	"""The numbers beside the place's rows: the viewer's own work only."""
	out = {}
	if _stock():
		out.update(frappe.get_attr("stock.screens.nav_counts_part")())
	if _can(CERT):
		certs = frappe.get_list(CERT, filters={"status": "Valid"}, fields=["name", "verified"], limit_page_length=0)
		waiting = set()
		if _can(CERT, "write"):
			waiting |= {c.name for c in certs if not c.verified}
		if certs and _matches():
			waiting |= set(_unlinked([c.name for c in certs]))
		out["certificates"] = len(waiting)
	if _can(BATCH, "write"):
		out["heats"] = len(_held_heats_on_the_shelf())
	return out


# ── Heats ────────────────────────────────────────────────────────────────────

HEAT_VIEWS = (("all", N_("All")), ("held", N_("Quarantined or recalled")), ("uncovered", N_("Without a certificate")))


@frappe.whitelist()
def heats(view: str = "all", search: str | None = None) -> dict:
	"""Every heat in the register: its grade and mill, its status, the
	certificates that cover it and — where the warehouse is installed — its lots
	and what of it is still on the shelf."""
	frappe.has_permission(HEAT, "read", throw=True)
	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = [["name", "like", like], ["cast_number", "like", like], ["grade", "like", like]]
	every = frappe.get_list(HEAT, or_filters=or_filters, fields=["name", "cast_number", "grade", "mill", "status",
																	 "production_date", "modified"],
							order_by="modified desc", limit_page_length=1000)
	names = [h.name for h in every]
	covering = {}
	if names and _can(CERT):
		readable = set(frappe.get_list(CERT, pluck="name", limit_page_length=0))
		for r in frappe.get_all(COVER, filters={"parenttype": CERT, "heat": ["in", names]}, fields=["parent", "heat"]):
			if r.parent in readable:
				covering.setdefault(r.heat, set()).add(r.parent)
	by_heat = _lots_of_heats(names)
	shelf = {}
	if by_heat:
		every_lot = {x for s in by_heat.values() for x in s}
		lots = {b.name: b for b in frappe.get_list(BATCH, filters={"name": ["in", list(every_lot)]},
												   fields=["name", "available_qty", "stock_uom", "lot_status"],
												   limit_page_length=0)}
		for h, members in by_heat.items():
			total, uoms = 0, set()
			for n in members:
				b = lots.get(n)
				if b and b.lot_status != "Rejected":
					total += flt(b.available_qty)
					uoms.add(b.stock_uom)
			shelf[h] = f"{_num(total)} {uoms.pop()}" if total and len(uoms) == 1 else (_num(total) if total else None)
	mills = _supplier_names([h.mill for h in every])
	grades = _grade_names([h.grade for h in every])
	tests = {"all": lambda h: True, "held": lambda h: h.status in HELD, "uncovered": lambda h: not covering.get(h.name)}
	counts = {k: len([h for h in every if t(h)]) for k, t in tests.items()}
	rows = []
	for h in every:
		if not (tests.get(view) or tests["all"])(h):
			continue
		rows.append({"name": h.name, "link": {"doctype": HEAT, "name": h.name}, "title": h.name,
					 "subtitle": _join(h.cast_number and _("cast {0}").format(h.cast_number), mills.get(h.mill) or h.mill),
					 "grade": grades.get(h.grade) or h.grade, "status": _w(h.status, HEAT), "theme": HEAT_THEME.get(h.status, "gray"),
					 "certificates": len(covering.get(h.name, ())), "lots": len(by_heat.get(h.name, ())) if _stock() else None,
					 "shelf": shelf.get(h.name), "produced": _d(h.production_date)})
	return {"views": [{"key": k, "label": _(label), "count": counts.get(k, 0)} for k, label in HEAT_VIEWS],
			"rows": rows, "stock": _stock(), "may_create": bool(frappe.has_permission(HEAT, "create"))}


def _recall(heat):
	"""The Recall Simulation's own answer for this heat: on the shelf, built in,
	left with nobody saying where — split lots included."""
	if not _stock() or not frappe.db.exists("Report", "Recall Simulation"):
		return None
	if not frappe.has_permission(BATCH, "read"):
		return None
	from frappe.desk.query_report import run

	try:
		result = run("Recall Simulation", filters={"heat": heat}, ignore_prepared_report=True)
	except frappe.PermissionError:
		return None
	# the report's summary, in its own order: lots reached, on the shelf, built in, left undeclared
	values = [s.get("value") for s in result.get("report_summary") or []] + [0, 0, 0, 0]
	reached, shelf, built, undeclared = values[:4]
	rows = [r for r in result.get("result") or [] if isinstance(r, dict)]
	states = {}
	for r in rows:
		states.setdefault(r.get("state"), []).append(r)
	return {
		"numbers": [
			{"label": _("Lots reached"), "value": cint(reached)},
			{"label": _("Still on the shelf"), "value": _num(shelf), "theme": "amber" if flt(shelf) else None},
			{"label": _("Built into something"), "value": _num(built), "theme": "red" if flt(built) else None},
			{"label": _("Left, undeclared"), "value": _num(undeclared), "theme": "red" if flt(undeclared) else None},
		],
		"undeclared": [{"lot": r.get("batch_id"), "qty": _num(r.get("qty"))} for r in states.get(_("Left, undeclared"), [])],
		"shelf": flt(shelf),
	}


def _built_into(heat, lots):
	"""What took the heat in: parts whose Made Of names it (or one of its lots),
	joints welded with it — each read only where the person may read it."""
	out = {"parts": [], "joints": []}
	if frappe.db.exists("DocType", "Assembly Part Material") and _can("Assembly Part"):
		rows = frappe.db.sql("""
			SELECT DISTINCT p.name, p.part_id, p.mark_number, p.assembly, p.project, m.qty, m.uom, m.lot
			FROM `tabAssembly Part Material` m JOIN `tabAssembly Part` p ON p.name = m.parent
			WHERE m.heat_number = %(heat)s OR m.lot IN %(lots)s
			LIMIT 200""", {"heat": heat, "lots": tuple(lots) or ("",)}, as_dict=True)
		readable = set(frappe.get_list("Assembly Part", filters={"name": ["in", [r.name for r in rows] or [""]]},
									   pluck="name", limit_page_length=0))
		out["parts"] = [{"name": r.name, "part": _join(r.part_id, r.mark_number), "assembly": r.assembly,
						 "project": r.project, "qty": f"{_num(r.qty)} {r.uom or ''}".strip(), "lot": r.lot}
						for r in rows if r.name in readable]
	if frappe.db.exists("DocType", "Assembly Joint") and _can("Assembly Joint"):
		joints = frappe.get_list("Assembly Joint", or_filters={"heat_number_1": heat, "heat_number_2": heat},
								 fields=["name", "joint_id", "project", "assembly", "welding_status", "ndt_status"],
								 order_by="project, name", limit_page_length=200)
		out["joints"] = [{"name": j.name, "joint": j.joint_id or j.name, "project": j.project, "assembly": j.assembly,
						  "welding": _w(j.welding_status, "Assembly Joint"), "ndt": _w(j.ndt_status, "Assembly Joint")}
						 for j in joints]
	return out


@frappe.whitelist()
def heat_workspace(name: str) -> dict:
	"""A heat as the material QM traces it: the certificates that cover it, every
	lot of it (split lots included) with where it is and how much, what took it
	in (parts, joints), the recall answer in its three states — and the two
	deliberate acts: hold what is still on the shelf, change the heat's standing
	in the register."""
	doc = frappe.get_doc(HEAT, name)
	doc.check_permission("read")
	certs = []
	if _can(CERT):
		names = frappe.get_all(COVER, filters={"parenttype": CERT, "heat": doc.name}, pluck="parent")
		for c in frappe.get_list(CERT, filters={"name": ["in", names or [""]]},
								 fields=["name", "certificate_number", "certificate_type", "status", "attachment",
										 "verified", "certificate_date", "issuing_body"], order_by="certificate_date desc"):
			certs.append({"name": c.name, "number": c.certificate_number or c.name, "type": c.certificate_type,
						  "status": _w(c.status, CERT), "theme": CERT_STATUS_THEME.get(c.status, "gray"),
						  "verified": bool(c.verified), "file": c.attachment, "date": _d(c.certificate_date),
						  "issuer": c.issuing_body})
	lots, lot_names = [], []
	if _stock() and _can(BATCH):
		scope = set()
		try:
			from stock.stock.report.recall_simulation.recall_simulation import _lots_in_scope

			scope = set(_lots_in_scope({"heat": doc.name}))
		except Exception:
			frappe.log_error(title="materials.screens: recall scope")
		scope |= _lots_of_heats([doc.name]).get(doc.name, set())
		places = {}
		if scope:
			for r in frappe.get_all("Lot Bin", filters={"batch": ["in", list(scope)], "actual_qty": [">", 0]},
									fields=["batch", "warehouse", "actual_qty"]):
				places.setdefault(r.batch, []).append(r)
		for b in frappe.get_list(BATCH, filters={"name": ["in", list(scope) or [""]]},
								 fields=["name", "batch_id", "item", "item_name", "lot_status", "available_qty", "stock_uom",
										 "current_warehouse", "is_remnant", "parent_batch", "supplier_name", "project",
										 "certificate_status", "heat_number"],
								 order_by="creation asc", limit_page_length=0):
			lot_names.append(b.name)
			where = places.get(b.name) or []
			lots.append({"name": b.name, "lot": b.batch_id or b.name, "item": b.item_name or b.item,
						 "state": b.lot_status, "state_label": _w(b.lot_status, BATCH),
						 "theme": LOT_THEME.get(b.lot_status, "gray"),
						 "available": f"{_num(b.available_qty)} {b.stock_uom or ''}".strip(),
						 "where": ", ".join(f"{p.warehouse} {_num(p.actual_qty)}" for p in where) or None,
						 "offcut": bool(b.is_remnant), "split_from": b.parent_batch, "project": b.project,
						 "secondary": b.heat_number != doc.name,
						 "certificates": _w(b.certificate_status, BATCH)})
	recall = None
	try:
		recall = _recall(doc.name)
	except Exception:
		frappe.log_error(title="materials.screens: recall answer")
	acts = []
	if _stock() and frappe.has_permission(BATCH, "write"):
		stoppable = [x for x in lots if x["state"] in ("Released", "Pending Inspection")]
		# the one act of the moment only when the register already holds the heat;
		# otherwise a deliberate choice, kept under Recall
		hold_group = None if doc.status in HELD and stoppable else _("Recall")
		acts.append({
			"id": "hold", "label": _("Hold what is still on the shelf"), "icon": "shield-alert", "theme": "red",
			"group": hold_group,
			"method": "stock.stock.report.recall_simulation.recall_simulation.quarantine_what_is_on_the_shelf",
			"args": {"filters": {"heat": doc.name}},
			"fields": [{"fieldname": "reason", "label": _("Why"), "fieldtype": "Small Text", "reqd": 1,
						"default": _("Heat {0} under investigation").format(doc.name)}],
			"description": _("Every lot of this heat still Released or waiting for inspection goes to Quarantine. What is already built in is a telephone call, not a click."),
			"success": _("Lots held"),
			"disabled": None if stoppable else _("Nothing of this heat is on the shelf in a state a hold can stop."),
		})
	if frappe.has_permission(HEAT, "write", doc):
		from materials.material_certifications.doctype.material_heat.material_heat import MaterialHeat

		allowed = MaterialHeat.ALLOWED_STATUS_TRANSITIONS.get(doc.status, set())
		for status, label, icon, theme in HEAT_ACTS:
			if status not in allowed:
				continue
			act = {"id": f"heat_{frappe.scrub(status)}", "label": _(label), "icon": icon, "group": _("Recall"),
				   "method": "frappe.client.set_value",
				   "args": {"doctype": HEAT, "name": doc.name, "fieldname": "status", "value": status},
				   "success": _("Heat {0}").format(_w(status, HEAT))}
			if theme:
				act["theme"] = theme
			if status == "Recalled":
				act["confirm"] = _("Recall heat {0}? A recalled heat cannot come back. Its lots are not held by this: hold them with Hold what is still on the shelf.").format(doc.name)
			acts.append(act)
	mill = frappe.db.get_value("Supplier", doc.mill, "supplier_name") if doc.mill else None
	grade = _grade_names([doc.grade]).get(doc.grade) or doc.grade
	return {
		"name": doc.name, "cast": doc.cast_number, "grade": grade, "mill": mill or doc.mill, "mill_id": doc.mill,
		"produced": _d(doc.production_date), "status": doc.status, "status_label": _w(doc.status, HEAT),
		"theme": HEAT_THEME.get(doc.status, "gray"), "notes": frappe.utils.strip_html_tags(doc.notes or "").strip() or None,
		"certificates": certs, "lots": lots, "stock": _stock(),
		"built_into": _built_into(doc.name, lot_names),
		"recall": recall, "acts": acts,
		"headline": {"text": _("This heat is recalled: none of it may be used."), "theme": "red"} if doc.status == "Recalled"
		else {"text": _("This heat is quarantined in the register."), "theme": "amber"} if doc.status == "Quarantined" else None,
	}


# ── Certificates ─────────────────────────────────────────────────────────────

CERT_VIEWS = (("verify", N_("To verify")), ("match", N_("To match")), ("valid", N_("Valid")),
			  ("out", N_("Expired or revoked")))


@frappe.whitelist()
def certificates(view: str = "valid", search: str | None = None) -> dict:
	"""The mill certificates: to verify (no PDF, or not checked), to tie to the
	lots of their heats, valid, out of force — each with the heats it covers and
	the lots that carry it."""
	frappe.has_permission(CERT, "read", throw=True)
	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = [["certificate_number", "like", like], ["name", "like", like], ["issuing_body", "like", like]]
	every = frappe.get_list(CERT, or_filters=or_filters,
							fields=["name", "certificate_number", "certificate_type", "certificate_date", "status",
									"supplier", "issuing_body", "attachment", "verified", "expiry_date"],
							order_by="certificate_date desc", limit_page_length=1000)
	names = [c.name for c in every]
	coverage = _coverage(names)
	carrying = _carrying(names)
	unlinked = _unlinked(names, coverage, carrying) if _stock() else {}
	tests = {
		"verify": lambda c: c.status == "Valid" and not c.verified,
		"match": lambda c: c.status == "Valid" and bool(unlinked.get(c.name)),
		"valid": lambda c: c.status == "Valid",
		"out": lambda c: c.status in ("Expired", "Revoked"),
	}
	counts = {k: len([c for c in every if t(c)]) for k, t in tests.items()}
	suppliers = _supplier_names([c.supplier for c in every])
	rows = []
	for c in every:
		if not (tests.get(view) or tests["valid"])(c):
			continue
		heats_ = coverage.get(c.name, [])
		badges = []
		if c.status != "Valid":
			badges.append({"label": _w(c.status, CERT), "theme": CERT_STATUS_THEME.get(c.status, "gray")})
		elif c.verified:
			badges.append({"label": _("Verified"), "theme": "green"})
		rows.append({"name": c.name, "link": {"doctype": CERT, "name": c.name}, "title": c.certificate_number or c.name,
					 "subtitle": _join(c.issuing_body or suppliers.get(c.supplier) or c.supplier, c.name),
					 "type": c.certificate_type, "date": _d(c.certificate_date),
					 "heats": ", ".join(heats_[:3]) + (f" +{len(heats_) - 3}" if len(heats_) > 3 else "") if heats_ else None,
					 "lots": len(carrying.get(c.name, ())) if _stock() else None,
					 "to_link": len(unlinked.get(c.name, ())) or None,
					 "file": bool(c.attachment), "badges": badges})
	return {"views": [{"key": k, "label": _(label), "count": counts.get(k, 0)} for k, label in CERT_VIEWS],
			"rows": rows, "stock": _stock(), "may_create": bool(frappe.has_permission(CERT, "create"))}


@frappe.whitelist()
def certificate_workspace(name: str) -> dict:
	"""A mill certificate as the inspector reads it: the document itself beside
	what it certifies — the heats it covers and their standing, the lots that
	carry it and those of its heats that should, the chemistry and the
	mechanicals as transcribed, who verified it."""
	doc = frappe.get_doc(CERT, name)
	doc.check_permission("read")
	heat_names = [r.heat for r in doc.heats_covered or [] if r.heat]
	heat_info = {h.name: h for h in frappe.get_all(HEAT, filters={"name": ["in", heat_names or [""]]},
												   fields=["name", "status", "grade"])}
	grades = _grade_names([h.grade for h in heat_info.values()])
	for h in heat_info.values():
		h.grade = grades.get(h.grade) or h.grade
	heats_ = [{"heat": r.heat, "qty": f"{_num(r.qty_covered)} {r.qty_unit or ''}".strip() if flt(r.qty_covered) else None,
			   "status": _w((heat_info.get(r.heat) or {}).get("status"), HEAT),
			   "theme": HEAT_THEME.get((heat_info.get(r.heat) or {}).get("status"), "gray"),
			   "grade": (heat_info.get(r.heat) or {}).get("grade")} for r in doc.heats_covered or [] if r.heat]
	carrying, should = [], []
	if _stock() and _can(BATCH):
		on = _carrying([doc.name]).get(doc.name, set())
		missing = _unlinked([doc.name], {doc.name: heat_names}, {doc.name: on}).get(doc.name, set())
		info = {b.name: b for b in frappe.get_list(BATCH, filters={"name": ["in", list(on | missing) or [""]]},
												   fields=["name", "batch_id", "item", "item_name", "lot_status", "heat_number",
														   "available_qty", "stock_uom", "supplier_name"],
												   limit_page_length=0)}

		def lot(n):
			b = info[n]
			return {"name": b.name, "lot": b.batch_id or b.name, "item": b.item_name or b.item, "heat": b.heat_number,
					"state": _w(b.lot_status, BATCH), "theme": LOT_THEME.get(b.lot_status, "gray"),
					"available": f"{_num(b.available_qty)} {b.stock_uom or ''}".strip()}

		carrying = [lot(n) for n in sorted(on) if n in info]
		should = [lot(n) for n in sorted(missing) if n in info]
	chemistry = [{"element": r.element_other if r.element == "Other" else r.element, "value": _num(r.value_percent),
				  "range": _range(r.spec_min, r.spec_max),
				  "ok": bool(r.within_spec) if (r.spec_min or r.spec_max) else None}
				 for r in doc.chemical_results or []]
	mechanics = [{"test": r.test_type_other if r.test_type == "Other" else _w(r.test_type, "Certificate Mechanical Result"),
				  "value": f"{_num(r.value)} {r.unit or ''}".strip(), "temperature": r.temperature,
				  "range": _range(r.spec_min, r.spec_max),
				  "ok": bool(r.within_spec) if (r.spec_min or r.spec_max) else None}
				 for r in doc.mechanical_results or []]
	pmi = [{"point": r.test_point_location, "expected": r.material_expected, "found": r.material_found,
			"result": _w(r.result, "PMI Test Point"), "ok": r.result == "Pass"} for r in doc.pmi_test_points or []]
	supplier = frappe.db.get_value("Supplier", doc.supplier, "supplier_name") if doc.supplier else None
	file = doc.attachment
	return {
		"name": doc.name, "number": doc.certificate_number or doc.name, "type": doc.certificate_type,
		"date": _d(doc.certificate_date), "status": doc.status, "status_label": _w(doc.status, CERT),
		"theme": CERT_STATUS_THEME.get(doc.status, "gray"),
		"issuer": doc.issuing_body, "supplier": supplier or doc.supplier, "laboratory": doc.testing_laboratory,
		"edition": doc.standard_edition, "third_party": bool(doc.third_party_verified),
		"expiry": _d(doc.expiry_date),
		"file": file, "pdf": bool(file and str(file).lower().split("?")[0].endswith(".pdf")),
		"verified": bool(doc.verified),
		"verified_by": frappe.db.get_value("Personnel", doc.verified_by, "full_name") if doc.verified_by and frappe.db.exists("DocType", "Personnel") else doc.verified_by,
		"verified_on": _d(doc.verification_date), "verification_remarks": doc.verification_remarks,
		"heats": heats_, "carrying": carrying, "should": should, "stock": _stock(),
		"chemistry": chemistry, "mechanics": mechanics, "pmi": pmi,
		"pmi_result": _w(doc.pmi_overall_result, CERT),
		"may_write": bool(frappe.has_permission(CERT, "write", doc)) and doc.status != "Revoked",
	}
