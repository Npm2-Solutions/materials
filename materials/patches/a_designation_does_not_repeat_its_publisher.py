"""`API-API-5CT`, `EN-EN-10028-4`, `JIS-JIS-G-3101` — thirty keys say it twice.

The key is `record_key(organization, designation)`, and thirty designations
carry the organization inside them: `API 5CT` rather than `5CT`. worgify has
`_strip_org_prefix` for exactly this and `Standard.resolve` uses it; this
autoname did not.

Nothing pointed at any of the thirty — measured across every Link into
`Material Specification`, including `Material Grade.specification`, the WPS's
two base-material specs and the qualification's base-grade selection: **zero
references, and no collision with the corrected name**. So they are renamed
rather than left as a spelling nobody can search for.

Also here, because they were found in the same sweep and are the same shape of
defect:

* **`supersedes` on `Material Specification` is dropped.** Empty on all 178
  rows, and a second supersession model beside `Standard Edition.supersedes` /
  `.superseded_by`. Design 24 dropped the identical field from the filler
  specifications with the identical note. `spec_status`, which it drove, is set
  by hand now — which is what the Withdraw action already did.
* **`Material Grade Form.notes`** — empty on all 233.
* **`Material Certificate.applicable_standard` → `standard_edition`**, the one
  name Design 28 leaves for a printing a reader is meant to see.
"""

import frappe

DT = "Material Specification"
DEAD = [(DT, "supersedes"), ("Material Grade Form", "notes")]


def execute():
	if not frappe.db.table_exists(DT):
		return

	renamed = blocked = 0
	for name, designation in frappe.db.sql(f"SELECT name, designation FROM `tab{DT}`"):
		head, _, tail = name.partition("-")
		if not tail or not tail.startswith(f"{head}-"):
			continue
		target = tail
		if frappe.db.exists(DT, target):
			# A first pass renamed the record and the fixture, still carrying the
			# doubled spelling, inserted it straight back beside the corrected
			# one. Nothing points at either — measured — so the twin goes.
			if not frappe.db.sql(
				"SELECT 1 FROM `tabMaterial Grade` WHERE specification=%s LIMIT 1", name):
				# `on_trash` refuses to delete a row with `is_standard` set, and
				# `is_standard` is set on 176 of 178 — a guard that forbids every
				# deletion forbids the corrections too. Clear it on the twin only.
				frappe.db.set_value(DT, name, "is_standard", 0, update_modified=False)
				frappe.delete_doc(DT, name, force=True, ignore_permissions=True)
				print(f"  {name} rimosso — doppione di {target}")
				continue
			blocked += 1
			print(f"  ! {name} → {target} già esistente e citato, lasciata com'è")
			continue
		# the designation is the half that carries the duplication
		clean = (designation or "").strip()
		for lead in (f"{head} ", f"{head}-", head):
			if clean.upper().startswith(lead.upper()):
				clean = clean[len(lead):].strip()
				break
		if clean and clean != designation:
			frappe.db.set_value(DT, name, "designation", clean, update_modified=False)
		frappe.rename_doc(DT, name, target, force=True, show_alert=False)
		renamed += 1
	print(f"  {renamed} chiavi non ripetono più l'editore, {blocked} bloccate")

	# `applicable_standard` was the only Link into `Standard Edition` here, and it
	# is the citation a certificate reports against — a name a reader sees.
	if "applicable_standard" in frappe.db.get_table_columns("Material Certificate"):
		columns = frappe.db.get_table_columns("Material Certificate")
		if "standard_edition" in columns:
			frappe.db.sql(
				"""UPDATE `tabMaterial Certificate` SET `standard_edition`=`applicable_standard`
				   WHERE (`standard_edition` IS NULL OR `standard_edition`='')
				     AND `applicable_standard`<>''""")
			frappe.db.commit()
			frappe.db.sql_ddl("ALTER TABLE `tabMaterial Certificate` DROP COLUMN `applicable_standard`")
			print("  Material Certificate.applicable_standard → standard_edition")

	for doctype, field in DEAD:
		if frappe.db.table_exists(doctype) and field in frappe.db.get_table_columns(doctype):
			if not frappe.get_meta(doctype).get_field(field):
				frappe.db.sql_ddl(f"ALTER TABLE `tab{doctype}` DROP COLUMN `{field}`")
				print(f"  {doctype}.{field} rimosso")
