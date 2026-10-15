# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""A recalled heat, followed to its end (Design 55 MA-06, board M6).

A recall is judged by its end: the last delivered piece reached. So it is a task
with five branches — what is on the shelf, what was cut into parts, what was
welded into joints, what was delivered, who must be told — each with the person
who closes it, and the recall closes when all are closed:

* nothing on the shelf can be used (the lots are held);
* the assemblies carrying its parts are stopped;
* the joints have the non-conformity's decision;
* the people who had to know, know.

The warehouse's lots are read where stock is installed; where the heat went
inside the structure and who must hear it are asked of the other products
through ``heat_trace_providers`` (fabrication: parts, joints, assemblies;
inspecta: the notified body and the inspection parties of the jobs' plans).

Design 49 Materials finding 4 is closed here: a lot is found by **any** heat it
carries (its own, its other heats, the heats its certificates cover), not only
by its primary one.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, formatdate, getdate, nowdate

from materials import conformity

RECALL = "Material Recall"
HEAT = "Material Heat"
BRANCHES = ("On the shelf", "Cut into parts", "Welded into joints", "Delivered", "People to tell")


def _stock():
	return bool(frappe.db.exists("DocType", "Batch"))


def lots_of_heat(heat) -> list:
	"""Every lot carrying the heat — primary, secondary, or through a certificate."""
	if not _stock():
		return []
	names = set(frappe.get_all("Batch", filters={"heat_number": heat}, pluck="name"))
	if frappe.db.exists("DocType", "Batch Heat Number"):
		names |= set(frappe.get_all("Batch Heat Number", filters={"heat_number": heat, "parenttype": "Batch"}, pluck="parent"))
	certs = frappe.get_all("Material Heat Coverage", filters={"heat": heat, "parenttype": conformity.CERT}, pluck="parent")
	if certs and frappe.db.exists("DocType", "Mill Test Certificate"):
		names |= set(frappe.get_all("Mill Test Certificate", filters={"certificate": ["in", certs], "parenttype": "Batch"},
									pluck="parent"))
	if not names:
		return []
	return frappe.get_all("Batch", filters={"name": ["in", list(names)]},
						  fields=["name", "batch_id", "item_name", "lot_status", "available_qty", "stock_uom", "is_remnant",
								  "length", "width", "thickness", "quarantine_date", "received_date", "received_qty",
								  "parent_batch", "current_warehouse"])


def _trace(heat, projects):
	context = {"projects": set(projects)}
	out = {}
	for path in frappe.get_hooks("heat_trace_providers") or []:
		try:
			got = frappe.get_attr(path)([heat], context) or {}
		except Exception:
			frappe.log_error(title=f"heat trace: {path} failed")
			continue
		for key, rows in got.items():
			out.setdefault(key, []).extend(rows)
			if key in ("parts", "assemblies"):
				context["projects"] |= {r.get("project") for r in rows if r.get("project")}
	out["projects"] = context["projects"]
	return out


def _dims(b):
	dims = [flt(b.length), flt(b.width)]
	return " × ".join(conformity.num(d, 0) for d in dims if d) or None


def _person(p):
	return frappe.db.get_value("Personnel", p, "full_name") if p else None


def _branch_rows(doc):
	return {r.branch: r for r in doc.get("branches") or []}


def _ncr_of(heat):
	if "quality" not in frappe.get_installed_apps():
		return None
	r = frappe.get_all("NCR", filters={"ncr_title": ["like", f"%{heat}%"]}, fields=["name", "status", "disposition"]
					   if frappe.get_meta("NCR").has_field("disposition") else ["name", "status"], order_by="creation desc", limit=1)
	return r[0] if r else None


@frappe.whitelist()
def workspace(name: str) -> dict:
	doc = frappe.get_doc(RECALL, name)
	doc.check_permission("read")
	heat = doc.heat
	h = frappe.db.get_value(HEAT, heat, ["grade", "mill", "status"], as_dict=True) or {}
	_s, grade_name, grade_label = conformity.standard_and_name(h.get("grade"))
	mill = frappe.db.get_value("Supplier", h.get("mill"), "supplier_name") if h.get("mill") else None
	lots = lots_of_heat(heat)
	lot_projects = set()
	if lots and frappe.get_meta("Batch").has_field("project"):
		lot_projects = {p for p in frappe.get_all("Batch", filters={"name": ["in", [b.name for b in lots]]}, pluck="project") if p}
	t = _trace(heat, lot_projects)
	rows = _branch_rows(doc)
	branches = []

	# 1. on the shelf
	shelf = [b for b in lots if flt(b.available_qty) > 0]
	usable = [b for b in shelf if b.lot_status == "Released"]
	items = [{"text": " ".join(x for x in [b.batch_id or b.name, _("offcut") if b.is_remnant else "", f"({_dims(b)})" if _dims(b) else ""] if x)
			  + ": " + (_("in quarantine since {0}").format(formatdate(b.quarantine_date, "d MMMM")) if b.lot_status == "Quarantine" and b.quarantine_date
						else _(b.lot_status)),
			  "route": {"doctype": "Batch", "name": b.name}, "held": b.lot_status != "Released"} for b in shelf]
	branches.append(_branch("On the shelf", rows, state="done" if not usable else "stop",
							line=_("everything held") if shelf and not usable
							else (_("{0} lots still usable").format(len(usable)) if usable else _("nothing on the shelf")),
							items=items, act={"id": "hold", "label": _("Hold what is on the shelf")} if usable else None))

	# 2. cut into parts
	parts = t.get("parts") or []
	assemblies = {a["name"]: a for a in t.get("assemblies") or []}
	by_asm = {}
	for p in parts:
		by_asm.setdefault(p["assembly"], []).append(p)
	stopped = all(assemblies.get(a, {}).get("on_hold") or assemblies.get(a, {}).get("shipped") for a in by_asm) if by_asm else True
	part_lines = []
	for a, ps in by_asm.items():
		ps = sorted(ps, key=lambda p: p["label"])
		label = (assemblies.get(a) or {}).get("label") or a
		welded = all(p["welded"] for p in ps)
		part_lines.append(f"{label}: " + ", ".join(p["label"] for p in ps) + (" · " + _("all already welded") if welded else ""))
	to_stop = [a for a in by_asm if not (assemblies.get(a) or {}).get("on_hold") and not (assemblies.get(a) or {}).get("shipped")]
	branches.append(_branch("Cut into parts", rows, state="nothing" if not parts else ("done" if stopped else "stop"),
							line="; ".join(part_lines) or _("no part was cut from it"),
							act={"id": "stop", "label": _("Put a stop on {0}").format(", ".join((assemblies.get(a) or {}).get("label") or a for a in to_stop)),
								 "assemblies": to_stop} if to_stop else None))

	# 3. welded into joints
	joints = t.get("joints") or []
	ncr = _ncr_of(heat) if joints else None
	decided = bool(ncr and (ncr.get("disposition") or ncr.get("status") in ("Closed", "Verified")))
	by_asm_j = {}
	for j in sorted(joints, key=lambda j: j["label"]):
		by_asm_j.setdefault(j["assembly_label"], []).append(j["label"])
	branches.append(_branch("Welded into joints", rows, state="nothing" if not joints else ("done" if decided else "decide"),
							line="; ".join(f"{', '.join(v)} " + _("of {0}").format(k) for k, v in by_asm_j.items()) or _("no joint"),
							items=[{"text": _("non-conformity {0}").format(ncr["name"]), "route": {"doctype": "NCR", "name": ncr["name"]}}] if ncr else [],
							act={"id": "ncr", "label": _("Open the non-conformity")} if joints and not ncr else None))

	# 4. delivered
	shipped = [a for a in assemblies.values() if a.get("shipped")]
	branches.append(_branch("Delivered", rows, state="done" if not shipped else "decide",
							line=_("nothing delivered: no piece of this heat has left the shop") if not shipped
							else _("delivered: {0}").format(", ".join(a["label"] for a in shipped))))

	# 5. who must know
	tell = []
	for p in sorted(t["projects"]):
		client = frappe.db.get_value("Project", p, "client")
		if client and not any(x["label"] == client for x in tell):
			tell.append({"label": client, "why": _("customer of {0}").format(", ".join(a["label"] for a in assemblies.values() if a.get("project") == p) or p)})
	for x in t.get("tell") or []:
		if not any(y["label"] == x["label"] for y in tell):
			tell.append({"label": x["label"], "why": x["why"]})
	told = rows.get("People to tell") and rows["People to tell"].closed
	branches.append(_branch("People to tell", rows, state="nothing" if not tell else ("done" if told else "decide"),
							line="; ".join(f"{x['label']} ({x['why']})" for x in tell) or _("nobody outside"),
							act={"id": "notices", "label": _("Prepare the notices")} if tell and not told and ncr else None))

	# the proposal: an offcut of the same heat answers the question cheaper than cutting
	offcut = next((b for b in lots if b.is_remnant and flt(b.available_qty) > 0), None)
	proposal = None
	cert = frappe.get_doc(conformity.CERT, doc.certificate) if doc.certificate else None
	if offcut and joints:
		proposal = {"text": _("The offcut {0} is of the same heat: a test on it says whether the parts of {1} are good, before deciding whether to cut them out.").format(
			offcut.batch_id or offcut.name, ", ".join(sorted(by_asm_j)) or "—"), "act": {"id": "test", "label": _("Ask for the test on {0}").format(offcut.batch_id or offcut.name),
																		  "lot": offcut.name}}
	closing = [
		{"text": _("nothing on the shelf can be used"), "state": "done" if not usable else "stop"},
		{"text": _("the parts are stopped on their route"), "state": "done" if stopped else "stop"},
		{"text": _("the non-conformity has its decision"), "state": "done" if (decided or not joints) else "decide"},
		{"text": _("whoever had to know, knows"), "state": "done" if (told or not tell) else "decide"},
	]
	origin = None
	if lots:
		first = sorted(lots, key=lambda b: str(b.received_date or ""))[0]
		root = next((b for b in lots if not b.parent_batch), first)
		origin = _("Lot {0}, {1} {2}, received on {3}").format(root.batch_id or root.name, conformity.num(root.received_qty, 0),
															 root.stock_uom or "", formatdate(root.received_date, "d MMMM") if root.received_date else "—")
	return {
		"name": doc.name, "heat": heat, "grade": grade_name or grade_label, "mill": mill, "status": doc.status,
		"cause": _(doc.cause) if doc.cause else "", "since": formatdate(doc.notice_date, "d MMMM") if doc.notice_date else None,
		"cause_text": doc.cause_text, "branches": branches, "proposal": proposal, "closing": closing,
		"may_close": all(c["state"] == "done" for c in closing) and doc.status == "Open",
		"origin": origin, "certificate": {"name": cert.name, "number": cert.certificate_number or cert.name,
										  "contested": bool(cert.get("contested"))} if cert else None,
		"may_write": bool(frappe.has_permission(RECALL, "write", doc=doc)) and doc.status == "Open",
	}


def _branch(kind, rows, state, line, items=None, act=None):
	row = rows.get(kind)
	words = {"done": _("done"), "stop": _("to stop"), "decide": _("to decide"), "nothing": _("nothing")}
	return {"kind": kind, "title": {"On the shelf": _("On the shelf", context="Recall branch"), "Cut into parts": _("Cut into parts"),
									"Welded into joints": _("Welded into joints"), "Delivered": _("Delivered"),
									"People to tell": _("Who to tell")}[kind],
			"state": state, "state_label": words[state], "line": line, "items": items or [], "act": act,
			"owner": _person(row.owner_person) if row else None, "owner_id": row.owner_person if row else None,
			"closed": bool(row.closed) if row else False, "row": row.name if row else None}


@frappe.whitelist(methods=["POST"])
def open_recall(heat: str, cause: str, cause_text: str, notice_date: str | None = None, certificate: str | None = None) -> dict:
	"""The recall begins: the heat is recalled, its certificate contested, and the
	task has its five branches (MaterialRecall's own insert, the same from every door)."""
	frappe.has_permission(RECALL, "create", throw=True)
	doc = frappe.get_doc({"doctype": RECALL, "heat": heat, "cause": cause, "cause_text": cause_text,
						  "notice_date": notice_date or nowdate(), "certificate": certificate})
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def set_owner(name: str, branch: str, person: str | None = None) -> dict:
	doc = frappe.get_doc(RECALL, name)
	doc.check_permission("write")
	row = _branch_rows(doc).get(branch)
	if not row:
		row = doc.append("branches", {"branch": branch})
	row.owner_person = person or None
	doc.save()
	return {"message": _("Saved.")}


@frappe.whitelist(methods=["POST"])
def act(name: str, what: str, lot: str | None = None, assemblies: str | list | None = None) -> dict:
	"""One step of the recall, done where it belongs: a lot held by the warehouse,
	an assembly stopped by fabrication, the non-conformity opened by quality, the
	test asked of incoming inspection."""
	doc = frappe.get_doc(RECALL, name)
	doc.check_permission("write")
	reason = _("heat {0} recalled ({1})").format(doc.heat, doc.name)
	if what == "hold":
		held = 0
		for b in lots_of_heat(doc.heat):
			if b.lot_status == "Released" and flt(b.available_qty) > 0:
				frappe.get_attr("stock.stock.doctype.batch.batch.quarantine_lot")(b.name, reason)
				held += 1
		_mark(doc, "On the shelf", None, None)
		return {"message": _("{0} lots held.").format(held)}
	if what == "stop":
		names = frappe.parse_json(assemblies) if isinstance(assemblies, str) else (assemblies or [])
		for a in names:
			asm = frappe.get_doc("Assembly", a)
			if asm.status not in ("On Hold", "Shipped"):
				asm.put_on_hold(reason)
		_mark(doc, "Cut into parts", "Assembly", names[0] if names else None)
		return {"message": _("{0} stopped on their route.").format(", ".join(names))}
	if what == "ncr":
		if "quality" not in frappe.get_installed_apps():
			frappe.throw(_("Non-conformities live in the quality app, which is not installed."))
		w = workspace(name)
		joints = next((b["line"] for b in w["branches"] if b["kind"] == "Welded into joints"), "")
		create = frappe.get_attr("quality.quality.utils.create_ncr")
		ncr = create(ncr_title=_("Heat {0} recalled: parts and welds").format(doc.heat)[:140], ncr_type="Material",
					 severity="Major", source="Supplier", description=f"{doc.cause_text}\n\n{joints}",
					 source_doctype=RECALL, source_document=doc.name)
		_mark(doc, "Welded into joints", "NCR", ncr, close=False)
		return {"message": _("Non-conformity {0} opened.").format(ncr), "route": {"doctype": "NCR", "name": ncr}}
	if what == "test":
		if not lot:
			frappe.throw(_("Which lot?"))
		b = frappe.db.get_value("Batch", lot, ["item", "available_qty", "stock_uom", "current_warehouse", "project"], as_dict=True)
		m = frappe.get_doc({"doctype": "Material Inspection Request", "item_code": b.item, "batch_no": lot,
							"qty": flt(b.available_qty) or 1, "stock_uom": b.stock_uom, "warehouse": b.current_warehouse,
							"request_date": nowdate(), "inspection_type": "Re-Inspection", "priority": "Urgent",
							"visual_condition_notes": _("Impact test on this offcut: heat {0} recalled ({1}). {2}").format(
								doc.heat, doc.name, doc.cause_text or "")})
		m.insert()
		out = m.name
		return {"message": _("Test asked on {0}: {1}.").format(lot, out), "route": {"doctype": "Material Inspection Request", "name": out}}
	if what == "notices":
		_mark(doc, "People to tell", None, None)
		return {"message": _("Marked as told.")}
	frappe.throw(_("Unknown step."))


def _mark(doc, branch, act_doctype, act_name, close=True):
	row = _branch_rows(doc).get(branch) or doc.append("branches", {"branch": branch})
	if act_doctype and act_name:
		row.act_doctype, row.act_name = act_doctype, act_name
	if close:
		row.closed = 1
		row.closed_on = nowdate()
	doc.save()


@frappe.whitelist(methods=["POST"])
def close(name: str) -> dict:
	w = workspace(name)
	if not w["may_close"]:
		frappe.throw(_("Not every branch is closed: {0}.").format(", ".join(c["text"] for c in w["closing"] if c["state"] != "done")))
	doc = frappe.get_doc(RECALL, name)
	doc.status = "Closed"
	doc.closed_on = nowdate()
	doc.closed_by = frappe.session.user
	doc.save()
	return {"message": _("Recall of heat {0} closed.").format(doc.heat)}


@frappe.whitelist()
def queue() -> dict:
	frappe.has_permission(RECALL, "read", throw=True)
	rows = frappe.get_list(RECALL, fields=["name", "heat", "status", "cause", "notice_date", "cause_text"], order_by="status asc, notice_date desc",
						   limit_page_length=100)
	return {"rows": [{"name": r.name, "heat": r.heat, "status": r.status, "status_label": _(r.status),
					  "cause": _(r.cause) if r.cause else "", "since": formatdate(r.notice_date, "d MMMM") if r.notice_date else "",
					  "text": r.cause_text} for r in rows],
			"may_create": bool(frappe.has_permission(RECALL, "create"))}


# ── the one list (Design 60) ─────────────────────────────────────────────────


@frappe.whitelist()
def recall_layers() -> dict:
	"""What *Richiami* adds on the complete list of the recalls (Design 60): the open ones where it opens, the closed
	ones. A recall begins from what names it — the heat, why, what was found — through its own insert."""
	frappe.has_permission(RECALL, "read", throw=True)
	from worgify.interface import lists

	chips = [lists.chip("open", _("Open", context="Recalls"), filters=[["status", "=", "Open"]]),
			 lists.chip("closed", _("Closed", context="Recalls"), filters=[["status", "=", "Closed"]])]
	return {"chips": chips, "default_chip": "open", "sort": "notice_date desc",
			"may_create": bool(frappe.has_permission(RECALL, "create"))}


@frappe.whitelist()
def recall_words(names) -> dict:
	"""The words of the recalls on screen: the heat, why and since when, what was found — and the one line of where
	its task stands (open, its branches still to end)."""
	from worgify.interface import lists

	asked = (frappe.parse_json(names) if isinstance(names, str) else list(names or []))[:500] or ["—"]
	rows = frappe.get_list(RECALL, filters=[["name", "in", asked]],
						   fields=["name", "heat", "status", "cause", "notice_date", "cause_text"], limit=500)
	out = {}
	for r in rows:
		words = lists.row(_("Heat {0}").format(r.heat), " · ".join(x for x in [_(r.cause) if r.cause else "", r.cause_text] if x),
						  mark=lists.mark("late", _("open")) if r.status == "Open" else None,
						  when=lists.day(r.notice_date) if r.notice_date else None,
						  cells={"cause": _(r.cause) if r.cause else ""},
						  sort={"when": str(r.notice_date or "")})
		words.pop("name", None)
		out[r.name] = words
	return out
