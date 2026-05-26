"""Drop 12 dead fields from materials DocTypes (Material Grade, Material Specification).

Empty-everywhere fields confirmed via fixture-population audit + no code reads them.
"""

import frappe

DROPS = [
    # Material Grade — 11
    ("tabMaterial Grade", "carbon_equivalent_formula"),
    ("tabMaterial Grade", "carbon_equivalent_max"),
    ("tabMaterial Grade", "density_kg_m3"),
    ("tabMaterial Grade", "thermal_conductivity_w_mk"),
    ("tabMaterial Grade", "coefficient_thermal_expansion_um_mk"),
    ("tabMaterial Grade", "sour_service_compatible"),
    ("tabMaterial Grade", "cryogenic_compatible"),
    ("tabMaterial Grade", "min_service_temp_c"),
    ("tabMaterial Grade", "max_service_temp_c"),
    # Material Specification — 0 column drops needed (the dropped field is a
    # Table MultiSelect; child table rows handled by JSON sync).
]


def execute():
    site_db = frappe.conf.db_name
    for table, column in DROPS:
        existing = frappe.db.sql(
            """SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
               WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s""",
            (site_db, table, column),
        )
        if not existing:
            continue
        frappe.db.commit()
        frappe.db.sql(f"ALTER TABLE `{table}` DROP COLUMN `{column}`")
        frappe.db.commit()
        print(f"  dropped {table}.{column}")
