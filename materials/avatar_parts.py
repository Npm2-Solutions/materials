"""The avatar part this app contributes.

Collected by worgify through the ``avatar_parts`` hook: install this app and the
piece appears in everyone's avatar builder; uninstall it and the piece quietly
stops being offered. Nothing here is imported by worgify directly — see
`worgify/utils/avatar/contrib.py` for the contract.

Drawn on the 32x32 authoring grid, low and to one side so it does not cover the
face, and inside the circle the Desk crops avatars to.
"""

COPPER = (0xC8, 0x7B, 0x3A)
STEEL_D = (0x6B, 0x74, 0x7E)


def get_parts():
	"""a coupon cut from the heat"""
	return [
		{
			"slug": "billet",
			"label": "Material sample",
			"slot": "gear",
			"sprite": {
				"y": 23,
				"rows": [
					"...AAAAAAAAAA...................",
					"...AACCCACCCA...................",
					"...AACCCACCCA...................",
					"...AACCCACCCA...................",
					"...AAAAAAAAAA...................",
				],
				"palette": {"A": STEEL_D, "C": COPPER},
			},
		}
	]
