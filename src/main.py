"""
Collector Module Main Application
Kepler power data collection and cost conversion API server
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import logging

from .kepler_client import KeplerClient
from .power_metrics import PowerCalculator, PowerData
from .data_processor import DataProcessor
from .config.settings import get_settings

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app initialization
app = FastAPI(
    title="kcloud-collector",
    description="Kepler power data collection and cost conversion API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load settings
settings = get_settings()

# Global instances
kepler_client = None
power_calculator = None
data_processor = None

@app.on_event("startup")
async def startup_event():
    """Initialize on application startup"""
    global kepler_client, power_calculator, data_processor
    
    logger.info("Starting Collector module...")
    
    try:
        # Initialize Kepler client
        kepler_client = KeplerClient(
            prometheus_url=settings.kepler_prometheus_url,
            metrics_interval=settings.kepler_metrics_interval
        )
        
        # Initialize power calculator
        power_calculator = PowerCalculator(
            electricity_rate=settings.electricity_rate,
            cooling_factor=settings.cooling_factor,
            carbon_rate=settings.carbon_rate
        )
        
        # Initialize data processor
        data_processor = DataProcessor(
            redis_url=settings.redis_url,
            influxdb_url=settings.influxdb_url,
            influxdb_bucket=settings.influxdb_bucket
        )
        
        # Test Kepler connection
        await kepler_client.health_check()
        logger.info("Kepler connection successful")
        
        logger.info("Collector module initialization completed")
        
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        raise

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "kcloud-collector",
        "version": "1.0.0",
        "description": "Kepler power data collection and cost conversion",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check"""
    try:
        # Check Kepler connection
        kepler_status = await kepler_client.health_check()
        
        # Check database connection
        db_status = await data_processor.health_check()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "kepler": kepler_status,
                "database": db_status
            }
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")

# =============================================================================
# Power data collection API
# =============================================================================

@app.get("/power/current")
async def get_current_power(
    namespace: Optional[str] = None,
    workload: Optional[str] = None,
    time_range: str = "5m"
):
    """Query real-time power data"""
    try:
        power_data = await kepler_client.get_container_power_metrics(
            namespace=namespace,
            workload=workload,
            time_range=time_range
        )
        
        return {
            "data": power_data,
            "timestamp": datetime.utcnow().isoformat(),
            "time_range": time_range
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Power data query failed: {str(e)}")

@app.get("/power/containers")
async def get_container_power(
    namespace: Optional[str] = None,
    limit: int = 100
):
    """Query power data by container"""
    try:
        containers = await kepler_client.get_all_container_metrics(
            namespace=namespace,
            limit=limit
        )
        
        return {
            "containers": containers,
            "count": len(containers),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Container power data query failed: {str(e)}")

@app.get("/power/nodes")
async def get_node_power():
    """Query power data by node"""
    try:
        nodes = await kepler_client.get_node_power_metrics()
        
        return {
            "nodes": nodes,
            "count": len(nodes),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Node power data query failed: {str(e)}")

# =============================================================================
# Cost calculation API
# =============================================================================

@app.get("/cost/current")
async def get_current_cost(
    namespace: Optional[str] = None,
    workload: Optional[str] = None
):
    """Calculate current operation costs"""
    try:
        # Collect power data
        power_data = await kepler_client.get_container_power_metrics(
            namespace=namespace,
            workload=workload,
            time_range="1h"
        )
        
        # Calculate costs
        cost_data = power_calculator.calculate_total_cost(power_data)
        
        return {
            "cost": cost_data,
            "timestamp": datetime.utcnow().isoformat(),
            "period": "1 hour"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cost calculation failed: {str(e)}")

@app.get("/cost/hourly")
async def get_hourly_cost(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    namespace: Optional[str] = None
):
    """Hourly cost analysis"""
    try:
        if not start:
            start = datetime.utcnow() - timedelta(hours=24)
        if not end:
            end = datetime.utcnow()
            
        cost_data = await data_processor.get_hourly_cost_analysis(
            start_time=start,
            end_time=end,
            namespace=namespace
        )
        
        return {
            "cost_analysis": cost_data,
            "period": f"{start.isoformat()} to {end.isoformat()}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hourly cost analysis failed: {str(e)}")

@app.get("/cost/workload/{workload_id}")
async def get_workload_cost(workload_id: str):
    """Detailed cost analysis by workload"""
    try:
        cost_breakdown = await data_processor.get_workload_cost_breakdown(workload_id)
        
        return {
            "workload_id": workload_id,
            "cost_breakdown": cost_breakdown,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workload cost analysis failed: {str(e)}")

# =============================================================================
# Power profiling API
# =============================================================================

@app.get("/profile/workload-types")
async def get_workload_types():
    """Power profile by workload type"""
    try:
        profiles = await data_processor.get_workload_power_profiles()
        
        return {
            "profiles": profiles,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile query failed: {str(e)}")

@app.post("/profile/classify")
async def classify_workload(power_data: Dict):
    """Classify workload power patterns"""
    try:
        classification = await data_processor.classify_workload_pattern(power_data)
        
        return {
            "classification": classification,
            "confidence": classification.get("confidence", 0.0),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workload classification failed: {str(e)}")

# =============================================================================
# Background data collection tasks
# =============================================================================

@app.post("/collect/start")
async def start_collection(background_tasks: BackgroundTasks):
    """Start background data collection"""
    try:
        background_tasks.add_task(data_processor.start_continuous_collection)
        
        return {
            "message": "Data collection started",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data collection start failed: {str(e)}")

@app.post("/collect/stop")
async def stop_collection():
    """Stop background data collection"""
    try:
        await data_processor.stop_continuous_collection()
        
        return {
            "message": "Data collection stopped",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data collection stop failed: {str(e)}")

# =============================================================================
# Metrics and statistics
# =============================================================================

@app.get("/metrics/summary")
async def get_metrics_summary():
    """Collection metrics summary"""
    try:
        summary = await data_processor.get_collection_summary()
        
        return {
            "summary": summary,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics summary query failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )