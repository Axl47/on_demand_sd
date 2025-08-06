#!/usr/bin/env bash
# ---------- Persistent ComfyUI with nginx reverse proxy ----------
set -euxo pipefail
logger -t startup-script ">> Persistent ComfyUI GPU worker starting"

# -------- 0. Configuration from metadata -------------------------------
meta() { 
    curl -s -H "Metadata-Flavor: Google" \
        "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1" 2>/dev/null || echo ""
}

# Get configuration from metadata (with defaults)
ALLOWED_IP="$(meta allowed_ip)"
AUTH_USER="$(meta auth_user || echo 'admin')"
AUTH_PASS="$(meta auth_pass || echo 'comfyui123')"
DOMAIN_NAME="$(meta domain_name)"  # Domain for SSL certificate
EMAIL="$(meta ssl_email)"          # Email for Let's Encrypt
CF_CERT_PATH="$(meta cf_cert_path)"  # Path to Cloudflare origin certificate
CF_KEY_PATH="$(meta cf_key_path)"    # Path to Cloudflare origin private key

# -------- 1. Mount persistent disk if available ------------------------
PERSIST_MNT="/mnt/persist"
PERSIST_DISK="/dev/disk/by-id/google-persistent-comfyui"

if [[ -e "$PERSIST_DISK" ]]; then
    logger -t startup-script ">> Mounting persistent disk"
    mkdir -p "$PERSIST_MNT"
    
    # Check if already mounted
    if ! mountpoint -q "$PERSIST_MNT"; then
        # Try to mount, format if needed
        if ! mount "$PERSIST_DISK" "$PERSIST_MNT" 2>/dev/null; then
            logger -t startup-script ">> Formatting new persistent disk"
            mkfs.ext4 -F "$PERSIST_DISK"
            mount "$PERSIST_DISK" "$PERSIST_MNT"
        fi
    fi
else
    logger -t startup-script ">> No persistent disk found, using root disk"
    mkdir -p "$PERSIST_MNT"
fi

