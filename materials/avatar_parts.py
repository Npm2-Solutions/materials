"""The avatar part this app contributes.

Collected by worgify through the ``avatar_parts`` hook: install this app and the
piece appears in everyone's avatar builder; uninstall it and the piece quietly
stops being offered. Nothing here is imported by worgify directly — see
`worgify/utils/avatar/contrib.py` for the contract.

Drawn on the 32x32 fine grid — the body itself uses the coarse 16 grid, but a
tool is a small thing and needs the resolution to be recognisable. It sits in
the free corner beside the body, clear of the face and inside the circle the
Desk crops avatars to.
"""

STEEL = (0x9A, 0xA3, 0xAD)


def get_parts():
	"""a coupon cut from the heat, dog-bone and all"""
	return [
		{
			"slug": "billet",
			"label": "Material coupon",
			"slot": "gear",
			"sprite": {
				"y": 20,
				"rows": [
					"....AAA...AAA...................",
					"....AAAAAAAAA...................",
					".....AAAAAAA....................",
					"....AAAAAAAAA...................",
					"....AAA...AAA...................",
				],
				"palette": {"A": STEEL},
			},
		}
	]
