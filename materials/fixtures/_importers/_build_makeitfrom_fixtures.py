"""Merge step: take parsed MakeItFrom rows (/tmp/makeitfrom_raw.json) and
emit Material Grade fixture additions to
`materials/fixtures/material_grade.json`.

Each parsed row may map to multiple existing Material Specification rows
(e.g., a single MakeItFrom page covers ASTM A36 + EN S275 + JIS SS400 —
we'd emit 3 Material Grade rows pointing at 3 different spec parents).

Idempotent: same (specification, grade) pair only added once. Re-runs
with new MakeItFrom data augment the `notes` field with the source URL.
"""
import json
import os
import re

RAW = "/tmp/makeitfrom_raw.json"
GRADE_FIXTURE = "/workspace/frappe-bench/apps/materials/materials/fixtures/material_grade.json"
SOURCE_LABEL = "MakeItFrom.com"


def slugify(s):
    s = (s or "").lower()
    s = s.replace("/", "_").replace(" ", "_").replace("-", "_").replace(".", "_")
    s = re.sub(r"_+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s.strip("_")


def extract_grade_from_name(material_name: str, designation: str) -> str:
    """Best-effort grade extraction from material name.
    e.g. 'ASTM A516 Grade 70 K02700 Carbon Steel' → '70'
    e.g. 'ASTM A36 Structural Carbon Steel' → 'A36' (fallback)
    """
    # Look for "Grade X" / "Gr.X" / "Type X" patterns
    for pat in (
        r"Grade\s+([A-Z0-9][A-Za-z0-9\-/]*)",
        r"Gr\.?\s*([A-Z0-9][A-Za-z0-9\-/]*)",
        r"Type\s+([A-Z0-9][A-Za-z0-9\-/]*)",
        r"\b([A-Z]\d{2,3}[A-Z]*)\b",  # e.g., S275, P355
    ):
        m = re.search(pat, material_name)
        if m:
            return m.group(1)
    # Fallback — just use designation
    return designation


def build():
    if not os.path.exists(RAW):
        print(f"  No {RAW} — run import_makeitfrom.py first.")
        return

    with open(RAW) as f:
        parsed_rows = json.load(f)
    with open(GRADE_FIXTURE) as f:
        grades = json.load(f)

    # Index existing by (specification, grade) tuple
    existing_pairs = {(r.get("specification"), r.get("grade")): r for r in grades}

    added = 0
    augmented = 0
    for data in parsed_rows:
        url = data["url"]
        name = data["name"]
        uns = data.get("uns_number") or ""

        # One emission per matched specification
        for spec_slug in data.get("matched_specs", []):
            # Find the designation that matched this spec — useful for grade extraction
            matched_designation = ""
            for m in data.get("spec_matches", []):
                if m["matched_to"] == spec_slug:
                    matched_designation = m["designation"]
                    break

            grade = extract_grade_from_name(name, matched_designation or spec_slug)
            grade_slug = slugify(grade)
            row_name = f"{spec_slug}__{grade_slug}"
            key = (spec_slug, grade)

            prov_tag = f"[{SOURCE_LABEL}] {url}"

            if key in existing_pairs:
                existing = existing_pairs[key]
                notes = existing.get("notes") or ""
                if prov_tag not in notes:
                    existing["notes"] = (
                        (notes + "\n" if notes else "") + prov_tag
                    )[:1500]
                    augmented += 1
                continue

            grades.append({
                "doctype": "Material Grade",
                "name": row_name,
                "specification": spec_slug,
                "grade": grade,
                "uns_number": uns,
                "is_standard": 1,
                "enabled": 1,
                "docstatus": 0,
                "notes": prov_tag,
                "display_name": f"{name}",
                "group_assignments": [],
                "product_forms": [],
            })
            existing_pairs[key] = grades[-1]
            added += 1

    with open(GRADE_FIXTURE, "w") as f:
        json.dump(grades, f, indent=1)

    print(f"✓ Added {added} new Material Grade rows (now {len(grades)} total)")
    print(f"✓ Augmented {augmented} existing rows with MakeItFrom URL provenance")


if __name__ == "__main__":
    build()
