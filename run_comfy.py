import subprocess
import time
import requests
import json
import os

# === CONFIG ===
COMFY_PATH = r"C:\Users\adnjo\Documents\comfy\ComfyUI"  # path to ComfyUI folder
PROMPT_FILE = "a_fixed.json"  # should be in same directory as this script
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

if __name__ == "__main__":
    # Step 1: Start Comfy
    proc = launch_comfy()

    # Step 2: Wait for server to boot up
    print("Waiting 100 seconds for ComfyUI to start...")
    time.sleep(100)

    try:
        # Step 3: Send prompt
        send_prompt()
    finally:
        # Optional: Stop ComfyUI process
        input("Press Enter to terminate ComfyUI...")
        proc.terminate()