# -------- 2. System packages --------------------------------------------
# Clean up any retired APT sources
sed -i '/bullseye-backports/d' /etc/apt/sources.list /etc/apt/sources.list.d/*.list 2>/dev/null || true

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -yq \
    git python3-venv libgl1 wget curl jq nginx apache2-utils supervisor \
    certbot python3-certbot-nginx

# -------- 3. ComfyUI setup ----------------------------------------------
COMFY_DIR="$PERSIST_MNT/ComfyUI"
VENV_DIR="$COMFY_DIR/venv"
MODEL_DIR="$COMFY_DIR/models"

# Clone or update ComfyUI
if [[ -d "$COMFY_DIR/.git" ]]; then
    logger -t startup-script ">> ComfyUI repo exists, pulling latest"
    git -C "$COMFY_DIR" pull --quiet || true
else
    if [[ -d "$COMFY_DIR" ]]; then
        logger -t startup-script ">> Non-git ComfyUI directory exists, backing up"
        mv "$COMFY_DIR" "$COMFY_DIR.backup.$(date +%s)"
    fi
    logger -t startup-script ">> Cloning ComfyUI"
    git clone --depth=1 https://github.com/comfyanonymous/ComfyUI.git "$COMFY_DIR"
fi

# Setup Python environment
if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "$COMFY_DIR/requirements.txt"
pip install --quiet --upgrade comfy-cli

# -------- 4. Install popular ComfyUI extensions ------------------------
CUSTOM_NODES="$COMFY_DIR/custom_nodes"
mkdir -p "$CUSTOM_NODES"

# ComfyUI-Manager for easy model/node management
if [[ ! -d "$CUSTOM_NODES/ComfyUI-Manager" ]]; then
    git clone --depth=1 https://github.com/ltdrdata/ComfyUI-Manager.git \
        "$CUSTOM_NODES/ComfyUI-Manager"
    pip install --quiet -r "$CUSTOM_NODES/ComfyUI-Manager/requirements.txt" || true
fi

# -------- 5. Configure nginx with basic auth ---------------------------
# Create auth file
htpasswd -bc /etc/nginx/.htpasswd "$AUTH_USER" "$AUTH_PASS"

# Configure nginx with SSL support
cat > /etc/nginx/sites-available/comfyui << 'NGINX_CONF'
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

# HTTP server (will redirect to HTTPS if domain is configured)
server {
    listen 80;
    server_name _;
    
    # Health check endpoint (always available via HTTP)
    location /health {
        return 200 "OK\n";
        add_header Content-Type text/plain;
    }
    
    # If domain is configured, redirect to HTTPS, otherwise serve directly
    location / {
        # Allow iframe embedding from frontend (no X-Frame-Options restrictions)
        add_header Access-Control-Allow-Origin "*" always;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Authorization, Content-Type" always;
        
        # Proxy to ComfyUI
        proxy_pass http://127.0.0.1:8188;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
        
        # Large file uploads for models
        client_max_body_size 10G;
    }
}
NGINX_CONF

# Enable site
ln -sf /etc/nginx/sites-available/comfyui /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test and reload nginx
nginx -t
systemctl restart nginx

# -------- 5b. Setup SSL certificate if domain is provided ---------------
if [[ -n "$DOMAIN_NAME" ]]; then
    logger -t startup-script ">> Setting up SSL for domain: $DOMAIN_NAME"
    
    # Update nginx config to use the domain name
    sed -i "s/server_name _;/server_name $DOMAIN_NAME;/" /etc/nginx/sites-available/comfyui
    
    # Check if Cloudflare origin certificates are provided
    if [[ -n "$CF_CERT_PATH" && -n "$CF_KEY_PATH" ]]; then
        logger -t startup-script ">> Using Cloudflare origin certificates"
        
        # Create SSL directory
        mkdir -p /etc/ssl/cloudflare
        
        # Download certificates from metadata or use provided paths
        if [[ "$CF_CERT_PATH" == gs://* ]]; then
            gsutil cp "$CF_CERT_PATH" /etc/ssl/cloudflare/cert.pem
            gsutil cp "$CF_KEY_PATH" /etc/ssl/cloudflare/key.pem
        elif [[ "$CF_CERT_PATH" == http* ]]; then
            wget -q "$CF_CERT_PATH" -O /etc/ssl/cloudflare/cert.pem
            wget -q "$CF_KEY_PATH" -O /etc/ssl/cloudflare/key.pem
        else
            logger -t startup-script ">> Certificate paths should be GCS URLs or HTTP URLs"
            logger -t startup-script ">> Falling back to HTTP only"
            DOMAIN_NAME=""
        fi
        
        if [[ -n "$DOMAIN_NAME" ]]; then
            # Configure nginx for HTTPS with Cloudflare certificates
            cat > /etc/nginx/sites-available/comfyui << 'NGINX_HTTPS_CONF'
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

# HTTP server (redirects to HTTPS)
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;
    
    # Health check endpoint (always available via HTTP)
    location /health {
        return 200 "OK\n";
        add_header Content-Type text/plain;
    }
    
    # Redirect all other traffic to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS server with Cloudflare origin certificate
server {
    listen 443 ssl http2;
    server_name DOMAIN_PLACEHOLDER;
    
    # Cloudflare origin certificate
    ssl_certificate /etc/ssl/cloudflare/cert.pem;
    ssl_certificate_key /etc/ssl/cloudflare/key.pem;
    
    # SSL settings optimized for Cloudflare
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # Security headers - Allow iframe embedding (removed X-Frame-Options for ComfyUI embedding)
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Allow iframe embedding from specific origins
    add_header Access-Control-Allow-Origin "*" always;
    add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Authorization, Content-Type" always;
    
    # Main location block
    location / {
        # Proxy to ComfyUI
        proxy_pass http://127.0.0.1:8188;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
        
        # Large file uploads for models
        client_max_body_size 10G;
    }
}
NGINX_HTTPS_CONF
            
            # Replace placeholder with actual domain
            sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN_NAME/g" /etc/nginx/sites-available/comfyui
            
            logger -t startup-script ">> Cloudflare SSL configuration applied"
        fi
        
    elif [[ -n "$EMAIL" ]]; then
        logger -t startup-script ">> Using Let's Encrypt certificates"
        
        # Add HTTPS redirect for domain requests
        sed -i '/location \/ {/i\
    # Redirect HTTP to HTTPS for domain requests\
    if ($host = '$DOMAIN_NAME') {\
        return 301 https://$server_name$request_uri;\
    }'  /etc/nginx/sites-available/comfyui
        
        # Reload with domain config
        nginx -t && systemctl reload nginx
        
        # Get SSL certificate via Let's Encrypt
        certbot --nginx -d "$DOMAIN_NAME" --email "$EMAIL" --agree-tos --non-interactive --redirect
        
        if [[ $? -eq 0 ]]; then
            logger -t startup-script ">> Let's Encrypt certificate obtained successfully for $DOMAIN_NAME"
        else
            logger -t startup-script ">> Failed to obtain Let's Encrypt certificate, continuing with HTTP"
            # Reset nginx config to HTTP only
            sed -i "s/server_name $DOMAIN_NAME;/server_name _;/" /etc/nginx/sites-available/comfyui
            sed -i '/# Redirect HTTP to HTTPS/,+3d' /etc/nginx/sites-available/comfyui
        fi
    else
        logger -t startup-script ">> Domain provided but no SSL configuration (no email or Cloudflare certs)"
        logger -t startup-script ">> Continuing with HTTP only"
    fi
    
    # Test and reload nginx with final config
    nginx -t && systemctl reload nginx
else
    logger -t startup-script ">> No domain configured, using HTTP only"
fi

# -------- 6. Configure supervisor for ComfyUI --------------------------
cat > /etc/supervisor/conf.d/comfyui.conf << SUPERVISOR_CONF
[program:comfyui]
command=$VENV_DIR/bin/python $COMFY_DIR/main.py --listen 127.0.0.1 --port 8188
directory=$COMFY_DIR
user=root
autostart=true
autorestart=true
stderr_logfile=/var/log/comfyui.err.log
stdout_logfile=/var/log/comfyui.out.log
environment=PATH="$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
SUPERVISOR_CONF

# Start supervisor
systemctl restart supervisor

# -------- 7. Wait for ComfyUI to be ready ------------------------------
logger -t startup-script ">> Waiting for ComfyUI to start..."
for i in {1..60}; do
    if curl -s http://127.0.0.1:8188/ >/dev/null 2>&1; then
        logger -t startup-script ">> ComfyUI is ready!"
        break
    fi
    sleep 2
done

# -------- 8. Configure firewall if IP restriction is set ---------------
if [[ -n "$ALLOWED_IP" ]]; then
    logger -t startup-script ">> Configuring firewall to allow only: $ALLOWED_IP"
    # Install ufw if not present
    apt-get install -yq ufw
    
    # Configure firewall
    ufw --force enable
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow from "$ALLOWED_IP" to any port 80
    ufw allow from "$ALLOWED_IP" to any port 22
    ufw reload
fi

# -------- 9. Setup auto-shutdown cron job ------------------------------
cat > /usr/local/bin/check-activity.sh << 'ACTIVITY_SCRIPT'
#!/bin/bash
# Check for ComfyUI activity and shutdown if idle for 30 minutes

IDLE_THRESHOLD=1800  # 30 minutes in seconds
ACTIVITY_FILE="/tmp/comfyui-activity"
CURRENT_TIME=$(date +%s)

# Create activity file if it doesn't exist
if [[ ! -f "$ACTIVITY_FILE" ]]; then
    echo "$CURRENT_TIME" > "$ACTIVITY_FILE"
fi

# Check if ComfyUI is processing (high CPU usage)
CPU_USAGE=$(top -bn1 | grep python | awk '{print $9}' | cut -d'.' -f1 | head -1)
if [[ -n "$CPU_USAGE" ]] && [[ "$CPU_USAGE" -gt 10 ]]; then
    echo "$CURRENT_TIME" > "$ACTIVITY_FILE"
    exit 0
fi

# Check last activity time
LAST_ACTIVITY=$(cat "$ACTIVITY_FILE")
IDLE_TIME=$((CURRENT_TIME - LAST_ACTIVITY))

if [[ "$IDLE_TIME" -gt "$IDLE_THRESHOLD" ]]; then
    logger -t auto-shutdown "No activity for 30 minutes, shutting down"
    shutdown -h now
fi
ACTIVITY_SCRIPT

chmod +x /usr/local/bin/check-activity.sh

# Add cron job for activity checking (every 5 minutes)
echo "*/5 * * * * /usr/local/bin/check-activity.sh" | crontab -

