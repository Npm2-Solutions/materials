"""MakeItFrom.com material-grade scraper.

Public-facing material data on makeitfrom.com is licensed CC-BY-SA 4.0
(per the site footer — verify before each extraction run). This script
discovers material URLs from group index pages, fetches each material's
detail page, parses chemistry + mechanical properties + equivalent
designations, and writes a JSON file ready to merge into
`materials/fixtures/material_grade.json`.

USAGE
-----
1. Install deps (one-time):
     pip install requests beautifulsoup4

2. Run the discovery + scrape pipeline (group names must be GROUP_INDEX_URLS
   keys — alloy bases like "Iron Alloy"/"Aluminum Alloy", NOT product forms
   like "Carbon Steel" which match nothing and scrape nothing):
     python3 apps/materials/materials/fixtures/_importers/import_makeitfrom.py \
         --group "Iron Alloy,Aluminum Alloy,Nickel Alloy,Titanium Alloy" \
         --max-pages 500 \
         --delay 1.5

3. Output:
     apps/materials/source/cache/<slug>.html     ← raw HTML cache (gitignored)
     /tmp/makeitfrom_raw.json                    ← parsed structured rows
     /tmp/makeitfrom_unmatched.json              ← rows where the MakeItFrom
                                                   designation didn't match an
                                                   existing Material Specification
                                                   row (review + create spec rows
                                                   first, then re-merge).

4. Merge into fixtures (separate step — review unmatched first):
     python3 apps/materials/materials/fixtures/_importers/_build_makeitfrom_fixtures.py

DESIGN
------
- Polite scraping: 1.5s delay between requests; identifies as
  "Worgify-fixtures-bot/1.0 (research; contact: mm@mmwebagency.it)";
  respects HTTP 429 with exponential backoff.
- Resumable: HTML pages are cached on disk; re-runs skip already-cached
  URLs. To force a refresh, delete the cache file.
- Idempotent merge: matching is by (specification_slug, grade_slug); if a
  pair already exists in the fixture, augments the notes field with the
  MakeItFrom URL instead of duplicating.
- Provenance: every emitted row carries
  notes = "[MakeItFrom.com] <full URL of source page>"
  per the platform's reference-data provenance rule
  (worgify-platform-guides/01-ecosystem/11-reference-data-provenance.md).

PROVENANCE NOTE
---------------
MakeItFrom.com publishes its data under CC-BY-SA 4.0 (verify each run by
checking the page footer). The CC-BY-SA license REQUIRES attribution.
Each fixture row's `notes` field carries the source URL — that satisfies
attribution at the row level. If the data is republished in any UI or
PDF, the README or footer of the report should also credit makeitfrom.com.

EXIT CODES
----------
0 — success
1 — HTTP failure (429/5xx after retries)
2 — parser failure (HTML structure changed; update selectors)
3 — disk failure (no space, no write permission on cache dir)
"""
import argparse
import json
import logging
import os
import random
import re
import sys
import time
import urllib.parse
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from _paths import fixture, source, apps_path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://www.makeitfrom.com"
USER_AGENT = (
    "Worgify-fixtures-bot/1.0 "
    "(material-reference-data extraction; contact: mm@mmwebagency.it)"
)
CACHE_DIR = apps_path("materials/source/cache/makeitfrom")
OUT_RAW = "/tmp/makeitfrom_raw.json"
OUT_UNMATCHED = "/tmp/makeitfrom_unmatched.json"
SOURCE_LABEL = "MakeItFrom.com"

# Existing material specification fixture — used to match equivalent designations.
SPEC_FIXTURE = fixture("material_specification.json")

