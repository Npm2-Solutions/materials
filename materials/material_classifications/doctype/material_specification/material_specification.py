# Copyright (c) 2025, WeldTrack and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from worgify.utils.display_name import pretty_spec_code, slugify


class MaterialSpecification(Document):
    """
    Material Specification DocType - The document/standard level.

    Examples: SA-516, EN 10025-2, A516 (ASTM)

    This is the first level of the two-level material hierarchy:
    1. Material Specification - the document (SA-516)
    2. Material Grade - the specific grade (Gr.70)

    Naming pattern: {standard}-{designation}
    Examples: asme_sa_516, en_10025_2, astm_a516
    """

    def autoname(self):
        """Slug name: '{org_slug}_{slug(designation)}'.

        Example: organization 'ASME' + designation 'SA-516' → 'ASME-SA-516'.
        Falls back to slug of designation alone if the Standard is unset.
        """
        from worgify.utils.record_key import owned_key

        # The publisher comes from the DOCUMENT. This read `Standard Edition`,
        # which the field stopped pointing at in Design 22 phase 3 — so every new
        # specification would have been named without its organisation.
        org = ""
        if self.standard:
            org = frappe.db.get_value("Standard", self.standard, "organization") or ""
        self.name = owned_key(self, org, self.designation)

    def before_save(self):
        # Computed human label for dropdowns + lists.
        # Display = canonical spec code ('ASME SA-516') — the spec IS the standard,
        # no need for a — separator. Falls back to slug-pretty when designation empty.
        self.display_name = pretty_spec_code(self.designation, self.name)

    def validate(self):
        if not self.designation:
            frappe.throw("Specification designation is required")


    # `_guard_supersedes_cycle` and `update_spec_status` went with the
    # `supersedes` Link they served. It was a second supersession model beside
    # `Standard Edition.supersedes` / `.superseded_by`, empty on all 178 rows —
    # the same duplicate Design 24 dropped from the filler specifications, whose
    # note read: "`Standard Edition.supersedes` already models it."

    @frappe.whitelist()
    def withdraw(self):
        """Manually withdraw this specification."""
        self.spec_status = "Withdrawn"
        self.save()
        frappe.msgprint(
            _("Specification {0} has been withdrawn.").format(self.name),
            indicator="red",
        )

