# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""What a standard says a grade must be — transcribed from the printed standard,
table by table, with the citation beside every number (Design 55 MA-03, MA-07).

A mill certificate prints its own limits beside its values, and judging a value
against the limit printed next to it is how a wrong certificate passes: the
3.1 of heat 24131 printed *S max 0,015* for a 13MnNi6-3, the standard says
0,010, and the certificate called itself compliant. The limits here come from
the standard; the certificate's own are shown, never used.

Read from the PDFs in ``guides/reference standards/`` (rendered to images, cell
by cell):

* **EN 10028-4:2017** — nickel alloy steels with specified low temperature
  properties (flat products): Table 1 (cast analysis), Table 2 (product analysis
  tolerances), Table 3 (room temperature mechanicals), Table 4 (impact).
* **EN 10216-5:2021** — seamless stainless tubes: Table 2 (cast analysis of
  austenitic corrosion resisting steels), Table 5 (product analysis deviations).

What is NOT here is said, never guessed: the impact table of the 9 % nickel
grades (EN 10028-4 Table 4, page 10) merges its heat treatment cells across two
directions in a way that cannot be read unambiguously, so those grades carry no
impact limits; the individual-value rule of a Charpy set lives in EN 10028-1,
which the library does not hold, so only the mean is judged.

A grade is found by its standard and its name (``("EN-10028-4", "13MnNi6-3")``),
because the same name lives in more than one standard: 13MnNi6-3 is a plate in
EN 10028-4 and a tube in EN 10216-4, with different tables.
"""

from __future__ import annotations

EN_10028_4 = {"standard": "EN-10028-4", "edition": "EN-10028-4-2017", "title": "EN 10028-4:2017"}
EN_10216_5 = {"standard": "EN-10216-5", "edition": "EN-10216-5-2021", "title": "EN 10216-5:2021"}

# ── EN 10028-4:2017 ──────────────────────────────────────────────────────────
# Table 1 — Chemical composition (cast analysis), % by mass. (min, max); None = no limit.
_T1 = {
	"11MnNi5-3": {"number": "1.6212", "C": (None, 0.14), "Si": (None, 0.50), "Mn": (0.70, 1.50), "P": (None, 0.025),
				  "S": (None, 0.010), "Al": (0.020, None), "Nb": (None, 0.05), "Ni": (0.30, 0.80), "V": (None, 0.05)},
	"13MnNi6-3": {"number": "1.6217", "C": (None, 0.16), "Si": (None, 0.50), "Mn": (0.85, 1.70), "P": (None, 0.025),
				  "S": (None, 0.010), "Al": (0.020, None), "Nb": (None, 0.05), "Ni": (0.30, 0.85), "V": (None, 0.05)},
	"15NiMn6": {"number": "1.6228", "C": (None, 0.18), "Si": (None, 0.35), "Mn": (0.80, 1.50), "P": (None, 0.025),
				"S": (None, 0.010), "Ni": (1.30, 1.70), "V": (None, 0.05)},
	"12Ni14": {"number": "1.5637", "C": (None, 0.15), "Si": (None, 0.35), "Mn": (0.30, 0.80), "P": (None, 0.020),
			   "S": (None, 0.005), "Ni": (3.25, 3.75), "V": (None, 0.05)},
	"X12Ni5": {"number": "1.5680", "C": (None, 0.15), "Si": (None, 0.35), "Mn": (0.30, 0.80), "P": (None, 0.020),
			   "S": (None, 0.005), "Ni": (4.75, 5.25), "V": (None, 0.05)},
	"X8Ni9": {"number": "1.5662", "C": (None, 0.10), "Si": (None, 0.35), "Mn": (0.30, 0.80), "P": (None, 0.020),
			  "S": (None, 0.005), "Mo": (None, 0.10), "Ni": (8.5, 10.0), "V": (None, 0.05)},
	"X7Ni9": {"number": "1.5663", "C": (None, 0.10), "Si": (None, 0.35), "Mn": (0.30, 0.80), "P": (None, 0.015),
			  "S": (None, 0.005), "Mo": (None, 0.10), "Ni": (8.5, 10.0), "V": (None, 0.01)},
}
# Table 1 footnote a: "The content of Cr + Cu + Mo shall not exceed 0,50 %." (every grade)
# Table 1 footnote b: "For nominal thicknesses ≤ 40 mm, a minimum nickel content of 0,15 % is permitted."
_T1_THIN_NI = {"11MnNi5-3", "13MnNi6-3"}

# Table 2 — Permissible product analysis tolerances on the Table 1 limits.
# (element, cast limit up to, deviation, sign): "+" above the max only, "-" below the min only, "±" both.
_T2 = [
	("C", 0.18, 0.02, "+"), ("Si", 0.50, 0.05, "+"), ("Mn", 1.00, 0.05, "±"), ("Mn", 1.70, 0.10, "±"),
	("P", 0.015, 0.003, "+"), ("P", 0.025, 0.005, "+"), ("S", 0.010, 0.003, "+"), ("Al", None, 0.005, "-"),
	("Mo", 0.10, 0.03, "+"), ("Nb", 0.05, 0.01, "+"), ("Ni", 0.85, 0.05, "±"), ("Ni", 3.75, 0.07, "±"),
	("Ni", 10.0, 0.10, "±"), ("V", 0.05, 0.01, "+"),
]

# Table 3 — Mechanical properties at room temperature. ReH min by nominal thickness
# [(t up to mm, MPa)], Rm (min, max) MPa, A min %. Usual delivery condition.
_T3 = {
	"11MnNi5-3": {"condition": "+N (+NT)", "ReH": [(30, 285), (50, 275), (80, 265)], "Rm": (420, 530), "A": 24},
	"13MnNi6-3": {"condition": "+N (+NT)", "ReH": [(30, 355), (50, 345), (80, 335)], "Rm": (490, 610), "A": 22},
	"15NiMn6": {"condition": "+N or +NT or +QT", "ReH": [(30, 355), (50, 345), (80, 335)], "Rm": (490, 640), "A": 22},
	"12Ni14": {"condition": "+N or +NT or +QT", "ReH": [(30, 355), (50, 345), (80, 335)], "Rm": (490, 640), "A": 22},
	"X12Ni5": {"condition": "+N or +NT or +QT", "ReH": [(30, 390), (50, 380)], "Rm": (530, 710), "A": 20},
	"X8Ni9": {"condition": "+N plus +NT (+NT640)", "ReH": [(30, 490), (50, 480)], "Rm": (640, 840), "A": 18},
	"X7Ni9": {"condition": "+QT", "ReH": [(30, 585), (125, 575)], "Rm": (680, 820), "A": 18},
}

# Table 4 — Minimum impact energy KV2 in J at a temperature in °C, by direction.
# Footnote d (the transverse values marked so): "A minimum impact energy value of
# 40 J may be agreed at the time of enquiry and order" (and clause 8.4).
_T4 = {
	"11MnNi5-3": {"up_to": 80,
				  "longitudinal": {-60: 40, -50: 45, -40: 50, -20: 55, 0: 60, 20: 70},
				  "transverse": {-60: 27, -50: 30, -40: 35, -20: 45, 0: 50, 20: 50}, "d": {-60, -50, -40}},
	"13MnNi6-3": {"up_to": 80,
				  "longitudinal": {-60: 40, -50: 45, -40: 50, -20: 55, 0: 60, 20: 70},
				  "transverse": {-60: 27, -50: 30, -40: 35, -20: 45, 0: 50, 20: 50}, "d": {-60, -50, -40}},
	"15NiMn6": {"up_to": 80,
				"longitudinal": {-80: 40, -60: 50, -50: 50, -40: 60, -20: 65, 0: 65, 20: 65},
				"transverse": {-80: 27, -60: 35, -50: 35, -40: 40, -20: 45, 0: 50, 20: 50}, "d": {-80, -60, -50}},
	"12Ni14": {"up_to": 80,
			   "longitudinal": {-100: 40, -80: 45, -60: 50, -50: 50, -40: 55, -20: 55, 0: 60, 20: 65},
			   "transverse": {-100: 27, -80: 30, -60: 35, -50: 35, -40: 35, -20: 45, 0: 50, 20: 50},
			   "d": {-100, -80, -60, -50, -40}},
	# X12Ni5: the −120 °C column carries footnote c (applicable at −110 °C up to 25 mm,
	# at −115 °C from 25 to 30 mm) — left out rather than simplified.
	"X12Ni5": {"up_to": 50,
			   "longitudinal": {-100: 50, -80: 60, -60: 65, -50: 65, -40: 65, -20: 70, 0: 70, 20: 70},
			   "transverse": {-100: 30, -80: 40, -60: 45, -50: 45, -40: 45, -20: 55, 0: 60, 20: 60}, "d": {-100}},
}

# ── EN 10216-5:2021 ──────────────────────────────────────────────────────────
# Table 2 — Chemical composition (cast analysis) of austenitic corrosion resisting steels.
_T2_TUBE = {
	"X2CrNi18-9": {"number": "1.4307", "C": (None, 0.030), "Si": (None, 1.00), "Mn": (None, 2.00), "P": (None, 0.040),
				   "S": (None, 0.015), "N": (None, 0.10), "Cr": (17.5, 19.5), "Ni": (8.0, 10.0)},
	"X2CrNi19-11": {"number": "1.4306", "C": (None, 0.030), "Si": (None, 1.00), "Mn": (None, 2.00), "P": (None, 0.040),
					"S": (None, 0.015), "N": (None, 0.10), "Cr": (18.0, 20.0), "Ni": (10.0, 12.0)},
	"X5CrNi18-10": {"number": "1.4301", "C": (None, 0.07), "Si": (None, 1.00), "Mn": (None, 2.00), "P": (None, 0.040),
					"S": (None, 0.015), "N": (None, 0.10), "Cr": (17.0, 19.5), "Ni": (8.0, 10.5)},
	"X2CrNiMo17-12-2": {"number": "1.4404", "C": (None, 0.030), "Si": (None, 1.00), "Mn": (None, 2.00), "P": (None, 0.040),
						"S": (None, 0.015), "N": (None, 0.10), "Cr": (16.5, 18.5), "Mo": (2.0, 2.5), "Ni": (10.0, 13.0)},
	"X5CrNiMo17-12-2": {"number": "1.4401", "C": (None, 0.07), "Si": (None, 1.00), "Mn": (None, 2.00), "P": (None, 0.040),
						"S": (None, 0.015), "N": (None, 0.10), "Cr": (16.5, 18.5), "Mo": (2.0, 2.5), "Ni": (10.0, 13.0)},
}
# Table 5 — Permissible deviations of the product analysis from the cast limits.
_T5 = [
	("C", 0.030, 0.005, "+"), ("C", 0.15, 0.01, "±"), ("Si", 2.00, 0.05, "±"), ("Mn", 1.00, 0.03, "+"),
	("Mn", 2.00, 0.04, "±"), ("Mn", 7.00, 0.10, "±"), ("P", 0.030, 0.003, "+"), ("P", 0.040, 0.005, "+"),
	("S", 0.015, 0.003, "+"), ("S", 0.030, 0.005, "+"), ("N", 0.35, 0.01, "±"), ("Cr", 20.0, 0.20, "±"),
	("Cr", 28.0, 0.25, "±"), ("Cu", 1.00, 0.07, "±"), ("Mo", 0.60, 0.03, "±"), ("Mo", 1.75, 0.05, "±"),
	("Mo", 7.0, 0.10, "±"), ("Nb", 1.25, 0.05, "±"), ("Ni", 5.0, 0.07, "±"), ("Ni", 10.0, 0.10, "±"),
	("Ni", 20.0, 0.15, "±"), ("Ni", 35.0, 0.20, "±"), ("Ti", 0.80, 0.05, "±"),
]

# The carbon equivalent the purchaser may ask for (ASME BPVC II-A 2025, SA-106 S6.1 and S9.2,
# the IIW formula): CE = C + Mn/6 + (Cr + Mo + V)/5 + (Ni + Cu)/15.
CEV_SOURCE = "ASME BPVC II-A 2025, SA-106 S6.1"


def cev(values: dict) -> tuple[float | None, list[str]]:
	"""The carbon equivalent from what the certificate printed, and the
	elements of the formula it did not print (computed as zero, said aloud)."""
	if values.get("C") is None or values.get("Mn") is None:
		return None, ["C", "Mn"]
	missing = [e for e in ("Cr", "Mo", "V", "Ni", "Cu") if values.get(e) is None]
	g = lambda e: values.get(e) or 0  # noqa: E731
	return round(g("C") + g("Mn") / 6 + (g("Cr") + g("Mo") + g("V")) / 5 + (g("Ni") + g("Cu")) / 15, 3), missing


def _band(limit, rows):
	for up_to, deviation, sign in rows:
		if up_to is None or limit is None or limit <= up_to + 1e-9:
			return deviation, sign
	return None, None


def _tolerance(table, element, low, high):
	"""Each limit is widened by the deviation of its own band (the tables are by
	the specified value: Mn 0,85 and Mn 1,70 sit in different rows)."""
	rows = [(up_to, dev, sign) for el, up_to, dev, sign in table if el == element]
	if not rows:
		return low, high
	if low is not None:
		dev, sign = _band(low, rows)
		if dev is not None and sign in ("±", "-"):
			low = round(low - dev, 4)
	if high is not None:
		dev, sign = _band(high, rows)
		if dev is not None and sign in ("±", "+"):
			high = round(high + dev, 4)
	return low, high


def limits(standard: str, grade: str, thickness: float | None = None, product: bool = False) -> dict | None:
	"""Everything a standard says this grade must be, or None when it is not
	transcribed. ``product``: a reading on the product (a PMI) is judged on the
	cast limits widened by the standard's product-analysis tolerances."""
	if standard == EN_10028_4["standard"] and grade in _T1:
		cast = {k: v for k, v in _T1[grade].items() if k != "number"}
		if grade in _T1_THIN_NI and thickness and thickness <= 40:
			cast["Ni"] = (0.15, cast["Ni"][1])
		chem = {e: (_tolerance(_T2, e, *lim) if product else lim) for e, lim in cast.items()}
		out = {"source": EN_10028_4, "grade": grade, "number": _T1[grade]["number"], "chemistry": chem,
			   "chemistry_clause": "Table 2" if product else "Table 1",
			   "sums": [{"elements": ["Cr", "Cu", "Mo"], "max": 0.50, "clause": "Table 1, footnote a"}],
			   "thin_nickel": bool(grade in _T1_THIN_NI and thickness and thickness <= 40)}
		t3 = _T3.get(grade)
		if t3:
			reh = None
			if thickness:
				reh = next((mpa for up_to, mpa in t3["ReH"] if thickness <= up_to), None)
			out["mechanical"] = {"condition": t3["condition"], "ReH": reh, "ReH_bands": t3["ReH"], "Rm": t3["Rm"],
								 "A": t3["A"], "clause": "Table 3"}
		t4 = _T4.get(grade)
		if t4:
			out["impact"] = {"longitudinal": t4["longitudinal"], "transverse": t4["transverse"], "up_to": t4["up_to"],
							 "agreed_40": sorted(t4["d"]), "clause": "Table 4"}
		return out
	if standard == EN_10216_5["standard"] and grade in _T2_TUBE:
		cast = {k: v for k, v in _T2_TUBE[grade].items() if k != "number"}
		chem = {e: (_tolerance(_T5, e, *lim) if product else lim) for e, lim in cast.items()}
		return {"source": EN_10216_5, "grade": grade, "number": _T2_TUBE[grade]["number"], "chemistry": chem,
				"chemistry_clause": "Table 5" if product else "Table 2", "sums": []}
	return None


def transcribed() -> list[tuple[str, str]]:
	"""(standard, grade) of every grade written down here."""
	return [(EN_10028_4["standard"], g) for g in _T1] + [(EN_10216_5["standard"], g) for g in _T2_TUBE]


def by_number(number: str) -> tuple[str, str] | None:
	"""(standard, grade) for a steel number (1.4404) — what a tube's marking prints."""
	for g, row in _T1.items():
		if row["number"] == number:
			return EN_10028_4["standard"], g
	for g, row in _T2_TUBE.items():
		if row["number"] == number:
			return EN_10216_5["standard"], g
	return None