# Group index URLs — discovery starts here. Add more as needed; keys must
# match the canonical "Material Category" enum used on Material Specification.
GROUP_INDEX_URLS = {
    # MakeItFrom uses alloy-type grouping (not carbon/stainless split — those are
    # sub-categories within Iron-Alloy). Verified live 2026-05-26 from
    # https://www.makeitfrom.com/ navigation.
    "Iron Alloy": f"{BASE_URL}/material-group/Iron-Alloy",
    "Aluminum Alloy": f"{BASE_URL}/material-group/Aluminum-Alloy",
    "Cobalt Alloy": f"{BASE_URL}/material-group/Cobalt-Alloy",
    "Copper Alloy": f"{BASE_URL}/material-group/Copper-Alloy",
    "Magnesium Alloy": f"{BASE_URL}/material-group/Magnesium-Alloy",
    "Nickel Alloy": f"{BASE_URL}/material-group/Nickel-Alloy",
    "Titanium Alloy": f"{BASE_URL}/material-group/Titanium-Alloy",
    "Zinc Alloy": f"{BASE_URL}/material-group/Zinc-Alloy",
    "Other Metal Alloy": f"{BASE_URL}/material-group/Other-Metal-Alloy",
}

# Designation patterns we'll try to match against existing Material Specification slugs.
# Each tuple: (regex_to_extract_designation_from_page_title, spec_slug_template).
DESIGNATION_PATTERNS = [
    # ASTM A###
    (re.compile(r"\bASTM\s+(A\d+)"), "astm_{0}"),
    # ASTM B### (non-ferrous)
    (re.compile(r"\bASTM\s+(B\d+)"), "astm_{0}"),
    # ASME SA-###
    (re.compile(r"\bASME\s+SA[-\s]?(\d+)"), "asme_sa_{0}"),
    # EN 10025-X
    (re.compile(r"\bEN\s+(10025-?\d?)"), "en_{0}"),
    # EN 10028-X
    (re.compile(r"\bEN\s+(10028-?\d?)"), "en_{0}"),
    # EN 10216-X
    (re.compile(r"\bEN\s+(10216-?\d?)"), "en_{0}"),
    # EN 10217-X
    (re.compile(r"\bEN\s+(10217-?\d?)"), "en_{0}"),
    # JIS G ####
    (re.compile(r"\bJIS\s+G\s*(\d{4})"), "jis_g_{0}"),
    # API 5L / 5CT
    (re.compile(r"\bAPI\s+(5L|5CT|6A)"), "api_{0}"),
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("makeitfrom")


# ---------------------------------------------------------------------------
# HTTP layer — polite, retrying, cached
# ---------------------------------------------------------------------------

def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    return os.path.join(CACHE_DIR, f"{slug}.html")


def fetch(url: str, delay: float = 1.5, force: bool = False) -> str:
    """Fetch URL with on-disk cache + exponential backoff. Returns HTML body."""
    _ensure_cache_dir()
    cache_path = _cache_path(url)
    if not force and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()

    headers = {"User-Agent": USER_AGENT}
    backoff = delay
    for attempt in range(1, 6):
        try:
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code == 200:
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(r.text)
                # Polite delay AFTER successful fetch
                time.sleep(delay + random.uniform(0, 0.5))
                return r.text
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", str(backoff)))
                log.warning("429 Too Many Requests; waiting %ds (attempt %d)", wait, attempt)
                time.sleep(wait)
                backoff *= 2
                continue
            if r.status_code >= 500:
                log.warning("HTTP %d on %s; retry %d/5", r.status_code, url, attempt)
                time.sleep(backoff)
                backoff *= 2
                continue
            log.error("HTTP %d on %s (not retryable)", r.status_code, url)
            return ""
        except requests.RequestException as e:
            log.warning("Network error on %s: %s; retry %d/5", url, e, attempt)
            time.sleep(backoff)
            backoff *= 2
    log.error("Giving up on %s after 5 retries", url)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Discovery — find material URLs from group index pages
# ---------------------------------------------------------------------------

def discover_material_urls(group_url: str, delay: float,
                           max_depth: int = 4, _visited: set | None = None) -> list[str]:
    """Recursively find all /material-properties/* URLs reachable from a group page.

    MakeItFrom organizes materials hierarchically:
      /material-group/Iron-Alloy
        → /material-group/Wrought-Carbon-Or-Non-Alloy-Steel
          → /material-properties/astm_a36-...
          → /material-properties/astm_a516-...
    So we recurse through /material-group/* links to depth max_depth,
    collecting all /material-properties/* URLs we find along the way.
    """
    if _visited is None:
        _visited = set()
    if group_url in _visited or max_depth <= 0:
        return []
    _visited.add(group_url)
    log.info("Discovering [depth %d]: %s", max_depth, group_url.replace(BASE_URL, ""))

    html = fetch(group_url, delay=delay)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")

    material_urls = set()
    subgroup_urls = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/material-properties/" in href:
            material_urls.add(urllib.parse.urljoin(BASE_URL, href))
        elif "/material-group/" in href:
            subgroup = urllib.parse.urljoin(BASE_URL, href)
            if subgroup not in _visited:
                subgroup_urls.add(subgroup)

    log.info("  +%d materials, +%d sub-groups to recurse",
             len(material_urls), len(subgroup_urls))

    # Recurse into sub-groups
    for sg in sorted(subgroup_urls):
        material_urls.update(
            discover_material_urls(sg, delay, max_depth - 1, _visited)
        )

    return sorted(material_urls)


# ---------------------------------------------------------------------------
# Parser — extract structured data from a material page
# ---------------------------------------------------------------------------

def slugify(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("/", "_").replace(" ", "_").replace("-", "_").replace(".", "_")
    s = re.sub(r"_+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s.strip("_")


def parse_material(html: str, url: str) -> dict | None:
    """Parse a /material-properties/* page. Returns None if parse fails."""
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if not h1:
        return None
    name = h1.get_text(strip=True)

    # Try to extract designations from the H1 + breadcrumbs
    designations: list[str] = []
    title_text = name
    # Find equivalent designations in parentheses / commas of the title
    # e.g., "ASTM A36 (SS400, S275) Structural Carbon Steel"
    for m in re.finditer(r"\b([A-Z]{2,5}\s*[\-]?\s*[A-Z0-9][A-Z0-9\-]*)", title_text):
        token = m.group(1).strip()
        if len(token) > 2 and len(token) < 25:
            designations.append(token)

    # Map designations to spec slugs using our patterns
    spec_matches: list[dict] = []
    for designation in designations:
        for pattern, template in DESIGNATION_PATTERNS:
            m = pattern.search(designation)
            if m:
                spec_slug = template.format(*[slugify(g) for g in m.groups()])
                spec_matches.append({
                    "designation": designation,
                    "matched_to": spec_slug,
                })

    # Chemistry: sometimes presented as dl/dt/dd or as "Element: X to Y%"
    chemistry: dict[str, str] = {}
    chem_section = None
    for h in soup.find_all(["h2", "h3"]):
        if "composition" in h.get_text(strip=True).lower():
            chem_section = h
            break
    if chem_section:
        # Walk siblings until next heading
        for sib in chem_section.find_next_siblings():
            if sib.name in ("h2", "h3"):
                break
            text = sib.get_text("\n", strip=True)
            for m in re.finditer(
                r"\b([A-Z][a-z]?)\b[^:]*?:?\s*([0-9.]+)\s*(?:to)?\s*([0-9.]*)\s*%",
                text,
            ):
                el, low, hi = m.group(1), m.group(2), m.group(3)
                if hi:
                    chemistry[el] = f"{low}-{hi}"
                else:
                    chemistry[el] = low

    # Mechanical properties similarly
    mech: dict[str, str] = {}
    for h in soup.find_all(["h2", "h3"]):
        if "mechanical" in h.get_text(strip=True).lower():
            for sib in h.find_next_siblings():
                if sib.name in ("h2", "h3"):
                    break
                text = sib.get_text("\n", strip=True)
                for line in text.split("\n"):
                    m = re.match(
                        r"(Yield Strength|Tensile Strength|Ultimate Tensile|Elastic Modulus"
                        r"|Elongation|Brinell Hardness|Shear Strength|Charpy)\b.*?"
                        r"([0-9.]+)\s*(MPa|GPa|HV|HB|J|%)?",
                        line,
                        re.IGNORECASE,
                    )
                    if m:
                        mech[m.group(1).strip()] = f"{m.group(2)} {m.group(3) or ''}".strip()
            break

    # Try to find UNS number (e.g., K02700, S30400)
    uns = ""
    m_uns = re.search(r"\b([A-Z]\d{5})\b", name)
    if m_uns:
        uns = m_uns.group(1)

    return {
        "url": url,
        "name": name,
        "designations": designations,
        "spec_matches": spec_matches,
        "uns_number": uns,
        "chemistry": chemistry,
        "mechanical": mech,
    }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def load_known_specs() -> set[str]:
    """Return the set of Material Specification slugs we already have in the fixture."""
    with open(SPEC_FIXTURE) as f:
        rows = json.load(f)
    return {r["name"] for r in rows}


def run(groups: Iterable[str], max_pages: int, delay: float, force: bool = False):
    log.info("MakeItFrom.com extractor — start")
    log.info("  cache dir: %s", CACHE_DIR)
    log.info("  delay: %.1fs between requests", delay)
    log.info("  max material pages: %d", max_pages)

    known_specs = load_known_specs()
    log.info("  loaded %d existing Material Specification slugs to match against", len(known_specs))

    # 1. Discover
    all_urls: list[str] = []
    for group_name in groups:
        if group_name not in GROUP_INDEX_URLS:
            log.warning("Unknown group: %s (skipped)", group_name)
            continue
        urls = discover_material_urls(GROUP_INDEX_URLS[group_name], delay)
        all_urls.extend(urls)
    # dedup keep-order
    seen = set()
    unique_urls = [u for u in all_urls if not (u in seen or seen.add(u))]
    log.info("Total unique material URLs: %d", len(unique_urls))

    if len(unique_urls) > max_pages:
        log.warning("Capping at --max-pages=%d (was %d)", max_pages, len(unique_urls))
        unique_urls = unique_urls[:max_pages]

    # 2. Fetch + parse
    parsed: list[dict] = []
    unmatched: list[dict] = []
    for i, url in enumerate(unique_urls, 1):
        log.info("[%d/%d] %s", i, len(unique_urls), url.split("/")[-1])
        html = fetch(url, delay=delay, force=force)
        if not html:
            continue
        data = parse_material(html, url)
        if data is None:
            log.warning("  parse failed; skipped")
            continue
        # Was any designation matched to a known spec?
        matched = [m for m in data["spec_matches"] if m["matched_to"] in known_specs]
        if matched:
            data["matched_specs"] = [m["matched_to"] for m in matched]
            parsed.append(data)
        else:
            unmatched.append(data)

    with open(OUT_RAW, "w") as f:
        json.dump(parsed, f, indent=2)
    with open(OUT_UNMATCHED, "w") as f:
        json.dump(unmatched, f, indent=2)
    log.info("")
    log.info("Done.")
    log.info("  Parsed + matched: %d → %s", len(parsed), OUT_RAW)
    log.info("  Parsed but unmatched: %d → %s", len(unmatched), OUT_UNMATCHED)
    log.info("")
    log.info("Next step: review %s, then merge with _build_makeitfrom_fixtures.py", OUT_RAW)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--group",
        default=",".join(GROUP_INDEX_URLS.keys()),
        help="Comma-separated group names to scrape. Default: all known groups.",
    )
    ap.add_argument(
        "--max-pages", type=int, default=200,
        help="Cap on total material pages fetched (default 200). Increase for full scrape.",
    )
    ap.add_argument(
        "--delay", type=float, default=1.5,
        help="Delay in seconds between HTTP requests (default 1.5, be polite).",
    )
    ap.add_argument(
        "--force", action="store_true",
        help="Refetch even if a cached HTML file exists.",
    )
    args = ap.parse_args()
    groups = [g.strip() for g in args.group.split(",") if g.strip()]
    run(groups=groups, max_pages=args.max_pages, delay=args.delay, force=args.force)
