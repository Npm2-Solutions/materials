# Copyright (c) 2025, WeldTrack and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from optisuites.utils.display_name import pretty_spec_code, slugify


class MaterialSpecification(Document):
    """
    Base Material Specification DocType - The document/standard level.

    Examples: SA-516, EN 10025-2, A516 (ASTM)

    This is the first level of the two-level base material hierarchy:
    1. Base Material Specification - the document (SA-516)
    2. Base Material Grade - the specific grade (Gr.70)

    Naming pattern: {standard}-{designation}
    Examples: ASME-SA-516, EN-10025-2, ASTM-A516
    """

    def autoname(self):
        """Slug name: '{org_slug}_{slug(designation)}'.

        Example: organization 'ASME' + designation 'SA-516' → 'asme_sa_516'.
        Falls back to slug of designation alone if the Standard is unset.
        """
        org = ""
        if self.standard:
            org = frappe.db.get_value("Standard", self.standard, "organization") or ""
        desig = slugify(self.designation)
        if org:
            self.name = f"{slugify(org)}_{desig}"
        else:
            self.name = desig

    def before_save(self):
        # Computed human label for dropdowns + lists.
        # Display = canonical spec code ('ASME SA-516') — the spec IS the standard,
        # no need for a — separator. Falls back to slug-pretty when designation empty.
        self.display_name = pretty_spec_code(self.designation, self.name)

    def validate(self):
        if not self.designation:
            frappe.throw("Specification designation is required")
        self.update_spec_status()

    def update_spec_status(self):
        """Auto-compute spec_status based on supersedes link."""
        if self.spec_status == "Withdrawn":
            return  # Withdrawn is set manually via button
        if self.supersedes:
            self.spec_status = "Superseded"
        else:
            self.spec_status = "Active"

    @frappe.whitelist()
    def withdraw(self):
        """Manually withdraw this specification."""
        self.spec_status = "Withdrawn"
        self.save()
        frappe.msgprint(
            _("Specification {0} has been withdrawn.").format(self.name),
            indicator="red",
        )

    def on_trash(self):
        """Prevent deletion of system standard records."""
        if self.is_standard:
            frappe.throw(
                _("Cannot delete system standard '{0}'. This base material specification is required by the system.").format(self.name),
                title=_("Deletion Not Allowed")
            )
