# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class MaterialHeat(Document):
	"""Material Heat — a single mill pour, identified by heat_number.

	The heat_number IS the primary key (see autoname='field:heat_number' in
	the JSON), so existing free-text heat number strings from legacy Data
	columns map naturally onto Material Heat rows on migration.
	"""

	# Governed status transitions. Recalled is terminal (EN 10204 §4
	# chain-of-custody: a recalled heat cannot be silently reinstated).
	ALLOWED_STATUS_TRANSITIONS = {
		"Active": {"Released", "Quarantined", "Recalled"},
		"Released": {"Quarantined", "Recalled"},
		"Quarantined": {"Active", "Released", "Recalled"},
		"Recalled": set(),
	}

	def validate(self):
		self._guard_status_transition()
		if not self.mill:
			# The JSON description has long promised this warning; deliver it.
			frappe.msgprint(
				_("No mill (manufacturer) recorded for this heat — EN 10204 traceability is incomplete."),
				indicator="orange", alert=True,
			)

	def _guard_status_transition(self):
		before = self.get_doc_before_save()
		if not before or not before.status or before.status == self.status:
			return
		if self.status not in self.ALLOWED_STATUS_TRANSITIONS.get(before.status, set()):
			frappe.throw(
				_("Cannot change Material Heat status from {0} to {1}.").format(
					before.status, self.status
				),
				title=_("Invalid Status Transition"),
			)