# -------- 10. Create activity update endpoint --------------------------
cat > /usr/local/bin/update-activity.py << 'ACTIVITY_UPDATE'
#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import time

class ActivityHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/keep-alive':
            with open('/tmp/comfyui-activity', 'w') as f:
                f.write(str(int(time.time())))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logs

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 8189), ActivityHandler)
    server.serve_forever()
ACTIVITY_UPDATE

chmod +x /usr/local/bin/update-activity.py

# Add to supervisor
cat >> /etc/supervisor/conf.d/comfyui.conf << 'SUPERVISOR_APPEND'

[program:activity-tracker]
command=/usr/local/bin/update-activity.py
autostart=true
autorestart=true
stderr_logfile=/var/log/activity.err.log
stdout_logfile=/var/log/activity.out.log
SUPERVISOR_APPEND

systemctl restart supervisor

# -------- 11. Download some popular models if not present --------------
# Only download if models directory is empty
if [[ ! -d "$MODEL_DIR/checkpoints" ]] || [[ -z "$(ls -A $MODEL_DIR/checkpoints 2>/dev/null)" ]]; then
    logger -t startup-script ">> Downloading default SD 1.5 model..."
    mkdir -p "$MODEL_DIR/checkpoints"
    
    # Download SD 1.5 base model (smaller, for testing)
    wget -q --show-progress \
        "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors" \
        -O "$MODEL_DIR/checkpoints/sd_v1.5_pruned.safetensors" || true
fi

logger -t startup-script ">> Persistent ComfyUI setup complete!"
logger -t startup-script ">> Access at http://$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google")"