# /opt/ComfyUI/custom_nodes/dispatch_gpu.py
import os, uuid, tempfile, requests

DISPATCHER_URL = os.getenv("DISPATCHER_URL") or "http://dispatcher:8187/render"

# ----------------------------------------------------------------------
def build_workflow(prompt_txt: str, sampler: str, steps: int, ckpt: str, job_id: str, seed: int) -> dict:
    """Return a valid ComfyUI API-format workflow"""
    return {
        "prompt": {
            # 0 ▸ blank latent
            "0": {"class_type": "EmptyLatentImage",
                  "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},

            # 1 ▸ load checkpoint
            "1": {"class_type": "CheckpointLoaderSimple",
                  "inputs": {"ckpt_name": ckpt}},

            # 2 ▸ CLIP Text Encode (Positive)
            "2": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": prompt_txt,
                             "clip": ["1", 1]}},

            # 3 ▸ CLIP Text Encode (Negative)
            "3": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": "",
                             "clip": ["1", 1]}},

            # 4 ▸ KSampler
            "4": {"class_type": "KSampler",
                  "inputs": {"model": ["1", 0],
                             "positive": ["2", 0],
                             "negative": ["3", 0],
                             "latent_image": ["0", 0],
                             "seed": seed,
                             "steps": steps,
                             "cfg": 8.0,
                             "sampler_name": sampler,
                             "scheduler": "normal",
                             "denoise": 1.0}},

            # 5 ▸ VAE Decode
            "5": {"class_type": "VAEDecode",
                  "inputs": {"samples": ["4", 0],
                             "vae": ["1", 2]}},

            # 6 ▸ save
            "6": {"class_type": "SaveImage",
                  "inputs": {"images": ["5", 0],
                             "filename_prefix": f"job_{job_id}"}}
        },
        "client_id": job_id,
        "output_path": "/tmp/comfy-out"
    }

# ----------------------------------------------------------------------
class DispatchToGPU:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "PROMPT":    ("STRING", {"multiline": True}),
            "MODEL_URL": ("STRING", {"default": "https://civitai.com/api/download/models/2010753?token=b10fa8a6813b11b59ff5043f154aa1b9"}),
            "SAMPLER":   ("STRING", {"default": "euler"}),
            "STEPS":     ("INT",    {"default": 30, "min": 1, "max": 150}),
            "CKPT_NAME": ("STRING", {"default": "hassakuXLIllustrious_v30.safetensors"}),
            "SEED": ("INT", {"default": 156680208700286})
        }}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"
    CATEGORY = "Utility / Dispatch"

    # -------------------------------------------------------------
    def run(self, PROMPT, MODEL_URL="https://civitai.com/api/download/models/2010753?token=b10fa8a6813b11b59ff5043f154aa1b9", SAMPLER="euler",
            STEPS=30, CKPT_NAME="hassakuXLIllustrious_v30.safetensors", SEED=156680208700286):

        job_id   = str(uuid.uuid4())
        workflow = build_workflow(PROMPT, SAMPLER, int(STEPS), CKPT_NAME, job_id, SEED)

        payload  = {
            "workflow" : workflow,          # <── new, full graph
            "model_url": MODEL_URL          # URL the GPU worker should fetch
        }

        # call dispatcher -------------------------------------------------
        try:
            r = requests.post(DISPATCHER_URL, json=payload, timeout=180)
            r.raise_for_status()
            job = r.json()
        except Exception as e:
            raise RuntimeError(f"Dispatcher error: {e}")

        # fetch first image for thumbnail --------------------------------
        try:
            png_data = requests.get(job["files"][0], timeout=60).content
        except Exception:
            # 1×1 px fallback
            png_data = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
                        b"\x00\x00\x00\nIDATx\xdac\xf8\x0f\x00\x01\x01\x01\x00"
                        b"\x18\xdd\x8a\xe5\x00\x00\x00\x00IEND\xaeB`\x82")

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp.write(png_data); tmp.close()
        return (tmp.name,)

# register --------------------------------------------------------------
NODE_CLASS_MAPPINGS = {"DispatchToGPU": DispatchToGPU}
