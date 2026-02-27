import os
from app.core.config import settings

class CalibrationService:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.status_file = os.path.join(data_dir, "calibration_status.txt")
    
    def get_learned_voltage(self) -> float:
        """Read the learned nominal voltage from calibration_status.txt"""
        try:
            if os.path.exists(self.status_file):
                with open(self.status_file, "r") as f:
                    content = f.read().strip()
                    if content:
                        return float(content)
        except Exception as e:
            print(f"[CalibrationService] Error reading calibration status: {e}")
        
        # Default to 120V if file doesn't exist or can't be read
        return 120.0

calibration_service = CalibrationService(settings.data_dir)
