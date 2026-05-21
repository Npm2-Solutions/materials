# Copyright (c) 2025, NPM2 Solutions Srl and contributors
# For license information, please see license.txt

"""
Material Certificate Controller
================================

Structured certificate document with chemical composition and mechanical test
results stored as queryable child tables. Results are auto-validated against
spec limits, and heat numbers are cross-checked against the linked batch.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate


class MaterialCertificate(Document):
	def validate(self):
		self.update_status()
		self.update_validation_status()
		self.validate_spec_ranges()
		self.validate_results_within_spec()
		self.validate_certificate_uniqueness()
		self.cross_check_heat_numbers_with_batch()
		self.validate_pmi_fields()

	def update_status(self):
		"""Auto-compute status based on expiry date."""
		if self.status == "Revoked":
			return
		if self.expiry_date and getdate(self.expiry_date) < getdate(nowdate()):
			self.status = "Expired"
		else:
			self.status = "Valid"

	def update_validation_status(self):
		"""Auto-compute validation_status based on verification and test results."""
		if self.validation_status == "Rejected":
			return  # terminal state
		if self.verified and self.verification_date:
			# Check if there are out-of-spec results that warrant Conditional
			has_out_of_spec = False
			for row in (self.chemical_results or []):
				if (row.spec_min or row.spec_max) and not self._check_within_spec(
					row.value_percent, row.spec_min, row.spec_max
				):
					has_out_of_spec = True
					break
			if not has_out_of_spec:
				for row in (self.mechanical_results or []):
					if (row.spec_min or row.spec_max) and not self._check_within_spec(
						row.value, row.spec_min, row.spec_max
					):
						has_out_of_spec = True
						break
			if has_out_of_spec:
				self.validation_status = "Conditional"
			else:
				self.validation_status = "Validated"
		elif self.validation_status != "Conditional":
			self.validation_status = "Pending Review"

	@frappe.whitelist()
	def revoke(self):
		"""Revoke this certificate."""
		self.status = "Revoked"
		self.save()

	@frappe.whitelist()
	def reject(self):
		"""Reject this certificate's validation."""
		self.validation_status = "Rejected"
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

	def cross_check_heat_numbers_with_batch(self):
		"""Compare certificate heat numbers against batch heat numbers.

		Warns (does not block) if the certificate covers heats not found
		in the batch, or if the batch has heats not covered by the certificate.
		"""
		if not self.batch or not self.heat_numbers_covered:
			return

		# Parse certificate heat numbers (one per line, strip whitespace)
		cert_heats = {
			h.strip()
			for h in self.heat_numbers_covered.split("\n")
			if h.strip()
		}

		if not cert_heats:
			return

		# Get batch heat numbers from Batch Heat Number child table
		batch_heats = set()
		batch_doc = frappe.get_doc("Batch", self.batch)

		# Primary heat number
		if batch_doc.heat_number:
			batch_heats.add(batch_doc.heat_number.strip())

		# Child table heat numbers
		for row in (batch_doc.heat_numbers or []):
			if row.heat_number:
				batch_heats.add(row.heat_number.strip())

		if not batch_heats:
			return

		# Find mismatches
		cert_only = cert_heats - batch_heats
		batch_only = batch_heats - cert_heats

		warnings = []
		if cert_only:
			warnings.append(
				_("Heat numbers on certificate but not on batch: {0}").format(
					", ".join(sorted(cert_only))
				)
			)
		if batch_only:
			warnings.append(
				_("Heat numbers on batch but not on certificate: {0}").format(
					", ".join(sorted(batch_only))
				)
			)

		if warnings:
			frappe.msgprint(
				"<br>".join(warnings),
				indicator="yellow",
				title=_("Heat Number Mismatch"),
			)

	def validate_pmi_fields(self):
		"""Validate PMI fields when certificate type is PMI Report."""
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
		"""Auto-set verification metadata when verified checkbox is toggled."""
		if self.verified and not self.verification_date:
			self.db_set("verification_date", nowdate())
		if self.verified and not self.verified_by:
			self.db_set("verified_by", frappe.session.user)

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


@frappe.whitelist()
def suggest_certificate_matches(batch_no):
	"""Find Material Certificates that match a batch's heat numbers.

	Returns list of potential matches with match quality classification.
	"""
	batch = frappe.get_doc("Batch", batch_no)

	# Collect batch heat numbers
	batch_heats = set()
	if batch.heat_number:
		batch_heats.add(batch.heat_number.strip())
	for row in (batch.heat_numbers or []):
		if row.heat_number:
			batch_heats.add(row.heat_number.strip())

	if not batch_heats:
		return []

	# Get already-linked certificates
	existing = set(frappe.get_all(
		"Material Certificate",
		filters={"batch": batch_no},
		pluck="name",
	))

	# Search certificates by heat numbers
	conditions = " OR ".join(["heat_numbers_covered LIKE %s"] * len(batch_heats))
	params = [f"%{h}%" for h in batch_heats]

	candidates = frappe.db.sql(f"""
		SELECT name, certificate_number, certificate_type, heat_numbers_covered, status
		FROM `tabMaterial Certificate`
		WHERE ({conditions})
		AND name NOT IN ({','.join(['%s'] * len(existing)) if existing else "''"})
	""", params + list(existing), as_dict=True)

	matches = []
	for cert in candidates:
		cert_heats = {
			h.strip() for h in (cert.heat_numbers_covered or "").split("\n") if h.strip()
		}
		matched = batch_heats & cert_heats
		if not matched:
			continue

		if matched == batch_heats:
			match_type = "exact"
		elif len(matched) > 0:
			match_type = "partial"
		else:
			match_type = "weak"

		matches.append({
			"name": cert.name,
			"certificate_number": cert.certificate_number,
			"certificate_type": cert.certificate_type,
			"status": cert.status,
			"match_type": match_type,
			"matched_heats": list(matched),
		})

	# Sort: exact first, then partial
	matches.sort(key=lambda m: {"exact": 0, "partial": 1, "weak": 2}.get(m["match_type"], 3))
	return matches


@frappe.whitelist()
def auto_link_certificate(batch_no, certificate_name):
	"""Link a Material Certificate to a Batch."""
	cert = frappe.get_doc("Material Certificate", certificate_name)
	if cert.batch and cert.batch != batch_no:
		frappe.throw(
			_("Certificate {0} is already linked to batch {1}.").format(
				certificate_name, cert.batch
			)
		)
	cert.batch = batch_no
	cert.save(ignore_permissions=True)
	return {"status": "linked", "certificate": certificate_name, "batch": batch_no}


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


@frappe.whitelist()
def get_batch_certificates(batch):
	"""Get all certificates for a batch."""
	return frappe.get_all(
		"Material Certificate",
		filters={"batch": batch},
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
