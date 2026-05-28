"""Portable path resolution for fixture importers.

Replaces hardcoded absolute paths (/workspace/frappe-bench/...) so the
importers run on any bench (/home/frappe/frappe-bench, CI, laptop) without
editing. Works standalone (python foo.py) AND under bench.

Layout: this file is at apps/<app>/<app>/fixtures/_importers/_paths.py
"""
import os

_IMPORTERS_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.dirname(_IMPORTERS_DIR)              # .../<app>/fixtures
_APP_PKG = os.path.dirname(FIXTURES_DIR)                    # .../<app> (python pkg)
APP_ROOT = os.path.dirname(_APP_PKG)                        # .../apps/<app>
SOURCES_DIR = os.path.join(APP_ROOT, "sources")            # .../apps/<app>/sources


def fixture(name: str) -> str:
    """Absolute path to a fixture JSON by filename."""
    return os.path.join(FIXTURES_DIR, name)


def source(name: str = "") -> str:
    """Absolute path inside the app's sources/ dir (gitignored PDFs)."""
    return os.path.join(SOURCES_DIR, name) if name else SOURCES_DIR


# Bench-level apps dir, for cross-app source references (e.g. weldcore
# importers reading filler-catalog PDFs co-located in materials/source).
# Override with env WELD_SOURCES_ROOT to relocate all sources at once.
BENCH_APPS = os.path.dirname(APP_ROOT)                     # .../apps


def apps_path(rel: str) -> str:
    """Resolve a path relative to the bench apps/ dir (portable).

    apps_path('materials/source/Foo.pdf') →
      <env WELD_SOURCES_ROOT>/materials/source/Foo.pdf  if set, else
      <bench>/apps/materials/source/Foo.pdf
    """
    root = os.environ.get("WELD_SOURCES_ROOT")
    if root:
        return os.path.join(root, rel)
    return os.path.join(BENCH_APPS, rel)
