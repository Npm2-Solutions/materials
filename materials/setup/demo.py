# Copyright (c) 2026, NPM2 Solutions Srl
# Demo data for the Materials app (L1.5 — invisible materials library).
#
# Story (see optisuites/setup/DEMO_DATA_GUIDE.md): Petrolia Energy's pressure
# vessel is fabricated from SA-516 Gr.70 plate, welded with ER70S-6 wire and
# E7018 electrodes. This module seeds the *as-received material evidence* for
# that bill of materials:
#
#   Material Specification → Material Grade → Material Heat → Material Certificate
#
# It deliberately does NOT recreate the SA-516 Gr.70 grade: that record is
# shipped as a materials FIXTURE (`asme_sa_516__70`, is_standard=1) and is
# referenced here. Only the welding-consumable grades — which have no fixture —
# are created as demo-owned rows (is_standard=0) so cleanup can remove them.
#
# Cross-app coherence: the heat numbers / lot references / quantities mirror
# stock's demo batches (H-2026-0142, LOT-ER70S-001, LOT-E7018-001; 2000/100 Kg),
# so the heat-bridge in material_certificate.py (Batch.heat_number ↔
# Material Heat ↔ Material Certificate.heats_covered) tells one continuous story.
#
# NOTE — wiring: this app's `demo_setup`/`demo_cleanup` hooks only run if
# `materials` is present in optisuites.setup.demo.APP_INSTALL_ORDER. As of this
# writing materials is not yet listed there; add it (after `training`) for the
# end-to-end build to include this data. This file owns no cross-app edits.

import frappe
from frappe.utils import today, add_days

from optisuites.setup import persona  # shared multi-persona demo driver


# SA-516 Gr.70 plate grade — shipped as a materials fixture. Referenced, not created.
PLATE_GRADE_FIXTURE = "asme_sa_516__70"

# Demo-owned reference rows for welding consumables (no fixture exists for these).
# is_standard stays 0 (the default) so cleanup is allowed to delete them.
# Keyed by designation → spec metadata; standard link left NULL on purpose
# (accepted pattern — links are 100% NULL in demo and not yet reqd-enforced).
DEMO_SPECS = [
    {
        "designation": "A5.18",
        "title": "AWS A5.18 — Carbon Steel Solid Wire (GMAW/GTAW)",
        "material_category": "Carbon Steel",
        "description": "Filler-metal specification for ER70S-x carbon-steel solid wires.",
    },
    {
        "designation": "A5.1",
        "title": "AWS A5.1 — Carbon Steel Covered Electrodes (SMAW)",
        "material_category": "Carbon Steel",
        "description": "Filler-metal specification for E70xx carbon-steel covered electrodes.",
    },
]

# Grade → its parent spec designation. grade strings drive cleanup filters.
DEMO_GRADES = [
    {"designation": "A5.18", "grade": "ER70S-6", "uns_number": "",
     "notes": "Copper-coated solid wire, Mn-Si deoxidised, for GMAW/GTAW of carbon steel."},
    {"designation": "A5.1", "grade": "E7018", "uns_number": "",
     "notes": "Low-hydrogen iron-powder covered electrode for SMAW of carbon steel."},
]

# Material Heats (mill pours / casts). heat_number IS the record name.
#   grade_ref:  "fixture" → resolved to PLATE_GRADE_FIXTURE; otherwise a demo grade designation
DEMO_HEATS = [
    {"heat_number": "H-2026-0142", "grade_ref": "fixture", "cast_number": "C-0142/3",
     "mill_is_supplier": False, "lot_ref": "H-2026-0142",
     "notes": "SA-516 Gr.70 20mm plate heat — stock batch H-2026-0142 (2000 kg received)."},
    {"heat_number": "ER-2026-1187", "grade": "ER70S-6", "cast_number": "LOT-ER70S-001",
     "mill_is_supplier": True, "lot_ref": "LOT-ER70S-001",
     "notes": "ER70S-6 1.2mm wire cast — stock batch LOT-ER70S-001 (100 kg received)."},
    {"heat_number": "EB-2026-0453", "grade": "E7018", "cast_number": "LOT-E7018-001",
     "mill_is_supplier": True, "lot_ref": "LOT-E7018-001",
     "notes": "E7018 3.2mm electrode batch — stock batch LOT-E7018-001."},
]

