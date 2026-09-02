# Copyright (c) 2025, WeldTrack and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from worgify.utils.display_name import pretty_spec_code, slugify


class MaterialGrade(Document):
    """
    Material Grade DocType - Specific grade within a specification.

    Examples: SA-516 Gr.70, EN 10025-2 S355J2

    This is the second level of the two-level base material hierarchy:
    1. Material Specification - the document (SA-516)
    2. Material Grade - the specific grade (Gr.70)

    Key features:
    - Multi-standard group assignments via child table
    - Product form variations with thickness/diameter ranges
    - Mechanical properties
    - UNS number for cross-reference

    Naming pattern: {spec}-{grade}
    Examples: asme_sa_516-70, en_10025_2-S355J2
    """

    def autoname(self):
        """Slug name: '{specification}__{slug(grade)}'.

        specification is already a slug (Link to Material Specification);
        slugify grade to handle the unusual chars some carry (spaces, dots,
        Roman numerals, dashes — e.g. 'Gr B', 'TP304L').
        """
        if self.specification and self.grade:
            from worgify.utils.record_key import owned_child_key

            self.name = owned_child_key(self, self.specification, self.grade)
        else:
            self.name = frappe.generate_hash(length=10)

    def before_save(self):
        # Display = '{Spec} Gr.{grade}' for ASME SA-/ASTM A- specs,
        # or '{Spec} {grade}' for everything else (EN material numbers
        # like 'EN 10088-2 1.4301', JIS, etc.).
        spec_dn = pretty_spec_code(
            frappe.db.get_value("Material Specification", self.specification, "display_name")
            or self.specification,
            self.specification,
        ) if self.specification else ""
        grade = (self.grade or "").strip()
        spec_lower = spec_dn.lower()
        if spec_lower.startswith(("asme sa", "astm a")) and grade and grade.isdigit():
            self.display_name = f"{spec_dn} Gr.{grade}".strip()
        else:
            self.display_name = f"{spec_dn} {grade}".strip()

    def validate(self):
        self._validate_group_assignments()

    def _validate_group_assignments(self):
        """Ensure no duplicate grouping systems in assignments.

        ``group_assignments`` is a weldcore-provided overlay Custom Field
        (the grade↔welding-group mapping is a welding-domain concern, kept out
        of materials' own schema to avoid an L1.5→L2 dependency). Use .get() so
        materials stays standalone-safe when weldcore is not installed — the
        check simply no-ops without the field.
        """
        if not self.get("group_assignments"):
            return

        systems = set()
        for row in self.get("group_assignments"):
            if row.grouping_system in systems:
                frappe.throw(
                    _("Duplicate grouping system: {0}. Each material can only "
                      "have one group per grouping system.").format(row.grouping_system)
                )
            systems.add(row.grouping_system)

    def get_group_for_system(self, system_code):
        """Get the Welding Material Group for a specific grouping system.

        Args:
            system_code: The Material Grouping System code (e.g., 'ASME-P', 'ISO-15608')

        Returns:
            Welding Material Group name or None
        """
        for row in self.get("group_assignments") or []:
            if row.grouping_system == system_code:
                return row.material_group
        return None

    def get_all_groups(self):
        """Get all Base Material Groups this grade is assigned to.

        Returns:
            dict: {system_code: base_material_group_name}
        """
        return {
            row.grouping_system: row.material_group
            for row in self.get("group_assignments") or []
        }

