# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""What the metal is asked, in the job's requirement review (Design 55
X-requisiti, the kernel's ``worgify.jobs.requirements``).

* **The judge:** the impact the specification asks is compared with what the
  grade's standard guarantees (EN 10028-4:2017 Table 4, ``grade_limits``). When
  the specification asks more — 40 J at −50 °C on transverse specimens, where
  13MnNi6-3 guarantees 30 J — the requirement is *to resolve*: unless it is
  written into the order to the supplier, no certificate will prove it.
* **The act:** *Add to the material order* writes the job's material requirement
  (``Job Material Requirement``, which the order and the issue already read).
* **The applier:** a signed review writes the same for every material row.
"""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import flt

JMR = "Job Material Requirement"
GRADE = re.compile(r"\b(EN\s*10\d{3}-\d)\s+([0-9A-Za-z][0-9A-Za-z\-+.]*[0-9A-Za-z])(?:\s+(\+[A-Z]+))?")
IMPACT = re.compile(r"(\d+)\s*J\D+?([−\-–]?\d+)\s*°C(?:,\s*(\w+))?")


def _rows_by_key(rows):
	out = {}
	for r in rows:
		key = r.get("key") if isinstance(r, dict) else r.key
		out.setdefault(key, []).append(r)
	return out


def _get(r, field):
	return r.get(field) if isinstance(r, dict) else getattr(r, field, None)


def _grade_of(rows):
	"""(standard key, grade, delivery condition) from the specification's material line."""
	for r in _rows_by_key(rows).get("material.grade", []):
		m = GRADE.search(_get(r, "value") or "")
		if m:
			return m.group(1).replace(" ", "-"), m.group(2), m.group(3)
	return None, None, None


def _impact_of(value):
	m = IMPACT.search(value or "")
	if not m:
		return None
	direction = "transverse"
	if m.group(3) and m.group(3).lower().startswith(("long", "longitud")):
		direction = "longitudinal"
	return int(m.group(1)), int(m.group(2).replace("−", "-").replace("–", "-")), direction


def judge(rows, project):
	from materials.grade_limits import limits

	standard, grade, _cond = _grade_of(rows)
	if not grade:
		return rows
	lim = limits(standard, grade)
	if not lim or not lim.get("impact"):
		return rows
	title = lim["source"]["title"]
	for r in rows:
		if r.get("key") != "material.impact":
			continue
		got = _impact_of(r.get("value"))
		if not got:
			continue
		joules, temp, direction = got
		table = lim["impact"].get(direction) or {}
		guaranteed = table.get(temp)
		if guaranteed is None or joules <= guaranteed:
			continue
		r["state"] = "To resolve"
		r["note"] = _("The specification asks more than the standard: {0} J at {1} °C on {2} specimens, where {3} guarantees "
					  "{4} J for {5} at that temperature ({6}). The requirement goes into the order to the supplier, otherwise no "
					  "certificate will prove it.").format(joules, str(temp).replace("-", "−"),
														  _("transverse", context="Specimens") if direction == "transverse" else _("longitudinal", context="Specimens"),
														  title, guaranteed, grade, _("Table 4"))
	return rows


def act_label(row):
	return _("Add to the material order") if row.key == "material.impact" else None


def _write(review) -> str | None:
	"""The job's material requirement, from the review's material rows."""
	rows = list(review.requirements)
	by = _rows_by_key(rows)
	standard, grade, condition = _grade_of(rows)
	if not grade:
		return None
	grade_name = f"{standard}--{grade}"
	if not frappe.db.exists("Material Grade", grade_name):
		grade_name = None
	values = {"grade": grade_name, "delivery_condition": condition}
	cert = (by.get("material.certificate") or [None])[0]
	if cert and frappe.db.exists("Conformity Certificate Type", cert.value):
		values["certificate_type"] = cert.value
	imp = (by.get("material.impact") or [None])[0]
	got = _impact_of(imp.value) if imp else None
	if got:
		values.update({"impact_energy": got[0], "impact_temperature": got[1],
					   "impact_direction": "Transverse" if got[2] == "transverse" else "Longitudinal"})
	cev = (by.get("material.cev") or [None])[0]
	if cev:
		m = re.search(r"(\d+[.,]\d+)", cev.value or "")
		if m:
			values["cev_max"] = flt(m.group(1).replace(",", "."))
	values["pmi_required"] = 1 if by.get("material.pmi") else 0
	# the review that wrote it, by name (a fact, not a sentence): a new version rewrites its own row
	values["source"] = review.name
	name = frappe.db.get_value(JMR, {"project": review.project, "source": ["like", "JRR-%"]})
	if name:
		doc = frappe.get_doc(JMR, name)
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc({"doctype": JMR, "project": review.project,
							  "title": _("Pressure-bearing material, {0}").format(grade), **values}).insert(ignore_permissions=True)
	return doc.name


def act(review, row):
	if row.key != "material.impact":
		return None
	name = _write(review)
	return _("Written in the job's material requirements ({0}): the orders and the issues follow it.").format(name) if name else None


def apply(review) -> list[str]:
	name = _write(review)
	return [_("the job's material requirements ({0})").format(name)] if name else []
