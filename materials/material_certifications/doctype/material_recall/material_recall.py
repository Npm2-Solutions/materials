# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate


class MaterialRecall(Document):
	"""A recall begins the same way from every door (its page's start, the heat's act, the API): one open recall
	per heat, the five branches of its task, the heat recalled, the certificate it contests marked contested
	(Design 55 MA-06, materials.recall)."""

	def before_insert(self):
		from materials.recall import BRANCHES

		if frappe.db.exists(self.doctype, {"heat": self.heat, "status": "Open"}):
			frappe.throw(_("Heat {0} already has an open recall.").format(self.heat))
		self.notice_date = self.notice_date or nowdate()
		if not self.get("branches"):
			for branch in BRANCHES:
				self.append("branches", {"branch": branch})

	def after_insert(self):
		from materials import conformity

		frappe.db.set_value("Material Heat", self.heat, "status", "Recalled")
		if self.certificate:
			c = frappe.get_doc(conformity.CERT, self.certificate)
			c.contested = 1
			c.contested_reason = self.cause_text
			c.flags.ignore_permissions = True
			c.save()
