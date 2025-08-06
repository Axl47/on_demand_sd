#!/bin/bash
# Debug script to manually check ComfyUI on the GCE instance
# SSH into your instance and run this script

echo "=== ComfyUI Debug Script ==="
echo ""

echo "1. Checking supervisor status:"
supervisorctl status

echo ""
echo "2. Checking ComfyUI error logs (last 50 lines):"
tail -n 50 /var/log/comfyui.err.log

echo ""
echo "3. Checking ComfyUI output logs (last 50 lines):"
tail -n 50 /var/log/comfyui.out.log

echo ""
echo "4. Checking Python and venv:"
/mnt/persist/ComfyUI/venv/bin/python --version
ls -la /mnt/persist/ComfyUI/venv/bin/

echo ""
echo "5. Testing direct ComfyUI start:"
cd /mnt/persist/ComfyUI
timeout 5 /mnt/persist/ComfyUI/venv/bin/python main.py --listen 127.0.0.1 --port 8188 2>&1 | head -20

echo ""
echo "6. Checking GPU availability:"
nvidia-smi

echo ""
echo "7. Checking memory:"
free -h

echo ""
echo "8. Checking disk space:"
df -h /mnt/persist

echo ""
echo "9. Checking nginx status:"
systemctl status nginx --no-pager

echo ""
echo "10. Testing local connectivity:"
curl -I http://127.0.0.1:8188/

echo ""
echo "11. Checking firewall rules:"
ufw status numbered

echo "=== End Debug Script ==="