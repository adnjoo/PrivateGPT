import tempfile
from telegram import Update
from telegram.ext import ContextTypes
import logging
from main import user_histories, logger

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