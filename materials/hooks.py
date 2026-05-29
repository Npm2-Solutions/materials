app_name = "materials"
app_title = "Materials"
app_publisher = "NPM2 Solutions Srl"
app_description = "Universal materials library — material grades, specifications, MTRs, testing labs. Tier-1 knowledge library consumed by weldcore, stock, ndtnext, inspecta."
app_email = "info@npm2solutions.it"
app_license = "mit"

# Pattern B: invisible library — no apps-screen entry, no workspace. Consumers
# (weldcore, stock, ndtnext, inspecta) Link to materials' DocTypes directly.
required_apps = ["frappe", "optisuites"]

# Domain-neutral reference catalog. Each DocType is seeded by the consuming
# project's demo/init; materials itself only ships schema + display_name
# controllers. Fixtures keep the seed data exportable for diff-based audits.
fixtures = [
	"Material Specification",
	"Material Grade",
	"Material Form",
]

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
# after_install = "materials.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "materials.uninstall.before_uninstall"
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

