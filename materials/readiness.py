# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt

"""What the material register knows about a heat, for "can it be used?" (Design
43): a heat recalled is never used, one quarantined is held until released."""

import frappe
from frappe import _

from worgify.readiness import NOT_USABLE, SUSPENDED, USABLE, within

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


CERTIFICATE = {"Valid": USABLE, "Expired": NOT_USABLE, "Revoked": NOT_USABLE}


def certificate(name, on, for_what):
	"""A certificate certifies while Valid and not past its date — its status is
	not refreshed by a daily job, so the date is read here too."""
	c = frappe.db.get_value("Material Certificate", name, ["status", "expiry_date"], as_dict=True)
	if not c or not c.status:
		return []
	status = CERTIFICATE.get(c.status, NOT_USABLE)
	if status == USABLE and not within(on, None, c.expiry_date):
		status = NOT_USABLE
	return [{
		"status": status, "layer": "certificate", "label": _("Material certificate"), "competence": _("Certificate"),
		"reason": _("Certificate status: {0}").format(_(c.status)), "until": c.expiry_date,
		"ref": {"doctype": "Material Certificate", "name": name},
	}]
