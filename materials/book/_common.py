"""
Shared helpers for materials RecordBook (MRB) contributor builders.

HTML produced here uses the class names from recordbook.composition.style
(.print-heading, .badge, .badge-success, .mrb-tight, …) so the dossier's
visual style stays consistent across every contributor's section.

materials imports nothing from recordbook at module scope — the knob /
print-format accessors guard the import so the app stays installable and
testable without recordbook present.
"""

from __future__ import annotations

import frappe


def esc(value) -> str:
	return frappe.utils.escape_html("" if value is None else str(value))


def section_title(title: str, subtitle: str = "") -> str:
	sub = f'<small class="sub-heading">{esc(subtitle)}</small>' if subtitle else ""
	return f'<div class="print-heading"><h2><div>{esc(title)}</div>{sub}</h2></div>'


def badge(label: str, severity: str = "muted") -> str:
	cls = {
		"success": "badge-success",
		"danger": "badge-danger",
		"warning": "badge-warning",
		"info": "badge-info",
		"muted": "badge-muted",
	}.get(severity, "badge-muted")
	return f'<span class="badge {cls}">{esc(label)}</span>'


def fmtdate(value) -> str:
	return frappe.utils.formatdate(value) if value else ""


def empty_section(message: str = "No data in scope.") -> dict:
	return {
		"metadata": {
			"empty": True,
			"warnings": [{"severity": "info", "code": "empty", "message": message}],
		}
	}


def get_knob(section_row, key: str, default=None):
	"""Read a per-section knob if recordbook is installed, else the default."""
	try:
		from recordbook.composition.knobs import get_knob as _real
	except ImportError:
		return default
	return _real(section_row, key, default=default)


def get_print_format(section_row, key: str, fallback: str | None = None):
	"""Read a per-section sub-renderer Print Format pick if recordbook present."""
	try:
		from recordbook.composition.subrenderers import get_print_format as _real
	except ImportError:
		return fallback
	return _real(section_row, key, fallback=fallback)
