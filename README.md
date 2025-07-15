# TGBot

A Telegram bot that forwards messages to a local LM Studio server and replies with context-aware responses.

## Quick Start
```bash
python -m venv venv
source venv/bin/activate  # or venv/Scripts/activate on Windows
pip install -r requirements.txt
# Add BOT_TOKEN=... to a .env file
python main.py [--show-context]
```

- Requires LM Studio running at http://localhost:1234/v1/chat/completions
- The bot keeps a short-term memory (last 30 messages per user) for context.
- Use `--show-context` to print the context window sent to the LLM for each user message.

## Troubleshooting
- If you see errors, ensure LM Studio is running and your .env has the correct BOT_TOKEN.

## [License](./LICENSE)
