# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt

"""What a job's requirement review asks of the metal (Design 55 X-requisiti):
an impact the grade's standard does not guarantee is to resolve — EN 10028-4
Table 4 gives 13MnNi6-3 30 J at −50 °C on transverse specimens, so a
specification asking 40 J must put it in the order — and the act writes the
job's material requirement the orders and the issues already read."""

import frappe
from frappe.tests import IntegrationTestCase

from materials import job_requirements


def _rows(impact="40 J at −50 °C, transverse"):
	return [{"key": "material.grade", "value": "EN 10028-4 13MnNi6-3 +N", "state": "To confirm"},
			{"key": "material.certificate", "value": "EN 10204 3.1", "state": "To confirm"},
			{"key": "material.impact", "value": impact, "state": "To confirm"},
			{"key": "material.cev", "value": "CEV ≤ 0,43", "state": "To confirm"}]


class TestTheReviewAsksTheMetal(IntegrationTestCase):
	def test_more_than_the_standard_guarantees_is_to_resolve(self):
		rows = job_requirements.judge(_rows(), None)
		impact = next(r for r in rows if r["key"] == "material.impact")
		self.assertEqual(impact["state"], "To resolve")
		self.assertIn("30 J", impact["note"])

	def test_what_the_standard_guarantees_needs_nothing(self):
		rows = job_requirements.judge(_rows("27 J at −50 °C, transverse"), None)
		self.assertEqual(next(r for r in rows if r["key"] == "material.impact")["state"], "To confirm")

	def test_the_act_writes_the_jobs_material_requirement(self):
		c = frappe.get_doc({"doctype": "Customer", "customer_name": f"Metal Customer {frappe.generate_hash(length=5)}"})
		c.flags.ignore_mandatory = True
		c.insert(ignore_permissions=True)
		p = frappe.get_doc({"doctype": "Project", "project_name": f"Metal job {frappe.generate_hash(length=5)}", "project_type": "Job",
							"client": c.name})
		p.flags.ignore_mandatory = True
		p.insert(ignore_permissions=True)
		review = frappe.get_doc({"doctype": "Job Requirement Review", "project": p.name,
								 "requirements": [{**r, "what": r["key"], "group": "Materials"} for r in _rows()]}).insert()
		row = next(r for r in review.requirements if r.key == "material.impact")
		self.assertTrue(job_requirements.act(review, row))
		jmr = frappe.get_doc("Job Material Requirement", {"project": p.name})
		self.assertEqual((jmr.grade, jmr.impact_energy, jmr.impact_temperature, jmr.impact_direction, jmr.cev_max, jmr.certificate_type),
						 ("EN-10028-4--13MnNi6-3", 40, -50, "Transverse", 0.43, "EN 10204 3.1"))
		self.assertEqual(jmr.source, review.name)
