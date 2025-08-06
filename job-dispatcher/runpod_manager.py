#!/usr/bin/env python3
"""
Runpod Instance Manager - Manages Runpod pod lifecycle for ComfyUI
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
import os
import logging
from typing import Optional
import runpod

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ComfyUI Runpod Manager")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration from environment
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
POD_ID = os.getenv("RUNPOD_POD_ID")
POD_TEMPLATE_ID = os.getenv("RUNPOD_TEMPLATE_ID")  # Optional: for creating new pods
GPU_TYPE = os.getenv("RUNPOD_GPU_TYPE", "NVIDIA L40S")  # Default GPU type
DISK_SIZE = int(os.getenv("RUNPOD_DISK_SIZE", "100"))  # GB
VOLUME_ID = os.getenv("RUNPOD_VOLUME_ID")  # Optional: persistent volume
COMFYUI_DOMAIN = os.getenv("COMFYUI_DOMAIN")  # Optional: custom domain

# Initialize Runpod client
if RUNPOD_API_KEY:
    runpod.api_key = RUNPOD_API_KEY
    logger.info("Runpod API key configured")
else:
    logger.error("RUNPOD_API_KEY not set")

# Log configuration (without sensitive data)
logger.info(f"Configuration loaded:")
logger.info(f"  POD_ID: {POD_ID}")
logger.info(f"  POD_TEMPLATE_ID: {POD_TEMPLATE_ID}")
logger.info(f"  GPU_TYPE: {GPU_TYPE}")
logger.info(f"  DISK_SIZE: {DISK_SIZE}GB")
logger.info(f"  VOLUME_ID: {VOLUME_ID}")
logger.info(f"  COMFYUI_DOMAIN: {COMFYUI_DOMAIN}")

# Activity tracking
last_activity = datetime.now()
INACTIVITY_TIMEOUT = timedelta(minutes=30)

class InstanceStatus(BaseModel):
    status: str
    external_ip: Optional[str] = None
    comfyui_url: Optional[str] = None
    last_activity: Optional[str] = None
    pod_id: Optional[str] = None
    
class OperationResult(BaseModel):
    success: bool
    message: str
    status: Optional[str] = None
    pod_id: Optional[str] = None

def map_runpod_status(runpod_status: str) -> str:
    """Map Runpod status to our unified status format"""
    status_map = {
        "RUNNING": "RUNNING",
        "IDLE": "RUNNING",  # Idle pods are still accessible
        "STOPPED": "TERMINATED",
        "STOPPING": "STOPPING",
        "STARTING": "PROVISIONING",
        "PENDING": "PROVISIONING",
        "FAILED": "TERMINATED",
        "EXITED": "TERMINATED"
    }
    return status_map.get(runpod_status.upper(), "UNKNOWN")

def get_pod_status(pod_id: str = None):
    """Get current status of the Runpod pod"""
    try:
        pod_id = pod_id or POD_ID
        if not pod_id:
            return {
                "status": "NOT_CONFIGURED",
                "external_ip": None,
                "comfyui_url": None,
                "last_activity": last_activity.isoformat()
            }
        
        # Get pod details
        pod = runpod.get_pod(pod_id)
        
        if not pod:
            return {
                "status": "NOT_FOUND",
                "external_ip": None,
                "comfyui_url": None,
                "last_activity": last_activity.isoformat()
            }
        
        # Extract status and connection info
        runpod_status = pod.get("desiredStatus", "UNKNOWN")
        status = map_runpod_status(runpod_status)
        
        # Get connection URL
        external_ip = None
        comfyui_url = None
        
        if status == "RUNNING":
            # Runpod proxy URL format: https://{pod_id}-{port}.proxy.runpod.net
            # ComfyUI typically runs on port 8188
            if pod_id:
                comfyui_url = f"https://{pod_id}-8188.proxy.runpod.net"
                external_ip = f"{pod_id}.proxy.runpod.net"
                logger.info(f"Generated Runpod proxy URL: {comfyui_url}")
            
            # Override with custom domain if configured
            if COMFYUI_DOMAIN:
                comfyui_url = f"https://{COMFYUI_DOMAIN}"
                logger.info(f"Using custom domain: {comfyui_url}")
            
            # Fallback: Direct IP if available (rare for Runpod)
            if not comfyui_url and pod.get("ip"):
                external_ip = pod["ip"]
                comfyui_url = f"http://{external_ip}:8188"
                logger.info(f"Using direct IP: {comfyui_url}")
        
        result = {
            "status": status,
            "external_ip": external_ip,
            "comfyui_url": comfyui_url,
            "last_activity": last_activity.isoformat(),
            "pod_id": pod_id
        }
        
        logger.info(f"Pod status: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to get pod status: {e}")
        return {
            "status": "ERROR",
            "external_ip": None,
            "comfyui_url": None,
            "last_activity": last_activity.isoformat(),
            "error": str(e)
        }

def create_or_get_pod():
    """Create a new pod or get existing pod ID"""
    global POD_ID
    
    try:
        # If we have a pod ID, check if it exists
        if POD_ID:
            pod = runpod.get_pod(POD_ID)
            if pod:
                return POD_ID
        
        # Create a new pod if template ID is provided
        if POD_TEMPLATE_ID:
            logger.info(f"Creating new pod from template {POD_TEMPLATE_ID}")
            pod = runpod.create_pod(
                name="comfyui-pod",
                template_id=POD_TEMPLATE_ID,
                gpu_type_id=GPU_TYPE,
                cloud_type="SECURE",  # or "COMMUNITY" for cheaper
                container_disk_in_gb=DISK_SIZE,
                volume_in_gb=0 if not VOLUME_ID else None,
                volume_id=VOLUME_ID
            )
            POD_ID = pod["id"]
            logger.info(f"Created new pod: {POD_ID}")
            return POD_ID
        
        # Otherwise, try to find an existing pod
        pods = runpod.get_pods()
        for pod in pods:
            if "comfyui" in pod.get("name", "").lower():
                POD_ID = pod["id"]
                logger.info(f"Found existing pod: {POD_ID}")
                return POD_ID
        
        raise ValueError("No pod found and no template ID provided to create one")
        
    except Exception as e:
        logger.error(f"Failed to create or get pod: {e}")
        raise

@app.get("/")
def read_root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ComfyUI Runpod Manager"}

@app.get("/status", response_model=InstanceStatus)
def get_status():
    """Get current pod status"""
    try:
        status = get_pod_status()
        return InstanceStatus(**status)
    except Exception as e:
        logger.error(f"Failed to get pod status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/start", response_model=OperationResult)
def start_instance():
    """Start/Resume the ComfyUI pod"""
    global last_activity, POD_ID
    last_activity = datetime.now()
    
    try:
        # Get or create pod
        if not POD_ID:
            POD_ID = create_or_get_pod()
        
        # Check current status
        status = get_pod_status(POD_ID)
        
        if status["status"] == "RUNNING":
            return OperationResult(
                success=True,
                message="Pod is already running",
                status="RUNNING",
                pod_id=POD_ID
            )
        
        if status["status"] in ["PROVISIONING", "STAGING"]:
            return OperationResult(
                success=True,
                message="Pod is already starting",
                status=status["status"],
                pod_id=POD_ID
            )
        
        # Resume the pod
        logger.info(f"Resuming pod {POD_ID}")
        runpod.resume_pod(POD_ID)
        
        return OperationResult(
            success=True,
            message="Pod started successfully",
            status="PROVISIONING",
            pod_id=POD_ID
        )
        
    except Exception as e:
        error_msg = str(e)
        
        # Handle Runpod-specific errors
        if "insufficient" in error_msg.lower() or "capacity" in error_msg.lower():
            error_msg = "GPU resources are currently unavailable. Please try again in a few minutes."
            logger.error(f"Resource unavailable: {e}")
            raise HTTPException(status_code=503, detail=error_msg)
        elif "quota" in error_msg.lower():
            error_msg = "Account quota exceeded. Please check your Runpod account or upgrade your plan."
            logger.error(f"Quota exceeded: {e}")
            raise HTTPException(status_code=503, detail=error_msg)
        
        logger.error(f"Failed to start pod: {e}")
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/stop", response_model=OperationResult)
def stop_instance():
    """Stop the ComfyUI pod"""
    global POD_ID
    
    try:
        if not POD_ID:
            return OperationResult(
                success=True,
                message="No pod configured",
                status="TERMINATED"
            )
        
        # Check current status
        status = get_pod_status(POD_ID)
        
        if status["status"] in ["TERMINATED", "STOPPING"]:
            return OperationResult(
                success=True,
                message="Pod is already stopped or stopping",
                status=status["status"],
                pod_id=POD_ID
            )
        
        # Stop the pod
        logger.info(f"Stopping pod {POD_ID}")
        runpod.stop_pod(POD_ID)
        
        return OperationResult(
            success=True,
            message="Pod stopped successfully",
            status="STOPPING",
            pod_id=POD_ID
        )
        
    except Exception as e:
        logger.error(f"Failed to stop pod: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/keep-alive", response_model=OperationResult)
def keep_alive():
    """Reset the inactivity timer"""
    global last_activity
    last_activity = datetime.now()
    
    return OperationResult(
        success=True,
        message="Activity timer reset",
        status=None
    )

@app.get("/activity")
def get_activity():
    """Get last activity time and timeout status"""
    time_since_activity = datetime.now() - last_activity
    is_inactive = time_since_activity > INACTIVITY_TIMEOUT
    
    return {
        "last_activity": last_activity.isoformat(),
        "seconds_since_activity": int(time_since_activity.total_seconds()),
        "is_inactive": is_inactive,
        "timeout_seconds": int(INACTIVITY_TIMEOUT.total_seconds())
    }

@app.post("/terminate", response_model=OperationResult)
def terminate_instance():
    """Terminate (delete) the ComfyUI pod - use with caution"""
    global POD_ID
    
    try:
        if not POD_ID:
            return OperationResult(
                success=True,
                message="No pod to terminate",
                status="TERMINATED"
            )
        
        # Terminate the pod
        logger.info(f"Terminating pod {POD_ID}")
        runpod.terminate_pod(POD_ID)
        
        # Clear the pod ID since it's terminated
        old_pod_id = POD_ID
        POD_ID = None
        
        return OperationResult(
            success=True,
            message="Pod terminated successfully",
            status="TERMINATED",
            pod_id=old_pod_id
        )
        
    except Exception as e:
        logger.error(f"Failed to terminate pod: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting ComfyUI Runpod Manager on 0.0.0.0:8187")
    try:
        uvicorn.run(app, host="0.0.0.0", port=8187, log_level="info")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise