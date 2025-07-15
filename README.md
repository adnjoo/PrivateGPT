# TGBot

### Instructions
```bash
python -m venv venv
source venv/bin/activate # mac. for Windows, use venv/Scripts/activate

pip install -r requirements.txt
python main.py
```

Put in .env
```bash
BOT_TOKEN=...
```

## LM Studio Integration

This bot forwards user messages to an LM Studio server running locally and replies with the response.

### Requirements
- LM Studio server running and accessible at http://localhost:1234/v1/chat/completions
- The Telegram bot token in your .env file as shown above

### How it works
- Any message sent to the bot is forwarded to LM Studio as a single-turn chat (no conversation history)
- The bot replies with the LM Studio response
- Logging is enabled; you will see info about incoming messages and LM Studio replies in your console

### Troubleshooting
- If you see "Sorry, I couldn't get a response from the LM Studio bot.", make sure LM Studio is running and accessible at http://localhost:1234
- Check your console for error logs for more details
