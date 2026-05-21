"""Consolidate material certificate ownership into materials.

Prior to this patch the codebase had two parallel certificate schemas:

  stock     : Material Certificate (52 fields, naming MCERT-{YYYY}-{#####})
              + Certificate Chemical Result / Mechanical Result / PMI Test Point children
              + Mill Test Certificate (4-field child table — Batch.certificates bridge)
  materials : Material Test Certificate (31 fields, unused)
              + Mill Test Certificate (22-field standalone, unused)

The rich stock schema carries live production data; the materials versions
were aspirational orphans. weldtrack's certification_export / traceability /
turnover APIs already targeted "Material Test Certificate", expecting it to
be the canonical store — so we promote stock's schema into materials under
the name "Material Certificate" and repoint weldtrack to that name.

What this patch does on existing DBs:
  1. Promote stock's 4 DocTypes (Material Certificate + 3 result children)
     to module 'Material Certifications'. Data tables and row keys untouched.
  2. Remove the orphan 'Material Test Certificate' DocType row + its empty table.
  3. Repair the 'Mill Test Certificate' DocType: the materials standalone
     wrongly hijacked the name on a prior install, leaving tabMill Test
     Certificate with a union of stock-child + materials-standalone columns.
     - Reset module to 'Stock' so stock's child-table JSON owns it.
     - Drop the surplus materials-side columns from the table.
  4. Cascade options refs: anywhere a Link/Table field options column held
     'Material Test Certificate', repoint to 'Material Certificate'.

Idempotent: each step checks state before acting.
"""

import frappe


# Stock DocTypes that move to module 'Material Certifications'
PROMOTED = [
	"Material Certificate",
	"Certificate Chemical Result",
	"Certificate Mechanical Result",
	"PMI Test Point",
]

# Materials standalone Mill Test Certificate columns we need to drop —
# these were added when the materials version hijacked the name.
MILL_TEST_CERT_ORPHAN_COLUMNS = [
	"certificate_date",
	"issuing_body",
	"attachment",
	"valid_from",
	"valid_until",
	"heat_number",
	"lot_number",
	"tensile_strength_mpa",
	"yield_strength_mpa",
	"elongation_pct",
	"impact_value_j",
	"impact_temp_c",
	"hardness_hv",
	"composition_summary",
	# Materials standalone also had section break fields that don't generate
	# table columns — listed here only for traceability, not column drops.
]


def execute():
	_promote_module_ownership()
	_drop_orphan_material_test_certificate()
	_repair_mill_test_certificate()
	_cascade_options_refs("Material Test Certificate", "Material Certificate")
	frappe.clear_cache()


def _promote_module_ownership() -> None:
	"""Update tabDocType.module for the 4 promoted DocTypes."""
	for dt in PROMOTED:
		if not frappe.db.exists("DocType", dt):
			continue
		current = frappe.db.get_value("DocType", dt, "module")
		if current != "Material Certifications":
			frappe.db.set_value("DocType", dt, "module", "Material Certifications", update_modified=False)
	frappe.db.commit()


def _drop_orphan_material_test_certificate() -> None:
	"""Remove the unused Material Test Certificate DocType + its empty table."""
	if frappe.db.exists("DocType", "Material Test Certificate"):
		# Delete child rows first
		for child in ("tabDocField", "tabDocPerm", "tabDocType Action", "tabDocType Link", "tabDocType State"):
			if frappe.db.sql(f"SHOW TABLES LIKE '{child}'"):
				frappe.db.sql(f"DELETE FROM `{child}` WHERE parent = %s", ("Material Test Certificate",))
		frappe.db.sql("DELETE FROM tabDocType WHERE name = %s", ("Material Test Certificate",))
		frappe.db.commit()
	# Drop the table if it exists (always empty per pre-patch audit)
	if frappe.db.sql("SHOW TABLES LIKE 'tabMaterial Test Certificate'"):
		row_count = frappe.db.sql("SELECT COUNT(*) FROM `tabMaterial Test Certificate`")[0][0]
		if row_count == 0:
			frappe.db.sql("DROP TABLE `tabMaterial Test Certificate`")
			frappe.db.commit()
		else:
			frappe.throw(
				f"tabMaterial Test Certificate holds {row_count} rows — manual review required."
			)


def _repair_mill_test_certificate() -> None:
	"""Reclaim Mill Test Certificate ownership for stock (child table form)."""
	# Reset module ownership so stock's child-table JSON wins on next sync
	current_mod = frappe.db.get_value("DocType", "Mill Test Certificate", "module")
	if current_mod and current_mod != "Stock":
		frappe.db.set_value("DocType", "Mill Test Certificate", "module", "Stock", update_modified=False)
		frappe.db.commit()

	# Drop materials-side surplus columns
	if not frappe.db.sql("SHOW TABLES LIKE 'tabMill Test Certificate'"):
		return
	existing_cols = {
		row[0] for row in frappe.db.sql("""
			SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
			WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tabMill Test Certificate'
		""")
	}
	to_drop = [c for c in MILL_TEST_CERT_ORPHAN_COLUMNS if c in existing_cols]
	for col in to_drop:
		try:
			frappe.db.sql(f"ALTER TABLE `tabMill Test Certificate` DROP COLUMN `{col}`")
		except Exception:
			# Column may have a default expression or be referenced; skip individually
			pass
	if to_drop:
		frappe.db.commit()


def _cascade_options_refs(old_dt: str, new_dt: str) -> None:
	"""Repoint Link / Table field 'options' from old DocType name to new."""
	for table in ("tabDocField", "tabCustom Field"):
		frappe.db.sql(
			f"UPDATE `{table}` SET options = %s WHERE options = %s",
			(new_dt, old_dt),
		)
	frappe.db.sql(
		"""UPDATE `tabProperty Setter` SET value = %s
		   WHERE property = 'options' AND value = %s""",
		(new_dt, old_dt),
	)
	frappe.db.commit()
