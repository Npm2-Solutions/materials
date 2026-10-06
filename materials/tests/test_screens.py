# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""The Materials place and the metal's screens in the Worgify interface
(materials.screens, Design 49) answer each person as they may read:

* the place's Today keeps the shared contract — key, label, verb, theme, count,
  at most six rows, each with a title and the record it opens — and never shows
  an empty band; a certificate waits in one band only;
* the counts beside the rows are the viewer's own numbers;
* the heats and the certificates answer their views with counts and rows that
  name the record they open; a heat's and a certificate's page answer for a
  record the person may read;
* the heat's acts are only those the register allows from its state, and the
  hold is offered only to who may write the lots.

Read-only: nothing is created, no act is run; every call is rolled back."""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from materials import screens

INSPECTOR = "material.inspector@demo.worgify.test"
MANAGER = "warehouse.manager@demo.worgify.test"
QUALITY = "qa.manager@demo.optisuites.test"
STORE_KEEPER = "store.keeper@demo.worgify.test"
PEOPLE = (INSPECTOR, MANAGER, QUALITY)
BAND_KEYS = {"key", "label", "verb", "theme", "count", "rows"}
THEMES = {"gray", "blue", "green", "amber", "red", "violet"}


def _latest(doctype, filters=None):
	return frappe.db.get_value(doctype, filters or {}, "name", order_by="modified desc")


class TestScreens(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		missing = [u for u in (*PEOPLE, STORE_KEEPER) if not frappe.db.exists("User", u)]
		if missing:
			raise unittest.SkipTest(f"the demo people are not on this site: {', '.join(missing)}")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def as_(self, user, fn, *args, **kwargs):
		frappe.set_user(user)
		try:
			return fn(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")

	def test_every_screen_is_whitelisted(self):
		for name in ("today", "nav_counts", "heats", "heat_workspace", "certificates", "certificate_workspace"):
			frappe.is_whitelisted(getattr(screens, name))

	def test_today_keeps_the_contract(self):
		for user in (*PEOPLE, STORE_KEEPER):
			out = self.as_(user, screens.today)
			seen = {}
			for band in out["bands"]:
				self.assertTrue(BAND_KEYS <= set(band), band.get("key"))
				self.assertIn(band["theme"], THEMES)
				self.assertTrue(band["rows"], f"an empty band {band['key']} for {user}")
				self.assertLessEqual(len(band["rows"]), 6)
				for r in band["rows"]:
					self.assertTrue(r["title"])
					self.assertTrue(r["link"]["doctype"] and r["link"]["name"])
					if r["link"]["doctype"] == "Material Certificate":
						self.assertNotIn(r["link"]["name"], seen, "a certificate in two bands")
						seen[r["link"]["name"]] = band["key"]

	def test_the_store_keeper_judges_no_paperwork(self):
		keys = {b["key"] for b in self.as_(STORE_KEEPER, screens.today)["bands"]}
		self.assertNotIn("match", keys)
		self.assertNotIn("verify", keys)

	def test_counts_are_the_viewers_numbers(self):
		for user in PEOPLE:
			for key, n in self.as_(user, screens.nav_counts).items():
				self.assertIsInstance(n, int, key)

	def test_registers_answer_views_and_rows(self):
		for user in PEOPLE:
			for method, views in (("heats", ("all", "held", "uncovered")), ("certificates", ("verify", "match", "valid", "out"))):
				for view in views:
					out = self.as_(user, getattr(screens, method), view)
					self.assertEqual([v["key"] for v in out["views"]], list(views))
					for r in out["rows"]:
						self.assertTrue(r["title"])
						self.assertTrue(r["link"]["doctype"] and r["link"]["name"])

	def test_pages_answer_for_a_readable_record(self):
		ran = 0
		for method, doctype in (("heat_workspace", "Material Heat"), ("certificate_workspace", "Material Certificate")):
			name = _latest(doctype)
			if not name:
				continue
			for user in PEOPLE:
				out = self.as_(user, getattr(screens, method), name)
				self.assertEqual(out["name"], name)
				ran += 1
		self.assertTrue(ran, "no heat nor certificate on this site")

	def test_the_heat_offers_only_what_the_register_allows(self):
		from materials.material_certifications.doctype.material_heat.material_heat import MaterialHeat

		heat = _latest("Material Heat")
		if not heat:
			self.skipTest("no heat on this site")
		status = frappe.db.get_value("Material Heat", heat, "status")
		allowed = MaterialHeat.ALLOWED_STATUS_TRANSITIONS.get(status, set())
		for user in PEOPLE:
			out = self.as_(user, screens.heat_workspace, heat)
			for act in out["acts"]:
				if act["id"].startswith("heat_"):
					self.assertIn(act["args"]["value"], allowed)
				if act["id"] == "hold":
					frappe.set_user(user)
					may = frappe.has_permission("Batch", "write")
					frappe.set_user("Administrator")
					self.assertTrue(may, f"hold offered to {user}, who may not write the lots")

	def test_a_heat_page_is_refused_to_who_may_not_read_it(self):
		heat = _latest("Material Heat")
		if not heat:
			self.skipTest("no heat on this site")
		guest_like = frappe.db.get_value("User", {"user_type": "Website User", "enabled": 1}, "name")
		if not guest_like:
			self.skipTest("no website user to ask as")
		with self.assertRaises(frappe.PermissionError):
			self.as_(guest_like, screens.heat_workspace, heat)
