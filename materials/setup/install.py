"""Install/uninstall hooks for materials."""


def before_uninstall():
	"""Remove nav records frappe's remove_app leaves behind (platform guide 14 §7)."""
	try:
		from optisuites.utils.uninstall import cleanup_app_nav
	except ImportError:  # kernel app already gone — nothing left to clean with
		return

	cleanup_app_nav("materials")
