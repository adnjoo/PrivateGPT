from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import os
import logging
import requests
import argparse
import subprocess
import time
import ollama_client
import run_comfy
import asyncio
import tempfile

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# In-memory user conversation histories (user_id -> list of messages)
user_histories = {}
CONTEXT_WINDOW = 30  # Number of messages to keep in context

parser = argparse.ArgumentParser(description="Telegram Bot with optional context window display.")
parser.add_argument('--show-context', action='store_true', help='Print the context window sent to the LLM for each user message')
parser.add_argument('--use-chroma', action='store_true', help='Enable Chroma DB for message storage and semantic search')
args = parser.parse_args()
SHOW_CONTEXT = args.show_context
USE_CHROMA = args.use_chroma

# Conditionally import and initialize Chroma
if USE_CHROMA:
    import chroma_store
    chroma_store.init_chroma("chat_history")
    logger.info("Chroma DB enabled and initialized with collection 'chat_history'.")
else:
    logger.info("Chroma DB disabled - running in memory-only mode.")

# Path to ComfyUI output directory
COMFY_PATH = os.getenv("COMFY_PATH")
COMFY_OUTPUT_DIR = os.path.join(COMFY_PATH, "output")
PROMPT_FILE = os.getenv("PROMPT_FILE")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/start command received from user {update.effective_user.id}")
    await update.message.reply_text("Hello! I'm your bot 👋")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Message received from user {update.effective_user.id}: {update.message.text}")
    user_id = update.effective_user.id
    user_message = update.message.text

    # Get or create history for this user
    history = user_histories.get(user_id, [])
    history.append({"role": "user", "content": user_message})
    # Limit context window
    history = history[-CONTEXT_WINDOW:]

    if SHOW_CONTEXT:
        print(f"\n--- Context window for user {user_id} ---")
        for msg in history:
            print(f"{msg['role']}: {msg['content']}")
        print("--- End context window ---\n")

    # Store user message in Chroma with embedding (if enabled)
    if USE_CHROMA:
        chroma_store.save_message(user_message, user_id=user_id, role="user", message_id=update.message.message_id)
        logger.info(f"Saved user message to Chroma: user_id={user_id}, message_id={update.message.message_id}")

        # Demonstrate semantic search: print top 3 similar messages to the current user message
        similar = chroma_store.get_similar_messages(user_message, top_k=3)
        logger.debug(f"[Semantic Search] Top 3 similar messages for user {user_id}: {similar}")

    try:
        lm_reply = ollama_client.send_to_ollama(history)
        logger.info(f"Ollama reply: {lm_reply}")
        await update.message.reply_text(lm_reply)
        # Add assistant reply to history
        history.append({"role": "assistant", "content": lm_reply})
        # Limit context window again
        history = history[-CONTEXT_WINDOW:]
        user_histories[user_id] = history
        # Store bot reply in Chroma with embedding (if enabled)
        if USE_CHROMA:
            chroma_store.save_message(lm_reply, user_id=user_id, role="assistant", message_id=update.message.message_id)
            logger.info(f"Saved assistant reply to Chroma: user_id={user_id}, message_id={update.message.message_id}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error communicating with Ollama: {e}")
        await update.message.reply_text("Sorry, I couldn't get a response from the Ollama bot.")
    except Exception as e:
        logger.error(f"Error communicating with Ollama: {e}")
        await update.message.reply_text("Sorry, I couldn't get a response from the Ollama bot.")

