# Copyright (c) 2026, NPM2 Solutions Srl and contributors
"""Materiali (Design 55 §6): the certificate read and judged against its standard
and the order (MA-03, X-certificato), the PMI against the grade's product limits
(MA-07), the lot against the job (MA-04), the recall that finds a lot by any heat
it carries (MA-06), stainless kept apart from carbon steel (MA-11), and the
supplier's portal closed to whoever is not the supplier (MA-01)."""

import frappe
import pymupdf
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from materials import certificate_reader, conformity, grade_limits as gl, pmi, recall, separation

GRADE = "EN-10028-4--13MnNi6-3"


def cert_pdf(heat="T-24131", s="0,012", printed_s="0,015", impact_at="-40", values="61 58 64", cr_mo_v=False):
	"""A 3.1 as a mill's system prints it: a header, the ladle analysis under its symbols, the tests."""
	pdf = pymupdf.open()
	p = pdf.new_page()
	p.insert_text((50, 60), "SIDERURGICA LOMBARDA  Reparto collaudo", fontsize=12)
	p.insert_text((50, 85), "INSPECTION CERTIFICATE EN 10204 - 3.1", fontsize=11)
	p.insert_text((380, 85), f"No. SL-T-{heat}", fontsize=11)
	p.insert_text((50, 110), "Product: plates 20 x 2500 x 8000", fontsize=10)
	p.insert_text((330, 110), "Quantity: 6 pcs", fontsize=10)
	p.insert_text((50, 126), "Grade: 13MnNi6-3 +N", fontsize=10)
	p.insert_text((330, 126), "Standard: EN 10028-4", fontsize=10)
	p.insert_text((50, 142), f"Heat: {heat}", fontsize=10)
	p.insert_text((330, 142), "Order: MPO-TEST", fontsize=10)
	els = ["C", "Si", "Mn", "P", "S", "Al", "Ni", "Cu"] + (["Cr", "Mo", "V"] if cr_mo_v else [])
	vals = ["0,14", "0,38", "1,30", "0,014", s, "0,032", "0,55", "0,08"] + (["0,05", "0,02", "0,01"] if cr_mo_v else [])
	mx = ["0,16", "0,50", "1,70", "0,025", printed_s, "-", "0,85", "-"] + (["-", "-", "0,05"] if cr_mo_v else [])
	for i, (e, v, m) in enumerate(zip(els, vals, mx)):
		x = 130 + i * 38
		p.insert_text((x, 180), e, fontsize=10)
		p.insert_text((x, 195), m, fontsize=10)
		p.insert_text((x, 210), v, fontsize=10)
	p.insert_text((50, 195), "max", fontsize=10)
	p.insert_text((50, 210), heat, fontsize=10)
	p.insert_text((50, 240), "Tensile test (transverse)", fontsize=10)
	p.insert_text((50, 256), "ReH 398 MPa   Rm 545 MPa   A 27 %", fontsize=10)
	p.insert_text((50, 280), "Impact test KV2 (transverse)", fontsize=10)
	p.insert_text((50, 296), f"Test temperature {impact_at} °C: {values} J", fontsize=10)
	p.insert_text((50, 330), "Date: 2026-10-06", fontsize=10)
	return pdf.tobytes()


def keep_file(content, name):
	return frappe.get_doc({"doctype": "File", "file_name": name, "is_private": 1, "content": content}).insert(ignore_permissions=True).file_url


ORDER = [
	{"requirement": "Material", "grade": GRADE, "delivery_condition": "+N"},
	{"requirement": "Document", "certificate_type": "EN 10204 3.1"},
	{"requirement": "Impact", "impact_energy": 40, "impact_temperature": -50, "impact_direction": "Transverse", "source": "specifica §3.4"},
	{"requirement": "Carbon equivalent", "cev_max": 0.43, "cev_elements": 1},
]


def certificate(url, heat):
	if not frappe.db.exists("Material Heat", heat):
		frappe.get_doc({"doctype": "Material Heat", "heat_number": heat, "grade": GRADE}).insert(ignore_permissions=True)
	doc = frappe.new_doc("Material Certificate")
	doc.attachment = url
	certificate_reader.apply(doc, certificate_reader.read(url), heat)
	doc.status = "Valid"
	return doc


