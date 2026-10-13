# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt

"""Supplier portal — the certificates before shipping (Design 55 MA-01, board M1):
the orders addressed to the supplier, what each line must be, and the 3.1 it
sends before loading, read and judged at once. Read through
materials.supplier_portal.my_orders, which opens at require_portal_supplier()."""

import frappe

no_cache = 1


def get_context(context):
	from worgify.utils.portal import setup_portal_nav
	from worgify.utils.supplier_portal import require_portal_supplier

	context.no_cache = 1
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/supplier-certificates"
		raise frappe.Redirect
	require_portal_supplier()
	setup_portal_nav(context, "/supplier-certificates")
	from materials.supplier_portal import my_orders

	context.mine = my_orders()
	return context
