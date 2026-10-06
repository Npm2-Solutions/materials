# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""The metal's record pages in the Worgify interface (worgify_ui, Design 48
Part 7): the material certificate (material_certificate.js), the material
specification (material_specification.js) — and what materials adds to stock's
lot.

Matching a lot with the certificates of its heat was a button on stock's lot form
calling materials' methods (`suggest_certificate_matches`, `auto_link_certificate`)
— a call in the wrong direction. Here it is materials' extension of the Batch: it
appears where materials is installed, and only there. Both directions — the lot
finds its certificates, the certificate finds its lots — are one picker each:
the candidates as checkboxes, linked in one call (`link_certificates`,
`link_lots`).

Reading the certificate PDF while judging a lot, and reviewing what extraction
read from it, are parts the interface draws by hand: `materials.certificate_viewer`
(stock's inspection request names it) and `materials.certificate_extraction`."""

import frappe
from frappe import _
from frappe.utils import flt

CERT = "Material Certificate"
CERT_METHODS = "materials.material_certifications.doctype.material_certificate.material_certificate"
RUN = "run_doc_method"  # the desk's frm.call(): a whitelisted controller method

# who may revoke (MaterialCertificate.revoke: frappe.only_for)
REVOKERS = ("STK Quality Manager", "STK Manager", "System Manager")

LOT_THEME = {"Pending Inspection": "orange", "Released": "green", "Quarantine": "red",
			 "Returned Pending Re-Inspection": "yellow", "Rejected": "gray"}


def _can(doctype, ptype="read", doc=None):
	try:
		return frappe.db.exists("DocType", doctype) and bool(frappe.has_permission(doctype, ptype, doc=doc))
	except Exception:
		return False


def _soft(fn, *args, default=None, **kwargs):
	"""A part that reads another record is dropped when it fails, never the page."""
	try:
		return fn(*args, **kwargs)
	except frappe.PermissionError:
		return default
	except Exception:
		frappe.log_error(title=f"materials.ui: {getattr(fn, '__name__', fn)}")
		return default


def _check(fieldname, label, description=None):
	out = {"fieldname": fieldname, "label": label, "fieldtype": "Check"}
	if description:
		out["description"] = description
	return out


# ── the lot (stock's Batch): Match Certificates ───────────────────────────────


def batch_page(doc):
	"""The lot's Match Certificates (batch.js, on a lot with a heat number): the
	certificates that document its heats and are not on it yet."""
	if not doc.get("heat_number") or not _can("Batch", "write", doc):
		return {}
	from materials.material_certifications.doctype.material_certificate.material_certificate import (
		suggest_certificate_matches,
	)

	matches = _soft(suggest_certificate_matches, doc.name, default=[]) or []
	fields = [_check(
		m["name"],
		" · ".join(x for x in (m.get("certificate_number") or m["name"], _(m["certificate_type"]) if m.get("certificate_type") else None,
							   _("exact match") if m.get("match_type") == "exact" else _("partial match")) if x),
		_("Heats: {0}").format(", ".join(m.get("matched_heats") or [])),
	) for m in matches]
	return {"acts": [{
		"id": "match_certificates", "label": _("Match Certificates"), "group": _("Actions"), "icon": "file-badge",
		"method": "materials.ui.link_certificates", "args": {"batch": doc.name, "certificates": {}},
		"into": "certificates", "fields": fields,
		"description": _("Certificate Matches for {0}").format(doc.get("batch_id") or doc.name),
		"success": _("Certificates linked"),
		"disabled": None if fields else _(
			"No certificate documents this lot's heat yet. Match Certificates comes back on its own once one "
			"is recorded."),
	}]}


# ── Material Certificate ──────────────────────────────────────────────────────


def _extraction_enabled():
	"""The switch is stock's (`Stock Settings.enable_certificate_extraction`, read by
	the desk and by extract_certificate_data): off where stock is absent, and off
	where the field does not exist."""
	if not frappe.db.exists("DocType", "Stock Settings"):
		return False
	if not frappe.get_meta("Stock Settings").get_field("enable_certificate_extraction"):
		return False
	return bool(frappe.db.get_single_value("Stock Settings", "enable_certificate_extraction"))


def _lots_of_heats(doc):
	"""The lots whose heat this certificate covers (the desk's Find Matching
	Batches: Batch.heat_number in the covered heats, at most 20), read as the
	person may read them, and whether each already carries it."""
	heats = [r.heat for r in doc.get("heats_covered") or [] if r.get("heat")]
	if not heats or not _can("Batch"):
		return None, []
	lots = frappe.get_list("Batch", filters={"heat_number": ["in", heats]},
						   fields=["name", "batch_id", "item", "heat_number", "lot_status"], limit=20,
						   order_by="creation desc")
	carrying = set(frappe.get_all("Mill Test Certificate", pluck="parent", filters={
		"certificate": doc.name, "parenttype": "Batch", "parent": ["in", [b.name for b in lots] or [""]]}))
	table = {
		"type": "table", "title": _("Matching Batches"), "doctype": "Batch",
		"empty": _("No matching batches found."),
		"columns": [{"key": "lot", "label": _("Lot"), "subtitle": "item"},
					{"key": "heat", "label": _("Heat")},
					{"key": "status", "label": _("Status"), "type": "status"},
					{"key": "linked", "label": _("Linked"), "type": "status", "width": "7rem"}],
		"rows": [{"name": b.name, "lot": b.batch_id or b.name, "item": b.item, "heat": b.heat_number,
				  "status": _(b.lot_status) if b.lot_status else None,
				  "linked": _("Yes") if b.name in carrying else _("No"),
				  "__themes": {"status": LOT_THEME.get(b.lot_status, "gray"),
							   "linked": "green" if b.name in carrying else "gray"}} for b in lots],
	}
	return table, [b for b in lots if b.name not in carrying]


def certificate_page(doc):
	acts, overview, tabs = [], [], []
	label = doc.get("certificate_number") or doc.name

	if doc.status != "Revoked" and set(REVOKERS) & set(frappe.get_roles()) and _can(CERT, "write", doc):
		acts.append({"id": "revoke", "label": _("Revoke"), "group": _("Actions"), "icon": "ban", "theme": "red",
					 "method": RUN, "args": {"dt": CERT, "dn": doc.name, "method": "revoke"},
					 "confirm": _("Revoke certificate {0}? This cannot be undone.").format(label)})

	if doc.get("heats_covered"):
		table, unlinked = _soft(_lots_of_heats, doc, default=(None, [])) or (None, [])
		if table:
			overview.append(table)
			writable = [b for b in unlinked if _can("Batch", "write", b.name)]
			acts.append({
				"id": "find_batches", "label": _("Find Matching Batches"), "icon": "link",
				"method": "materials.ui.link_lots", "args": {"certificate": doc.name, "lots": {}}, "into": "lots",
				"fields": [_check(b.name, " · ".join(x for x in (b.batch_id or b.name, b.item, b.heat_number,
																  _(b.lot_status) if b.lot_status else None) if x))
						   for b in writable],
				"description": _("The lots whose heat this certificate covers, and that do not carry it yet."),
				"success": _("Linked"),
				"disabled": None if writable else (
					_("Every lot of these heats already carries this certificate.") if table["rows"] else
					_("No lot carries a heat this certificate covers. It comes back on its own once one does.")),
			})

	if doc.get("attachment") and _extraction_enabled() and _can(CERT, "write", doc):
		tabs.append({"id": "extract", "label": _("Extract from PDF"), "component": "materials.certificate_extraction",
					 "props": {"certificate": doc.name, "file_url": doc.attachment,
							   "read": f"{CERT_METHODS}.extract_certificate_data",
							   "apply": "materials.ui.apply_extracted_results"}})

	return {"acts": acts, "overview": overview, "tabs": tabs}


# ── Material Specification ────────────────────────────────────────────────────


def specification_page(doc):
	if doc.get("spec_status") == "Withdrawn" or not _can("Material Specification", "write", doc):
		return {}
	return {"acts": [{
		"id": "withdraw", "label": _("Withdraw", context="Material Specification"), "group": _("Actions"),
		"icon": "archive", "method": RUN, "args": {"dt": "Material Specification", "dn": doc.name, "method": "withdraw"},
		"confirm": _("Withdraw specification {0}?").format(doc.get("display_name") or doc.name),
	}]}


OBJECTS = {
	"Material Certificate": {"page": certificate_page},
	"Material Specification": {"page": specification_page},
	# stock's lot, where stock is installed (nothing asks for it otherwise)
	"Batch": {"page": batch_page},
}


# ── one call where the desk took several ──────────────────────────────────────


def _picked(values):
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	return [name for name, on in values.items() if on and str(on) not in ("0", "false", "False")]


@frappe.whitelist()
def link_certificates(batch, certificates=None):
	"""Match Certificates: link each certificate ticked to the lot
	(auto_link_certificate, which checks the lot may be written)."""
	from materials.material_certifications.doctype.material_certificate.material_certificate import (
		auto_link_certificate,
	)

	picked = _picked(certificates)
	if not picked:
		frappe.throw(_("Please select certificates to link."))
	for certificate in picked:
		auto_link_certificate(batch, certificate)
	return {"message": _("Certificates linked")}


@frappe.whitelist()
def link_lots(certificate, lots=None):
	"""Find Matching Batches: link the certificate to each lot ticked."""
	from materials.material_certifications.doctype.material_certificate.material_certificate import (
		auto_link_certificate,
	)

	frappe.has_permission(CERT, "read", doc=certificate, throw=True)
	picked = _picked(lots)
	if not picked:
		frappe.throw(_("Choose at least one lot."))
	for lot in picked:
		auto_link_certificate(lot, certificate)
	return {"message": _("Linked to {0} lot(s)").format(len(picked))}


def _option(doctype, fieldname, value):
	"""A value the Select offers, or Other — the doctype's own way to say an
	unlisted one (element_other / test_type_other)."""
	options = (frappe.get_meta(doctype).get_field(fieldname).options or "").split("\n")
	return (value, None) if value in options else ("Other", value)


@frappe.whitelist()
def apply_extracted_results(certificate, chemical=None, mechanical=None):
	"""The extraction review's Apply: the chemistry and the mechanicals the person
	kept, added to the certificate's tables (the desk added them to the open form
	for the person to save)."""
	doc = frappe.get_doc(CERT, certificate)
	doc.check_permission("write")
	chemical = frappe.parse_json(chemical) if isinstance(chemical, str) else (chemical or [])
	mechanical = frappe.parse_json(mechanical) if isinstance(mechanical, str) else (mechanical or [])
	if not (chemical or mechanical):
		frappe.throw(_("No data could be extracted from the PDF."))
	for row in chemical:
		element, other = _option("Certificate Chemical Result", "element", row.get("element"))
		doc.append("chemical_results", {"element": element, "element_other": other,
										"value_percent": flt(row.get("value_percent"))})
	for row in mechanical:
		test, other = _option("Certificate Mechanical Result", "test_type", row.get("test_type"))
		doc.append("mechanical_results", {"test_type": test, "test_type_other": other,
										  "value": flt(row.get("value")), "unit": row.get("unit") or ""})
	doc.save()
	return {"message": _("Data applied: {0} chemical, {1} mechanical.").format(len(chemical), len(mechanical))}
