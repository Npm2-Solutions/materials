# Copyright (c) 2025, NPM2 Solutions and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class MaterialTestCertificate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		certificate_attachment: DF.Attach | None
		certificate_date: DF.Date | None
		certificate_number: DF.Data | None
		certificate_type: DF.Literal["2.1", "2.2", "3.1", "3.2"]
		chemical_composition: DF.Text | None
		dimensions: DF.Data | None
		elongation: DF.Float
		grade: DF.Data | None
		hardness: DF.Float
		heat_number: DF.Data
		impact_value: DF.Float
		manufacturer: DF.Data | None
		material: DF.Link | None
		naming_series: DF.Literal["MTC-.YYYY.-.#####"]
		notes: DF.Text | None
		product_form: DF.Literal["", "Plate", "Pipe", "Tube", "Bar", "Fitting", "Forging"]
		reduction_area: DF.Float
		specification: DF.Data | None
		supplier: DF.Link | None
		tensile_strength: DF.Float
		yield_strength: DF.Float
	# end: auto-generated types

	pass
