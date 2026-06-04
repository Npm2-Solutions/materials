"""Drop the deprecated 'Testing Laboratory' DocType (Design 05 Phase 5).

External bodies are consolidated into the optisuites Third Party Body registry.
All Link consumers were repointed; 'Testing Laboratory' is now orphaned. Remove the DocType
+ its table. Idempotent.
"""

import frappe


def execute():
	if frappe.db.exists("DocType", "Testing Laboratory"):
		frappe.delete_doc("DocType", "Testing Laboratory", force=True, ignore_permissions=True)
	frappe.db.sql_ddl("DROP TABLE IF EXISTS `tabTesting Laboratory`")
	frappe.db.commit()
	print("dropped deprecated DocType Testing Laboratory")
