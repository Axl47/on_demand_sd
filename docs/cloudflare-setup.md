# Cloudflare Configuration for ComfyUI Iframe Embedding

## Problem
Cloudflare automatically adds `X-Frame-Options: SAMEORIGIN` header which blocks iframe embedding.

## Solution Options

### Option 1: Cloudflare Worker (Recommended)
1. Go to Cloudflare Dashboard → Workers & Pages
2. Create new Worker
3. Use the simple worker code from `cloudflare-worker-simple.js`
4. Deploy and add route for `comfy.axorai.net/*`

### Option 2: Transform Rules (Business/Enterprise Plans)
If you have a Business or Enterprise plan:
1. Go to Rules → Transform Rules → Modify Response Header
2. Create new rule:
   - When: `Hostname equals comfy.axorai.net`
   - Then: Remove header `X-Frame-Options`
   - And: Set header `Content-Security-Policy` to `frame-ancestors *;`

### Option 3: Page Rules (Limited)
1. Go to Rules → Page Rules
2. Create rule for `comfy.axorai.net/*`
3. Settings:
   - Security Level: Essentially Off
   - Disable Performance
   - Disable Security

### Option 4: Direct Origin Access
If none of the above work:
1. Create a subdomain that bypasses Cloudflare proxy (grey cloud)
2. Point directly to your GCE instance IP
3. Use that subdomain for iframe embedding

## Testing
After implementing any solution:
1. Clear browser cache
2. Test in incognito/private window
3. Check response headers using browser DevTools
4. Verify `X-Frame-Options` header is removed

## Debugging Connection Timeouts
If you get connection timeouts after adding Worker:
1. Check Worker logs in Cloudflare dashboard
2. Ensure Worker route is properly configured
3. Verify origin server is accessible
4. Try the simple worker version first
5. Check if WebSocket connections are being handled properly