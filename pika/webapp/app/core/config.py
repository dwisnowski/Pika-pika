import yaml
import os
from pydantic import BaseModel

class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000

class LimitsConfig(BaseModel):
    realtime_max_ms: int = 500
    history_max_points: int = 50000

class WebConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    limits: LimitsConfig = LimitsConfig()
    data_dir: str = "/home/debian/pika/pika/datalogger/data"

def load_config(path: str = "config/web.yaml") -> WebConfig:
    if not os.path.exists(path):
        return WebConfig()
    
    with open(path, "r") as f:
        data = yaml.safe_load(f)
        return WebConfig(**data)

# Global settings
settings = load_config()
