"""Install/uninstall hooks for materials."""

import os

import frappe


def after_install():
	_sync_sidebar_and_icon_files()


def after_migrate():
	_sync_sidebar_and_icon_files()


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
