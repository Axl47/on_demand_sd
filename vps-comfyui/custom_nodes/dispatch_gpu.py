# dispatch_gpu.py  –  a single-node bridge to your FastAPI dispatcher
import json, os, time, tempfile, requests, shutil
from comfy import model_management            # shipped with ComfyUI
from nodes import NODE_CLASS_MAPPINGS, Node

DISPATCHER_URL = os.getenv("DISPATCHER_URL", "http://localhost:8187/render")

class DispatchToGPU(Node):
    """
    Send the entire workflow JSON to /render on the FastAPI dispatcher.
    Returns a temporary PNG so you can preview something in ComfyUI.
    """
    NAME        = "⚡Dispatch to GPU"
    CATEGORY    = "Utility"
    OUTPUT_TYPES= ("IMAGE",)      # so ComfyUI shows a thumbnail

    def run(self, PROMPT: str, MODEL_URL: str, SAMPLER: str = "euler", STEPS: int = 30):
        payload = {
            "prompt": PROMPT,
            "model_url": MODEL_URL,
            "sampler": SAMPLER,
            "steps": STEPS
        }
        r = requests.post(DISPATCHER_URL, json=payload, timeout=10)
        r.raise_for_status()
        j = r.json()

        # (Optional) download first image to preview in the UI ---------
        first_png = j["files"][0]   # path on dispatcher container
        png_data  = requests.get(f"http://dispatcher:8187/files/{os.path.basename(first_png)}").content
        tmp_png   = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        with open(tmp_png.name, "wb") as f:
            f.write(png_data)

        return (tmp_png.name,)      # ComfyUI expects a tuple

NODE_CLASS_MAPPINGS["DispatchToGPU"] = DispatchToGPU