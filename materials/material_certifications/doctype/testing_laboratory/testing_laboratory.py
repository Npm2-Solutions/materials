# Copyright (c) 2026, WeldTrack Enhancement
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from optisuites.utils.display_name import compose


class TestingLaboratory(Document):
    """
    Testing Laboratory DocType Controller

    Represents laboratories that perform mechanical testing, NDT,
    and metallurgical examination for welding procedure qualification.
    """

    def before_save(self):
        # Computed human label for dropdowns + lists.
        self.display_name = compose(self.lab_code)

    def validate(self):
        self.validate_email()
        self.validate_url()

    def validate_email(self):
        """Validate email format if provided"""
        if self.contact_email and not frappe.utils.validate_email_address(self.contact_email):
            frappe.throw(f"Invalid email address: {self.contact_email}")

    def validate_url(self):
        """Validate website URL format if provided"""
        if self.website:
            if not self.website.startswith(('http://', 'https://')):
                self.website = 'https://' + self.website
