from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import timedelta
import uuid, time, os, json

from google.cloud import storage
from googleapiclient import discovery

app = FastAPI()
gcs      = storage.Client()
compute  = discovery.build("compute", "v1")

# ── static env ───────────────────────────────────────────────
PROJECT          = os.getenv("GCP_PROJECT")
INSTANCE         = os.getenv("GCE_INSTANCE")
ZONE             = os.getenv("GCE_ZONE")
JOB_BUCKET       = os.getenv("JOB_BUCKET")        # e.g. gs://sd-jobs
OUT_BUCKET       = os.getenv("OUT_BUCKET")        # e.g. gs://sd-outputs
STARTUP_URL      = os.getenv("STARTUP_URL")

# ── helpers ──────────────────────────────────────────────────
def signed_url(bucket, name, exp_minutes=20):
    return (
        gcs.bucket(bucket)
        .blob(name)
        .generate_signed_url(version="v4",
                             expiration=timedelta(minutes=exp_minutes),
                             method="GET")
    )

def bucket_and_key(uri: str):
    path = uri.replace("gs://", "")
    parts  = path.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] + "/" if len(parts) == 2 else ""
    return bucket, prefix

def upload_json(bucket_uri: str, blob_name: str, data: dict):
    bucket_name, prefix = bucket_and_key(bucket_uri)
    blob = gcs.bucket(bucket_name).blob(prefix + blob_name)
    blob.upload_from_string(json.dumps(data), content_type="application/json")

def list_blobs(bucket_uri, prefix):
    bucket_name = bucket_uri.replace("gs://", "")
    return gcs.bucket(bucket_name).list_blobs(prefix=prefix)

def push_metadata(items):
    """Set VM metadata with optimistic-locking fingerprint."""
    inst = compute.instances().get(
        project=PROJECT, zone=ZONE, instance=INSTANCE
    ).execute()
    fp = inst["metadata"]["fingerprint"]
    body = {"fingerprint": fp, "items": items}

    op = compute.instances().setMetadata(
        project=PROJECT, zone=ZONE, instance=INSTANCE, body=body
    ).execute()

    # Simple wait loop until the set-metadata operation is DONE
    while True:
        result = compute.zoneOperations().get(
            project=PROJECT, zone=ZONE, operation=op["name"]
        ).execute()
        if result.get("status") == "DONE":
            if "error" in result:
                raise RuntimeError(result["error"])
            break
        time.sleep(1)

# ── request schema ───────────────────────────────────────────
class RenderRequest(BaseModel):
    prompt: str
    model_url: str   # civitai or gs://…
    sampler: str = "euler"
    steps:   int = 30

# ── main endpoint ────────────────────────────────────────────
@app.post("/render")
def render(req: RenderRequest):
    job_id      = str(uuid.uuid4())
    job_prefix  = f"{job_id}/"
    job_json    = f"{job_id}.json"

    # 1) build & upload workflow JSON
    workflow = {
        "prompt": req.prompt,
        "sampler": req.sampler,
        "steps":   req.steps,
        "client_id": job_id,
        "output_path": "/tmp/comfy-out"
    }
    upload_json(JOB_BUCKET, job_json, workflow)

    # 2) set per-boot metadata
    items = [
        {"key": "startup-script-url", "value": STARTUP_URL},
        {"key": "job_workflow",  "value": f"{JOB_BUCKET}/{job_json}"},
        {"key": "model_uri",     "value": req.model_url},
        {"key": "output_bucket", "value": f"{OUT_BUCKET}/{job_prefix}"}
    ]
    push_metadata(items)

    # 3) start the GPU VM (no body!)
    compute.instances().start(
        project=PROJECT, zone=ZONE, instance=INSTANCE
    ).execute()

    # 4) wait for DONE.flag
    flag_blob = gcs.bucket(OUT_BUCKET.replace("gs://", "")).blob(f"{job_prefix}DONE.flag")
    while not flag_blob.exists():
        time.sleep(5)

    # 5) collect PNG/JPG URLs (signed, 20-min expiry)
    bucket_name = OUT_BUCKET.replace("gs://", "")
    files = [
        signed_url(bucket_name, b.name)
        for b in list_blobs(OUT_BUCKET, prefix=job_prefix)
        if b.name.endswith((".png", ".jpg"))
    ]

    if not files:
        raise HTTPException(500, "No images produced")

    return {"job_id": job_id, "files": files}
