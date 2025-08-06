# Migration Guide: GCE to Runpod

## Overview
This guide helps you migrate from Google Cloud Engine (GCE) to Runpod for hosting your ComfyUI instance.

## Key Changes

### 1. Infrastructure Provider
- **Before**: Google Cloud Compute Engine with GPU instances
- **After**: Runpod GPU cloud platform with on-demand pods

### 2. Cost Benefits
- **L40S GPU**: Better performance than T4 at competitive pricing
- **No idle charges**: Only pay when the pod is running
- **Simplified billing**: No complex GCP quota management

### 3. Access Method
- **Before**: Direct IP or custom domain pointing to GCE instance
- **After**: Runpod proxy URLs (format: `https://{pod-id}-8188.proxy.runpod.net`)

## Migration Steps

### Step 1: Set up Runpod Account
1. Create an account at [runpod.io](https://runpod.io)
2. Add billing information
3. Generate an API key from your account settings

### Step 2: Create ComfyUI Pod (Optional)
You can either:
- Use an existing pod ID
- Create a pod manually in Runpod dashboard
- Let the system create one using a template

If creating manually:
1. Go to Pods → Deploy
2. Select GPU type (L40S recommended)
3. Choose ComfyUI template or custom Docker image
4. Configure storage (100GB+ recommended)
5. Note the Pod ID for configuration

### Step 3: Configure Environment
1. Copy the Runpod environment template:
   ```bash
   cp .env.runpod.example .env
   ```

2. Edit `.env` with your settings:
   ```env
   # Required
   RUNPOD_API_KEY=your-runpod-api-key
   
   # Optional - if you have an existing pod
   RUNPOD_POD_ID=your-pod-id
   
   # Optional - for automatic pod creation
   RUNPOD_TEMPLATE_ID=your-template-id
   RUNPOD_GPU_TYPE=NVIDIA L40S
   RUNPOD_DISK_SIZE=100
   ```

### Step 4: Deploy with Docker Compose
1. Stop the old GCE-based system:
   ```bash
   docker-compose down
   ```

2. Start the Runpod-based system:
   ```bash
   docker-compose -f docker-compose.runpod.yml up -d
   ```

3. Check logs:
   ```bash
   docker-compose -f docker-compose.runpod.yml logs -f
   ```

### Step 5: Test the System
1. Access the frontend at `http://localhost:3000`
2. Log in with your configured password
3. Click "Start Instance" to start the Runpod pod
4. Wait for the pod to be RUNNING
5. The ComfyUI interface should appear in the iframe

## URL Structure

### Runpod Proxy URLs
When your pod is running, ComfyUI is accessible via:
- **Direct Proxy**: `https://{pod-id}-8188.proxy.runpod.net`
- **Custom Domain**: Configure your own domain with Runpod (optional)

The frontend automatically constructs the correct URL based on the pod ID.

## Troubleshooting

### Pod Won't Start
- Check your Runpod account has sufficient credits
- Verify the GPU type is available in your selected region
- Check API key permissions

### ComfyUI Not Accessible
- Ensure port 8188 is exposed in your pod configuration
- Check that ComfyUI is running inside the pod
- Verify the proxy URL is correctly formed

### Authentication Issues
- Frontend authentication remains unchanged
- Runpod API key must be valid and have pod management permissions

## API Compatibility

The instance manager API remains the same:
- `GET /status` - Get pod status
- `POST /start` - Start/resume pod
- `POST /stop` - Stop pod (preserves data)
- `POST /keep-alive` - Reset activity timer
- `POST /terminate` - Delete pod (use with caution)

## Data Persistence

### With Network Volume
- Attach a Runpod network volume to preserve data
- Data in `/workspace` persists across stop/start cycles
- Models and outputs are retained

### Without Network Volume
- Data is lost when pod is stopped
- Use persistent disk or external storage for important data

## Cost Optimization

1. **Auto-stop**: Pods automatically stop after 30 minutes of inactivity
2. **Spot Instances**: Use community cloud for cheaper rates
3. **Right-sizing**: Choose appropriate GPU for your workloads
4. **Volume Management**: Use network volumes only when needed

## Rollback Plan

If you need to switch back to GCE:
1. Keep your GCE configuration files (`.env.new.example`, original `docker-compose.yml`)
2. Stop Runpod system: `docker-compose -f docker-compose.runpod.yml down`
3. Restore GCE configuration: `cp .env.gce.backup .env`
4. Start GCE system: `docker-compose up -d`

## Support

For Runpod-specific issues:
- [Runpod Documentation](https://docs.runpod.io)
- [Runpod Discord](https://discord.gg/runpod)
- [API Reference](https://docs.runpod.io/api)