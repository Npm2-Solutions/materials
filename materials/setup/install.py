"""Install/uninstall hooks for materials."""

import os

import frappe


def after_install():
	_sync_sidebar_and_icon_files()
	_compose_homes()
	order_requirements_field()
	steel_kept_field()


def after_migrate():
	_sync_sidebar_and_icon_files()
	_compose_homes()
	order_requirements_field()
	steel_kept_field()


def steel_kept_field():
	"""Where stock is installed, a place may keep one family of steel only (Design 55
	MA-11, materials.separation): the metal's field on the warehouse."""
	if not frappe.db.exists("DocType", "Warehouse"):
		return
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields({"Warehouse": [
		{"fieldname": "steel_kept", "fieldtype": "Select", "label": "Keeps only",
		 "options": "\nStainless steel only\nCarbon and low-alloy steel only", "insert_after": "zone_purpose",
		 "description": "Stainless steel and carbon steel kept apart: a movement that would put the other kind here is refused"},
	]}, update=True)


def order_requirements_field():
	"""Where stock is installed, the order carries the metal's technical requirements
	(Design 55 MA-01): grade, document, impact at temperature, CEV, PMI — what the
	supplier received and what its certificates are checked against. The field is
	materials': stock's order says what is bought, the metal says what it must be
	(stock's rule: each trade contributes its fields from its own app)."""
	if not frappe.db.exists("DocType", "Material Purchase Order"):
		return
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields({"Material Purchase Order": [
		{"fieldname": "technical_requirements_section", "fieldtype": "Section Break", "label": "Technical requirements",
		 "insert_after": "items", "collapsible": 0, "allow_on_submit": 1},
		{"fieldname": "technical_requirements", "fieldtype": "Table", "options": "Material Order Requirement",
		 "label": "Technical requirements", "insert_after": "technical_requirements_section", "allow_on_submit": 1,
		 "description": "What the supplier receives with the order, and what its certificates are checked against"},
	]}, update=True)


def _sync_sidebar_and_icon_files():
	"""Force-sync this app's nav JSONs (platform guide 14 §2).

	materials shipped nav JSONs but NO install hooks at all (found 2026-07-13 while
	fixing the desk icons): frappe never re-imported them on migrate, so every edit
	stayed dead on disk while the DB kept the auto-generated record.
	"""
	from frappe.modules.import_file import import_file_by_path

	app_path = frappe.get_app_path("materials")
	for folder in ("workspace_sidebar", "desktop_icon"):
		dir_path = os.path.join(app_path, folder)
		if not os.path.exists(dir_path):
			continue
		for fname in sorted(os.listdir(dir_path)):
			if fname.endswith(".json"):
				import_file_by_path(os.path.join(dir_path, fname), force=True, ignore_version=True)
	frappe.db.commit()



def before_uninstall():
	"""Remove nav records frappe's remove_app leaves behind (platform guide 14 §7)."""
	try:
		from worgify.utils.uninstall import cleanup_app_nav
	except ImportError:  # kernel app already gone — nothing left to clean with
		return

	cleanup_app_nav("materials")


def _compose_homes():
	"""The *Materials* home is composed by the kernel: this app's files are its
	baseline, stock adds the warehouse (hooks.worgify_homes, Design 41). After
	the file sync above, the composition is rebuilt."""
	try:
		from worgify.desk.homes import compose_for_app

		compose_for_app("materials")
	except Exception:
		frappe.log_error(title="desk homes: compose failed", message=frappe.get_traceback())
