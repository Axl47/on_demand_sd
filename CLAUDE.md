# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is an on-demand ComfyUI system with web-based control and embedded GPU-accelerated ComfyUI interface:

- **Next.js Frontend** (`frontend/`): Web interface with authentication and embedded ComfyUI iframe
- **Instance Manager** (`job-dispatcher/instance_manager.py`): FastAPI service that manages GCE GPU instance lifecycle
- **Persistent ComfyUI** (`startup/persistent-comfyui.sh`): GPU VM setup with persistent disk and nginx SSL proxy
- **Docker Stack**: Containerized frontend and instance manager with proper networking

## Key Components

### Frontend (`frontend/`)
- **Authentication**: JWT-based with localStorage (cookie-free for proxy compatibility)
- **Instance Control**: Start/stop GCE instances with real-time status monitoring
- **ComfyUI Embedding**: Direct iframe access to GPU-accelerated ComfyUI
- **Auto-shutdown**: Keep-alive mechanism prevents idle resource waste
- **Technology Stack**: Next.js 14, TypeScript, TailwindCSS, Axios

### Instance Manager (`job-dispatcher/instance_manager.py`)
- **GCE Lifecycle**: Start/stop GPU instances with proper error handling
- **Status Monitoring**: Real-time instance status and external IP detection
- **SSL Support**: Automatic HTTPS URL generation when domain is configured
- **Activity Tracking**: Keep-alive endpoint for usage-based shutdown
- **Error Handling**: User-friendly messages for GPU quota/availability issues

### Persistent ComfyUI Setup (`startup/persistent-comfyui.sh`)
- **Persistent Storage**: Models and configurations survive stop/start cycles
- **SSL/HTTPS Support**: Automatic Let's Encrypt certificate management
- **Nginx Proxy**: HTTPS termination, CORS headers for iframe compatibility
- **Supervisor Management**: ComfyUI runs as supervised service with auto-restart
- **Activity Monitoring**: Auto-shutdown after 30 minutes of inactivity
- **Security**: Firewall rules and optional IP-based access control

## Development Commands

### Local Development
```bash
# Start all services (Frontend + Instance Manager)
docker-compose up -d

# Build specific services
docker-compose build frontend
docker-compose build dispatcher

# View logs
docker-compose logs -f frontend
docker-compose logs -f comfyui-dispatcher

# Development with hot reload
cd frontend && npm run dev
```

### Configuration
- Copy `.env.new.example` to `.env` and configure:
  - GCP project, instance, and zone settings
  - Frontend authentication password
  - SSL domain and email for HTTPS (optional)
  - Instance manager settings

### Service URLs
- Frontend UI: `https://image.axorai.net` (or configured domain)
- Instance Manager API: `http://localhost:8187`
- GCE ComfyUI: `https://comfy.yourdomain.com` or `http://external-ip`

## GCP Integration

### Required Permissions
- Compute Engine: start/stop instances, manage metadata, network access
- Service Account: `/tmp/sa-key.json` mounted in dispatcher container
- Firewall Rules: Allow HTTP/HTTPS to GCE instances

### Instance Metadata
The instance manager configures these VM metadata keys:
- `startup-script-url`: Points to the persistent ComfyUI setup script
- `domain_name`: Domain for SSL certificate (optional)
- `ssl_email`: Let's Encrypt email for certificate (optional)
- `allowed_ip`: IP address allowed through firewall (optional)
- `auth_user`/`auth_pass`: Basic auth credentials (legacy)

### GPU Instance Requirements
- **Machine Type**: n1-standard-4 or similar with GPU attachment
- **GPU**: nvidia-tesla-t4 (or other supported GPU)
- **Persistent Disk**: Optional but recommended for model storage
- **Network**: External IP with HTTP/HTTPS firewall rules
- **Image**: Deep Learning VM or Ubuntu with CUDA drivers

## File Organization

- `frontend/`: Next.js web application with authentication and controls
- `job-dispatcher/instance_manager.py`: GCE instance lifecycle management
- `startup/persistent-comfyui.sh`: GPU VM setup script with SSL support
- `docker-compose.yml`: Production container orchestration
- `MIGRATION.md`: Guide for migrating from legacy dual-ComfyUI setup
- `.env.new.example`: Environment configuration template

## Current Workflow

1. **User Authentication**: Login to frontend with password-based JWT auth
2. **Instance Control**: Start GCE instance via web interface
3. **Automatic Setup**: VM boots with ComfyUI, nginx SSL proxy, and persistent storage
4. **Direct Access**: Frontend embeds ComfyUI via HTTPS iframe
5. **Usage Monitoring**: Keep-alive signals prevent premature shutdown
6. **Cost Control**: Instance auto-stops after 30 minutes of inactivity

## Authentication System

### Frontend Authentication
- **Method**: JWT tokens stored in localStorage (bypasses cookie proxy issues)
- **API Headers**: Uses `x-auth-token` header for authenticated requests
- **Dual Support**: `checkAuthFlex()` supports both header and cookie methods
- **Session Length**: 24-hour token expiry with secure logout

### ComfyUI Access
- **SSL/HTTPS**: Automatic Let's Encrypt certificate when domain configured
- **Iframe Compatible**: No basic auth to prevent browser blocking
- **Network Security**: Optional IP-based firewall restrictions
- **Mixed Content**: HTTPS frontend requires HTTPS ComfyUI for security

## Environment Variables

### Frontend Configuration
- `AUTH_PASSWORD`: Frontend login password
- `JWT_SECRET`: Token signing secret
- `DISPATCHER_URL`: Instance manager endpoint (auto-configured in containers)

### Instance Manager Configuration  
- `GCP_PROJECT`: Google Cloud project ID
- `GCE_INSTANCE`: Name of ComfyUI GPU instance
- `GCE_ZONE`: GCP zone for instance deployment
- `STARTUP_SCRIPT_URL`: GCS URL of setup script
- `COMFYUI_DOMAIN`: Domain for SSL certificate (optional)
- `SSL_EMAIL`: Let's Encrypt registration email (optional)
- `ALLOWED_IP`: IP address for firewall restriction (optional)

## Troubleshooting

### Common Issues
- **Mixed Content**: Ensure ComfyUI uses HTTPS when frontend is HTTPS
- **GPU Quota**: Handle `ZONE_RESOURCE_POOL_EXHAUSTED` errors gracefully
- **SSL Issues**: Verify domain DNS points to instance IP for certificate generation
- **Auth Failures**: Check JWT token storage and header transmission
- **Network**: Confirm firewall rules allow HTTP/HTTPS access to instances

### Development Tips
- Use browser dev tools to monitor auth token and iframe loading
- Check instance manager logs for GCP API errors
- Monitor GCE instance logs during startup for script execution
- Test direct ComfyUI access before troubleshooting iframe issues
- Verify SSL certificate status with `curl -I https://domain.com`