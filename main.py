from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import os
import logging
import requests

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

LM_STUDIO_TIMEOUT = 180  # Timeout in seconds for LM Studio API requests

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/start command received from user {update.effective_user.id}")
    await update.message.reply_text("Hello! I'm your bot 👋")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Message received from user {update.effective_user.id}: {update.message.text}")
    user_message = update.message.text
    try:
        response = requests.post(
            "http://localhost:1234/v1/chat/completions",
            json={
                "model": "LM Studio",
                "messages": [
                    {"role": "user", "content": user_message}
                ]
            },
            timeout=LM_STUDIO_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        lm_reply = data["choices"][0]["message"]["content"]
        logger.info(f"LM Studio reply: {lm_reply}")
        await update.message.reply_text(lm_reply)
    except Exception as e:
        logger.error(f"Error communicating with LM Studio: {e}")
        await update.message.reply_text("Sorry, I couldn't get a response from the LM Studio bot.")

logger.info("Starting the bot...")
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

app.run_polling()
