"""History page handlers.

Serves history page using Jinja2 template.
"""

from fastapi import FastAPI, Request


def history(request: Request):
    """Serve history page using Jinja2 template."""
    from ...app import templates
    return templates.TemplateResponse("history.html", {
        "request": request,
        "page_title": "Pika-pika History",
        "page_description": "Browse historical voltage data and view detailed analysis."
    })


def register_history_pages_routes(app: FastAPI):
    """Register history page routes with FastAPI app."""
    app.get("/history")(history)
