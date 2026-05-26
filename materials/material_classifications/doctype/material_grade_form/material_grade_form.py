# Copyright (c) 2025, WeldTrack and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class MaterialGradeForm(Document):
    """
    Child table for Base Material Grade product form variations.

    The same grade can be available in multiple forms with different
    thickness/diameter limits:
    - SA-516 Gr.70 Plate: 6mm - 200mm
    - SA-516 Gr.70 Sheet: 1mm - 6mm
    """
    pass
