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

    # Launch ComfyUI (if not running) and send prompt
    try:
        proc = run_comfy.launch_comfy()
        await update.message.reply_text("ComfyUI launched. Waiting for server to start...")
        await asyncio.sleep(100)  # Wait for ComfyUI to boot up (adjust as needed)
        run_comfy.send_prompt()
        await update.message.reply_text("Prompt sent to ComfyUI. Waiting for image...")
        await asyncio.sleep(10)  # Wait for image to be generated (adjust as needed)
    except Exception as e:
        logger.error(f"Error running ComfyUI: {e}")
        await update.message.reply_text("Error running ComfyUI.")
        return

    # Find the latest image
    image_path = run_comfy.get_latest_image(COMFY_OUTPUT_DIR)
    if not image_path:
        await update.message.reply_text("No image generated.")
        return
    # Send the image
    try:
        with open(image_path, "rb") as img_file:
            await update.message.reply_photo(photo=img_file)
    except Exception as e:
        logger.error(f"Failed to send image: {e}")
        await update.message.reply_text("Failed to send image.")

logger.info("Starting the bot...")
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
app.add_handler(CommandHandler("image", image_command))

app.run_polling()