class TestTheMetalIsJudged(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_the_standard_says_the_limits(self):
		lim = gl.limits("EN-10028-4", "13MnNi6-3", thickness=45)
		self.assertEqual(lim["chemistry"]["S"], (None, 0.010), "EN 10028-4 Table 1")
		self.assertEqual(lim["chemistry"]["Ni"], (0.30, 0.85), "the thin-plate nickel of note b is only up to 40 mm")
		self.assertEqual(lim["mechanical"]["ReH"], 345, "Table 3, 30 < t ≤ 50")
		self.assertEqual(lim["impact"]["transverse"][-50], 30, "Table 4")
		thin = gl.limits("EN-10028-4", "13MnNi6-3", thickness=20)
		self.assertEqual(thin["chemistry"]["Ni"], (0.15, 0.85), "Table 1 note b")
		product = gl.limits("EN-10028-4", "13MnNi6-3", thickness=20, product=True)
		self.assertEqual(product["chemistry"]["Mn"], (0.80, 1.80), "Table 2: each limit widened by its own band")
		self.assertEqual(product["chemistry"]["Al"], (0.015, None))
		tube = gl.limits("EN-10216-5", "X2CrNiMo17-12-2", product=True)
		self.assertEqual(tube["chemistry"]["Cr"], (16.3, 18.7), "EN 10216-5 Table 5")
		self.assertIsNone(gl.limits("EN-10028-3", "P355NL1"), "not transcribed: said, never guessed")
		value, missing = gl.cev({"C": 0.14, "Mn": 1.30, "Ni": 0.55, "Cu": 0.08})
		self.assertAlmostEqual(value, 0.399, places=3)
		self.assertEqual(missing, ["Cr", "Mo", "V"])

	def test_a_certificate_is_read_with_its_boxes(self):
		url = keep_file(cert_pdf(), "read-24131.pdf")
		r = certificate_reader.read(url)
		self.assertFalse(r["scanned"])
		f = {k: v["value"] for k, v in r["fields"].items()}
		self.assertEqual(f["heat"], "T-24131")
		self.assertEqual(f["certificate_type"], "EN 10204 3.1")
		self.assertEqual(f["order"], "MPO-TEST")
		self.assertEqual(f["thickness"], 20)
		self.assertEqual(r["chemistry"]["S"]["value"], 0.012)
		self.assertEqual(r["printed"]["S"]["value"], 0.015, "the printed limit is kept apart, not as a value")
		self.assertTrue(r["chemistry"]["S"]["at"].startswith("1,"), "every value keeps the box it came from")
		self.assertEqual(r["impact"][0]["temperature"], -40)
		self.assertEqual(r["impact"][0]["values"], [61, 58, 64])
		self.assertEqual(r["direction"], "Transverse")

	def test_the_limit_printed_is_not_the_standard(self):
		doc = certificate(keep_file(cert_pdf(), "judge-24131.pdf"), "T-24131")
		j = conformity.judge(doc, ORDER, 20)
		self.assertEqual(j["verdict"], conformity.NO)
		s = next(r for r in j["rows"] if r["key"] == "S")
		self.assertEqual(s["outcome"], conformity.NO, "0,012 against 0,010 — whatever the certificate prints")
		impact = next(r for r in j["rows"] if r["key"] == "impact")
		self.assertEqual(impact["outcome"], conformity.NO, "tested at −40, asked at −50")
		cev = next(r for r in j["rows"] if r["key"] == "cev")
		self.assertEqual(cev["outcome"], conformity.ASK, "within, but Cr, Mo, V not printed")
		self.assertEqual(len(j["said"]), 2)
		msg = conformity.message_to_supplier("1", "T-24131", j["short"], "T-24139")
		self.assertIn("T-24131", msg)
		self.assertIn("T-24139", msg)

	def test_a_compliant_certificate(self):
		pdf = cert_pdf("T-24139", s="0,004", printed_s="0,010", impact_at="-50", values="47 49 48", cr_mo_v=True)
		doc = certificate(keep_file(pdf, "judge-24139.pdf"), "T-24139")
		j = conformity.judge(doc, ORDER, 20)
		self.assertEqual(j["verdict"], conformity.OK, j["rows"])
		self.assertTrue(any(n.startswith("CEV") for n in j["notes"]))

	def test_the_pmi_reads_against_the_product_limits(self):
		grade = "EN-10216-5--X2CrNiMo17-12-2"
		doc = frappe.get_doc({"doctype": "PMI Check", "subject_doctype": "Batch", "subject": "X", "grade": grade,
							  "readings": [{"element": "Cr", "read_percent": 17.1}, {"element": "Ni", "read_percent": 10.4},
										   {"element": "Mo", "read_percent": 2.05}, {"element": "Mn", "read_percent": 1.42}]})
		j = pmi.judge(doc)
		self.assertEqual(j["proposal"], "Alloy confirmed")
		self.assertEqual({r["element"] for r in j["rows"]}, {"Cr", "Ni", "Mo", "Mn"}, "the elements a handheld XRF reads")
		self.assertIn("C", j["unread"], "carbon is said as unread, not judged")
		doc.readings[2].read_percent = 1.80
		self.assertEqual(pmi.judge(doc)["proposal"], "Alloy not confirmed", "Mo below 2,0 − 0,10")
		self.assertEqual(pmi._next_piece("tubo 3 di 12"), "tubo 4 di 12")
		self.assertIsNone(pmi._next_piece("tubo 12 di 12"))

	def _lot(self, item, heat, **extra):
		b = frappe.get_doc({"doctype": "Batch", "batch_id": f"T-{heat}-{frappe.generate_hash(length=4)}", "item": item,
							"heat_number": heat, "lot_status": "Released", **extra})
		b.insert(ignore_permissions=True)
		return b

	def _item(self, code="T-MA-PLATE"):
		if not frappe.db.exists("Item", code):
			frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": code, "item_group": "Raw Material",
							"stock_uom": "Nos", "has_batch_no": 1, "is_stock_item": 1}).insert(ignore_permissions=True)
		return code

	def test_a_lot_is_fit_or_not_for_the_job(self):
		if not frappe.db.exists("DocType", "Batch"):
			self.skipTest("the warehouse is not installed")
		item = self._item()
		project = frappe.get_doc({"doctype": "Project", "project_name": f"T-MA-{frappe.generate_hash(length=5)}", "project_type": "Internal",
								  "company": frappe.db.get_value("Company", {}, "name")}).insert(ignore_permissions=True).name
		frappe.get_doc({"doctype": "Job Material Requirement", "project": project, "title": "plates", "grade": GRADE,
						"certificate_type": "EN 10204 3.1", "impact_energy": 40, "impact_temperature": -50}).insert(ignore_permissions=True)
		good = certificate(keep_file(cert_pdf("T-F1", s="0,004", impact_at="-50", values="47 49 48", cr_mo_v=True), "fit-1.pdf"), "T-F1")
		good.insert(ignore_permissions=True)
		cold = certificate(keep_file(cert_pdf("T-F2", s="0,004", impact_at="-40"), "fit-2.pdf"), "T-F2")
		cold.insert(ignore_permissions=True)
		from materials.material_certifications.doctype.material_certificate.material_certificate import auto_link_certificate

		lot_fit = self._lot(item, "T-F1")
		lot_cold = self._lot(item, "T-F2")
		# as the receipt does (materials.receiving.tie_certificates): the lot carries its heat's certificate
		auto_link_certificate(lot_fit.name, good.name)
		auto_link_certificate(lot_cold.name, cold.name)
		from worgify.readiness import NOT_USABLE, USABLE, can_use

		a = can_use("Batch", lot_fit.name, for_what={"job": project})
		self.assertEqual(a.status, USABLE, a.findings)
		b = can_use("Batch", lot_cold.name, for_what={"job": project})
		self.assertEqual(b.status, NOT_USABLE)
		self.assertTrue(any("−50" in f.reason for f in b.findings), "Released is not fit: no test at the job's temperature")
		self.assertFalse([f for f in can_use("Batch", lot_fit.name).findings if f.purpose], "asked no job, the metal is silent")

	def test_the_recall_finds_a_lot_by_any_heat(self):
		if not frappe.db.exists("DocType", "Batch"):
			self.skipTest("the warehouse is not installed")
		item = self._item()
		for h in ("T-R1", "T-R2"):
			if not frappe.db.exists("Material Heat", h):
				frappe.get_doc({"doctype": "Material Heat", "heat_number": h, "grade": GRADE}).insert(ignore_permissions=True)
		lot = self._lot(item, "T-R1", heat_numbers=[{"heat_number": "T-R1"}, {"heat_number": "T-R2"}])
		found = [b.name for b in recall.lots_of_heat("T-R2")]
		self.assertIn(lot.name, found, "Design 49 finding 4: the second heat of a lot is a heat of the lot")

	def test_stainless_and_carbon_are_kept_apart(self):
		if not frappe.get_meta("Warehouse").has_field("steel_kept"):
			self.skipTest("the warehouse is not installed")
		wh = frappe.db.get_value("Warehouse", {"warehouse_name": "T-INOX"}) or frappe.get_doc(
			{"doctype": "Warehouse", "warehouse_name": "T-INOX", "steel_kept": separation.STAINLESS_ONLY}).insert(ignore_permissions=True).name
		item = self._item()
		if not frappe.db.exists("Material Heat", "T-C1"):
			frappe.get_doc({"doctype": "Material Heat", "heat_number": "T-C1", "grade": GRADE}).insert(ignore_permissions=True)
		lot = self._lot(item, "T-C1")
		self.assertEqual(separation.family_of(item, lot.name), "carbon")
		self.assertTrue(separation.refusal(wh, item, lot.name, "Row 1"), "carbon steel into a stainless-only place")
		frappe.db.set_value("Warehouse", wh, "steel_kept", separation.CARBON_ONLY)
		self.assertFalse(separation.refusal(wh, item, lot.name, "Row 1"))

	def test_the_supplier_portal_is_closed_to_others(self):
		from worgify.utils.supplier_portal import require_portal_supplier

		frappe.set_user("Guest")
		try:
			self.assertRaises(frappe.PermissionError, require_portal_supplier)
		finally:
			frappe.set_user("Administrator")
		self.assertRaises(frappe.PermissionError, require_portal_supplier)
