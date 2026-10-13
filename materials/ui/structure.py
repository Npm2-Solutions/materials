# Copyright (c) 2026, NPM2 Solutions Srl and contributors
# For license information, please see license.txt
"""*Materiali* in the interface (guide 33 §2, Design 55 §6.3). The space is
materials': it stays on every bench that keeps the metal register, with or
without the warehouse. Where stock is installed it adds the warehouse's pages in
front (*Magazzino*, *Acquisti*) and its lots and checks to the traceability page
(``stock/ui/structure.py``); the metal keeps its heats, certificates, recalls,
PMI and what each job asks of its material.

The catalogs are Frappe Roles (G13); Frappe's permission on what an app opens is
the only gate. Read by ``worgify.interface.structure``; nothing here grants
anything (P5).
"""

from frappe import _lt

AUTHOR = ["Material Record Author"]
READER = ["Materials Reader"]
CURATOR = ["Material Catalog Curator"]
EVERYONE = AUTHOR + READER

COUNTS = "materials.screens.nav_counts"

SPACES = [{
	"id": "materials", "name": _lt("Materials"), "icon": "lucide-package", "order": 50,
	"pages": [
		{"id": "traceability", "name": _lt("Traceability"), "icon": "lucide-route", "order": 30,
		 "sections": [{"id": "lots", "name": _lt("The lots, and to which job")},
					  {"id": "checks", "name": _lt("The checks on the material")}]},
		{"id": "metal", "name": _lt("Metal traceability"), "icon": "lucide-flame", "order": 40,
		 "sections": [{"id": "heats", "name": _lt("Heats and their papers")},
					  {"id": "jobs", "name": _lt("What each job asks")}]},
		{"id": "setup", "name": _lt("Set-up"), "icon": "lucide-settings-2", "order": 70,
		 "sections": [{"id": "warehouse", "name": _lt("The warehouse")},
					  {"id": "catalog", "name": _lt("The grades and their standards")}]},
	],
}]


def _list(doctype):
	return {"name": "list", "params": {"doctype": doctype.lower().replace(" ", "-")}}


APPS = [
	# ── Traceability › the checks ─────────────────────────────────────────
	{"id": "ma.pmi", "holds": ["PMI Check"], "code": "MA-07", "title": _lt("PMI"),
	 "task": _lt("Confirm the alloy with the analyser, element by element"), "use_case": "UC-MA-07",
	 "kind": "worklist", "place": "materials.traceability.checks", "order": 20, "catalogs": EVERYONE,
	 "opens": {"doctype": "PMI Check"}, "devices": ["desktop", "phone"], "route": {"name": "materials-pmi"},
	 "icon": "lucide-scan-search", "line": _lt("the reading against the grade's limits"), "also": ["materials-pmi-check"]},
	# ── Metal traceability ───────────────────────────────────────────────
	{"id": "ma.heats", "holds": ["Material Heat"], "code": "MA-15", "title": _lt("Heats"),
	 "task": _lt("Know where a heat is: on the shelf, in a part, in a weld"), "use_case": "UC-MA-15",
	 "kind": "register", "place": "materials.metal.heats", "order": 10, "catalogs": EVERYONE,
	 "opens": {"doctype": "Material Heat"}, "devices": ["desktop"], "route": {"name": "materials-heats"},
	 "icon": "lucide-flame", "line": _lt("held, recalled, without a certificate"), "count": f"{COUNTS}:heats",
	 "count_label": _lt("held on the shelf"), "also": ["materials-heat"]},
	{"id": "ma.certificates", "holds": ["Material Certificate"], "code": "MA-03", "title": _lt("Certificates"),
	 "task": _lt("Read a mill certificate against its standard and the order"), "use_case": "UC-MA-03",
	 "kind": "register", "place": "materials.metal.heats", "order": 20, "catalogs": EVERYONE,
	 "opens": {"doctype": "Material Certificate"}, "devices": ["desktop"], "route": {"name": "materials-certificates"},
	 "icon": "lucide-file-badge", "line": _lt("to verify, to tie to their lots"), "count": f"{COUNTS}:certificates",
	 "count_label": _lt("to verify"), "also": ["materials-certificate"]},
	{"id": "ma.recalls", "holds": ["Material Recall"], "code": "MA-06", "title": _lt("Recalls"),
	 "task": _lt("Follow a recalled heat to the last piece, and close it"), "use_case": "UC-MA-06",
	 "kind": "worklist", "place": "materials.metal.heats", "order": 30, "catalogs": EVERYONE,
	 "opens": {"doctype": "Material Recall"}, "devices": ["desktop"], "route": {"name": "materials-recalls"},
	 "icon": "lucide-siren", "line": _lt("shelf, parts, welds, delivered, who to tell"), "count": f"{COUNTS}:recalls",
	 "count_label": _lt("open"), "also": ["materials-recall"]},
	{"id": "ma.requirements", "holds": ["Job Material Requirement"], "code": "MA-17",
	 "title": _lt("Material requirements of the jobs"),
	 "task": _lt("Say what each job asks of its material, so orders and issues follow it"), "use_case": "UC-MA-17",
	 "kind": "register", "place": "materials.metal.jobs", "order": 10, "catalogs": EVERYONE,
	 "opens": {"doctype": "Job Material Requirement"}, "devices": ["desktop"], "route": _list("Job Material Requirement"),
	 "icon": "lucide-list-checks", "line": _lt("grade, document, impact, carbon equivalent, PMI")},
	# ── Set-up › the grades and their standards ─────────────────────────────
	{"id": "ma.grades", "holds": ["Material Grade"], "code": "MA-S5", "title": _lt("Grades"),
	 "task": _lt("Keep the grades and the standards that define them"), "use_case": "UC-MA-S5",
	 "kind": "admin", "place": "materials.setup.catalog", "order": 10, "catalogs": CURATOR,
	 "opens": {"doctype": "Material Grade"}, "devices": ["desktop"], "route": _list("Material Grade"),
	 "icon": "lucide-layers", "line": _lt("reference data")},
	{"id": "ma.specifications", "holds": ["Material Specification"], "code": "MA-S6", "title": _lt("Material specifications"),
	 "task": _lt("Keep the product standards grades belong to"), "use_case": "UC-MA-S6",
	 "kind": "admin", "place": "materials.setup.catalog", "order": 20, "catalogs": CURATOR,
	 "opens": {"doctype": "Material Specification"}, "devices": ["desktop"], "route": _list("Material Specification"),
	 "icon": "lucide-book-marked", "line": _lt("reference data")},
]

# ── the supplier's own space (guide 33 P1, D-9; level-up pass, phase 5) ────────────
# What /supplier-certificates did, in their space; the order stays closed to them at the API.
APPS += [
	{"id": "mat.out.orders", "code": "MA-X1", "title": _lt("Our orders"),
	 "task": _lt("Send the certificates our orders ask, before you ship"), "use_case": "UC-MA-X1",
	 "kind": "queue", "place": "supplier.orders.orders", "order": 10, "catalogs": ["OS Supplier Portal"],
	 "opens": {"outside": "supplier"}, "holds": ["Material Purchase Order"], "devices": ["desktop", "phone"],
	 "route": {"name": "outside-list", "params": {"app": "mat.out.orders"}}, "icon": "lucide-package",
	 "line": _lt("each line, the certificate it asks, how it was judged"), "rows": "materials.ui.outside.orders",
	 "today": "materials.ui.outside.today", "empty": _lt("No order of ours is open with you.")},
]
