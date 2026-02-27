import os
import yaml
from app.core.config import settings

class CalibrationService:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.status_file = os.path.join(data_dir, "calibration_status.txt")
        self.config_file = "../pika.yaml"  # Path to shared config
    
    def get_calibration_values(self) -> dict:
        """Read learned nominal voltage and transformer ratio from calibration_status.txt
        
        Returns:
            dict with keys:
                - nominal_vrms: learned nominal mains voltage (default: 120.0)
                - transformer_ratio: learned transformer ratio (default: 120.0)
        """
        # Load defaults from pika.yaml
        nominal_vrms = 120.0
        transformer_ratio = 120.0
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    config = yaml.safe_load(f)
                    if config and "sensor" in config:
                        nominal_vrms = float(config["sensor"].get("target_mains_vrms", 120.0))
                        transformer_ratio = float(config["sensor"].get("transformer_ratio", 120.0))
        except Exception as e:
            print(f"[CalibrationService] Error reading pika.yaml: {e}")
        
        # Try to read learned values from calibration_status.txt
        try:
            if os.path.exists(self.status_file):
                with open(self.status_file, "r") as f:
                    lines = f.read().strip().split('\n')
                    if len(lines) >= 2:
                        nominal_vrms = float(lines[0])
                        transformer_ratio = float(lines[1])
        except Exception as e:
            print(f"[CalibrationService] Error reading calibration status: {e}")
        
        return {
            "nominal_vrms": nominal_vrms,
            "transformer_ratio": transformer_ratio
        }

calibration_service = CalibrationService(settings.data_dir)
