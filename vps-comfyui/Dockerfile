FROM python:3.10-slim

# ---- system deps ----
RUN apt-get update -qq && \
  apt-get install -y --no-install-recommends git libgl1 && \
  rm -rf /var/lib/apt/lists/*

# ---- install ComfyUI + comfy-cli ----
RUN pip install --no-cache-dir \
  comfy-cli==1.4.1 \
  torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
  --index-url https://download.pytorch.org/whl/cpu \
  && comfy install

# ---- runtime config ----
WORKDIR /root/.cache/comfyui/ComfyUI
ENV COMFYUI_DISABLE_CUDA=1

EXPOSE 8188
CMD ["comfy", "launch", \
  "--listen", "0.0.0.0", \
  "--port", "8188", \
  "--dont-print-server", \
  "--background", \
  "--device", "cpu"]

