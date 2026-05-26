"""Rename child DocType `Material Form` → `Material Grade Form`.

The original name suggested a standalone catalog of product forms (plate,
pipe, bar, etc.) but it's actually a child of Material Grade.product_forms
that holds per-grade availability info. The new name makes that clear.
"""
import frappe


def execute():
    old_name = "Material Form"
    new_name = "Material Grade Form"

    old_exists = frappe.db.exists("DocType", old_name)
    new_exists = frappe.db.exists("DocType", new_name)
    site_db = frappe.conf.db_name

    if not old_exists:
        if new_exists:
            print(f"  Rename {old_name} → {new_name}: already applied")
        return

    if old_exists and new_exists:
        if frappe.db.sql(
            """SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s""",
            (site_db, f"tab{old_name}"),
        ):
            try:
                frappe.db.sql(
                    f"INSERT IGNORE INTO `tab{new_name}` "
                    f"SELECT * FROM `tab{old_name}`"
                )
            except Exception as e:
                print(f"  data move skipped: {e}")
            frappe.db.commit()
            frappe.db.sql(f"DROP TABLE `tab{old_name}`")
            frappe.db.commit()

        frappe.db.sql("DELETE FROM `tabDocField` WHERE parent = %s", (old_name,))
        frappe.db.sql("DELETE FROM `tabDocPerm` WHERE parent = %s", (old_name,))
        frappe.db.sql("DELETE FROM `tabDocType` WHERE name = %s", (old_name,))
        frappe.db.commit()
        print(f"  Dropped orphan old DocType + table: {old_name}")
        return

    frappe.rename_doc("DocType", old_name, new_name, force=True, merge=False)
    if frappe.db.sql(
        """SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
           WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s""",
        (site_db, f"tab{old_name}"),
    ):
        frappe.db.sql(f"RENAME TABLE `tab{old_name}` TO `tab{new_name}`")
    for col_table in ("tabDocField", "tabCustom Field"):
        frappe.db.sql(
            f"UPDATE `{col_table}` SET options = %s WHERE options = %s",
            (new_name, old_name),
        )
    frappe.db.sql(
        f"UPDATE `tab{new_name}` SET parenttype = %s WHERE parenttype = %s",
        (new_name, old_name),
    )
    frappe.db.commit()
    print(f"  Renamed: {old_name} → {new_name}")
