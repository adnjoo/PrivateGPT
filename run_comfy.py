import subprocess
import time
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# === CONFIG ===
COMFY_PATH = os.getenv("COMFY_PATH")  # path to ComfyUI folder
PROMPT_FILE = os.getenv("PROMPT_FILE") # should be in same directory as this script
COMFY_PORT = 8188

def launch_comfy():
    print("Launching ComfyUI...")
    return subprocess.Popen(
        ["python", "main.py"],
        cwd=COMFY_PATH,
        creationflags=subprocess.CREATE_NEW_CONSOLE  # opens in new terminal window (Windows only)
    )

def send_prompt():
    url = f"http://localhost:{COMFY_PORT}/prompt"

    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        prompt_json = json.load(f)

    print("Sending prompt...")
    response = requests.post(url, json=prompt_json)
    print("Server response:")
    print(response.json())

def get_latest_image(output_dir):
    """
    Returns the path to the most recently created image file in the output directory.
    """
    import glob
    import os
    image_files = glob.glob(os.path.join(output_dir, '*.png')) + glob.glob(os.path.join(output_dir, '*.jpg'))
    if not image_files:
        return None
    latest_file = max(image_files, key=os.path.getctime)
    return latest_file

# Remove the __main__ block to make this module importable
