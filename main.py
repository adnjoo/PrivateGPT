from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import os
import logging
import requests
import argparse
import subprocess
import time

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_START_TIMEOUT = 30  # seconds

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

# Start Ollama if not running
if not is_ollama_running():
    started = start_ollama()
    if not started:
        raise RuntimeError("Could not start Ollama server.")
else:
    logger.info("Ollama server already running.")

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

    SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are a helpful assistant.")
    # Insert system prompt at the start
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    print(f"Messages: {messages}")

    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 1000}
            },
            timeout=180
        )
        response.raise_for_status()
        data = response.json()
        lm_reply = data["message"]["content"]
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

logger.info("Starting the bot...")
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

app.run_polling()
