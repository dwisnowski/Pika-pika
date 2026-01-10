# Pika-pika

A Python-based Raspberry Pi voltage logger and live web viewer.

This documentation contains quick links and usage for the project. The full README is included in the repository and the site contains a short guide to the features and a demo page.

- Live UI: `/` (served by the running app)
- Demo UI: `/demo` (mock data — no hardware required)

## Quick start

1. Set up the virtual environment and install dependencies:

```bash
make venv
make install
```

2. Run the app:

```bash
# For production use:
make run

# For development with auto-reload:
make dev
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
