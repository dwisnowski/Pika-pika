"""Sync README.md into docs/README.md for MkDocs builds.

This is intentionally simple: it overwrites docs/README.md with the repository README
so the docs site contains a copy of the project's README automatically.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "README.md"
DST = ROOT / "docs" / "README.md"

if not SRC.exists():
    print("README.md not found at expected location.")
    raise SystemExit(1)

DST.parent.mkdir(parents=True, exist_ok=True)
text = SRC.read_text(encoding="utf-8")
# Add a small header so the docs page has a clear title
wrap = """# Project README (synced)

> This page is automatically generated from the repository README via scripts/sync_readme_to_docs.py

"""
DST.write_text(wrap + text, encoding="utf-8")
print(f"Wrote {DST}")
