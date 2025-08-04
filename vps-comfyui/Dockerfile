# ───────────────────────────────────────────────────────
# Minimal CPU-only ComfyUI image (800-900 MB)
# ───────────────────────────────────────────────────────
FROM --platform=linux/amd64 python:3.10-slim

# --- system packages needed at *build* time -------------
RUN apt-get update -qq && \
  apt-get install -y --no-install-recommends \
  git build-essential libgl1 libglib2.0-0 ffmpeg && \
  rm -rf /var/lib/apt/lists/*

# --- Python deps: CPU wheels only ------------------------
RUN pip install --no-cache-dir \
  torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
  --index-url https://download.pytorch.org/whl/cpu && \
  pip install --no-cache-dir \
  numpy==1.26.4 pillow==10.3.0 \
  opencv-python-headless==4.10.0.86 \
  scikit-image==0.23.2 \
  einops==0.8.0

# --- clone ComfyUI & install its requirements -----------
ENV COMFY_HOME=/opt/ComfyUI
RUN git clone --depth=1 https://github.com/comfyanonymous/ComfyUI.git "$COMFY_HOME"
WORKDIR $COMFY_HOME
RUN pip install --no-cache-dir -r requirements.txt \
  && pip cache purge

# --- runtime --------------------------------------------
ENV COMFYUI_DISABLE_CUDA=1
EXPOSE 8188
CMD ["python", "main.py", \
  "--device", "cpu", \
  "--listen", "0.0.0.0", \
  "--port", "8188", \
  "--dont-print-server"]
