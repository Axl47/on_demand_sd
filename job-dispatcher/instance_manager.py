#!/usr/bin/env python3
"""
Instance Manager - Manages GCE ComfyUI instance lifecycle
Replaces the job-based dispatcher with simple instance control
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
import os
import logging
from typing import Optional

from google.cloud import storage
from googleapiclient import discovery
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ComfyUI Instance Manager")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Google Cloud clients
compute = discovery.build("compute", "v1")

# Configuration from environment
PROJECT = os.getenv("GCP_PROJECT")
INSTANCE = os.getenv("GCE_INSTANCE", "gpu-sd-worker")
ZONE = os.getenv("GCE_ZONE", "us-central1-c")
STARTUP_SCRIPT_URL = os.getenv("STARTUP_SCRIPT_URL")
ALLOWED_IP = os.getenv("ALLOWED_IP")  # IP allowed to access ComfyUI
AUTH_USER = os.getenv("COMFYUI_AUTH_USER", "admin")
AUTH_PASS = os.getenv("COMFYUI_AUTH_PASS", "comfyui@123")

# Activity tracking
last_activity = datetime.now()
INACTIVITY_TIMEOUT = timedelta(minutes=1)

class InstanceStatus(BaseModel):
    status: str
    external_ip: Optional[str] = None
    last_activity: Optional[str] = None
    
class OperationResult(BaseModel):
    success: bool
    message: str
    status: Optional[str] = None

def get_instance_status():
    """Get current status of the GCE instance"""
    try:
        instance = compute.instances().get(
            project=PROJECT,
            zone=ZONE,
            instance=INSTANCE
        ).execute()
        
        status = instance.get("status", "UNKNOWN")
        
        # Get external IP if running
        external_ip = None
        if status == "RUNNING":
            for interface in instance.get("networkInterfaces", []):
                for config in interface.get("accessConfigs", []):
                    if config.get("natIP"):
                        external_ip = config["natIP"]
                        break
        
        return {
            "status": status,
            "external_ip": external_ip,
            "last_activity": last_activity.isoformat()
        }
    except HttpError as e:
        if e.resp.status == 404:
            return {"status": "NOT_FOUND", "external_ip": None}
        raise

def set_instance_metadata(metadata_items):
    """Update instance metadata"""
    try:
        # Get current instance to get fingerprint
        instance = compute.instances().get(
            project=PROJECT,
            zone=ZONE,
            instance=INSTANCE
        ).execute()
        
        fingerprint = instance["metadata"]["fingerprint"]
        
        # Update metadata
        body = {
            "fingerprint": fingerprint,
            "items": metadata_items
        }
        
        operation = compute.instances().setMetadata(
            project=PROJECT,
            zone=ZONE,
            instance=INSTANCE,
            body=body
        ).execute()
        
        return wait_for_operation(operation)
    except Exception as e:
        logger.error(f"Failed to set metadata: {e}")
        raise

def wait_for_operation(operation):
    """Wait for a GCE operation to complete"""
    while True:
        result = compute.zoneOperations().get(
            project=PROJECT,
            zone=ZONE,
            operation=operation["name"]
        ).execute()
        
        if result["status"] == "DONE":
            if "error" in result:
                raise RuntimeError(result["error"])
            return True
        
        import time
        time.sleep(2)

@app.get("/")
def read_root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ComfyUI Instance Manager"}

@app.get("/status", response_model=InstanceStatus)
def get_status():
    """Get current instance status"""
    try:
        status = get_instance_status()
        return InstanceStatus(**status)
    except Exception as e:
        logger.error(f"Failed to get instance status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/start", response_model=OperationResult)
def start_instance():
    """Start the ComfyUI instance"""
    global last_activity
    last_activity = datetime.now()
    
    try:
        # Check current status
        status = get_instance_status()
        
        if status["status"] == "RUNNING":
            return OperationResult(
                success=True,
                message="Instance is already running",
                status="RUNNING"
            )
        
        if status["status"] in ["PROVISIONING", "STAGING"]:
            return OperationResult(
                success=True,
                message="Instance is already starting",
                status=status["status"]
            )
        
        # Set metadata for startup script
        metadata_items = [
            {"key": "startup-script-url", "value": STARTUP_SCRIPT_URL}
        ]
        
        if ALLOWED_IP:
            metadata_items.append({"key": "allowed_ip", "value": ALLOWED_IP})
        
        metadata_items.extend([
            {"key": "auth_user", "value": AUTH_USER},
            {"key": "auth_pass", "value": AUTH_PASS}
        ])
        
        set_instance_metadata(metadata_items)
        
        # Start the instance
        operation = compute.instances().start(
            project=PROJECT,
            zone=ZONE,
            instance=INSTANCE
        ).execute()
        
        wait_for_operation(operation)
        
        return OperationResult(
            success=True,
            message="Instance started successfully",
            status="PROVISIONING"
        )
        
    except HttpError as e:
        if e.resp.status == 404:
            raise HTTPException(status_code=404, detail="Instance not found")
        logger.error(f"Failed to start instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop", response_model=OperationResult)
def stop_instance():
    """Stop the ComfyUI instance"""
    try:
        # Check current status
        status = get_instance_status()
        
        if status["status"] in ["TERMINATED", "STOPPING"]:
            return OperationResult(
                success=True,
                message="Instance is already stopped or stopping",
                status=status["status"]
            )
        
        # Stop the instance
        operation = compute.instances().stop(
            project=PROJECT,
            zone=ZONE,
            instance=INSTANCE
        ).execute()
        
        wait_for_operation(operation)
        
        return OperationResult(
            success=True,
            message="Instance stopped successfully",
            status="STOPPING"
        )
        
    except HttpError as e:
        if e.resp.status == 404:
            raise HTTPException(status_code=404, detail="Instance not found")
        logger.error(f"Failed to stop instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to stop instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/keep-alive", response_model=OperationResult)
def keep_alive():
    """Reset the inactivity timer"""
    global last_activity
    last_activity = datetime.now()
    
    # Also send keep-alive to the instance if it's running
    try:
        status = get_instance_status()
        if status["status"] == "RUNNING" and status["external_ip"]:
            # The instance's activity tracker will handle this via its own endpoint
            # This is just to track activity on the dispatcher side
            pass
    except Exception as e:
        logger.warning(f"Failed to check instance during keep-alive: {e}")
    
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

# Optional: Background task to auto-stop on inactivity
# This would need to be implemented with asyncio or a separate thread
# For now, the instance itself handles auto-shutdown via its cron job

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting ComfyUI Instance Manager on 0.0.0.0:8187")
    try:
        uvicorn.run(app, host="0.0.0.0", port=8187, log_level="info")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise