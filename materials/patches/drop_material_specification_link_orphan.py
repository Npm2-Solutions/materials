"""Drop orphan `Material Specification Link` child DocType.

The only parent that used it was Material Specification.equivalent_specifications
which was dropped in commit materials@523144c. Now truly orphan.
"""
import frappe


def execute():
    name = "Material Specification Link"
    site_db = frappe.conf.db_name

    frappe.db.sql("DELETE FROM `tabDocField` WHERE parent = %s", (name,))
    frappe.db.sql("DELETE FROM `tabDocPerm` WHERE parent = %s", (name,))
    frappe.db.sql("DELETE FROM `tabDocType Link` WHERE parent = %s", (name,))
    frappe.db.sql("DELETE FROM `tabDocType Action` WHERE parent = %s", (name,))
    frappe.db.sql("DELETE FROM `tabDocType State` WHERE parent = %s", (name,))
    frappe.db.sql("DELETE FROM `tabDocType` WHERE name = %s", (name,))
    frappe.db.commit()

    exists = frappe.db.sql(
        """SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
           WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s""",
        (site_db, f"tab{name}"),
    )
    if exists:
        frappe.db.sql(f"DROP TABLE `tab{name}`")
        frappe.db.commit()
    print(f"  dropped DocType + table for: {name}")
