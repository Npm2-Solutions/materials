# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""The record pages materials describes for the Worgify interface
(materials/ui.py, worgify_ui Design 48 Part 7) keep the contract it draws:

* every page — the certificate's, the specification's, and the certificate
  matching materials adds to stock's lot — runs on the latest record of its
  doctype and answers only the contract's keys, with acts the interface can run
  and components it has been told about;
* every method an act names is whitelisted — for a controller method run through
  `run_doc_method` (the desk's `frm.call`), the controller method is;
* the picker acts send what their helpers read: one checkbox per candidate, into
  the argument the helper takes;
* an unlisted element or test is kept as Other, the doctype's own way to say it.

Read-only: nothing is created and no act is run."""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

APP_MODULE = "materials.ui"
PAGE_KEYS = {"headline", "primary", "acts", "facts", "steps", "overview", "tabs", "hide"}
LAYOUT = {"Section Break", "Column Break", "Tab Break", "HTML"}
ROUTES = ({"doctype", "name"}, {"list"}, {"new"}, {"report"})
COMPONENTS = {"materials.certificate_extraction", "materials.certificate_viewer"}


def _latest(doctype, filters=None):
	if not frappe.db.exists("DocType", doctype) or not frappe.db.table_exists(doctype):
		return None
	return frappe.db.get_value(doctype, filters or {}, "name", order_by="modified desc")


class TestWorgifyUiPages(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if "worgify_ui" not in frappe.get_installed_apps():
			raise unittest.SkipTest("worgify_ui is not installed on this site")
		cls.objects = frappe.get_module(APP_MODULE).OBJECTS

	def test_the_module_is_declared(self):
		self.assertIn(APP_MODULE, frappe.get_hooks("worgify_ui"))

	def test_every_page_keeps_the_contract(self):
		from worgify_ui.api.ui import BLOCKS

		ran = 0
		for doctype, spec in self.objects.items():
			# the lot's page says something only for a lot with a heat
			name = _latest(doctype, {"heat_number": ["is", "set"]} if doctype == "Batch" else None) \
				or _latest(doctype)
			if not name or not spec.get("page"):
				continue
			with self.subTest(doctype=doctype, name=name):
				self.assert_page(spec["page"](frappe.get_doc(doctype, name)), BLOCKS)
				ran += 1
		if not ran:
			self.skipTest("no record to describe on this site")

	def test_filters_and_changes_answer(self):
		for doctype, spec in self.objects.items():
			name = _latest(doctype)
			if not name:
				continue
			values = frappe.get_doc(doctype, name).as_dict(convert_dates_to_str=True)
			meta = frappe.get_meta(doctype)
			for kind in ("link_filters", "on_change"):
				for field, fn in (spec.get(kind) or {}).items():
					with self.subTest(doctype=doctype, kind=kind, field=field):
						self.assertTrue(meta.has_field(field), f"{doctype} has no field {field}")
						self.assertIsInstance(fn(frappe.get_doc(dict(values))), dict)

	def test_the_helpers_are_whitelisted(self):
		from materials import ui

		for name in ("link_certificates", "link_lots", "apply_extracted_results"):
			with self.subTest(helper=name):
				frappe.is_whitelisted(getattr(ui, name))

	def test_only_what_is_ticked_is_linked(self):
		from materials.ui import _picked

		self.assertEqual(_picked({"A": 1, "B": 0, "C": True, "D": "0"}), ["A", "C"])
		self.assertEqual(_picked('{"A": 1}'), ["A"])
		self.assertEqual(_picked(None), [])

	def test_an_unlisted_value_is_kept_as_other(self):
		from materials.ui import _option

		self.assertEqual(_option("Certificate Chemical Result", "element", "Mn"), ("Mn", None))
		self.assertEqual(_option("Certificate Chemical Result", "element", "Zr"), ("Other", "Zr"))
		self.assertEqual(_option("Certificate Mechanical Result", "test_type", "Impact"), ("Other", "Impact"))

	# ── what the interface needs of a page ──

	def assert_page(self, page, blocks):
		self.assertIsInstance(page, dict)
		self.assertFalse(set(page) - PAGE_KEYS, f"keys the contract does not know: {set(page) - PAGE_KEYS}")
		acts = list(page.get("acts") or []) + ([page["primary"]] if page.get("primary") else [])
		parts = list(page.get("overview") or [])
		for tab in page.get("tabs") or []:
			self.assertTrue(tab.get("id") and tab.get("label"), tab)
			if tab.get("component"):
				self.assertIn(tab["component"], COMPONENTS, tab)
			parts += tab.get("blocks") or []
		for block in parts:
			self.assertIn(block.get("type"), blocks, block)
			acts += block.get("acts") or []
		for act in acts:
			self.assert_act(act)
		frappe.as_json(page)

	def assert_act(self, act):
		self.assertTrue(act.get("label"), act)
		self.assertTrue(act.get("method") or act.get("route"), act)
		if act.get("method") == "run_doc_method":
			args = act.get("args") or {}
			fn = getattr(frappe.get_doc(args["dt"], args["dn"]), args["method"])
			frappe.is_whitelisted(getattr(fn, "__func__", fn))
		elif act.get("method"):
			frappe.is_whitelisted(frappe.get_attr(act["method"]))
		if act.get("route"):
			self.assertTrue(any(set(r) <= set(act["route"]) for r in ROUTES), act["route"])
		if act.get("into"):
			self.assertIn(act["into"], act.get("args") or {}, act)
			# a picker: one checkbox per candidate
			for df in act.get("fields") or []:
				self.assertEqual(df.get("fieldtype"), "Check", df)
		for df in act.get("fields") or []:
			self.assertTrue(df.get("fieldname") and df.get("fieldtype"), df)
			self.assertNotIn(df["fieldtype"], LAYOUT, df)
