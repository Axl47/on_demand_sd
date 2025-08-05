# dispatcher/main.py  –  expects payload:
# { "workflow": { …full graph… }, "model_url": "https://civitai.com/api/download/models/…" }

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import timedelta
import uuid, time, os, json

from google.cloud import storage
from googleapiclient import discovery

app      = FastAPI()
gcs      = storage.Client()
compute  = discovery.build("compute", "v1")

# ── static env ───────────────────────────────────────────────
PROJECT     = os.getenv("GCP_PROJECT")
INSTANCE    = os.getenv("GCE_INSTANCE")
ZONE        = os.getenv("GCE_ZONE")
JOB_BUCKET  = os.getenv("JOB_BUCKET")        # gs://sd-jobs
OUT_BUCKET  = os.getenv("OUT_BUCKET")        # gs://sd-outputs
STARTUP_URL = os.getenv("STARTUP_URL")       # public URL of boot.sh

# ── helpers ──────────────────────────────────────────────────
def signed_url(bucket, name, exp_minutes=20):
    return (gcs.bucket(bucket)
            .blob(name)
            .generate_signed_url(version="v4",
                                 expiration=timedelta(minutes=exp_minutes),
                                 method="GET"))

def bucket_and_key(uri: str):
    path   = uri.replace("gs://", "")
    bucket, *rest = path.split("/", 1)
    prefix = rest[0] + "/" if rest else ""
    return bucket, prefix

def upload_json(bucket_uri: str, blob_name: str, data: dict):
    bucket_name, prefix = bucket_and_key(bucket_uri)
    gcs.bucket(bucket_name) \
       .blob(prefix + blob_name) \
       .upload_from_string(json.dumps(data),
                           content_type="application/json")

def list_blobs(bucket_uri, prefix):
    bucket_name = bucket_uri.replace("gs://", "")
    return gcs.bucket(bucket_name).list_blobs(prefix=prefix)

def push_metadata(items):
    """Overwrite *all* VM metadata items in one optimistic-locking call."""
    inst = compute.instances().get(project=PROJECT,
                                   zone=ZONE,
                                   instance=INSTANCE).execute()
    fp   = inst["metadata"]["fingerprint"]
    body = {"fingerprint": fp, "items": items}

    op = compute.instances() \
            .setMetadata(project=PROJECT, zone=ZONE,
                         instance=INSTANCE, body=body) \
            .execute()

    # wait until set-metadata operation is DONE
    while True:
        res = compute.zoneOperations() \
                     .get(project=PROJECT, zone=ZONE,
                          operation=op["name"]).execute()
        if res.get("status") == "DONE":
            if "error" in res:
                raise RuntimeError(res["error"])
            break
        time.sleep(1)

# ── request schema ───────────────────────────────────────────
class RenderRequest(BaseModel):
    workflow : dict             # full ComfyUI graph from the node
    model_url: str              # civitai or gs://…

# ── main endpoint ────────────────────────────────────────────
@app.post("/render")
def render(req: RenderRequest):
    job_id      = str(uuid.uuid4())
    job_prefix  = f"{job_id}/"
    workflow    = req.workflow.copy()     # never mutate caller’s object
    workflow["client_id"]   = job_id
    workflow["output_path"] = "/tmp/comfy-out"

    # 1) upload workflow JSON
    job_blob = f"{job_id}.json"
    upload_json(JOB_BUCKET, job_blob, workflow)

    # 2) push per-boot metadata (startup-script-url + job specifics)
    push_metadata([
        {"key": "startup-script-url", "value": STARTUP_URL},
        {"key": "job_workflow",       "value": f"{JOB_BUCKET}/{job_blob}"},
        {"key": "model_uri",          "value": req.model_url},
        {"key": "output_bucket",      "value": f"{OUT_BUCKET}/{job_prefix}"}
    ])

    # 3) start the GPU VM (empty body by Compute API spec)
    compute.instances().start(project=PROJECT,
                              zone=ZONE,
                              instance=INSTANCE).execute()

    # 4) wait for the worker to drop DONE.flag
    flag_blob = gcs.bucket(OUT_BUCKET.replace("gs://", "")) \
                  .blob(f"{job_prefix}DONE.flag")
    while not flag_blob.exists():
        time.sleep(5)

    # 5) collect PNG/JPG → signed URLs
    bucket_name = OUT_BUCKET.replace("gs://", "")
    files = [signed_url(bucket_name, b.name)
             for b in list_blobs(OUT_BUCKET, prefix=job_prefix)
             if b.name.endswith((".png", ".jpg"))]

    if not files:
        raise HTTPException(500, "No images produced")

    return {"job_id": job_id, "files": files}
