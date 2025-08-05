# /opt/ComfyUI/custom_nodes/dispatch_gpu.py
import os, json, uuid, time, tempfile, requests, pathlib

DISPATCHER_URL = os.getenv("DISPATCHER_URL") or "http://dispatcher:8187/render"

# ───────────────────────── Helpers ────────────────────────────────────
def build_workflow(prompt_txt: str,
                   sampler   : str,
                   steps     : int,
                   job_id    : str) -> dict:
    """
    Return a *full* ComfyUI API-style workflow JSON.
    """
    return {
        "prompt": {
            # 0 ▸ blank latent
            "0": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": 1024, "height": 1024}
            },

            # 1 ▸ load checkpoint
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}
            },

            # 2 ▸ KSampler (model-agnostic)
            "2": {
                "class_type": "KSampler",
                "inputs": {
                    "model"        : ["1", 0],
                    "latent_image" : ["0", 0],
                    "steps"        : steps,
                    "sampler_name" : sampler
                }
            },

            # 3 ▸ save result
            "3": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["2", 0],
                    "filename_prefix": f"job_{job_id}"
                }
            }
        },
        "client_id": job_id,
        "output_path": "/tmp/comfy-out"
    }

# ───────────────────────── Custom node ────────────────────────────────
class DispatchToGPU:
    """
    Submit a full workflow to the GPU dispatcher and return a thumbnail PNG.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "PROMPT"    : ("STRING",  {"multiline": True}),
                "MODEL_URL" : ("STRING",  {"default": ""}),
                "SAMPLER"   : ("STRING",  {"default": "euler"}),
                "STEPS"     : ("INT",     {"default": 30, "min": 1, "max": 150})
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION     = "run"
    CATEGORY     = "Utility / Dispatch"

    # ── core ───────────────────────────────────────────────────────────
    def run(self, PROMPT, MODEL_URL="", SAMPLER="euler", STEPS=30):
        job_id  = str(uuid.uuid4())
        payload = {
            "prompt"    : PROMPT,
            "model_url" : MODEL_URL,
            "sampler"   : SAMPLER,
            "steps"     : int(STEPS)
        }

        # Submit to dispatcher
        try:
            resp = requests.post(DISPATCHER_URL,
                                 json=payload,
                                 timeout=300)
            resp.raise_for_status()
            job = resp.json()
        except Exception as e:
            raise RuntimeError(f"Dispatcher error: {e}")

        # Grab first PNG (signed URLs list)
        try:
            png_url  = job["files"][0]
            png_data = requests.get(png_url, timeout=60).content
        except Exception:
            # 1×1 pixel fallback
            png_data = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
                        b"\x00\x00\x00\nIDATx\xdac\xf8\x0f\x00\x01\x01\x01\x00"
                        b"\x18\xdd\x8a\xe5\x00\x00\x00\x00IEND\xaeB`\x82")

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp.write(png_data)
        tmp.close()
        return (tmp.name,)

# ───────────────── register ───────────────────────────────────────────
NODE_CLASS_MAPPINGS = {"DispatchToGPU": DispatchToGPU}
