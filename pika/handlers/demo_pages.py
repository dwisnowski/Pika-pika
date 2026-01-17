"""Demo and history page handlers.

Serves demo and history pages using Jinja2 templates.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse


def demo(request: Request):
    """Serve demo page using Jinja2 template."""
    from ..app import templates
    return templates.TemplateResponse("demo.html", {
        "request": request,
        "page_title": "Pika-pika Demo",
        "page_description": "Simulated voltage monitoring demonstration with pre-generated sample data."
    })


def history(request: Request):
    """Serve history page using Jinja2 template."""
    from ..app import templates
    return templates.TemplateResponse("history.html", {
        "request": request,
        "page_title": "Pika-pika History",
        "page_description": "Browse historical voltage data and view detailed analysis."
    })


def register_demo_pages_routes(app: FastAPI):
    """Register demo and history page routes with FastAPI app."""
    app.get("/demo")(demo)
    app.get("/history")(history)
