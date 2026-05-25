"""Issue 16 Class B — repoint person-actor fields from User to Personnel."""
import frappe
from optisuites.personnel.api import find_personnel

TARGETS = [
    ("Material Certificate", "pmi_operator"),
    ("PMI Test Point", "operator"),
]

def execute():
    for dt, field in TARGETS:
        if not frappe.db.table_exists(dt):
            continue
        if field not in frappe.db.get_table_columns(dt):
            continue
        for r in frappe.db.sql(f"SELECT name, `{field}` AS val FROM `tab{dt}` WHERE `{field}` IS NOT NULL AND `{field}` != ''", as_dict=True):
            if frappe.db.exists("Personnel", r.val):
                continue
            frappe.db.set_value(dt, r.name, field, find_personnel(user=r.val, email=r.val), update_modified=False)
    frappe.db.commit()
