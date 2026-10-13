# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""The certificate against the standard and the order (Design 55 MA-03, proposal 17),
and the lot against the job (MA-04).

**A 3.1 is read against two things it does not choose:** the standard of its grade
(``materials.grade_limits``, transcribed with the clause) and what the order asked
(``Material Order Requirement``, copied from the job's review). The limits printed on
the certificate are shown beside its values and never used — judging a value
against the limit printed next to it is how heat 24131 passed with S 0,012 against
a printed *max 0,015*, where EN 10028-4 Table 1 says 0,010.

Every row says where its limit comes from; a value the certificate does not print
is *to ask*, never a pass; a grade whose standard is not transcribed is said so,
and only the order is checked.

**Released is not fit.** A lot may be used (stock answers that); whether it may be
used *for this job* is the job's material requirements against what the lot's
certificate shows. Materials answers it through the kernel's *can it be used?*
(``can_use("Batch", lot, for_what={"job": …})``), so the warehouse asks without
knowing what a heat is.
"""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from materials import grade_limits as gl

CERT = "Material Certificate"
REQ = "Material Order Requirement"
JOB_REQ = "Job Material Requirement"

OK, NO, ASK, INFO = "ok", "no", "ask", "info"

ELEMENTS = ("C", "Si", "Mn", "P", "S", "Al", "Cr", "Mo", "Nb", "Ni", "V", "Cu", "N", "Ti", "B", "W")
ELEMENT_WORDS = {
	"C": "carbon", "Si": "silicon", "Mn": "manganese", "P": "phosphorus", "S": "sulphur", "Al": "aluminium",
	"Cr": "chromium", "Mo": "molybdenum", "Nb": "niobium", "Ni": "nickel", "V": "vanadium", "Cu": "copper",
	"N": "nitrogen", "Ti": "titanium",
}
MECH = {"Yield Strength": "ReH", "Tensile Strength": "Rm", "Elongation": "A", "Impact (Charpy)": "KV"}


# ── numbers as the reader writes them ───────────────────────────────────────

def num(v, digits=3, keep=0):
	"""0.14 → «0,14» where the site writes a decimal comma; never 0.140000.
	``keep``: decimals always written (a percentage reads 1,30 as the standard prints it)."""
	if v is None:
		return "—"
	s = f"{round(flt(v), digits):.{digits}f}"
	if "." in s:
		whole, dec = s.split(".")
		dec = dec.rstrip("0")
		dec = dec + "0" * max(0, keep - len(dec))
		s = f"{whole}.{dec}" if dec else whole
	fmt = frappe.db.get_default("number_format") or "#,###.##"
	return s.replace(".", ",") if fmt in ("#.###,##", "# ###,##", "#'###,##", "#.###") else s


def pct(v):
	"""A mass percentage as a standard prints it: 0,50 · 1,70 · 0,010."""
	return num(v, 3, 3 if v is not None and abs(flt(v)) < 0.1 else 2)


def temp(t):
	t = flt(t)
	return f"{'−' if t < 0 else ''}{num(abs(t), 1)} °C"


def _range(low, high, unit=""):
	u = f" {unit}" if unit else ""
	f = num if unit else pct
	if low is not None and high is not None:
		return f"{f(low)} – {f(high)}{u}"
	if high is not None:
		return f"≤ {f(high)}{u}"
	if low is not None:
		return f"≥ {f(low)}{u}"
	return "—"


def _temperature_of(text):
	"""«-40 °C», «−40C», «-40» → -40.0; None when the row says no temperature."""
	if text in (None, ""):
		return None
	m = re.search(r"([−\-–+]?\s*\d+(?:[.,]\d+)?)", str(text))
	if not m:
		return None
	return flt(m.group(1).replace("−", "-").replace("–", "-").replace(" ", "").replace(",", "."))


# ── what the certificate is for ──────────────────────────────────────────────

def grade_of_heat(heat):
	g = frappe.db.get_value("Material Heat", heat, "grade") if heat else None
	return g


def standard_and_name(grade_record):
	"""(standard, grade name, label) of a Material Grade record."""
	if not grade_record:
		return None, None, None
	g = frappe.db.get_value("Material Grade", grade_record, ["grade", "specification", "display_name"], as_dict=True)
	if not g:
		return None, None, None
	standard = frappe.db.get_value("Material Specification", g.specification, "standard") if g.specification else None
	return standard, g.grade, g.display_name or g.grade


def _cert_grade(doc):
	for row in doc.get("heats_covered") or []:
		g = grade_of_heat(row.heat)
		if g:
			return g
	return None


def values_of(doc):
	"""{element: %}, {ReH, Rm, A}, [impact rows] as the certificate prints them,
	with where each was read."""
	chem, where, printed = {}, {}, {}
	for r in doc.get("chemical_results") or []:
		el = r.element if r.element and r.element != "Other" else (r.element_other or "").strip()
		if not el or r.value_percent is None:
			continue
		chem[el] = flt(r.value_percent)
		where[el] = r.get("read_at")
		if r.spec_max or r.spec_min:
			printed[el] = (flt(r.spec_min) or None, flt(r.spec_max) or None)
	mech, impact = {}, []
	for r in doc.get("mechanical_results") or []:
		key = MECH.get(r.test_type)
		if not key or r.value is None:
			continue
		if key == "KV":
			impact.append({"value": flt(r.value), "temperature": _temperature_of(r.temperature),
						   "direction": (r.get("direction") or "").lower() or None, "read_at": r.get("read_at")})
		else:
			mech[key] = flt(r.value)
			where[key] = r.get("read_at")
	return chem, mech, impact, where, printed


def _impact_sets(impact):
	"""{(temperature, direction): [values]} — a Charpy set is three specimens at one temperature."""
	sets = {}
	for i in impact:
		sets.setdefault((i["temperature"], i["direction"]), []).append(i["value"])
	return sets


def _impact_at(impact):
	return {(i["temperature"], i["direction"]): i.get("read_at") for i in impact if i.get("read_at")}


def _mean(values):
	return round(sum(values) / len(values), 1) if values else None


def _join_values(values):
	return " · ".join(num(v, 0) for v in values)


# ── the order's requirements ─────────────────────────────────────────────────

def requirements_of_order(order, line=None):
	"""The order's technical requirements for a line (rows without a line are for every line)."""
	if not order or not frappe.db.exists("DocType", REQ):
		return []
	rows = frappe.get_all(REQ, filters={"parent": order, "parenttype": "Material Purchase Order"},
						  fields=["*"], order_by="idx asc")
	return [r for r in rows if not r.order_line or not line or str(r.order_line) == str(line)]


def requirement_value(r):
	"""One requirement in words (the value column of the board's table)."""
	kind = r.get("requirement")
	if kind == "Material":
		_s, name, label = standard_and_name(r.get("grade"))
		spec = frappe.db.get_value("Material Grade", r.get("grade"), "specification") if r.get("grade") else None
		std = frappe.db.get_value("Material Specification", spec, "standard") if spec else None
		return " ".join(x for x in [name or label, r.get("delivery_condition")] if x) + (f", {std.replace('-', ' ', 1)}" if std else "")
	if kind == "Document":
		return r.get("certificate_type") or ""
	if kind == "Impact":
		text = _("{0} J mean at {1}, longitudinal specimens") if (r.get("impact_direction") == "Longitudinal") \
			else _("{0} J mean at {1}, transverse specimens")
		return text.format(num(r.get("impact_energy"), 0), temp(r.get("impact_temperature")))
	if kind == "Carbon equivalent":
		return _("CEV ≤ {0}").format(num(r.get("cev_max"), 2)) + (_(", with Cr, Mo, V declared") if r.get("cev_elements") else "")
	return r.get("text") or ""


def requirement_word(kind):
	return {"Material": _("Material"), "Document": _("Document", context="Material requirement"),
			"Impact": _("Impact energy"), "Carbon equivalent": _("Carbon equivalent"), "PMI": _("PMI"),
			"Other": _("Other")}.get(kind, kind)


# ── the judgement ────────────────────────────────────────────────────────────

def _row(what, standard, order, certificate, outcome, out_text="", read_at=None, key=None):
	return {"what": what, "standard": standard, "order": order, "certificate": certificate, "outcome": outcome,
			"out": out_text or ("✓" if outcome == OK else ""), "read_at": read_at, "key": key}


def judge(doc, requirements=None, thickness=None) -> dict:
	"""Every value of a certificate against its standard and the order's
	requirements. ``doc`` is a Material Certificate (or a dict shaped like one)."""
	requirements = list(requirements or [])
	grade = _cert_grade(doc)
	material_req = next((r for r in requirements if r.get("requirement") == "Material" and r.get("grade")), None)
	if not grade and material_req:
		grade = material_req.get("grade")
	standard, grade_name, label = standard_and_name(grade)
	thickness = flt(thickness or doc.get("product_thickness")) or None
	lim = gl.limits(standard, grade_name, thickness) if standard and grade_name else None
	chem, mech, impact, where, printed = values_of(doc)
	rows, said, short, brief, notes = [], [], [], [], []

	# the material the order asked
	if material_req and grade and material_req.get("grade") != grade:
		_s, asked, _l = standard_and_name(material_req.get("grade"))
		rows.append(_row(_("Material"), "—", asked, grade_name or grade, NO, _("✕ another material"), key="grade"))
		said.append(_("The certificate is for {0}; the order asks {1}.").format(grade_name or grade, asked))
		short.append(_("another material"))
		brief.append(_("another material: {0}").format(grade_name or grade))

	# chemistry against the standard's cast analysis
	if lim:
		for el, (low, high) in lim["chemistry"].items():
			v = chem.get(el)
			p = printed.get(el)
			p_text = (" " + _("(prints «max {0}»)").format(pct(p[1]))) if p and p[1] is not None and high is not None \
				and abs(p[1] - high) > 1e-9 else ""
			if v is None:
				if low is not None:
					rows.append(_row(el, _range(low, high), "—", _("not printed"), ASK, _("! ask for it"), key=el))
				continue
			bad = (low is not None and v < low - 1e-9) or (high is not None and v > high + 1e-9)
			rows.append(_row(el, _range(low, high), "—", pct(v) + p_text, NO if bad else OK,
							 _("✕ outside the standard") if bad else "", where.get(el), el))
			if bad:
				name = _(ELEMENT_WORDS.get(el, el)).capitalize()
				limit = _("at most {0} %").format(pct(high)) if high is not None and v > high else _("at least {0} %").format(pct(low))
				sentence = _("{0} {1} %: {2} allows {3} for {4}.").format(name, pct(v), lim["source"]["title"].split(":")[0], limit, grade_name)
				if p and p[1] is not None and high is not None and p[1] > high:
					sentence += " " + _("The certificate prints a limit of {0} and so calls itself compliant.").format(pct(p[1]))
				said.append(sentence)
				short.append(_("{0} above the standard").format(_(ELEMENT_WORDS.get(el, el))) if high is not None and v > high
							 else _("{0} below the standard").format(_(ELEMENT_WORDS.get(el, el))))
				brief.append(_("{0} {1} % over the {2} of the standard").format(el, pct(v), pct(high)) if high is not None and v > high
							 else _("{0} {1} % under the {2} of the standard").format(el, pct(v), pct(low)))
		for s in lim.get("sums") or []:
			present = [e for e in s["elements"] if chem.get(e) is not None]
			missing = [e for e in s["elements"] if chem.get(e) is None]
			total = round(sum(chem[e] for e in present), 3)
			what = " + ".join(s["elements"])
			if missing:
				rows.append(_row(what, _range(None, s["max"]), "—", _("{0} not printed").format(", ".join(missing)), ASK,
								 _("! ask for {0}").format(", ".join(missing)), key="sum"))
			else:
				bad = total > s["max"] + 1e-9
				rows.append(_row(what, _range(None, s["max"]), "—", pct(total), NO if bad else OK,
								 _("✕ outside the standard") if bad else "", key="sum"))
				if bad:
					said.append(_("{0} = {1} %: the standard allows at most {2} %.").format(what, pct(total), pct(s["max"])))
					short.append(_("{0} above the standard").format(what))
					brief.append(_("{0} {1} % over the {2} of the standard").format(what, pct(total), pct(s["max"])))

	# the carbon equivalent the order may ask
	for r in [r for r in requirements if r.get("requirement") == "Carbon equivalent"]:
		value, missing = gl.cev(chem)
		asked = _("≤ {0}").format(num(r.get("cev_max"), 2))
		if value is None:
			rows.append(_row(_("CEV (recomputed)"), "—", asked, _("C, Mn not printed"), ASK, _("! ask for the analysis"), key="cev"))
			continue
		bad = value > flt(r.get("cev_max")) + 1e-9
		missing_needed = [e for e in ("Cr", "Mo", "V") if e in missing]
		text = num(value, 2, 2) + (" · " + _("{0} not printed").format(", ".join(missing_needed)) if missing_needed else "")
		if bad:
			rows.append(_row(_("CEV (recomputed)"), "—", asked, text, NO, _("✕ above the order"), key="cev"))
			said.append(_("Carbon equivalent {0}: the order asks at most {1}.").format(num(value, 2), num(r.get("cev_max"), 2)))
			short.append(_("carbon equivalent above the order"))
			brief.append(_("CEV {0} over the {1} of the order").format(num(value, 2, 2), num(r.get("cev_max"), 2, 2)))
		elif missing_needed and r.get("cev_elements"):
			rows.append(_row(_("CEV (recomputed)"), "—", asked, text, ASK,
							 _("! within, but ask for {0}").format(", ".join(missing_needed)), key="cev"))
		else:
			rows.append(_row(_("CEV (recomputed)"), "—", asked, text, OK, key="cev"))
			if not missing_needed:
				notes.append(_("CEV {0} with Cr, Mo, V").format(num(value, 2, 2)))

	# mechanical properties at room temperature
	if lim and lim.get("mechanical"):
		m = lim["mechanical"]
		checks = [
			("ReH", (m["ReH"], None) if m["ReH"] else None, "MPa"),
			("Rm", m["Rm"], "MPa"),
			("A", (m["A"], None), "%"),
		]
		for key, bounds, unit in checks:
			v = mech.get(key)
			if bounds is None:
				if v is not None:
					rows.append(_row(key, _("thickness not known"), "—", f"{num(v, 0)} {unit}", ASK,
									 _("! say the thickness"), where.get(key), key))
				continue
			low, high = bounds
			if v is None:
				rows.append(_row(key, _range(low, high, unit), "—", _("not printed"), ASK, _("! ask for it"), key=key))
				continue
			bad = (low is not None and v < low) or (high is not None and v > high)
			rows.append(_row(key, _range(low, high, unit), "—", f"{num(v, 0)} {unit}", NO if bad else OK,
							 _("✕ outside the standard") if bad else "", where.get(key), key))
			if bad:
				said.append(_("{0} {1} {2}: {3} asks {4}.").format(key, num(v, 0), unit, lim["source"]["title"].split(":")[0],
																 _range(low, high, unit)))
				short.append(_("{0} outside the standard").format(key))
				brief.append(_("{0} {1} {2} outside {3}").format(key, num(v, 0), unit, _range(low, high, unit)))

	# impact energy: the standard at the tested temperature, the order at its own
	sets = _impact_sets(impact)
	at = _impact_at(impact)
	impact_reqs = [r for r in requirements if r.get("requirement") == "Impact"]
	table = (lim or {}).get("impact")
	def std_min(direction, t):
		return (table or {}).get(direction, {}).get(int(round(t))) if table and t is not None else None

	for r in impact_reqs:
		# the order asks a mean at a temperature: the set tested there answers it
		direction = (r.get("impact_direction") or "Transverse").lower()
		t_req = flt(r.get("impact_temperature"))
		std_at = std_min(direction, t_req)
		what = _("KV2 {0}").format(_(direction))
		std_text = _("{0} J at {1}").format(std_at, temp(t_req)) if std_at else "—"
		order_text = _("{0} J mean at {1}").format(num(r.get("impact_energy"), 0), temp(t_req))
		at_req = [v for (t, d), v in sets.items() if t is not None and abs(t - t_req) < 0.5 and d in (None, direction)]
		if not at_req:
			tested = sorted({t for (t, _d) in sets if t is not None})
			cert_text = "; ".join(_("{0} J at {1}").format(_join_values(v), temp(t)) for (t, _d), v in sets.items()) \
				or _("no impact test printed")
			rows.append(_row(what, std_text, order_text, cert_text, NO, _("✕ no test at {0}").format(temp(t_req)),
							 next(iter(at.values()), None), key="impact"))
			said.append(_("Impact tested at {0}: the order asks {1} J mean at {2} ({3}). At {2} there is no test.").format(
				", ".join(temp(t) for t in tested) or _("no temperature"), num(r.get("impact_energy"), 0), temp(t_req),
				r.get("source") or _("from the order")))
			short.append(_("impact not tested at {0}").format(temp(t_req)))
			brief.append(_("impact tested at {0}, not at {1}").format(", ".join(temp(t) for t in tested) or "—", temp(t_req)))
			continue
		for (t, d), values in [(k, v) for k, v in sets.items() if k[0] is not None and abs(k[0] - t_req) < 0.5 and k[1] in (None, direction)]:
			mean = _mean(values)
			bad = mean < flt(r.get("impact_energy")) or (std_at is not None and mean < std_at)
			rows.append(_row(what, std_text, order_text, _("{0} J at {1}").format(_join_values(values), temp(t_req)),
							 NO if bad else OK, (_("✕ mean {0} J") if bad else _("✓ mean {0} J")).format(num(mean, 0)),
							 at.get((t, d)), key="impact"))
			if bad:
				said.append(_("Impact energy mean {0} J at {1}: the order asks {2} J.").format(
					num(mean, 0), temp(t_req), num(r.get("impact_energy"), 0)))
				short.append(_("impact energy below the order"))
				brief.append(_("impact {0} J mean at {1}, asked {2}").format(num(mean, 0), temp(t_req), num(r.get("impact_energy"), 0)))
	if not impact_reqs:
		# no order asked: each tested set against the standard at its own temperature
		for (t, d), values in sets.items():
			direction = d or "transverse"
			std_at = std_min(direction, t)
			mean = _mean(values)
			bad = std_at is not None and mean < std_at
			rows.append(_row(_("KV2 {0}").format(_(direction)), _("{0} J at {1}").format(std_at, temp(t)) if std_at else "—",
							 "—", _("{0} J at {1}").format(_join_values(values), temp(t)) if t is not None else _join_values(values),
							 NO if bad else (OK if std_at is not None else INFO),
							 (_("✕ mean {0} J") if bad else _("✓ mean {0} J")).format(num(mean, 0)), at.get((t, d)), key="impact"))
			if bad:
				said.append(_("Impact energy mean {0} J at {1}: the standard asks {2} J.").format(num(mean, 0), temp(t), std_at))
				short.append(_("impact energy below the standard"))
				brief.append(_("impact {0} J mean at {1}, asked {2}").format(num(mean, 0), temp(t), std_at))

	# the document type
	for r in [r for r in requirements if r.get("requirement") == "Document"]:
		have = doc.get("certificate_type")
		bad = bool(r.get("certificate_type")) and have != r.get("certificate_type")
		rows.append(_row(_("Type of document"), "—", r.get("certificate_type"), have or _("not said"),
						 NO if bad else OK, _("✕ another document") if bad else "", key="document"))
		if bad:
			said.append(_("The certificate is a {0}; the order asks {1}.").format(have or _("document of no type"), r.get("certificate_type")))
			short.append(_("{0}, the order asks {1}").format(have or "?", r.get("certificate_type")))
			brief.append(_("{0}, the order asks {1}").format(have or "?", r.get("certificate_type")))

	# heat and quantity
	heats = [h.heat for h in doc.get("heats_covered") or [] if h.heat]
	if heats:
		qty = sum(flt(h.qty_covered) for h in doc.get("heats_covered") or [])
		rows.append(_row(_("Heat and quantity"), "—", "—", _("heat {0}").format(", ".join(heats))
						 + (f", {num(qty, 0)} " + _("pieces") if qty else ""), INFO, key="heat"))

	verdict = NO if any(r["outcome"] == NO for r in rows) else ASK if any(r["outcome"] == ASK for r in rows) else OK
	clauses = sorted({c for c in [(lim or {}).get("chemistry_clause"), ((lim or {}).get("mechanical") or {}).get("clause"),
								  ((lim or {}).get("impact") or {}).get("clause")] if c})
	numbers = [c.replace("Table ", "") for c in clauses]
	tables = (_("table {0}").format(numbers[0]) if len(numbers) == 1 else
			  _("tables {0} and {1}").format(", ".join(numbers[:-1]), numbers[-1])) if numbers else ""
	source = ", ".join(x for x in [lim["source"]["title"], tables] if x) if lim else None
	band = None
	if lim and thickness and (lim.get("mechanical") or {}).get("ReH_bands"):
		edges = [0] + [b for b, _m in lim["mechanical"]["ReH_bands"]]
		for low, high in zip(edges, edges[1:]):
			if thickness <= high:
				band = f"t ≤ {high:g} mm" if not low else f"{low:g} < t ≤ {high:g} mm"
				break
	standard_label = ", ".join(x for x in [lim["source"]["title"].split(":")[0], band] if x) if lim else None
	return {
		"grade": grade, "grade_name": grade_name or label, "standard": standard, "source": source,
		"standard_label": standard_label,
		"transcribed": bool(lim), "rows": rows, "verdict": verdict, "said": said, "short": short, "brief": brief, "notes": notes,
		"headline": _headline(verdict, said, lim, grade_name, standard),
	}


def _headline(verdict, said, lim, grade_name, standard):
	if not lim and grade_name:
		return _("The limits of {0} ({1}) are not transcribed yet: only the order was checked.").format(grade_name, standard or "—")
	if verdict == NO:
		n = len(said)
		return _("The certificate says «compliant». One thing is not.") if n == 1 else \
			_("The certificate says «compliant». {0} things are not.").format(n)
	if verdict == ASK:
		return _("Within the standard and the order, with values to ask for.")
	return _("Everything within the standard and the order.")


def message_to_supplier(order_line, heat, short, alternative=None) -> str:
	"""What we tell the supplier, in one sentence they can act on."""
	reasons = ", ".join(short)
	head = _("Line {0}: heat {1} is not acceptable ({2}).").format(order_line, heat, reasons) if order_line else \
		_("Heat {0} is not acceptable ({1}).").format(heat, reasons)
	tail = _("Ship heat {0} or another heat, with its certificate, before loading.").format(alternative) if alternative else \
		_("Ship another heat, with its certificate, before loading.")
	return f"{head} {tail}"


@frappe.whitelist()
def for_certificate(name: str) -> dict:
	"""The judgement of one certificate, with the order it names."""
	doc = frappe.get_doc(CERT, name)
	doc.check_permission("read")
	order = doc.get("order_reference")
	reqs = requirements_of_order(order, doc.get("order_line")) if order and frappe.db.exists("Material Purchase Order", order) else []
	out = judge(doc, reqs, doc.get("product_thickness") or _thickness_of_order_line(order, doc.get("order_line")))
	out["order"] = order if reqs or (order and frappe.db.exists("Material Purchase Order", order)) else None
	return out


def _thickness_of_order_line(order, line):
	if not order or not line or not frappe.db.exists("DocType", "Material Purchase Order Item"):
		return None
	row = frappe.db.get_value("Material Purchase Order Item", {"parent": order, "idx": cint(line)}, "item_code")
	return frappe.db.get_value("Item", row, "thickness") if row else None


# ── the lot against the job (MA-04), for can_use ────────────────────────────

def job_requirements(project, grade=None):
	if not project or not frappe.db.exists("DocType", JOB_REQ):
		return []
	rows = frappe.get_all(JOB_REQ, filters={"project": project}, fields=["*"], order_by="creation asc")
	return rows


def _lot_heats(lot):
	h = frappe.db.get_value("Batch", lot, "heat_number")
	heats = [h] if h else []
	if frappe.db.exists("DocType", "Batch Heat Number"):
		heats += [r for r in frappe.get_all("Batch Heat Number", filters={"parent": lot, "parenttype": "Batch"},
											 pluck="heat_number") if r and r not in heats]
	return heats


def _lot_certificates(lot):
	names = []
	if frappe.db.exists("DocType", "Mill Test Certificate"):
		names = [r for r in frappe.get_all("Mill Test Certificate", filters={"parent": lot, "parenttype": "Batch"},
										   pluck="certificate") if r]
	if not names:
		heats = _lot_heats(lot)
		if heats:
			names = list({r.parent for r in frappe.get_all("Material Heat Coverage", filters={"heat": ["in", heats],
																								"parenttype": CERT},
															 fields=["parent"])})
	return [frappe.get_doc(CERT, n) for n in names if frappe.db.exists(CERT, n)]


def _recalled(heats):
	if not heats or not frappe.db.exists("DocType", "Material Recall"):
		return None
	r = frappe.get_all("Material Recall", filters={"heat": ["in", heats], "status": "Open"}, fields=["name", "heat", "cause"], limit=1)
	return r[0] if r else None


def fit_for_job(lot, project) -> list[dict]:
	"""Findings: is this lot fit for this job's material requirements?"""
	from worgify.readiness import NOT_USABLE, SUSPENDED, USABLE

	reqs = job_requirements(project)
	heats = _lot_heats(lot)
	purpose = {"job": project}
	ref = {"doctype": "Batch", "name": lot}
	out = []
	recall = _recalled(heats)
	if recall:
		out.append({"status": NOT_USABLE, "layer": "state", "label": _("Heat"), "purpose": purpose, "ref": ref,
					"reason": _("heat {0} recalled").format(recall.heat) + (" " + _("by the mill") if recall.cause == "The mill's notice" else "")})
	if not reqs:
		return out
	grade = next((grade_of_heat(h) for h in heats if grade_of_heat(h)), None)
	mine = [r for r in reqs if not grade or r.grade == grade]
	if grade and not mine:
		asked = ", ".join(sorted({standard_and_name(r.grade)[1] or r.grade for r in reqs}))
		out.append({"status": NOT_USABLE, "layer": "state", "label": _("Material"), "purpose": purpose, "ref": ref,
					"reason": _("another material: the job asks {0}").format(asked)})
		return out
	certs = _lot_certificates(lot)
	for r in mine:
		if r.certificate_type:
			types = {c.certificate_type for c in certs if c.certificate_type}
			if r.certificate_type not in types:
				have = ", ".join(sorted(types)) or _("no certificate")
				out.append({"status": NOT_USABLE, "layer": "certificate", "label": _("Certificate"), "purpose": purpose,
							"ref": ref, "reason": _("{0}, the job asks {1}").format(have, r.certificate_type)})
		if flt(r.impact_energy):
			t_req, direction = flt(r.impact_temperature), (r.impact_direction or "Transverse").lower()
			best = None
			for c in certs:
				_chem, _mech, impact, _w, _p = values_of(c)
				for (t, d), values in _impact_sets(impact).items():
					if t is not None and abs(t - t_req) < 0.5 and d in (None, direction):
						best = max(best or 0, _mean(values))
			if best is None:
				out.append({"status": NOT_USABLE, "layer": "certificate", "label": _("Impact energy"), "purpose": purpose,
							"ref": ref, "reason": _("no impact test at {0}").format(temp(t_req))})
			elif best < flt(r.impact_energy):
				out.append({"status": NOT_USABLE, "layer": "certificate", "label": _("Impact energy"), "purpose": purpose,
							"ref": ref, "reason": _("impact {0} J at {1}, the job asks {2}").format(num(best, 0), temp(t_req),
																									 num(r.impact_energy, 0))})
			else:
				out.append({"status": USABLE, "layer": "certificate", "label": _("Impact energy"), "purpose": purpose,
							"ref": ref, "reason": _("impact {0} J at {1}").format(num(best, 0), temp(t_req))})
		if r.pmi_required and frappe.db.exists("DocType", "PMI Check"):
			done = frappe.db.exists("PMI Check", {"subject_doctype": "Batch", "subject": lot, "result": "Pass"})
			if not done:
				out.append({"status": SUSPENDED, "layer": "state", "label": _("PMI"), "purpose": purpose, "ref": ref,
							"reason": _("PMI not done yet")})
	if not any(f["status"] != USABLE for f in out) and not any(f["label"] == _("Impact energy") for f in out):
		out.append({"status": USABLE, "layer": "state", "label": _("Material"), "purpose": purpose, "ref": ref,
					"reason": _("fit: {0}").format(", ".join(sorted({standard_and_name(r.grade)[1] or r.grade for r in mine})))})
	return out


@frappe.whitelist(methods=["POST"])
def contest(name: str, reason: str) -> dict:
	"""The certificate does not stand up: said on it, with the reason, so every lot,
	recall and supplier evaluation that reads it knows (MA-03, MA-06)."""
	doc = frappe.get_doc(CERT, name)
	doc.check_permission("write")
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Say why the certificate is contested."))
	doc.contested = 1
	doc.contested_reason = reason
	doc.save()
	return {"message": _("Certificate {0} marked as contested.").format(doc.certificate_number or doc.name)}


@frappe.whitelist(methods=["POST"])
def open_non_conformity(name: str, lot: str | None = None) -> dict:
	"""A non-conformity on the lot this certificate covers, carrying what the check
	found (the quality app's own record, with its own permission)."""
	if "quality" not in frappe.get_installed_apps():
		frappe.throw(_("Non-conformities live in the quality app, which is not installed."))
	doc = frappe.get_doc(CERT, name)
	doc.check_permission("read")
	j = for_certificate(name)
	text = "\n".join(j["said"]) or j["headline"]
	create = frappe.get_attr("quality.quality.utils.create_ncr")
	ncr = create(ncr_title=_("Certificate {0}: {1}").format(doc.certificate_number or doc.name, ", ".join(j["short"]) or j["headline"])[:140],
				 ncr_type="Material", severity="Major", source="Supplier", description=text,
				 source_doctype="Batch" if lot else CERT, source_document=lot or doc.name)
	ncr_name = ncr if isinstance(ncr, str) else getattr(ncr, "name", None) or (ncr or {}).get("name")
	return {"name": ncr_name, "message": _("Non-conformity {0} opened.").format(ncr_name)}


@frappe.whitelist()
def job_asks(project: str) -> dict:
	"""What the job asks of its material, in words (the head of *Issue to a job*)."""
	frappe.has_permission("Project", "read", doc=project, throw=True)
	out = []
	for r in job_requirements(project):
		_s, name, label = standard_and_name(r.grade)
		bits = [" ".join(x for x in [name or label, r.delivery_condition] if x)]
		if r.certificate_type:
			bits.append(_("certificate {0}").format(r.certificate_type.replace("EN 10204 ", "")))
		if flt(r.impact_energy):
			bits.append(_("impact {0} J at {1}").format(num(r.impact_energy, 0), temp(r.impact_temperature)))
		if flt(r.cev_max):
			bits.append(_("CEV ≤ {0}").format(num(r.cev_max, 2, 2)))
		if r.pmi_required:
			bits.append(_("PMI on every piece"))
		out.append({"title": r.title, "grade": r.grade, "asks": " · ".join(bits), "source": r.source})
	return {"requirements": out}
