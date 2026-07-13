app_name = "materials"
app_title = "Materials"
app_publisher = "NPM2 Solutions Srl"
app_description = "Universal materials library — material grades, specifications, MTRs, testing labs. Tier-1 knowledge library consumed by weldcore, stock, ndtnext, inspecta."
app_email = "info@npm2solutions.it"
app_license = "mit"

# Was "Pattern B: invisible library — no workspace". Reversed 2026-06: the
# regulated grade/spec/MTR data needs a curation surface for the WC Material
# Specialist / STK roles, so materials now ships a "Materials" workspace
# (material_classifications/workspace/materials). Consumers still Link to
# materials' DocTypes directly. See audit-2026-06 (entry-point gaps).
required_apps = ["frappe", "optisuites"]

# Ring 3 (guide 33 CS12): Global Search Settings rebuilds its allowlist from THIS
# hook — without it, in_global_search fields index but the search bar returns
# NOTHING for these doctypes (global_search.py:496 gates results by allowlist).
global_search_doctypes = {
	"Default": [
		{"doctype": "Material Certificate"},
		{"doctype": "Material Grade"},
		{"doctype": "Material Heat"},
		{"doctype": "Material Specification"},
	],
}


# Domain-neutral reference catalog. Each DocType is seeded by the consuming
# project's demo/init; materials itself only ships schema + display_name
# controllers. Fixtures keep the seed data exportable for diff-based audits.
fixtures = [
	# Standard first — Material Specification.standard links to these. materials
	# owns the material-domain editions (API 5xx, EN 100xx/102xx, ASTM Axx, …) so
	# it is self-sufficient without depending on weldcore (L2).
	# The domain filter is load-bearing: unfiltered, an export pulls every app's
	# editions (welding, NDT, structural) into this fixture. That is how 157
	# material specs once ended up inside weldcore/fixtures/standard.json.
	{"dt": "Standard", "filters": [["domain", "=", "Mechanical"]]},
	"Material Specification",
	"Material Grade",
]

# Demo Data — context-based setup (see optisuites/setup/DEMO_DATA_GUIDE.md).
# Seeds Material Heats + EN 10204 3.1 certificates for the pressure-vessel BOM,
# referencing the SA-516 Gr.70 fixture grade and adding demo consumable grades.
# NB: only runs end-to-end if `materials` is in optisuites APP_INSTALL_ORDER.
demo_setup = "materials.setup.demo.setup"
demo_cleanup = "materials.setup.demo.cleanup"

# RecordBook (MRB) contributor — materials supplies the dossier's material
# evidence: the heat-traceability matrix and the full EN 10204 certificates.
# Pull-based projection (guide 09 Pattern 6): builders READ ONLY, never import
# recordbook at module scope, and degrade silently when recordbook is absent.
record_book_contributors = {
	"materials": {
		"label": "Materials",
		"icon": "package",
		"app_version_contract": "1.0",
		"sections": {
			"heat_traceability": {
				"title": "Material & Heat Traceability",
				"description": "Matrix of every heat used in scope mapped to its mill certificate(s); flags missing/recalled heats.",
				"builder": "materials.book.heat_traceability.build",
				"supported_scopes": ["Project", "Assembly", "JointList", "Organization"],
				"render_orientation": "Landscape",
				"pf_context_keys": ["doc", "scope", "knobs"],
			},
			"certificates": {
				"title": "Material Certificates (3.1)",
				"description": "Full EN 10204 material certificates with chemical + mechanical results for all heats in scope.",
				"builder": "materials.book.certificates.build",
				"supported_scopes": ["Project", "Assembly", "JointList", "Document", "Organization"],
				"render_orientation": "Portrait",
				"pf_context_keys": ["doc", "scope"],
			},
		},
	},
}

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "materials",
# 		"logo": "/assets/materials/logo.png",
# 		"title": "Materials",
# 		"route": "/materials",
# 		"has_permission": "materials.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/materials/css/materials.css"
# app_include_js = "/assets/materials/js/materials.js"

# include js, css files in header of web template
# web_include_css = "/assets/materials/css/materials.css"
# web_include_js = "/assets/materials/js/materials.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "materials/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "materials/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "materials.utils.jinja_methods",
# 	"filters": "materials.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "materials.install.before_install"
after_install = "materials.setup.install.after_install"
after_migrate = "materials.setup.install.after_migrate"

# Uninstallation
# ------------

before_uninstall = "materials.setup.install.before_uninstall"
# after_uninstall = "materials.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "materials.utils.before_app_install"
# after_app_install = "materials.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "materials.utils.before_app_uninstall"
# after_app_uninstall = "materials.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "materials.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"materials.tasks.all"
# 	],
# 	"daily": [
# 		"materials.tasks.daily"
# 	],
# 	"hourly": [
# 		"materials.tasks.hourly"
# 	],
# 	"weekly": [
# 		"materials.tasks.weekly"
# 	],
# 	"monthly": [
# 		"materials.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "materials.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "materials.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "materials.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "materials.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["materials.utils.before_request"]
# after_request = ["materials.utils.after_request"]

# Job Events
# ----------
# before_job = ["materials.utils.before_job"]
# after_job = ["materials.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"materials.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

