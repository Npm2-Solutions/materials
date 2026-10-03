# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt

"""What the material register knows about a heat, for "can it be used?" (Design
43): a heat recalled is never used, one quarantined is held until released."""

import frappe
from frappe import _

from worgify.readiness import NOT_USABLE, SUSPENDED, USABLE

STATUS = {"Active": USABLE, "Released": USABLE, "Quarantined": SUSPENDED, "Recalled": NOT_USABLE}


def heat(name, on, for_what):
	status = frappe.db.get_value("Material Heat", name, "status")
	if not status:
		return []
	return [{
		"status": STATUS.get(status, NOT_USABLE), "layer": "state", "label": _("Heat"), "competence": _("Heat"),
		"reason": _("Heat status: {0}").format(_(status)), "ref": {"doctype": "Material Heat", "name": name},
		"as_of_supported": False,
	}]
