"""Rename welding-specific DocType names to domain-neutral ones.

The materials library is consumed by welding, NDT, stock, inspection, etc.
Names like "Base Material Grade" carry the welding "base vs filler" dichotomy
that the other domains don't share. This patch renames them in-place using
frappe.rename_doc — Frappe auto-renames the underlying SQL table and cascades
the new value into every Link FK that references it.

Idempotent: safe to re-run. If the old name no longer exists (already renamed)
the rename call is skipped.
"""

import frappe


RENAMES = [
	# (old_name, new_name)
	("Base Material Specification Link", "Material Specification Link"),
	("Grade Mechanical Property Set", "Material Mechanical Property"),
	("Base Material Specification", "Material Specification"),
	("Base Material Grade", "Material Grade"),
	("Grade Product Form", "Material Form"),
]


def execute():
	for old, new in RENAMES:
		if not frappe.db.exists("DocType", old):
			# Already renamed (or never existed on a fresh install). Skip.
			continue
		if frappe.db.exists("DocType", new):
			# Both rows exist — likely a half-finished prior run. Bail loudly.
			frappe.throw(
				f"Cannot rename {old!r} → {new!r}: both DocType rows exist. "
				f"Investigate before re-running."
			)
		frappe.rename_doc("DocType", old, new, force=True, merge=False)
		frappe.db.commit()
