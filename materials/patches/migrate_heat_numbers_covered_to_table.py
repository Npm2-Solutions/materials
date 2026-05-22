"""Phase 18a — migrate Material Certificate.heat_numbers_covered Small Text
into Table → Material Heat Coverage rows + create Material Heat records.

Before:
  tabMaterial Certificate.heat_numbers_covered  Small Text (free-form list)

After:
  tabMaterial Certificate.heats_covered         Table → Material Heat Coverage
    (one row per heat number that the cert documents)
  tabMaterial Heat                              one row per distinct heat string
  tabMaterial Heat Coverage                     child rows hanging off the cert

The legacy heat_numbers_covered column stays in tabMaterial Certificate for
safety — Frappe doesn't auto-drop unreferenced columns. A future cleanup
patch can drop it once verified across all live sites. Until then this
patch is idempotent: it only runs against rows where heat_numbers_covered
has content AND the cert has no heats_covered rows yet.

String parsing splits on newline / comma / semicolon and trims whitespace.
Duplicate heat strings within one cert collapse to one Material Heat Coverage
row. Heat numbers shared across multiple certs map to the SAME Material Heat
record (heat_number is the PK).
"""

import re

import frappe


def execute():
	if not frappe.db.table_exists("Material Certificate"):
		return
	if not frappe.db.table_exists("Material Heat") or not frappe.db.table_exists("Material Heat Coverage"):
		# DocType sync hasn't materialized the new DocTypes — try-fail-skip safely.
		return
	# Skip if the legacy column was already dropped (idempotent re-run on cleaned site)
	cols = frappe.db.get_table_columns("Material Certificate")
	if "heat_numbers_covered" not in cols:
		return

	candidates = frappe.db.sql(
		"""
		SELECT name, heat_numbers_covered
		FROM `tabMaterial Certificate`
		WHERE heat_numbers_covered IS NOT NULL AND heat_numbers_covered != ''
		""",
		as_dict=True,
	)
	if not candidates:
		return

	heats_created = 0
	cov_inserted = 0
	for cert in candidates:
		# Skip if this cert already has heats_covered child rows (idempotent)
		already = frappe.db.count("Material Heat Coverage", {"parent": cert.name})
		if already:
			continue

		# Parse the free-form list — split on newline / comma / semicolon, trim
		heat_strs = [s.strip() for s in re.split(r"[,\n;]+", cert.heat_numbers_covered) if s.strip()]
		# Dedupe within one cert
		seen = []
		for h in heat_strs:
			if h not in seen:
				seen.append(h)

		for heat in seen:
			# Ensure the Material Heat row exists (heat_number is the PK)
			if not frappe.db.exists("Material Heat", heat):
				doc = frappe.new_doc("Material Heat")
				doc.heat_number = heat
				doc.status = "Active"
				doc.flags.ignore_permissions = True
				doc.flags.ignore_links = True
				doc.insert(ignore_permissions=True)
				heats_created += 1
			# Insert the Coverage child row (raw insert — child docs don't auto-name well via doc.insert)
			frappe.get_doc({
				"doctype": "Material Heat Coverage",
				"parenttype": "Material Certificate",
				"parent": cert.name,
				"parentfield": "heats_covered",
				"heat": heat,
			}).insert(ignore_permissions=True)
			cov_inserted += 1

	frappe.db.commit()
	print(
		f"  migrate_heat_numbers_covered_to_table: "
		f"created {heats_created} Material Heat records, "
		f"inserted {cov_inserted} Material Heat Coverage rows."
	)
