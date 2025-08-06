# Migration Guide: From Dual-ComfyUI to Single Instance

This guide helps you migrate from the current dual-ComfyUI setup to the new single-instance architecture.

## Architecture Changes

### Before (Current)

- Local CPU ComfyUI for workflow creation
- Custom dispatch node sends jobs to dispatcher
- Dispatcher spins up GPU instance per job
- GPU instance runs workflow and shuts down

### After (New)

- Single ComfyUI instance on GCE with persistent disk
- Frontend with iframe embedding and auth
- Instance manager controls start/stop
- Direct interaction with GPU-enabled ComfyUI

## Migration Steps

### 1. Upload New Startup Script

Upload the new startup script to GCS:

```bash
gsutil cp startup/persistent-comfyui.sh gs://your-bucket/persistent-comfyui.sh
gsutil acl ch -u AllUsers:R gs://your-bucket/persistent-comfyui.sh
```

### 2. Create/Update GCE Instance

If creating new instance:

```bash
gcloud compute instances create comfyui-gpu \
  --zone=us-central1-a \
  --machine-type=n1-standard-4 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --maintenance-policy=TERMINATE \
  --image-family=deep-learning-vm \
  --image-project=deeplearning-platform-release \
  --boot-disk-size=50GB \
  --metadata startup-script-url=https://storage.googleapis.com/your-bucket/persistent-comfyui.sh
```

Add persistent disk for models (optional but recommended):

```bash
gcloud compute disks create comfyui-models \
  --size=100GB \
  --zone=us-central1-a \
  --type=pd-standard

gcloud compute instances attach-disk comfyui-gpu \
  --disk=comfyui-models \
  --zone=us-central1-a \
  --device-name=persistent-comfyui
```

### 3. Configure Environment

Copy and update the environment file:

```bash
cp .env.new.example .env
# Edit .env with your values
```

Key configurations:

- `GCP_PROJECT`: Your GCP project ID
- `GCE_INSTANCE`: Name of your ComfyUI instance
- `STARTUP_SCRIPT_URL`: GCS URL of persistent-comfyui.sh
- `ALLOWED_IP`: Your Dokploy server's external IP
- `AUTH_PASSWORD`: Secure password for frontend access

### 4. Deploy with Docker Compose

Stop old services:

```bash
docker-compose down
```

Start new services:

```bash
docker-compose -f docker-compose.new.yml up -d
```

### 5. Access the Frontend

1. Navigate to `https://image.axorai.net` (or your configured domain)
2. Login with your configured password
3. Click "Start Instance" to boot up ComfyUI
4. Wait for instance to be ready (1-2 minutes)
5. ComfyUI will appear in the iframe

## Features

### Auto-shutdown

- Instance auto-stops after 30 minutes of inactivity
- Activity is tracked by:
  - Frontend keep-alive pings (every 30s when open)
  - ComfyUI processing activity (CPU usage > 10%)

### Persistent Storage

- Models stored on persistent disk (survives stop/start)
- Workflows saved in ComfyUI
- Custom nodes preserved

### Security

- Frontend authentication (JWT-based)
- ComfyUI nginx basic auth (additional layer)
- Optional IP restriction via firewall
- HTTPS through Dokploy reverse proxy

## Rollback Plan

If you need to rollback:

1. Keep old docker-compose.yml and related files
2. Stop new services: `docker-compose -f docker-compose.new.yml down`
3. Start old services: `docker-compose up -d`
4. Old workflow dispatching will resume

## Troubleshooting

### Instance won't start

- Check GCP quotas (GPU availability)
- Verify service account permissions
- Check dispatcher logs: `docker logs comfyui-dispatcher`

### Can't access ComfyUI

- Verify instance is RUNNING in frontend
- Check firewall rules allow your IP
- Verify nginx is running: SSH to instance and run `systemctl status nginx`

### Models missing

- Models download on first boot if not present
- Check persistent disk is mounted: `df -h | grep persist`
- Manually upload models to `/mnt/persist/ComfyUI/models/`

### Auto-shutdown not working

- Check cron job: `crontab -l` on instance
- Verify activity tracking: `cat /tmp/comfyui-activity`
- Frontend must be open to send keep-alive

## Benefits of New Architecture

1. **Simplicity**: Single ComfyUI instance, no synchronization
2. **Compatibility**: All workflows work without modification
3. **Cost-efficient**: Auto start/stop based on usage
4. **User-friendly**: Direct UI access, real-time feedback
5. **Maintainable**: Fewer moving parts, easier debugging
