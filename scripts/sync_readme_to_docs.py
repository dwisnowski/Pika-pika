"""Sync README.md into docs/README.md for MkDocs builds.

This is intentionally simple: it overwrites docs/README.md with the repository README
so the docs site contains a copy of the project's README automatically.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "README.md"
DST = ROOT / "docs" / "README-synced.md"

if not SRC.exists():
    print("README.md not found at expected location.")
    raise SystemExit(1)

DST.parent.mkdir(parents=True, exist_ok=True)
text = SRC.read_text(encoding="utf-8")
# Replace repository static image paths (so MkDocs sees them under docs/images)
# Common variants: pika/static/Pika-pika.png and /static/Pika-pika.png
text = text.replace('pika/static/Pika-pika.png', 'images/Pika-pika.png')
text = text.replace('/static/Pika-pika.png', 'images/Pika-pika.png')
# Copy the PNG into docs/images so mkdocs can include it
src_img = ROOT / 'pika' / 'static' / 'Pika-pika.png'
img_dst_dir = DST.parent / 'images'
if src_img.exists():
    img_dst_dir.mkdir(parents=True, exist_ok=True)
    (img_dst_dir / src_img.name).write_bytes(src_img.read_bytes())
    print(f"Copied {src_img} -> {img_dst_dir / src_img.name}")
else:
    print(f"Source image {src_img} not found; skipping copy")

# Add a small header so the docs page has a clear title
wrap = """# Project README (synced)

> This page is automatically generated from the repository README via scripts/sync_readme_to_docs.py

"""
DST.write_text(wrap + text, encoding="utf-8")
print(f"Wrote {DST}")