async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/image command received from user {update.effective_user.id} with args: {context.args}")
    if not context.args:
        await update.message.reply_text("Please provide a prompt, e.g. /image flower")
        return
    prompt = " ".join(context.args)

    # Load template and set prompt
    try:
        import json
        with open("assets/flux_template.json", "r", encoding="utf-8") as f:
            template = json.load(f)
        template["prompt"]["6"]["inputs"]["text"] = prompt
        with open(PROMPT_FILE, "w", encoding="utf-8") as f:
            json.dump(template, f)
    except Exception as e:
        logger.error(f"Failed to write prompt file: {e}")
        await update.message.reply_text("Failed to write prompt file.")
        return

    # Stop Ollama before running ComfyUI
    try:
        await update.message.reply_text("Stopping Ollama server before running ComfyUI...")
        ollama_client.stop_ollama()
    except Exception as e:
        logger.warning(f"Failed to stop Ollama: {e}")
        await update.message.reply_text("Warning: Could not stop Ollama server. Proceeding anyway.")

    # Get set of images before generation
    import glob
    existing_images = set(glob.glob(os.path.join(COMFY_OUTPUT_DIR, '*.png')) + glob.glob(os.path.join(COMFY_OUTPUT_DIR, '*.jpg')))

    # Launch ComfyUI (if not running) and send prompt
    try:
        proc = run_comfy.launch_comfy()
        await update.message.reply_text("ComfyUI launched. Waiting for server to start...")
        await asyncio.sleep(100)  # Wait for ComfyUI to boot up (adjust as needed)
        run_comfy.send_prompt()
        await update.message.reply_text("Prompt sent to ComfyUI. Waiting for image...")

        # Poll for new image
        import time
        timeout = 120  # seconds
        poll_interval = 2  # seconds
        start_time = time.time()
        new_image_path = None
        while time.time() - start_time < timeout:
            current_images = set(glob.glob(os.path.join(COMFY_OUTPUT_DIR, '*.png')) + glob.glob(os.path.join(COMFY_OUTPUT_DIR, '*.jpg')))
            new_images = current_images - existing_images
            if new_images:
                # Get the newest image among the new ones
                new_image_path = max(new_images, key=os.path.getctime)
                break
            await asyncio.sleep(poll_interval)
        if not new_image_path:
            await update.message.reply_text("No image generated after waiting.")
            return
    except Exception as e:
        logger.error(f"Error running ComfyUI: {e}")
        await update.message.reply_text("Error running ComfyUI.")
        return

    # Send the image
    try:
        with open(new_image_path, "rb") as img_file:
            await update.message.reply_photo(photo=img_file)
    except Exception as e:
        logger.error(f"Failed to send image: {e}")
        await update.message.reply_text("Failed to send image.")

    # Shut down ComfyUI
    try:
        await update.message.reply_text("Shutting down ComfyUI...")
        run_comfy.shutdown_comfy()  # This function should be implemented in run_comfy.py
    except Exception as e:
        logger.warning(f"Failed to shut down ComfyUI: {e}")
        await update.message.reply_text("Warning: Could not shut down ComfyUI. Proceeding anyway.")

    # Start Ollama server again
    try:
        await update.message.reply_text("Starting Ollama server again...")
        ollama_client.start_ollama()  # This function should be implemented in ollama_client.py
    except Exception as e:
        logger.warning(f"Failed to start Ollama: {e}")
        await update.message.reply_text("Warning: Could not start Ollama server.")

async def tts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Transcribe the last message (user or bot) to audio using kokoro and send as a voice message.
    """
    try:
        from kokoro import KPipeline
        import soundfile as sf
        import numpy as np
    except ImportError:
        await update.message.reply_text("Kokoro, soundfile, or numpy not installed. Please install dependencies.")
        return

    user_id = update.effective_user.id
    history = user_histories.get(user_id, [])
    if not history:
        await update.message.reply_text("No message history found.")
        return
    # Get the last message (prefer assistant, else user)
    for msg in reversed(history):
        if msg['role'] in ("assistant", "user") and msg['content']:
            last_text = msg['content']
            break
    else:
        await update.message.reply_text("No suitable message found for TTS.")
        return

    # Generate audio with kokoro
    try:
        pipeline = KPipeline(lang_code='a')  # American English
        voice = 'af_heart'  # Default voice
        generator = pipeline(last_text, voice=voice)
        audio_chunks = []
        for _, _, audio in generator:
            audio_chunks.append(audio)
        if not audio_chunks:
            await update.message.reply_text("No audio generated.")
            return
        # Concatenate all audio chunks
        full_audio = np.concatenate(audio_chunks)
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            sf.write(tmp.name, full_audio, 24000)
            tmp_path = tmp.name
    except Exception as e:
        logger.error(f"TTS error during audio generation: {e}")
        await update.message.reply_text("Failed to generate audio transcription.")
        return

    # Send as voice message
    try:
        with open(tmp_path, 'rb') as audio_file:
            await update.message.reply_voice(voice=audio_file)
    except Exception as e:
        logger.error(f"TTS error during sending audio: {e}")
        await update.message.reply_text("Failed to send audio transcription.")

logger.info("Starting the bot...")
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
app.add_handler(CommandHandler("image", image_command))
app.add_handler(CommandHandler("tts", tts_command))

app.run_polling()
