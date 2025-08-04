#!/bin/bash
WF="gs://bucket/jobs/$(date +%s).json"
MODEL="https://civitai.com/api/download/models/140272?token=$CIVITAI_TOKEN"
OUT="gs://bucket/outputs/$(date +%s)/"

# (The UI exported the workflow JSON to $WF here…)

gcloud compute instances start gpu-sd-worker \
  --zone=us-central1-a \
  --metadata job_workflow="$WF",model_uri="$MODEL",output_bucket="$OUT"
