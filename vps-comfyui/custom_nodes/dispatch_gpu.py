# /opt/ComfyUI/custom_nodes/dispatch_gpu.py
import os, json, uuid, time, tempfile, requests, pathlib

DISPATCHER_URL = os.getenv("DISPATCHER_URL", "http://localhost:8187")

class DispatchToGPU:
    """
    Send the prompt + model-URL to the FastAPI dispatcher and return
    a temporary PNG so you get a thumbnail preview.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "PROMPT": ("STRING", {"multiline": True}),
                "MODEL_URL": ("STRING", {"default": ""}),
                "SAMPLER": ("STRING", {"default": "euler"}),
                "STEPS": ("INT", {"default": 30, "min": 1, "max": 150})
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"
    CATEGORY = "Utility"

    def run(self, PROMPT, MODEL_URL, SAMPLER="euler", STEPS=30):
        payload = {
            "prompt": PROMPT,
            "model_url": MODEL_URL,
            "sampler": SAMPLER,
            "steps": int(STEPS)
        }

        # --- call the dispatcher -------------------------------------------------
        try:
            r = requests.post(DISPATCHER_URL + "/render", json=payload, timeout=15)
            r.raise_for_status()
            job = r.json()
        except Exception as e:
            raise RuntimeError(f"Dispatcher error: {e}")

        # --- fetch the first PNG for preview (optional) --------------------------
        try:
            first_remote = pathlib.Path(job["files"][0]).name
            png_data = requests.get(f"{DISPATCHER_URL}/files/{first_remote}", timeout=60).content
        except Exception:
            # fall back to a 1×1 black pixel to keep the node happy
            png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01" \
                       b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde" \
                       b"\x00\x00\x00\nIDATx\xdac\xf8\x0f\x00\x01\x01\x01\x00" \
                       b"\x18\xdd\x8a\xe5\x00\x00\x00\x00IEND\xaeB`\x82"

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp.write(png_data); tmp.close()
        return (tmp.name,)


# ----- register with ComfyUI ---------------------------------------------------
NODE_CLASS_MAPPINGS = {"DispatchToGPU": DispatchToGPU}