# Material Certificates (EN 10204 3.1 Mill Test Reports). Sequential autoname
# (MCERT-YYYY-#####) → not name-idempotent, so setup guards on certificate_number.
DEMO_CERTS = [
    {
        "certificate_number": "MTR-MARC-2026-0142",
        "certificate_type": "EN 10204 3.1",
        "issuing_body": "Marcegaglia Plates S.p.A.",
        "supplier_from_context": False,
        "heat": "H-2026-0142",
        "qty_covered": 2000.0,
        "qty_unit": "Kg",
        "chemical": [
            # element, value%, spec_min, spec_max   (spec_max 0 = no upper limit)
            ("C", 0.18, 0.0, 0.28),
            ("Mn", 1.08, 0.85, 1.20),
            ("Si", 0.24, 0.15, 0.40),
            ("P", 0.011, 0.0, 0.025),
            ("S", 0.006, 0.0, 0.025),
        ],
        "mechanical": [
            # test_type, value, unit, spec_min, spec_max, temperature
            ("Tensile Strength", 535.0, "MPa", 485.0, 620.0, ""),
            ("Yield Strength", 345.0, "MPa", 260.0, 0.0, ""),
            ("Elongation", 26.0, "%", 17.0, 0.0, ""),
            ("Impact (Charpy)", 110.0, "J", 27.0, 0.0, "-20 °C"),
        ],
    },
    {
        "certificate_number": "MTR-BW-2026-1187",
        "certificate_type": "EN 10204 3.1",
        "issuing_body": "Böhler Welding Group",
        "supplier_from_context": True,
        "heat": "ER-2026-1187",
        "qty_covered": 100.0,
        "qty_unit": "Kg",
        "chemical": [
            ("C", 0.08, 0.06, 0.15),
            ("Mn", 1.55, 1.40, 1.85),
            ("Si", 0.90, 0.80, 1.15),
            ("P", 0.012, 0.0, 0.025),
            ("S", 0.015, 0.0, 0.035),
        ],
        "mechanical": [
            ("Tensile Strength", 545.0, "MPa", 480.0, 0.0, ""),
            ("Yield Strength", 455.0, "MPa", 400.0, 0.0, ""),
            ("Elongation", 26.0, "%", 22.0, 0.0, ""),
        ],
    },
    {
        "certificate_number": "MTR-BW-2026-0453",
        "certificate_type": "EN 10204 3.1",
        "issuing_body": "Böhler Welding Group",
        "supplier_from_context": True,
        "heat": "EB-2026-0453",
        "qty_covered": 50.0,
        "qty_unit": "Kg",
        "chemical": [
            ("C", 0.06, 0.0, 0.15),
            ("Mn", 1.05, 0.0, 1.60),
            ("Si", 0.55, 0.0, 0.75),
        ],
        "mechanical": [
            ("Tensile Strength", 540.0, "MPa", 490.0, 660.0, ""),
            ("Yield Strength", 450.0, "MPa", 400.0, 0.0, ""),
            ("Elongation", 28.0, "%", 22.0, 0.0, ""),
            ("Impact (Charpy)", 130.0, "J", 27.0, 0.0, "-29 °C"),
        ],
    },
]


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def setup(context):
    """Seed materials demo data: consumable grades + heats + mill certificates.

    Idempotent: field-named DocTypes use insert(ignore_if_duplicate=True);
    sequentially-named Material Certificates are guarded on certificate_number.
    Adds material_specifications / material_grades / material_heats /
    material_certificates to context for any downstream consumer.
    """
    # Foundation must have run. company is always set by optisuites.
    if not context.get("company"):
        return

    start_date = context.get("start_date") or add_days(today(), -30)
    supplier = context.get("supplier")

    # --- Material Specifications + Grades (welding consumables only) ---------
    print("    Creating Material Specifications / Grades (welding consumables)...")
    spec_by_designation = {}
    for spec in DEMO_SPECS:
        doc = frappe.get_doc({
            "doctype": "Material Specification",
            "designation": spec["designation"],
            "title": spec["title"],
            "material_category": spec["material_category"],
            "description": spec["description"],
            # standard left NULL on purpose; is_standard stays 0 (demo-owned).
        })
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_if_duplicate=True)
        spec_by_designation[spec["designation"]] = doc.name
        context.setdefault("material_specifications", [])
        if doc.name not in context["material_specifications"]:
            context["material_specifications"].append(doc.name)

    grade_by_grade = {}
    for g in DEMO_GRADES:
        spec_name = spec_by_designation.get(g["designation"])
        if not spec_name:
            continue
        doc = frappe.get_doc({
            "doctype": "Material Grade",
            "specification": spec_name,
            "grade": g["grade"],
            "uns_number": g.get("uns_number") or "",
            "notes": g.get("notes") or "",
        })
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_if_duplicate=True)
        grade_by_grade[g["grade"]] = doc.name
        context.setdefault("material_grades", [])
        if doc.name not in context["material_grades"]:
            context["material_grades"].append(doc.name)

    # Reference (don't create) the SA-516 Gr.70 plate grade shipped as a fixture.
    plate_grade = PLATE_GRADE_FIXTURE if frappe.db.exists(
        "Material Grade", PLATE_GRADE_FIXTURE) else None
    if plate_grade:
        context.setdefault("material_grades", [])
        if plate_grade not in context["material_grades"]:
            context["material_grades"].append(plate_grade)
    else:
        print(f"      (skipping plate heat/cert — fixture grade "
              f"{PLATE_GRADE_FIXTURE} not found)")

    # --- Material Heats ------------------------------------------------------
    print("    Creating Material Heats...")
    heat_ok = set()
    for i, h in enumerate(DEMO_HEATS):
        if h.get("grade_ref") == "fixture":
            grade = plate_grade
        else:
            grade = grade_by_grade.get(h.get("grade"))
        if not grade:
            continue  # grade unavailable (e.g. fixture missing) → skip this heat
        doc = frappe.get_doc({
            "doctype": "Material Heat",
            "heat_number": h["heat_number"],
            "cast_number": h.get("cast_number") or "",
            "grade": grade,
            "mill": supplier if h.get("mill_is_supplier") else None,
            "production_date": add_days(start_date, -18 + i * 3),
            "status": "Released",
            "notes": h.get("notes") or "",
        })
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_if_duplicate=True)
        heat_ok.add(h["heat_number"])
        context.setdefault("material_heats", [])
        if doc.name not in context["material_heats"]:
            context["material_heats"].append(doc.name)

    # --- Material Certificates (EN 10204 3.1 MTRs) --------------------------
    print("    Creating Material Certificates (Mill Test Reports)...")
    ledger = persona.Ledger("Materials")
    personas = persona.ensure({"inspector": ("material_inspector", "STK Material Inspector")}, ledger)
    for c in DEMO_CERTS:
        if c["heat"] not in heat_ok:
            continue  # the heat this MTR documents wasn't created → skip
        # Guard idempotency: sequential autoname never collides, so check number.
        existing = frappe.db.get_value(
            "Material Certificate", {"certificate_number": c["certificate_number"]})
        if existing:
            context.setdefault("material_certificates", [])
            if existing not in context["material_certificates"]:
                context["material_certificates"].append(existing)
            continue

        def _issue_cert(cc=c, respect_perms=True):
            doc = frappe.get_doc({
                "doctype": "Material Certificate",
                "certificate_number": cc["certificate_number"],
                "certificate_type": cc["certificate_type"],
                "certificate_date": add_days(start_date, -10),
                "supplier": supplier if cc.get("supplier_from_context") else None,
                "issuing_body": cc.get("issuing_body") or "",
                "heats_covered": [
                    {"heat": cc["heat"], "qty_covered": cc["qty_covered"], "qty_unit": cc["qty_unit"]},
                ],
                "chemical_results": [
                    {"element": el, "value_percent": val, "spec_min": smin, "spec_max": smax}
                    for (el, val, smin, smax) in cc["chemical"]
                ],
                "mechanical_results": [
                    {"test_type": tt, "value": val, "unit": unit,
                     "spec_min": smin, "spec_max": smax, "temperature": temp}
                    for (tt, val, unit, smin, smax, temp) in cc["mechanical"]
                ],
            })
            doc.flags.ignore_permissions = not respect_perms
            doc.flags.ignore_mandatory = True
            doc.insert(ignore_if_duplicate=True)
            return doc.name
        name = persona.run_as(personas["inspector"], "Material Inspector",
                              f"issue MTR {c['certificate_number']}", _issue_cert, ledger,
                              fallback=lambda cc=c: _issue_cert(cc, respect_perms=False))
        if name:
            context.setdefault("material_certificates", [])
            context["material_certificates"].append(name)

    persona.print_ledger(ledger, len(context.get("material_certificates", [])))
    frappe.db.commit()
    print(f"      materials demo: "
          f"{len(context.get('material_grades', []))} grades, "
          f"{len(context.get('material_heats', []))} heats, "
          f"{len(context.get('material_certificates', []))} certificates")


