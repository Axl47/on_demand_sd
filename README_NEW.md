# ComfyUI Cloud Controller

A streamlined solution for running ComfyUI on Google Cloud with on-demand GPU instances.

## Overview

This system provides a web-based controller for ComfyUI running on Google Cloud Compute Engine. It features:
- 🚀 On-demand GPU instance management (start/stop)
- 🔐 Secure authentication and access control
- 💾 Persistent model storage
- ⏱️ Auto-shutdown on inactivity (30 minutes)
- 🖼️ Direct ComfyUI access via embedded iframe
- 💰 Cost-efficient pay-per-use model

## Architecture

```
┌─────────────────┐
│   Browser       │
│  (Frontend)     │
└────────┬────────┘
         │ HTTPS
         ▼
┌─────────────────┐
│  Dokploy VPS    │
│  ┌───────────┐  │
│  │ Next.js   │  │
│  │ Frontend  │  │
│  └─────┬─────┘  │
│        │        │
│  ┌─────▼─────┐  │
│  │ Instance  │  │
│  │ Manager   │  │
│  └─────┬─────┘  │
└────────┼────────┘
         │ GCP API
         ▼
┌─────────────────┐
│   GCE Instance  │
│   (GPU + ComfyUI)│
│   with nginx    │
└─────────────────┘
```

## Quick Start

### Prerequisites

- Google Cloud Platform account with billing enabled
- GCE API enabled and GPU quota
- Docker and Docker Compose installed
- Domain configured (for Dokploy deployment)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/on-demand-sd.git
cd on-demand-sd
```

2. **Configure environment**
```bash
cp .env.new.example .env
# Edit .env with your GCP credentials and preferences
```

3. **Upload startup script to GCS**
```bash
gsutil cp startup/persistent-comfyui.sh gs://your-bucket/
gsutil acl ch -u AllUsers:R gs://your-bucket/persistent-comfyui.sh
```

4. **Create GCE instance**
```bash
# See MIGRATION.md for detailed instance creation commands
```

5. **Deploy with Docker Compose**
```bash
docker-compose -f docker-compose.new.yml up -d
```

6. **Access the application**
- Navigate to your configured domain
- Login with your password
- Start the ComfyUI instance
- Begin creating!

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTH_PASSWORD` | Frontend login password | comfyui123 |
| `GCP_PROJECT` | Your GCP project ID | - |
| `GCE_INSTANCE` | Name of ComfyUI instance | comfyui-gpu |
| `GCE_ZONE` | GCP zone for instance | us-central1-a |
| `ALLOWED_IP` | IP allowed to access ComfyUI | Your server IP |

### Instance Configuration

The GCE instance runs:
- Ubuntu/Debian with NVIDIA drivers
- ComfyUI with ComfyUI-Manager
- Nginx reverse proxy with basic auth
- Automatic model downloading
- Persistent disk for model storage

## Usage

### Starting ComfyUI

1. Login to the frontend
2. Click "Start Instance"
3. Wait 1-2 minutes for boot
4. ComfyUI appears in iframe

### Stopping ComfyUI

- Click "Stop Instance" button
- Or wait 30 minutes for auto-shutdown

### Managing Models

Models are stored on persistent disk at `/mnt/persist/ComfyUI/models/`

Upload models via:
- ComfyUI-Manager in the UI
- Direct upload to GCE instance
- Pre-configured in startup script

## Security

- **Frontend**: JWT-based authentication
- **ComfyUI**: Nginx basic auth
- **Network**: Optional IP whitelisting
- **Transport**: HTTPS via reverse proxy

## Cost Optimization

- Instance auto-stops after 30 minutes idle
- Persistent disk preserves models between sessions
- Use preemptible instances for additional savings
- Monitor usage in GCP Console

## Troubleshooting

See [MIGRATION.md](MIGRATION.md#troubleshooting) for common issues and solutions.

## Development

### Local Development
```bash
# Frontend
cd frontend
npm install
npm run dev

# Instance Manager
cd job-dispatcher
pip install -r requirements.txt
python instance_manager.py
```

### Building Images
```bash
# Frontend
docker build -t comfyui-frontend ./frontend

# Full stack
docker-compose -f docker-compose.new.yml build
```

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or contributions, please open an issue on GitHub.