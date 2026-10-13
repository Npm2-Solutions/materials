# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""Reading a mill certificate (EN 10204 3.1 / 3.2 / 2.2) into what it says — the
number, the heat, the grade, the order it names, the product, the chemistry, the
tensile and impact tests — with the box each value was read from (Design 55
MA-02, X-certificato: *every value opens the point of the PDF it was read from*).

It proposes; a person confirms. Nothing read here is stored until somebody saves
it, and what could not be read is said, never filled: a scan has no words and
comes back as such.

The chemistry table is found by its header — a line carrying at least four
element symbols as words — and read column by column under it: a row starting
*max*/*min* is the certificate's own printed limit (kept, shown, never used to
judge), a row starting with a heat number carries the values.
"""

from __future__ import annotations

import re

from worgify.utils import pdf_words as pw

SYMBOLS = {"C", "Si", "Mn", "P", "S", "Al", "Cr", "Mo", "Nb", "Ni", "V", "Cu", "N", "Ti", "B", "W", "Co", "Ceq", "CEV"}
TYPES = (("3.2", "EN 10204 3.2"), ("3.1", "EN 10204 3.1"), ("2.2", "EN 10204 2.2"), ("2.1", "EN 10204 2.1"))


def _value(line, label):
	words = pw.after(line, label)
	if not words:
		return None, None
	return words, " ".join(w["text"] for w in words)


def _first(words):
	return words[:1] if words else []


def read(file_url: str) -> dict:
	got = pw.read(file_url)
	out = {"scanned": got["scanned"], "fields": {}, "chemistry": {}, "printed": {}, "mechanical": {}, "impact": [],
		   "direction": None, "not_read": []}
	if got["scanned"]:
		out["not_read"].append("everything: the file is a scan, with no words to read")
		return out
	lines = pw.lines(got)
	fields = out["fields"]

	def keep(key, words, value=None):
		if words and key not in fields:
			fields[key] = {"value": value if value is not None else " ".join(w["text"] for w in words), "at": pw.box_of(words)}

	for i, ln in enumerate(lines):
		text = ln["text"]
		for t, label in TYPES:
			if re.search(rf"10204\s*[-–—:]?\s*{re.escape(t)}\b", text) or re.search(rf"\b{re.escape(t)}\b", text) and "10204" in text:
				keep("certificate_type", [w for w in ln["words"] if t in w["text"]] or ln["words"], label)
		m = re.search(r"\b(?:No\.?|N\.|Nr\.?|Number)\s*([A-Z0-9][\w\-/]+)", text)
		if m and "certificate_number" not in fields and ("CERTIFICATE" in text.upper() or "No." in text):
			words = [w for w in ln["words"] if w["text"] == m.group(1)]
			keep("certificate_number", words, m.group(1))
		for key, label, take in (
			("heat", r"(?:Heat|Cast|Colata|Schmelze|Melt)\s*(?:No\.?|n\.)?\s*:?", 1),
			("order", r"(?:Order|Ordine|Bestellung|Your order)\s*(?:No\.?|n\.)?\s*:?", 1),
			("grade", r"(?:Grade|Steel grade|Qualità|Werkstoff)\s*:?", 2),
			("standard", r"(?:Standard|Norma|Specification)\s*:?", 3),
			("quantity", r"(?:Quantity|Quantità|Qty)\s*:?", 2),
			("date", r"(?:Date|Data|Datum)\s*:?", 1),
		):
			words, _v = _value(ln, label)
			if words:
				words = words[:take]
				if key == "standard":
					words = [w for w in words if not w["text"].lower().startswith(("heat", "order"))][:2]
				keep(key, words)
		m = re.search(r"(?:Product|Prodotto)\s*:?\s*(\w+)\s+(\d+(?:[.,]\d+)?)\s*[x×]", text, re.I)
		if m and "thickness" not in fields:
			words = [w for w in ln["words"] if w["text"] == m.group(2)]
			keep("thickness", words, pw.number(m.group(2)))
			words = []
			for w in ln["words"][1:]:
				if w["text"].endswith(":"):
					break
				words.append(w)
			keep("product", words, " ".join(w["text"] for w in words))

		# the chemistry table: the header, then its rows
		symbols = [w for w in ln["words"] if w["text"].strip(".:") in SYMBOLS]
		if len(symbols) >= 4 and not out["chemistry"]:
			cols = [(w["text"].strip(".:"), (w["box"][1] + w["box"][3]) / 2) for w in symbols]
			for row in lines[i + 1:i + 6]:
				first = row["words"][0]["text"].lower() if row["words"] else ""
				target = out["printed"] if first.startswith(("max", "min", "spec")) else out["chemistry"]
				if target is out["chemistry"] and not any(pw.number(w["text"]) is not None for w in row["words"][1:]):
					continue
				for w in row["words"][1:]:
					v = pw.number(w["text"])
					if v is None:
						continue
					cx = (w["box"][1] + w["box"][3]) / 2
					el, dist = min(((c, abs(cx - x)) for c, x in cols), key=lambda t: t[1])
					if dist < 0.05:
						target[el] = {"value": v, "at": pw.box_of([w])}
				if target is out["chemistry"] and out["chemistry"]:
					break

		# tensile and impact
		for key, label in (("ReH", r"R\s*e\s*H|Rp\s*0[.,]2|Yield"), ("Rm", r"R\s*m\b|Tensile strength"), ("A", r"\bA\s*(?:5|%)?\b")):
			for j, w in enumerate(ln["words"]):
				if re.fullmatch(label, w["text"]) and j + 1 < len(ln["words"]):
					v = pw.number(ln["words"][j + 1]["text"])
					if v is not None and key not in out["mechanical"]:
						out["mechanical"][key] = {"value": v, "at": pw.box_of([ln["words"][j + 1]])}
		m = re.search(r"(transverse|longitudinal|trasversal|longitudinal)", text, re.I)
		if m and re.search(r"impact|KV|resilienza|Charpy", text, re.I):
			out["direction"] = "Transverse" if m.group(1).lower().startswith("trans") else "Longitudinal"
		m = re.search(r"(?:temperature|temperatura|T)\s*:?\s*([−\-–]?\s*\d+)\s*°?\s*C\s*:?\s*(.*?)J?\s*$", text, re.I)
		if m and re.search(r"temperat", text, re.I):
			t = pw.number(m.group(1).replace(" ", ""))
			values = [pw.number(x) for x in re.findall(r"\d+(?:[.,]\d+)?", m.group(2))]
			values = [v for v in values if v is not None]
			if t is not None and values:
				vw = [w for w in ln["words"] if pw.number(w["text"]) in values]
				out["impact"].append({"temperature": t, "values": values, "direction": None, "at": pw.box_of(vw)})
	for i in out["impact"]:
		i["direction"] = out["direction"]
	for key in ("certificate_number", "heat", "grade"):
		if key not in fields:
			out["not_read"].append(key)
	if not out["chemistry"]:
		out["not_read"].append("chemistry")
	return out


def apply(doc, reading: dict, heat_name: str | None = None):
	"""Write what was read onto a Material Certificate (the rows carry where each
	value was read). The heat is linked by its record name, made by the caller."""
	f = reading["fields"]
	if f.get("certificate_number") and not doc.get("certificate_number"):
		doc.certificate_number = f["certificate_number"]["value"]
	if f.get("certificate_type") and not doc.get("certificate_type"):
		doc.certificate_type = f["certificate_type"]["value"]
	if f.get("order") and not doc.get("order_reference"):
		doc.order_reference = f["order"]["value"]
	if f.get("thickness") and not doc.get("product_thickness"):
		doc.product_thickness = f["thickness"]["value"]
	grade = (f.get("grade") or {}).get("value") or ""
	if "+" in grade and not doc.get("delivery_condition"):
		doc.delivery_condition = "+" + grade.split("+", 1)[1].strip()
	if f.get("date") and not doc.get("certificate_date"):
		try:
			from frappe.utils import getdate

			doc.certificate_date = getdate(f["date"]["value"])
		except Exception:
			pass
	doc.set("chemical_results", [])
	options = {"C", "Mn", "Si", "P", "S", "Cr", "Ni", "Mo", "V", "Cu", "Nb", "Ti", "Al", "N", "B", "W"}
	for el, v in reading["chemistry"].items():
		p = reading["printed"].get(el) or {}
		doc.append("chemical_results", {"element": el if el in options else "Other", "element_other": None if el in options else el,
										"value_percent": v["value"], "spec_max": p.get("value"), "read_at": v["at"]})
	doc.set("mechanical_results", [])
	for key, test in (("ReH", "Yield Strength"), ("Rm", "Tensile Strength"), ("A", "Elongation")):
		v = reading["mechanical"].get(key)
		if v:
			doc.append("mechanical_results", {"test_type": test, "value": v["value"], "unit": "%" if key == "A" else "MPa",
											  "read_at": v["at"], "direction": reading.get("direction")})
	for i in reading["impact"]:
		for value in i["values"]:
			doc.append("mechanical_results", {"test_type": "Impact (Charpy)", "value": value, "unit": "J",
											  "temperature": f"{i['temperature']:g} °C", "direction": i.get("direction"),
											  "read_at": i["at"]})
	if heat_name:
		qty = (f.get("quantity") or {}).get("value") or ""
		n = re.search(r"\d+(?:[.,]\d+)?", qty)
		doc.set("heats_covered", [{"heat": heat_name, "qty_covered": float(n.group(0).replace(",", ".")) if n else 0,
								   "qty_unit": "pcs" if n else ""}])
	return doc
