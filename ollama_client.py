import os
import requests
import subprocess
import time
import logging

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_START_TIMEOUT = 30  # seconds
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are a helpful assistant.")

logger = logging.getLogger(__name__)

def is_ollama_running():
    try:
        r = requests.get("http://localhost:11434")
        return r.status_code == 200
    except Exception:
        return False

def start_ollama():
    logger.info("Starting Ollama server...")
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(OLLAMA_START_TIMEOUT):
        if is_ollama_running():
            logger.info("Ollama server is running.")
            return True
        time.sleep(1)
    logger.error("Failed to start Ollama server within timeout.")
    return False

def ensure_ollama_running():
    if not is_ollama_running():
        started = start_ollama()
        if not started:
            raise RuntimeError("Could not start Ollama server.")
    else:
        logger.info("Ollama server already running.")

def send_to_ollama(history, temperature=0.7, num_predict=1000, timeout=180):
    ensure_ollama_running()
    # Insert system prompt at the start
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    response = requests.post(
        OLLAMA_API_URL,
        json={
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": num_predict}
        },
        timeout=timeout
    )
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"] 