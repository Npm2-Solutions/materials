# Materials fixture importers

Scripts that build/refresh material-domain fixtures from authoritative
source documents. Mirror of the welding-side
`apps/weldcore/weldcore/fixtures/_importers/`.

## Scripts

| Script | Source | Fixture(s) |
|---|---|---|
| `import_makeitfrom.py` | MakeItFrom.com (CC-BY-SA 4.0) web pages | `material_grade.json` |
| `_build_makeitfrom_fixtures.py` | reads `/tmp/makeitfrom_raw.json` | merges into `material_grade.json` |

## Run pipeline

```bash
# 1. Scrape (polite — 1.5s between requests; caches HTML locally; resumable)
python3 apps/materials/materials/fixtures/_importers/import_makeitfrom.py \
    --group "Iron Alloy,Aluminum Alloy,Nickel Alloy,Titanium Alloy,Copper Alloy,Cobalt Alloy,Magnesium Alloy,Zinc Alloy,Other Metal Alloy" \
    --max-pages 1000 \
    --delay 1.5
# NOTE: MakeItFrom groups by alloy base, not product form — "Iron Alloy" covers
# carbon / stainless / low-alloy steel + cast iron. Using "Carbon Steel" etc.
# matches no GROUP_INDEX_URLS key and silently scrapes nothing.

# 2. Review /tmp/makeitfrom_unmatched.json — these are MakeItFrom materials
#    whose designation didn't map to any existing Material Specification slug.
#    For each that's important, add the missing Material Specification row first.

# 3. Merge matched rows into the fixture
python3 apps/materials/materials/fixtures/_importers/_build_makeitfrom_fixtures.py

# 4. Smoke test on demo site
bench --site demo.localhost clear-cache
bench --site demo.localhost execute "frappe.utils.fixtures.sync_fixtures" --kwargs "{\"app\": \"materials\"}"
```

## Cache + storage

- HTML pages cached at `apps/materials/source/cache/makeitfrom/<slug>.html`
- `apps/materials/source/` and `apps/materials/source/cache/` are gitignored
  (copyright + cache files shouldn't enter the repo).
- Re-running the scraper skips already-cached URLs unless `--force` is set.

## Provenance

Every row emitted by this pipeline carries
`notes = "[MakeItFrom.com] <full URL of source page>"`. CC-BY-SA 4.0
requires attribution; this satisfies attribution at row level. If
fixture data is republished in any UI/PDF, the page footer should also
credit makeitfrom.com.

## Rate limiting

- Default delay: 1.5s between requests + jitter (random 0-0.5s) → ~3000
  pages/hour worst case. Adjust with `--delay`.
- Respects HTTP 429 with `Retry-After` header.
- Exponential backoff on 5xx errors.
- Identifies as `OptiSuites-fixtures-bot/1.0 (research; contact: <email>)`
  per RFC 9309 polite-bot conventions.

## Known limitations

- Designation matching is regex-heuristic. The output is split into
  `/tmp/makeitfrom_raw.json` (matched → ready to merge) and
  `/tmp/makeitfrom_unmatched.json` (review + create spec rows for
  important ones, then re-run merge).
- Chemistry + mechanical properties are extracted but NOT yet emitted
  into the Material Grade fixture rows (the current `Material Grade`
  DocType doesn't have fields for them). The eventual home for measured
  mechanicals is the certificate's `Certificate Mechanical Result` child
  on `Material Certificate`, not the grade reference data. Stored in the
  raw JSON for future use.
- Some MakeItFrom pages cover multi-grade specs (e.g., "ASTM A516 Grade
  55, 60, 65, 70"). The current parser only extracts the first grade
  found in the name. Consider adding a multi-grade splitter as a
  follow-up.
- One-page scrape ≈ 1.5s × pages. Full ~10K-page scrape would take ~4
  hours.
