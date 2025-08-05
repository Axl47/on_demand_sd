from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid, time, os, json, subprocess, tempfile
from google.cloud import storage              # python-storage lib :contentReference[oaicite:4]{index=4}
from googleapiclient import discovery         # compute API :contentReference[oaicite:5]{index=5}
from datetime import timedelta

app = FastAPI()
gcs = storage.Client()
compute = discovery.build("compute", "v1")

# ---- static env ----
PROJECT      = os.getenv("GCP_PROJECT")
INSTANCE     = os.getenv("GCE_INSTANCE")
ZONE         = os.getenv("GCE_ZONE")
JOB_BUCKET   = os.getenv("JOB_BUCKET")
OUT_BUCKET   = os.getenv("OUT_BUCKET")

def signed_url(bucket, name, exp_minutes=20):
    return gcs.bucket(bucket).blob(name).generate_signed_url(            # :contentReference[oaicite:3]{index=3}
        version="v4",
        expiration=timedelta(minutes=exp_minutes),
        method="GET"
    )

class RenderRequest(BaseModel):
    prompt: str
    model_url: str      # civitai or gs://
    sampler: str = "euler"
    steps: int = 30

def bucket_and_key(uri: str):
    # gs://my-bucket/optional/prefix/ -> ("my-bucket", "optional/prefix/")
    path = uri.replace("gs://", "")
    parts = path.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] + "/" if len(parts) == 2 else ""
    return bucket, prefix

def upload_json(bucket_uri: str, blob_name: str, data: dict):
    bucket_name, prefix = bucket_and_key(bucket_uri)
    bucket = gcs.bucket(bucket_name)
    blob   = bucket.blob(prefix + blob_name)
    blob.upload_from_string(json.dumps(data), content_type="application/json")

def list_blobs(bucket_uri, prefix):
    bucket_name = bucket_uri.replace("gs://", "")
    return gcs.bucket(bucket_name).list_blobs(prefix=prefix)

# ---------------------------------------------------------------------
@app.post("/render")
def render(req: RenderRequest):
    job_id = str(uuid.uuid4())
    job_prefix = f"{job_id}/"
    job_json   = f"{job_id}.json"

    # 1) build a minimal ComfyUI workflow (placeholder)
    workflow = {
        "prompt": req.prompt,
        "sampler": req.sampler,
        "steps": req.steps,
        "client_id": job_id,
        "output_path": "/tmp/comfy-out"
    }

    # 2) upload workflow JSON
    upload_json(JOB_BUCKET, job_json, workflow)

    # 3) start the GPU instance
    body = {
        "metadata": {
            "items": [
                {"key": "job_workflow",  "value": f"{JOB_BUCKET}/{job_json}"},
                {"key": "model_uri",     "value": req.model_url},
                {"key": "output_bucket", "value": f"{OUT_BUCKET}/{job_prefix}"}
            ]
        }
    }
    compute.instances().start(
        project=PROJECT, zone=ZONE, instance=INSTANCE, body=body
    ).execute()                                        # starts instantly  :contentReference[oaicite:6]{index=6}

    # 4) poll for DONE.flag
    flag = f"{job_prefix}DONE.flag"
    bucket_name = OUT_BUCKET.replace("gs://", "")
    bucket = gcs.bucket(bucket_name)
    while True:
        if bucket.blob(flag).exists():                # simple existence check :contentReference[oaicite:7]{index=7}
            break
        time.sleep(5)

    # 5) download all PNGs
    files = []
    for blob in list_blobs(OUT_BUCKET, prefix=job_prefix):
        if blob.name.endswith((".png", ".jpg")):
            files.append(signed_url(bucket_name, blob.name))

    if not files:
        raise HTTPException(500, "No images produced")

    return {"job_id": job_id, "files": files}
