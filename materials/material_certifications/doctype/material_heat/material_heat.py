# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class MaterialHeat(Document):
	"""Material Heat — a single mill pour, identified by heat_number.

	The heat_number IS the primary key (see autoname='field:heat_number' in
	the JSON), so existing free-text heat number strings from legacy Data
	columns map naturally onto Material Heat rows on migration.
	"""

	pass
