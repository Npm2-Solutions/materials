"""Two leftovers of a second, worse seeding pass over the JIS standards.

The library was seeded twice. One pass wrote eleven specifications with the
publisher's own designation (`JIS G 3101`) and full titles. A later, partial pass
wrote five more with the commercial shorthand (`G 3101`), truncated titles, and —
until `specs_name_their_own_standard` — every one of them pointing at the same
wrong document.

**1. Five duplicate specifications are removed.** Each names a standard that the
good pass already covers, and nothing references any of the ten: measured across
all five Link fields that target `Material Specification`, both halves of every
pair are used zero times. Keeping them means two answers to "which specification
is JIS G 3106", and only one of them carries the real title.

**2. `JIS G3115` gets its space.** JIS designations separate the division letter
from the number — the JSA titles the document `JIS G 3115:2020` — and twelve of
our thirteen JIS documents already say so. This one has no twin, so it is not a
split but a formatting defect, and correcting it means recreating the records:
`Standard` freezes `standard_number` on purpose, because a document that can
change its number is a document that can silently become a different one.

Nothing external references it, so the recreation loses nothing. The scope,
domain and year are carried across verbatim rather than re-derived.
"""

import frappe

DUPLICATE_SPECS = ("jis_g3101", "jis_g3106", "jis_g3454", "jis_g3458", "jis_g4304")
OLD_BOOK, OLD_EDITION = "jis_g3115", "jis_g3115_2020"


def execute():
	_drop_duplicate_specs()
	_give_g3115_its_space()


def _drop_duplicate_specs():
	if not frappe.db.table_exists("Material Specification"):
		return
	links = [
		f for f in frappe.get_all(
			"DocField", filters={"options": "Material Specification", "fieldtype": "Link"},
			fields=["parent", "fieldname"],
		) if frappe.db.table_exists(f.parent)
	]
	dropped = 0
	for name in DUPLICATE_SPECS:
		if not frappe.db.exists("Material Specification", name):
			continue
		# Never delete something in use, even when the survey said it was free:
		# the survey was a moment ago and this runs on every site.
		used = []
		for f in links:
			try:
				used += frappe.db.sql(
					"SELECT name FROM `tab{0}` WHERE `{1}` = %s".format(f.parent, f.fieldname),
					(name,), pluck=True,
				)
			except Exception:
				continue
		if used:
			print("    {0} is referenced by {1} record(s) — kept for review".format(name, len(used)))
			continue
		# The controller refuses to delete an `is_standard` record, and it is right
		# to: seeded reference data should not vanish by accident. It cannot tell
		# a seeded record from a DUPLICATE of one, which is what these are — so
		# the flag is cleared deliberately, here, where the reason is written
		# down, rather than the guard being weakened for everyone.
		frappe.db.set_value("Material Specification", name, "is_standard", 0, update_modified=False)
		frappe.delete_doc("Material Specification", name, force=True, ignore_permissions=True)
		dropped += 1
	frappe.db.commit()
	print("  {0} duplicate specification(s) removed".format(dropped))


def _give_g3115_its_space():
	if not frappe.db.exists("Standard Edition", OLD_EDITION):
		return
	old = frappe.get_doc("Standard Edition", OLD_EDITION)

	new = frappe.new_doc("Standard Edition")
	new.update({
		"organization": old.organization,
		"standard_number": "G 3115",
		"year": old.year,
		"edition": old.edition,
		"domain": old.domain,
		"sub_domain": old.sub_domain,
		"scope_description": old.scope_description,
		"notes": old.notes,
		"is_current": old.is_current,
		"is_active": old.is_active,
		"effective_date": old.effective_date,
		"withdrawal_date": old.withdrawal_date,
	})
	for row in old.get("applicable_sectors") or []:
		new.append("applicable_sectors", {"sector": row.sector})
	for row in old.get("normative_references") or []:
		new.append("normative_references", {
			"referenced_standard": row.referenced_standard,
			"cited_edition": row.cited_edition,
			"consulted_edition": row.consulted_edition,
			"clause": row.clause,
		})
	new.insert(ignore_permissions=True)

	moved = 0
	for f in frappe.get_all(
		"DocField", filters={"options": ["in", ["Standard", "Standard Edition"]], "fieldtype": "Link"},
		fields=["parent", "fieldname", "options"],
	):
		if not frappe.db.table_exists(f.parent) or f.parent == "Standard Edition" and f.fieldname == "standard":
			continue
		target = new.standard if f.options == "Standard" else new.name
		source = OLD_BOOK if f.options == "Standard" else OLD_EDITION
		try:
			rows = frappe.db.sql(
				"SELECT name FROM `tab{0}` WHERE `{1}` = %s".format(f.parent, f.fieldname),
				(source,), pluck=True,
			)
		except Exception:
			continue
		for name in rows:
			frappe.db.set_value(f.parent, name, f.fieldname, target, update_modified=False)
			moved += 1
	frappe.db.commit()

	frappe.delete_doc("Standard Edition", OLD_EDITION, force=True, ignore_permissions=True)
	if frappe.db.exists("Standard", OLD_BOOK):
		frappe.delete_doc("Standard", OLD_BOOK, force=True, ignore_permissions=True)
	frappe.db.commit()
	print("  {0} -> {1} ({2} link(s) moved)".format(OLD_EDITION, new.name, moved))
