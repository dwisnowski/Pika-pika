"""History Analysis API."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import logging
from ...analysis import StreamAnalyzer
from ...datalogger import Datalogger

logger = logging.getLogger("uvicorn")

def register_api_analysis_routes(app, datalogger_instance):
    router = APIRouter()
    
    @router.get("/api/analysis/history")
    def get_history_analysis(
        start: float,
        end: float,
        source: str = None
    ):
        """Get analysis metrics for a historical time range."""
        try:
            # Re-use Datalogger's retrieval logic
            # Using get_range_from_file or get_range
            # Note: get_range might use in-memory buffer for recent data
            
            # Since analysis needs high-res data to compute accurate RMS,
            # we should fetch raw data.
            # Datalogger.get_range returns list of (ts, val)
            # Beware: requesting large ranges will process A LOT of data.
            # We should probably limit the window or downsample.
            
            # For now, let's assume reasonable ranges (e.g. < 1 hour).
            # If range is too large, we might timeout.
             
            data = datalogger_instance.get_range(start, end, max_points=1000000) # Get all points?
            
            if not data:
                 return JSONResponse({"data": []})

            # Initialize analyzer
            # Use current config or defaults? config is in datalogger
            # But datalogger stores config in self.analysis_config?
            # We can access it via datalogger_instance if exposed, or just create new default
            
            # TODO: Ideally pass global analysis config
            # For now use default
            analyzer = StreamAnalyzer(config=getattr(datalogger_instance, 'analysis_config', {})) 
            
            results = analyzer.analyze_batch(data)
            
            # Downsample results for display?
            # Charts don't need 860Hz RMS data (RMS is slow changing).
            # StreamAnalyzer computes RMS every sample (sliding window).
            # We can downsample the output to e.g. 1Hz or 10Hz.
            
            downsampled = []
            last_ts = 0
            interval = 1.0 # 1 second interval for history analysis
            
            for res in results:
                ts = res['ts']
                if ts - last_ts >= interval:
                    downsampled.append(res)
                    last_ts = ts
            
            return JSONResponse({"data": downsampled})
            
        except Exception as e:
            logger.exception("Analysis history failed")
            return JSONResponse({"error": str(e)}, status_code=500)

    app.include_router(router)
