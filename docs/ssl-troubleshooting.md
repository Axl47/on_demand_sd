# SSL and Cloudflare Issues Troubleshooting

## Current Issues

### 1. Firewall Blocking Cloudflare IPs
- **Problem**: GCE instance firewall only allows `192.227.175.143` but Cloudflare uses `24.50.240.250`
- **Solution**: Updated startup script to automatically allow Cloudflare IP ranges for HTTPS traffic

### 2. SSL Certificate Verification Fails
```
curl: (60) SSL certificate problem: unable to get local issuer certificate
```
- **Cause**: Cloudflare origin certificates are only valid when traffic comes through Cloudflare proxy
- **Current Status**: `comfy.axorai.net` DNS is in grey-cloud mode (proxy disabled)

## Solutions

### Option A: Enable Cloudflare Proxy (Recommended)
1. **Enable orange cloud** for `comfy.axorai.net` in Cloudflare DNS
2. **Remove the Worker** that strips X-Frame-Options (no longer needed)
3. **Keep current startup script** - it will work with Cloudflare origin certificates

**Pros**: 
- SSL certificates work correctly
- DDoS protection and CDN benefits
- Automatic firewall allowlist for Cloudflare IPs

**Cons**: 
- X-Frame-Options header will block iframe (need alternative solution)

### Option B: Switch to Let's Encrypt
1. **Keep grey cloud** (proxy disabled)
2. **Update GCE metadata** to remove Cloudflare certificate paths:
   ```bash
   CF_CERT_PATH=""
   CF_KEY_PATH=""
   SSL_EMAIL="your-email@domain.com"
   ```
3. **Restart instance** to get Let's Encrypt certificate

**Pros**: 
- Direct SSL without Cloudflare interference
- No X-Frame-Options blocking iframe

**Cons**: 
- No Cloudflare protection
- Need to manage certificate renewals

### Option C: Disable SSL (HTTP Only)
1. **Remove domain metadata**: Set `COMFYUI_DOMAIN=""`
2. **Access via HTTP**: Use `http://34.55.81.124` or `http://comfy.axorai.net`
3. **Update frontend** to use HTTP URL for iframe

**Pros**: 
- No certificate issues
- No X-Frame-Options blocking

**Cons**: 
- Unencrypted traffic
- Mixed content warnings if frontend uses HTTPS

## Firewall Updates

The startup script now supports:
- **Multiple IPs**: `ALLOWED_IP="192.227.175.143,24.50.240.250"`
- **CIDR blocks**: `ALLOWED_IP="192.227.175.0/24"`
- **Automatic Cloudflare ranges**: Added when using Cloudflare origin certificates

## Testing Commands

```bash
# Test from your VPS
curl -I https://comfy.axorai.net

# Test direct IP access
curl -I http://34.55.81.124

# Check firewall rules on GCE instance
sudo ufw status numbered
```

## Recommended Next Steps

1. **Choose Option A** (enable Cloudflare proxy) for best security
2. **Update environment variables** in Dokploy to remove Worker route
3. **Test iframe embedding** - may need to find alternative to X-Frame-Options bypass