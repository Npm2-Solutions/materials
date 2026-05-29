# Copyright (c) 2026, NPM2 Solutions Srl and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from materials.material_certifications.doctype.material_certificate.material_certificate import (
	MaterialCertificate,
)


EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


def _new_cert(**kwargs):
	"""Build an unsaved Material Certificate for pure controller-logic tests."""
	doc = frappe.new_doc("Material Certificate")
	doc.certificate_number = kwargs.get("certificate_number", "TEST-MCERT-001")
	doc.certificate_type = kwargs.get("certificate_type", "EN 10204 3.1")
	doc.certificate_date = kwargs.get("certificate_date", nowdate())
	for k, v in kwargs.items():
		setattr(doc, k, v)
	return doc


class IntegrationTestMaterialCertificate(IntegrationTestCase):
	"""Controller-logic tests for Material Certificate.

	These cover the certificate's documentary/lifecycle responsibilities only.
	The incoming-acceptance verdict lives on stock's Material Inspection Request,
	not here (see guides/01-ecosystem/12), so there is no validation_status to test.
	"""

	# --- _check_within_spec (pure static logic) ---

	def test_within_spec_no_limits_passes(self):
		self.assertEqual(MaterialCertificate._check_within_spec(5.0, None, None), 1)

	def test_within_spec_below_min_fails(self):
		self.assertEqual(MaterialCertificate._check_within_spec(0.5, 1.0, 2.0), 0)

	def test_within_spec_above_max_fails(self):
		self.assertEqual(MaterialCertificate._check_within_spec(3.0, 1.0, 2.0), 0)

	def test_within_spec_inside_passes(self):
		self.assertEqual(MaterialCertificate._check_within_spec(1.5, 1.0, 2.0), 1)

	# --- update_status (lifecycle only) ---

	def test_status_valid_when_no_expiry(self):
		doc = _new_cert()
		doc.update_status()
		self.assertEqual(doc.status, "Valid")

	def test_status_valid_when_future_expiry(self):
		doc = _new_cert(expiry_date=add_days(nowdate(), 30))
		doc.update_status()
		self.assertEqual(doc.status, "Valid")

	def test_status_expired_when_past_expiry(self):
		doc = _new_cert(expiry_date=add_days(nowdate(), -1))
		doc.update_status()
		self.assertEqual(doc.status, "Expired")

	def test_status_revoked_is_terminal(self):
		doc = _new_cert(status="Revoked", expiry_date=add_days(nowdate(), -1))
		doc.update_status()
		self.assertEqual(doc.status, "Revoked")  # revoked is not overwritten by expiry

	# --- validate_spec_ranges ---

	def test_spec_range_inverted_throws(self):
		doc = _new_cert()
		doc.append("chemical_results", {
			"element": "C", "value_percent": 0.2, "spec_min": 2.0, "spec_max": 1.0,
		})
		with self.assertRaises(frappe.ValidationError):
			doc.validate_spec_ranges()

	def test_spec_range_valid_passes(self):
		doc = _new_cert()
		doc.append("chemical_results", {
			"element": "C", "value_percent": 0.2, "spec_min": 0.1, "spec_max": 0.25,
		})
		doc.validate_spec_ranges()  # should not raise

	# --- validate_pmi_fields ---

	def test_pmi_overall_pass(self):
		doc = _new_cert(certificate_type="PMI Report")
		doc.append("pmi_test_points", {"test_point_location": "A", "result": "Pass"})
		doc.append("pmi_test_points", {"test_point_location": "B", "result": "Pass"})
		doc.validate_pmi_fields()
		self.assertEqual(doc.pmi_overall_result, "Pass")

	def test_pmi_overall_fail_when_any_fail(self):
		doc = _new_cert(certificate_type="PMI Report")
		doc.append("pmi_test_points", {"test_point_location": "A", "result": "Pass"})
		doc.append("pmi_test_points", {"test_point_location": "B", "result": "Fail"})
		doc.validate_pmi_fields()
		self.assertEqual(doc.pmi_overall_result, "Fail")

	def test_pmi_overall_conditional_when_inconclusive(self):
		doc = _new_cert(certificate_type="PMI Report")
		doc.append("pmi_test_points", {"test_point_location": "A", "result": "Inconclusive"})
		doc.validate_pmi_fields()
		self.assertEqual(doc.pmi_overall_result, "Conditional")
