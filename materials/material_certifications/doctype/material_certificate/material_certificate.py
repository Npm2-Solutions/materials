# Copyright (c) 2025, NPM2 Solutions Srl and contributors
# For license information, please see license.txt

"""
Material Certificate Controller
================================

A material certificate is a DOCUMENTARY artifact (EN 10204 / EN 10168 / ASME MTR)
that *reports* intrinsic heat data — it does NOT carry the incoming-acceptance
verdict. Per the canonical model (guides/01-ecosystem/12), three concerns are
kept on three different objects:

  - certificate lifecycle (Valid / Expired / Revoked)  → here, on the certificate
  - incoming acceptance verdict (accept / reject / …)  → on stock's Material
        Inspection Request (status + disposition) — NOT here
  - goods receipt                                       → on the stock batch

The certificate→batch association is stored on the BATCH side
(Batch.certificates child table, "Mill Test Certificate" junction), never as a
field on the certificate. Both the batch and the certificate reference shared
Material Heat records; the association is via the heat bridge.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate


class MaterialCertificate(Document):
	def validate(self):
		self.update_status()
		self.validate_spec_ranges()
		self.validate_results_within_spec()
		self.validate_certificate_uniqueness()
		self.validate_pmi_fields()

	def update_status(self):
		"""Auto-compute lifecycle status based on expiry date.

		Lifecycle only: Valid / Expired / Revoked. The incoming-acceptance
		verdict lives on stock's Material Inspection Request, not here.
		"""
		if self.status == "Revoked":
			return
		if self.expiry_date and getdate(self.expiry_date) < getdate(nowdate()):
			self.status = "Expired"
		else:
			self.status = "Valid"

	@frappe.whitelist()
	def revoke(self):
		"""Revoke this certificate (lifecycle action — quality decision)."""
		frappe.only_for(["STK Quality Manager", "STK Manager", "System Manager"])
		self.status = "Revoked"
		self.save()

	def validate_spec_ranges(self):
		"""Reject if spec_min > spec_max on any result row."""
		for table_field in ("chemical_results", "mechanical_results"):
			for row in (getattr(self, table_field, None) or []):
				if row.spec_min and row.spec_max and flt(row.spec_min) > flt(row.spec_max):
					label = getattr(row, "element", None) or getattr(row, "test_type", None) or ""
					frappe.throw(
						_("Row {0} ({1}): Spec min ({2}) is greater than spec max ({3}). "
						  "Please correct the spec range.").format(
							row.idx, label, row.spec_min, row.spec_max
						)
					)

	def validate_results_within_spec(self):
		"""Auto-compute within_spec for each chemical and mechanical result row.

		Flags rows as within spec when the value falls between spec_min and spec_max.
		If either limit is zero/unset, that side of the range is not checked.
		Shows an orange warning if any result is out of spec.
		"""
		out_of_spec = []

		for row in (self.chemical_results or []):
			row.within_spec = self._check_within_spec(
				row.value_percent, row.spec_min, row.spec_max
			)
			if not row.within_spec and (row.spec_min or row.spec_max):
				out_of_spec.append(
					_("Chemical: {0} = {1}% (spec: {2} - {3})").format(
						row.element,
						flt(row.value_percent, 4),
						flt(row.spec_min, 4) if row.spec_min else "-",
						flt(row.spec_max, 4) if row.spec_max else "-",
					)
				)

		for row in (self.mechanical_results or []):
			row.within_spec = self._check_within_spec(
				row.value, row.spec_min, row.spec_max
			)
			if not row.within_spec and (row.spec_min or row.spec_max):
				out_of_spec.append(
					_("Mechanical: {0} = {1} {2} (spec: {3} - {4})").format(
						row.test_type,
						flt(row.value),
						row.unit or "",
						flt(row.spec_min) if row.spec_min else "-",
						flt(row.spec_max) if row.spec_max else "-",
					)
				)

		if out_of_spec:
			frappe.msgprint(
				_("The following results are outside specification limits:<br>{0}").format(
					"<br>".join(out_of_spec)
				),
				indicator="orange",
				title=_("Out of Spec Warning"),
			)

	def validate_certificate_uniqueness(self):
		"""Warn if same certificate number already exists from the same issuer."""
		if not self.certificate_number:
			return
		filters = {
			"certificate_number": self.certificate_number,
			"name": ["!=", self.name],
		}
		if self.issuing_body:
			filters["issuing_body"] = self.issuing_body
		duplicates = frappe.db.get_all(
			"Material Certificate", filters=filters, fields=["name"], limit=3
		)
		if duplicates:
			names = ", ".join(d.name for d in duplicates)
			frappe.msgprint(
				_("Certificate number {0} already exists: {1}. "
				  "If the data differs, one may be fraudulent.").format(
					frappe.bold(self.certificate_number), names
				),
				indicator="orange",
				title=_("Duplicate Certificate Number"),
			)

	def validate_pmi_fields(self):
		"""Validate PMI fields when certificate type is PMI Report.

		NOTE: PMI as an *incoming-verification* activity belongs on the quality
		inspection / receipt record (see guides/01-ecosystem/12). The PMI tab
		here only documents a PMI-type certificate's reported test points.
		"""
		if self.certificate_type != "PMI Report":
			return

		if not self.pmi_test_points or len(self.pmi_test_points) == 0:
			frappe.msgprint(
				_("PMI Report should have at least one test point."),
				indicator="orange",
				title=_("Missing PMI Test Points"),
			)
			return

		# Auto-compute overall result
		results = [tp.result for tp in self.pmi_test_points]
		if "Fail" in results:
			self.pmi_overall_result = "Fail"
		elif "Inconclusive" in results:
			self.pmi_overall_result = "Conditional"
		else:
			self.pmi_overall_result = "Pass"

	def on_update(self):
		"""Sync verification metadata with the verified checkbox — both directions."""
		if self.verified:
			if not self.verification_date:
				self.db_set("verification_date", nowdate())
			if not self.verified_by:
				self.db_set("verified_by", frappe.session.user)
		else:
			# Verified unchecked → clear stale verifier metadata so a phantom
			# verification can never leak onto prints/reports (audit P1).
			if self.verified_by:
				self.db_set("verified_by", None)
			if self.verification_date:
				self.db_set("verification_date", None)

	def covered_heat_names(self):
		"""Material Heat names this certificate documents (via heats_covered)."""
		return {
			row.heat for row in (self.heats_covered or []) if getattr(row, "heat", None)
		}

	@staticmethod
	def _check_within_spec(value, spec_min, spec_max):
		"""Check if a value falls within spec limits.

		Returns 1 (within spec) or 0 (out of spec).
		If both limits are unset, returns 1 (no spec to violate).
		"""
		val = flt(value)

		if not spec_min and not spec_max:
			return 1

		if spec_min and val < flt(spec_min):
			return 0

		if spec_max and val > flt(spec_max):
			return 0

		return 1


# ─────────────────────────────────────────────────────────────────────
# Batch ↔ Certificate association (via the Material Heat bridge)
#
# The certificate does NOT store a batch. Both reference Material Heat:
#   Batch.heat_number / Batch.heat_numbers[].heat_number → Material Heat
#   Material Certificate.heats_covered[].heat            → Material Heat
# The stored link lives on the BATCH (Batch.certificates child table).
# ─────────────────────────────────────────────────────────────────────

def _batch_heat_names(batch_doc):
	"""Set of Material Heat names referenced by a Batch (primary + child)."""
	heats = set()
	if batch_doc.get("heat_number"):
		heats.add(batch_doc.heat_number)
	for row in (batch_doc.get("heat_numbers") or []):
		if row.get("heat_number"):
			heats.add(row.heat_number)
	return heats


def _certs_covering_heats(heat_names):
	"""Material Certificate names whose heats_covered includes any of heat_names."""
	if not heat_names:
		return set()
	rows = frappe.get_all(
		"Material Heat Coverage",
		filters={"heat": ["in", list(heat_names)], "parenttype": "Material Certificate"},
		fields=["parent", "heat"],
	)
	return {r.parent for r in rows}


@frappe.whitelist()
def suggest_certificate_matches(batch_no):
	"""Find Material Certificates that document a batch's heats (via Material Heat).

	Returns potential matches classified exact / partial. Already-linked certs
	(present in the batch's `certificates` child) are excluded.
	"""
	batch = frappe.get_doc("Batch", batch_no)
	batch_heats = _batch_heat_names(batch)
	if not batch_heats:
		return []

	already_linked = {
		row.certificate for row in (batch.get("certificates") or []) if row.get("certificate")
	}

	matches = []
	for cert_name in _certs_covering_heats(batch_heats):
		if cert_name in already_linked:
			continue
		cert = frappe.db.get_value(
			"Material Certificate", cert_name,
			["certificate_number", "certificate_type", "status"], as_dict=True,
		)
		if not cert:
			continue
		cert_heats = set(frappe.get_all(
			"Material Heat Coverage",
			filters={"parent": cert_name, "parenttype": "Material Certificate"},
			pluck="heat",
		))
		matched = batch_heats & cert_heats
		if not matched:
			continue
		matches.append({
			"name": cert_name,
			"certificate_number": cert.certificate_number,
			"certificate_type": cert.certificate_type,
			"status": cert.status,
			"match_type": "exact" if matched == batch_heats else "partial",
			"matched_heats": sorted(matched),
		})

	matches.sort(key=lambda m: {"exact": 0, "partial": 1}.get(m["match_type"], 2))
	return matches


@frappe.whitelist()
def auto_link_certificate(batch_no, certificate_name):
	"""Link a Material Certificate to a Batch (stored on the BATCH side).

	Appends a row to Batch.certificates ("Mill Test Certificate" junction).
	The certificate is not modified — the association lives on the batch.
	"""
	if not frappe.has_permission("Batch", "write", doc=batch_no):
		frappe.throw(_("Not permitted to modify Batch {0}.").format(batch_no))

	batch = frappe.get_doc("Batch", batch_no)
	existing = {row.certificate for row in (batch.certificates or []) if row.certificate}
	if certificate_name in existing:
		return {"status": "already_linked", "certificate": certificate_name, "batch": batch_no}

	cert = frappe.db.get_value(
		"Material Certificate", certificate_name,
		["certificate_type", "certificate_number"], as_dict=True,
	)
	if not cert:
		frappe.throw(_("Material Certificate {0} not found.").format(certificate_name))

	batch.append("certificates", {
		"certificate": certificate_name,
		"certificate_type": cert.certificate_type,
		"certificate_number": cert.certificate_number,
		"is_primary": 0 if existing else 1,
	})
	batch.save()
	return {"status": "linked", "certificate": certificate_name, "batch": batch_no}


@frappe.whitelist()
def get_batch_certificates(batch):
	"""Get all Material Certificates linked to a batch (from Batch.certificates)."""
	rows = frappe.get_all(
		"Mill Test Certificate",
		filters={"parent": batch, "parenttype": "Batch"},
		pluck="certificate",
	)
	cert_names = [c for c in rows if c]
	if not cert_names:
		return []
	return frappe.get_all(
		"Material Certificate",
		filters={"name": ["in", cert_names]},
		fields=[
			"name",
			"certificate_type",
			"certificate_number",
			"certificate_date",
			"status",
			"verified",
			"issuing_organization",
			"issuing_body",
			"applicable_standard",
		],
	)


@frappe.whitelist()
def extract_certificate_data(certificate_name):
	"""Extract data from an attached PDF certificate using text extraction.

	Uses pdfplumber for text-based PDFs (not image OCR).
	Returns structured data that can be reviewed and applied.
	"""
	import re

	# Check settings
	enabled = frappe.db.get_single_value("Stock Settings", "enable_certificate_extraction")
	if not enabled:
		frappe.throw(_("Certificate extraction is not enabled in Stock Settings."))

	cert = frappe.get_doc("Material Certificate", certificate_name)
	if not cert.attachment:
		frappe.throw(_("No PDF attachment found on this certificate."))

	# Get file path
	file_doc = frappe.get_doc("File", {"file_url": cert.attachment})
	file_path = file_doc.get_full_path()

	# Extract text
	text = ""
	try:
		import pdfplumber
		with pdfplumber.open(file_path) as pdf:
			for page in pdf.pages:
				text += (page.extract_text() or "") + "\n"
	except ImportError:
		try:
			import PyPDF2
			with open(file_path, "rb") as f:
				reader = PyPDF2.PdfReader(f)
				for page in reader.pages:
					text += (page.extract_text() or "") + "\n"
		except ImportError:
			frappe.throw(_("PDF extraction requires pdfplumber or PyPDF2. Please install one."))

	if not text.strip():
		frappe.throw(_("Could not extract text from PDF. The file may be image-based."))

	result = {"heat_numbers": [], "chemical": [], "mechanical": []}

	# Extract heat numbers
	heat_patterns = [
		r"(?:heat|melt|charge|schmelze)\s*(?:no|number|nr|#)?\s*[:=]?\s*([A-Z0-9\-/]+)",
	]
	for pattern in heat_patterns:
		for m in re.finditer(pattern, text, re.IGNORECASE):
			val = m.group(1).strip()
			if val and val not in result["heat_numbers"]:
				result["heat_numbers"].append(val)

	# Extract chemical elements
	elements = ["C", "Mn", "Si", "P", "S", "Cr", "Ni", "Mo", "V", "Cu", "Nb", "Ti", "Al", "N"]
	for element in elements:
		pattern = rf"\b{element}\b\s*[:=]?\s*(\d+\.?\d*)"
		m = re.search(pattern, text)
		if m:
			result["chemical"].append({
				"element": element,
				"value_percent": float(m.group(1)),
				"confidence": 80,
			})

	# Extract mechanical properties
	mech_patterns = [
		(r"(?:tensile|rm|ultimate)\s*(?:strength)?\s*[:=]?\s*(\d+\.?\d*)\s*(MPa|N/mm|ksi)?", "Tensile Strength"),
		(r"(?:yield|rp0[\.,]2|re)\s*(?:strength|point)?\s*[:=]?\s*(\d+\.?\d*)\s*(MPa|N/mm|ksi)?", "Yield Strength"),
		(r"(?:elongation|a5|a50)\s*[:=]?\s*(\d+\.?\d*)\s*(%)?", "Elongation"),
		(r"(?:impact|kv|charpy)\s*[:=]?\s*(\d+\.?\d*)\s*(J|ft-lb)?", "Impact"),
		(r"(?:hardness|hb|hrc|hrb|hv)\s*[:=]?\s*(\d+\.?\d*)", "Hardness"),
	]
	for pattern, test_type in mech_patterns:
		m = re.search(pattern, text, re.IGNORECASE)
		if m:
			result["mechanical"].append({
				"test_type": test_type,
				"value": float(m.group(1)),
				"unit": m.group(2) if m.lastindex >= 2 else "",
				"confidence": 75,
			})

	return result
