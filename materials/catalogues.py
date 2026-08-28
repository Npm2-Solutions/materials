# Copyright (c) 2026, NPM2 Solutions and contributors
# For license information, please see license.txt
"""The catalogues materials ships, and therefore keeps in step with their documents.

The RULE is `worgify.utils.catalogues` — platform-wide, guide 22 §6. What lives
here is the ROSTER.

These two are the largest transcription on the bench: 4,203 grades and 560
specifications, copied out of ASME BPVC Section II Parts A and B and table
QW/QB-422. `SA-516 Gr.70` is P-No 1 because that table says so, and a customer
who edits it has made an error against a printed page — which the next migrate
would revert anyway, silently, since a fixture import rewrites every row it
matches.

Adding is untouched, and on this catalogue it is the half that matters most: a
proprietary steel, a client's own designation, a grade from a classification
society ISO does not carry. Those carry `is_standard = 0`, sit in no fixture, and
survive every migrate.
"""

#: Transcribed from ASME BPVC II-A/II-B and QW/QB-422.
SHIPPED = (
	"Material Grade",
	"Material Specification",
)

from worgify.utils.catalogues import (  # noqa: E402,F401
	WRITABLE_ON_SHIPPED,
	refuse_deleting_shipped_rows,
	refuse_edits_to_shipped_rows,
)
