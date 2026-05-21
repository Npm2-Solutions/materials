# Copyright (c) 2025, WeldTrack and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class BaseMaterialSpecificationLink(Document):
    """
    Child table for linking equivalent Base Material Specifications.
    Used for cross-standard equivalence (SA-516 = A516 = P355).
    """
    pass
