"""Index page handler.

Serves main application index page using Jinja2 templates.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse


def index(request: Request):
    """Serve the main index page using Jinja2 template."""
    from ...app import templates
    return templates.TemplateResponse("index.html", {
        "request": request,
        "page_title": "Pika-pika Live Monitor",
        "page_description": "Shows recent sampled values (live). Data is sampled at 100 Hz and stored on device."
    })


def register_index_routes(app: FastAPI):
    """Register index page routes with FastAPI app."""
    app.get("/")(index)
