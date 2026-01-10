# Pika-pika

A Python-based Raspberry Pi voltage logger and live web viewer.

This documentation contains quick links and usage for the project. The full README is included in the repository and the site contains a short guide to the features and a demo page.

- Live UI: `/` (served by the running app)
- Demo UI: `/demo` (mock data — no hardware required)

## Quick start

1. Create a Python virtual environment and install dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
uv pip install .
```

2. Run the app:

```bash
uvicorn pika.app:app --host 0.0.0.0 --port 8000
```

3. Open `http://<pi-ip>:8000/` or the demo at `http://<pi-ip>:8000/demo`.


## Documentation contribution

Docs are built with MkDocs and the Material theme. To build locally:

```bash
make docs
```

To serve locally and iterate:

```bash
make docs-serve
```
