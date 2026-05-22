# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class MaterialHeatCoverage(Document):
	"""Junction child table — links a parent (e.g. Material Certificate) to a
	Material Heat. Optional qty_covered + qty_unit record the portion of the
	heat the parent covers (e.g. "200 kg of heat ABC-123 are covered by this
	cert" when the heat itself is larger).
	"""

	pass
