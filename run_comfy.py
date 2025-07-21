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

# Store the process handle globally
comfy_process = None

def launch_comfy():
    global comfy_process
    print("Launching ComfyUI...")
    comfy_process = subprocess.Popen(
        ["python", "main.py"],
        cwd=COMFY_PATH,
        creationflags=subprocess.CREATE_NEW_CONSOLE  # opens in new terminal window (Windows only)
    )
    return comfy_process

def shutdown_comfy():
    global comfy_process
    import signal
    import psutil
    if comfy_process and comfy_process.poll() is None:
        print("Terminating ComfyUI process...")
        comfy_process.terminate()
        try:
            comfy_process.wait(timeout=10)
        except Exception:
            comfy_process.kill()
        comfy_process = None
    else:
        # Fallback: kill any python main.py process in COMFY_PATH
        print("No tracked process. Attempting fallback kill...")
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
            try:
                if (
                    proc.info['name'] and 'python' in proc.info['name'].lower() and
                    proc.info['cmdline'] and 'main.py' in ' '.join(proc.info['cmdline']) and
                    proc.info['cwd'] and os.path.abspath(proc.info['cwd']) == os.path.abspath(COMFY_PATH)
                ):
                    print(f"Killing process {proc.pid}...")
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except Exception:
                        proc.kill()
            except Exception:
                continue

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
