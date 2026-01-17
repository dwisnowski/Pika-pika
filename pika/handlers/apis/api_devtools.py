from fastapi import FastAPI, Response
import os
import uuid

def register_devtools_routes(app: FastAPI):
    """Register routes for Chrome DevTools integration."""
    
    # Generate a consistent UUID for this project instance
    # In a real app, this might be stored in a config or generated once
    project_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "pika-pika.local"))
    
    # Get the project root directory
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    
    @app.get("/.well-known/appspecific/com.chrome.devtools.json")
    async def get_devtools_json():
        return {
            "workspace": {
                "root": project_root,
                "uuid": project_uuid
            }
        }
