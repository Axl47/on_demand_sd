# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is an on-demand Stable Diffusion system that orchestrates ComfyUI workloads across local CPU and remote GPU resources:

- **Local ComfyUI Frontend** (`vps-comfyui/`): CPU-only Docker container for workflow composition
- **Job Dispatcher** (`job-dispatcher/main.py`): FastAPI service that manages GPU VM lifecycle and job orchestration
- **GPU Worker Bootstrap** (`startup/bash.sh`): Automated VM setup script that installs ComfyUI on fresh GPU instances
- **Custom ComfyUI Node** (`vps-comfyui/custom_nodes/dispatch_gpu.py`): Dispatches rendering jobs to GPU backend

## Key Components

### Job Dispatcher (`job-dispatcher/main.py`)
- Receives rendering requests with ComfyUI workflows and model URLs
- Manages GCE instance lifecycle (start/stop GPU VMs)
- Handles GCS bucket operations for job data and outputs
- Uses VM metadata for job-specific configuration
- Waits for completion signals before returning results

### GPU Worker (`startup/bash.sh`)
- Bootstraps GPU VMs with ComfyUI and dependencies
- Downloads models from Civitai or GCS
- Executes workflows via ComfyUI API
- Uploads results to GCS and signals completion
- Auto-shuts down after job completion

### Custom Node (`dispatch_gpu.py`)
- ComfyUI node that sends jobs to the dispatcher
- Builds workflow graphs programmatically
- Returns thumbnail images for UI feedback

## Development Commands

### Local Development
```bash
# Start services (CPU ComfyUI + Dispatcher)
docker-compose up

# Build only ComfyUI container
docker-compose build comfyui

# View logs
docker-compose logs -f [service_name]
```

### Configuration
- Copy `.env.example` to `.env` and configure:
  - GCP project, instance, and zone settings
  - GCS bucket names for jobs and outputs
  - API keys for model downloads
  - Service ports (ComfyUI: 8188, Dispatcher: 8187)

### Service URLs
- ComfyUI UI: `http://localhost:8188`
- Dispatcher API: `http://localhost:8187`
- Render endpoint: `POST http://localhost:8187/render`

## GCP Integration

### Required Permissions
- Compute Engine: start/stop instances, manage metadata
- Cloud Storage: read/write to job and output buckets
- Service Account: `/tmp/sa-key.json` mounted in dispatcher container

### Metadata Keys
The dispatcher uses these VM metadata keys:
- `startup-script-url`: Points to the bootstrap script
- `job_workflow`: GCS path to workflow JSON
- `model_uri`: Model download URL (Civitai or GCS)
- `output_bucket`: Target GCS path for results

## File Organization

- `docker-compose.yml`: Multi-service orchestration
- `vps-comfyui/Dockerfile`: CPU-only ComfyUI image
- `job-dispatcher/`: FastAPI dispatcher service
- `startup/bash.sh`: GPU VM bootstrap script
- `tools/`: Legacy helper scripts
- `.env.example`: Configuration template

## Workflow Process

1. User creates workflow in local ComfyUI UI
2. Custom node sends workflow + model URL to dispatcher
3. Dispatcher uploads job data to GCS and starts GPU VM
4. VM bootstraps, downloads model, executes workflow
5. Results uploaded to GCS with completion flag
6. Dispatcher returns signed URLs for generated images
7. VM auto-shuts down to minimize costs