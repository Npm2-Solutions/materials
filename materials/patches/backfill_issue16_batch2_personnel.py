"""Issue 16 Batch 2 (CODE-DEPENDENT auto-stamp) — repoint person-actor fields from User to Personnel.

These fields were auto-stamped with the current login (``frappe.session.user``
or a ``__user`` default); the controllers now stamp ``get_personnel_for_user()``
and the ``__user`` defaults were dropped, and the Links are retyped
User -> Personnel. This patch remaps existing rows. Unmatched values become NULL
per the Issue 16 convention.
"""
import frappe
from optisuites.personnel.api import find_personnel

TARGETS = [
    ("Material Certificate", "verified_by"),
]


def execute():
    for dt, field in TARGETS:
        if not frappe.db.table_exists(dt):
            continue
        if field not in frappe.db.get_table_columns(dt):
            continue
        for r in frappe.db.sql(
            f"SELECT name, `{field}` AS val FROM `tab{dt}` WHERE `{field}` IS NOT NULL AND `{field}` != ''",
            as_dict=True,
        ):
            if frappe.db.exists("Personnel", r.val):
                continue
            frappe.db.set_value(
                dt, r.name, field, find_personnel(user=r.val, email=r.val), update_modified=False
            )
    frappe.db.commit()
