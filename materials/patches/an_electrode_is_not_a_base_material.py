# Copyright (c) 2026, NPM2 Solutions and contributors
# For license information, please see license.txt
"""E7018 was filed as a steel plate, and the batch that holds it knew nothing.

The materials demo created four records so that a consumable could carry an
EN 10204 3.1 certificate:

    Material Specification   A5.1        A5.18
    Material Grade           E7018       ER70S-6
    Material Heat            EB-2026-0453  ER-2026-1187

An electrode is not a base material. It is classified by **F-Number**, not by
P-Number, and both of these already exist where they belong — `AWS-A5.1--E7018`
and `ASME-SFA-5.1--E7018` in weldcore's `Filler Metal Classification`, carrying
`ASME-F-4`. A `Material Grade` for them can never be assigned a P-Number, so
they sat permanently blank in the overlay that classifies base metal.

**And the real damage is the other end.** stock holds `Batch LOT-E7018-001` for
item `E7018-3.2`, with a `certificates` table built for exactly this — and it
was **empty**, on both consumable lots. The MTR hung off an invented heat
instead. The batch of electrodes did not know its own certificate, which is the
one link an auditor follows.

So the certificate moves to the batch, and the impersonation goes. Measured
before: `Material Certificate` requires only its number, type and date —
`heats_covered` is not mandatory, which is why the heat was never needed.

Nothing else pointed at any of the six records.
"""

import frappe

SPECS = ("A5.1", "A5.18")
GRADES = ("A5.1--E7018", "A5.18--ER70S-6")
#: heat → the stock batch that actually holds those goods
HEATS = {"EB-2026-0453": "LOT-E7018-001", "ER-2026-1187": "LOT-ER70S-001"}


def execute():
	if not frappe.db.table_exists("Material Heat"):
		return

	moved = 0
	for heat, batch in HEATS.items():
		if not frappe.db.exists("Material Heat", heat):
			continue
		for cert in frappe.db.sql_list(
			"SELECT parent FROM `tabMaterial Heat Coverage` WHERE heat=%s", heat):
			if frappe.db.table_exists("Batch") and frappe.db.exists("Batch", batch):
				if not frappe.db.exists("Mill Test Certificate",
										{"parenttype": "Batch", "parent": batch, "certificate": cert}):
					doc = frappe.get_doc("Batch", batch)
					doc.append("certificates", {
						"certificate": cert,
						"certificate_type": frappe.db.get_value(
							"Material Certificate", cert, "certificate_type"),
						"certificate_number": frappe.db.get_value(
							"Material Certificate", cert, "certificate_number"),
						"is_primary": 1,
					})
					doc.flags.ignore_permissions = True
					doc.flags.ignore_mandatory = True
					doc.save()
					moved += 1
					print(f"  {cert} → Batch {batch}")
			frappe.db.delete("Material Heat Coverage", {"parent": cert, "heat": heat})
		frappe.delete_doc("Material Heat", heat, force=True, ignore_permissions=True)
		print(f"  Material Heat {heat} rimossa")

	for grade in GRADES:
		if frappe.db.exists("Material Grade", grade):
			frappe.db.set_value("Material Grade", grade, "is_standard", 0, update_modified=False)
			frappe.delete_doc("Material Grade", grade, force=True, ignore_permissions=True)
			print(f"  Material Grade {grade} rimosso")

	for spec in SPECS:
		if frappe.db.exists("Material Specification", spec):
			frappe.db.set_value("Material Specification", spec, "is_standard", 0,
								update_modified=False)
			frappe.delete_doc("Material Specification", spec, force=True, ignore_permissions=True)
			print(f"  Material Specification {spec} rimossa")

	print(f"  {moved} certificati ora appesi al lotto che tiene la merce")
