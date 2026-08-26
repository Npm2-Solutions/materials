"""Four material specifications were filed under a standard that is not theirs.

`JIS G 3106` (rolled steels for **welded** structure), `G 3454` (carbon steel
pipes for pressure service), `G 3458` (alloy steel pipes) and `G 4304`
(hot-rolled **stainless** plate) all pointed at `JIS G 3101` — rolled steels for
general structure. A stainless plate specification filed under a carbon
structural steel standard answers "which standard governs this material" with
the wrong document, and nothing objected because a Link only checks that its
target exists.

The cause is visible in the data: one `Standard` was seeded from the first
specification and every other specification was pointed at it. The correction is
not a guess — **each specification already carries its own designation and its
own title**, which is exactly what a document record needs. Asking the record
beside it is the same rule that resolved the arithmetic family from the publisher
and the current edition from the document.

No editions are created. A document we know exists but hold no printing of is a
true statement, and the book level exists precisely so it can be made: inventing
a year to fill the gap would be the only dishonest move available here.
"""

import frappe

#: specification -> the JIS document it actually names, per its own designation.
MISFILED = ("jis_g3106", "jis_g3454", "jis_g3458", "jis_g4304")


def execute():
	if not frappe.db.exists("DocType", "Standard") or not frappe.db.table_exists("Material Specification"):
		return

	from worgify.normative.doctype.standard.standard import resolve

	fixed = 0
	for name in MISFILED:
		spec = frappe.db.get_value(
			"Material Specification", name,
			["designation", "title", "standard"], as_dict=True,
		)
		if not spec or not spec.designation:
			continue
		book = resolve("JIS", spec.designation, seed={
			"domain": frappe.db.get_value("Standard", spec.standard, "domain") if spec.standard else None,
			"title": spec.title,
		})
		if not book or book == spec.standard:
			continue
		frappe.db.set_value("Material Specification", name, "standard", book, update_modified=False)
		print("    {0}: {1} -> {2}".format(name, spec.standard, book))
		fixed += 1

	frappe.db.commit()
	print("  {0} specification(s) now name their own standard".format(fixed))
