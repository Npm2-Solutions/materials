"""The same defect, everywhere it is — eighteen more, found by scanning.

`specs_name_their_own_standard` stated the rule and then applied it to four
records typed out by hand:

> One `Standard` was seeded from the first specification and every other
> specification was pointed at it. […] Each specification already carries its
> own designation and its own title, which is exactly what a document record
> needs.

That is the rule. It was never scanned for. Eighteen specifications outside the
JIS four had the same thing done to them, and the results read worse:

    EN 10088-2   stainless sheet and plate        → EN 10025-2   structural steel
    ASTM A992    structural shapes                → ASTM A516    pressure-vessel plate
    ASTM A790    duplex stainless pipe            → ASTM A516
    API 5LC      corrosion-resistant line pipe    → API 5L
    EN 10216-5   stainless pressure tube          → EN 10025-2

A Link only checks that its target exists, so nothing objected, and the picker
on the specification list filters by exactly this field — so filtering the
library by *EN 10025-2* returned a stainless steel among the structural ones.

**Why the wrong document was reachable at all.** A `Standard Edition` creates
its document in `before_save`, and materials ships editions but shipped no
documents. So the documents that happened to have a printing in that file
existed, and the rest did not — and eighteen specifications were pointed at the
nearest one that did. `materials/fixtures/standard.json` now ships them, before
the editions and before the specifications that name them.

No editions are invented. A document we know exists but hold no printing of is a
true statement, and the book level exists so it can be made — the same sentence
the four-record patch ended on, and the reason this one does not end differently.
"""

import re

import frappe

#: A specification published INSIDE a volume genuinely names another document.
#: `SA-36` is a specification within ASME BPVC Section II Part A, and its Link
#: means *published in*, not *is* — nine rows, all correct, all left alone.
CONTAINERS = ("ASME-BPVC",)


def _norm(value):
	return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def execute():
	if not frappe.db.exists("DocType", "Standard"):
		return
	if not frappe.db.table_exists("Material Specification"):
		return

	from worgify.normative.doctype.standard.standard import resolve

	fixed = skipped = 0
	for spec in frappe.db.sql(
		"""SELECT name, designation, title, description, standard, material_category
		   FROM `tabMaterial Specification` WHERE IFNULL(standard, '') <> ''""",
		as_dict=True,
	):
		if not spec.designation:
			continue
		if spec.standard.startswith(CONTAINERS):
			continue
		if _norm(spec.name) == _norm(spec.standard):
			continue
		if _norm(spec.designation) in _norm(spec.standard):
			continue

		organization = spec.name.split("-")[0]
		book = resolve(organization, spec.designation, seed={
			"domain": frappe.db.get_value("Standard", spec.standard, "domain"),
			"title": spec.title,
			"scope_description": spec.description or spec.title,
		})
		if not book or book == spec.standard:
			skipped += 1
			continue
		frappe.db.set_value("Material Specification", spec.name, "standard", book,
							update_modified=False)
		print(f"    {spec.name}: {spec.standard} → {book}")
		fixed += 1

	frappe.db.commit()
	print(f"  {fixed} specifiche ripuntate sul proprio documento, {skipped} non risolte")
