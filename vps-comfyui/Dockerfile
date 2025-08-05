# ─────────────────────────────────────────────────────────────
# CPU-only ComfyUI front-end for the VPS
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

# 1. Basic build tools + runtime libs
RUN apt-get update -qq && \
  apt-get install -y --no-install-recommends \
  git build-essential libgl1 libglib2.0-0 ffmpeg curl && \
  rm -rf /var/lib/apt/lists/*

# 2. Latest CPU-only PyTorch stack (auto-selects compatible versions)
RUN pip install --no-cache-dir \
  torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cpu   # official CPU index :contentReference[oaicite:3]{index=3}

# 3. Clone ComfyUI and install its Python deps
ENV COMFY_HOME=/opt/ComfyUI
RUN git clone --depth=1 https://github.com/comfyanonymous/ComfyUI.git "$COMFY_HOME"
WORKDIR $COMFY_HOME
RUN pip install --no-cache-dir -r requirements.txt    # pulls OpenCV ≥4.11 automatically :contentReference[oaicite:4]{index=4}

# 4. Disable CUDA; run on port 8188
ENV COMFYUI_DISABLE_CUDA=1
EXPOSE 8188
CMD ["python", "main.py", \
  "--cpu", \
  "--listen", "0.0.0.0", \
  "--port", "8188", \
  "--dont-print-server"]
