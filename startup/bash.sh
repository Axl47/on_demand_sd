#! /usr/bin/env bash
# ---------- ComfyUI Spot-GPU worker (persistent-disk edition) ----------
set -euxo pipefail
logger -t startup-script ">> ComfyUI GPU worker booting"

# -------- 0. Read job-specific metadata --------------------------------
meta() { curl -s -H "Metadata-Flavor: Google" \
        "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1" ; }

JOB_JSON_GCS="$(meta job_workflow)"      # gs://…/job.json
MODEL_URI="$(meta model_uri)"            # gs://…/model.safetensors  OR  https://civitai.com/…
OUT_BUCKET="$(meta output_bucket)"       # gs://…/outputs/job-id/

# -------- 0b. Mount persistent SSD -------------------------------------
PERSIST_DEV="/dev/disk/by-id/google-$(meta persist_disk_id)"
PERSIST_MNT="/mnt/persist"

if ! mountpoint -q "$PERSIST_MNT"; then
  mkdir -p "$PERSIST_MNT"
  # format only if brand-new
  if ! blkid "$PERSIST_DEV" >/dev/null 2>&1; then
    mkfs.ext4 -F "$PERSIST_DEV"
  fi
  mount "$PERSIST_DEV" "$PERSIST_MNT"
fi

# -------- 1. System packages (CUDA & PyTorch already on image) ---------
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -yq git python3-venv libgl1 wget curl jq

# -------- 2. Directories on the SSD -----------------------------------
COMFY_DIR="$PERSIST_MNT/ComfyUI"
VENV_DIR="$COMFY_DIR/venv"
MODEL_DEST="$COMFY_DIR/models/checkpoints"

mkdir -p "$MODEL_DEST"

# -------- 3. Clone / update ComfyUI & comfy-cli ------------------------
if [[ ! -d "$COMFY_DIR/.git" ]]; then
  git clone --depth=1 https://github.com/comfyanonymous/ComfyUI.git "$COMFY_DIR"
else
  git -C "$COMFY_DIR" pull --quiet
fi

pip3 install --quiet --upgrade comfy-cli   # tiny helper wrapper

# -------- 4. Python venv (reuse if already built) ----------------------
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
  source "$VENV_DIR/bin/activate"
  pip install --quiet -r "$COMFY_DIR/requirements.txt"
else
  source "$VENV_DIR/bin/activate"
fi

# -------- 5. Fetch workflow & checkpoint ------------------------------
WORKFLOW_JSON=/tmp/workflow.json
gsutil cp "$JOB_JSON_GCS" "$WORKFLOW_JSON"

if [[ "$MODEL_URI" == https://civitai.com/* ]]; then
  # keep original filename, skip if exists
  wget -q -nc -L --content-disposition "$MODEL_URI" -P "$MODEL_DEST"
else
  # Cloud-Storage object; -n = no-clobber
  gsutil -q -m cp -n "$MODEL_URI" "$MODEL_DEST"/
fi

# -------- 6. Launch ComfyUI silently in background --------------------
cd "$COMFY_DIR"
comfy launch --background -- \
  --listen 0.0.0.0 --port 8188 --dont-print-server &
SERVER_PID=$!
sleep 5   # give Tornado time to bind

# -------- 7. Submit workflow via /prompt API --------------------------
export WORKFLOW_JSON   # make visible to Python

python3 - <<'PY'
import json, os, time, uuid, requests, pathlib

WF        = pathlib.Path(os.environ["WORKFLOW_JSON"])
OUT_DIR   = pathlib.Path("/tmp/comfy-out")
OUT_DIR.mkdir(parents=True, exist_ok=True)

payload = json.load(WF.open())
payload.setdefault("client_id", str(uuid.uuid4()))
payload.setdefault("output_path", str(OUT_DIR))

r = requests.post("http://127.0.0.1:8188/prompt", json=payload, timeout=300)
r.raise_for_status()
pid = r.json()["prompt_id"]
status_url = f"http://127.0.0.1:8188/history/{pid}"

while True:
    status = requests.get(status_url, timeout=120).json()
    if status.get("status") == "done":
        break
    time.sleep(5)
PY

# -------- 8. Push results to Cloud Storage ----------------------------
gsutil -m cp -r /tmp/comfy-out/* "$OUT_BUCKET"

# -------- 9. Clean shutdown ------------------------------------------
logger -t startup-script ">> Job done – shutting down"

touch /tmp/comfy-out/DONE.flag
gsutil cp /tmp/comfy-out/DONE.flag "$OUT_BUCKET"/

shutdown -h now