# ---------------------------------------------------------------------------
# Cleanup — reverse dependency order: certificates → heats → grades → specs.
# ---------------------------------------------------------------------------

def cleanup():
    """Remove materials demo data. Never touches fixture (is_standard=1) records."""
    cert_numbers = [c["certificate_number"] for c in DEMO_CERTS]
    heat_numbers = [h["heat_number"] for h in DEMO_HEATS]
    grade_names = [g["grade"] for g in DEMO_GRADES]
    spec_designations = [s["designation"] for s in DEMO_SPECS]

    # Certificates first — their child rows hold the only links to the heats.
    for name in frappe.get_all(
        "Material Certificate",
        filters={"certificate_number": ["in", cert_numbers]},
        pluck="name",
    ):
        try:
            doc = frappe.get_doc("Material Certificate", name)
            if doc.docstatus == 1:
                doc.cancel()
            doc.delete(force=True, ignore_permissions=True)
        except Exception:
            pass

    # Heats next (now unreferenced by our certificates).
    for name in frappe.get_all(
        "Material Heat",
        filters={"heat_number": ["in", heat_numbers]},
        pluck="name",
    ):
        try:
            frappe.delete_doc("Material Heat", name, force=True, ignore_permissions=True)
        except Exception:
            pass

    # Demo-owned grades (is_standard=0 only — protects the SA-516 fixture grade).
    for name in frappe.get_all(
        "Material Grade",
        filters={"grade": ["in", grade_names], "is_standard": 0},
        pluck="name",
    ):
        try:
            frappe.delete_doc("Material Grade", name, force=True, ignore_permissions=True)
        except Exception:
            pass

    # Demo-owned specs (is_standard=0 only).
    for name in frappe.get_all(
        "Material Specification",
        filters={"designation": ["in", spec_designations], "is_standard": 0},
        pluck="name",
    ):
        try:
            frappe.delete_doc("Material Specification", name, force=True, ignore_permissions=True)
        except Exception:
            pass

    frappe.db.commit()
