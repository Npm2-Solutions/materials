"""Heat number normalization + Material Heat row resolution.

Shared by per-app Phase 18b–18d migration patches that convert legacy
free-text heat_number columns into Link → Material Heat.

The dedupe is intentionally light for Phase 18 (Q4 2026 dedupe pass can
extend it). Today's rules:
  - Trim leading/trailing whitespace.
  - Reject empty strings (return None — caller leaves the column NULL).
  - Look up an existing Material Heat by exact name (MySQL VARCHAR's
    default case-insensitive collation handles 'ABC-123' / 'abc-123'
    convergence at the PK level).
  - Create a new Material Heat with status='Active' if none matches.

The function returns the canonical Material Heat name to write into the
caller's Link column.
"""

from __future__ import annotations

from typing import Optional

import frappe


def ensure_material_heat(raw: Optional[str]) -> Optional[str]:
	"""Return the canonical Material Heat name for ``raw``, creating one if
	necessary. Returns None for empty/whitespace input — caller writes NULL.

	Idempotent: re-invoking with the same string returns the same name and
	does not create a second row.
	"""
	if not raw:
		return None
	heat_number = raw.strip()
	if not heat_number:
		return None

	# Frappe.db.exists is case-insensitive for VARCHAR PKs by default — this
	# converges ABC-123 / abc-123 / Abc-123 on the row that was created first.
	existing = frappe.db.exists("Material Heat", heat_number)
	if existing:
		return existing  # canonical-cased name as stored

	doc = frappe.new_doc("Material Heat")
	doc.heat_number = heat_number
	doc.status = "Active"
	doc.flags.ignore_permissions = True
	doc.flags.ignore_links = True
	doc.insert(ignore_permissions=True)
	return doc.name


def migrate_column(doctype: str, column: str = "heat_number") -> tuple[int, int]:
	"""Bulk-migrate one (DocType, column) — pre-create Material Heat rows
	for every distinct non-null value in the column, then UPDATE the column
	to use the canonical Material Heat name (handles case-folding).

	Returns ``(rows_touched, heats_created)``. Idempotent — values that
	already resolve to an existing Material Heat row stay unchanged.

	Caller is responsible for committing the transaction. Caller is also
	responsible for ensuring the column's fieldtype has been changed to Link
	(by the JSON schema sync); this function only touches data, not schema.
	"""
	if not frappe.db.table_exists(doctype):
		return (0, 0)
	cols = frappe.db.get_table_columns(doctype)
	if column not in cols:
		return (0, 0)

	rows = frappe.db.sql(
		f"""
		SELECT DISTINCT `{column}` AS raw
		FROM `tab{doctype}`
		WHERE `{column}` IS NOT NULL AND `{column}` != ''
		""",
		as_dict=True,
	)
	if not rows:
		return (0, 0)

	heats_created_before = frappe.db.count("Material Heat")
	updates = 0
	for r in rows:
		canonical = ensure_material_heat(r.raw)
		if canonical and canonical != r.raw:
			# Case-folded or trimmed — UPDATE the column to canonical form
			frappe.db.sql(
				f"UPDATE `tab{doctype}` SET `{column}` = %s WHERE `{column}` = %s",
				(canonical, r.raw),
			)
			updates += 1
	heats_created = frappe.db.count("Material Heat") - heats_created_before
	return (updates, heats_created)
