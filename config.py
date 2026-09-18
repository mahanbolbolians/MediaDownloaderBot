import json
import os
import sys

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "api_id": 0,
    "api_hash": "",
    "bot_token": "",
    "allowed_users": []
}

def load_config() -> dict:
    config = dict(DEFAULT_CONFIG)

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                config.update(json.load(f))
        except Exception as e:
            print(f"[!] Warning reading config.json: {e}")

    # Environment variables override config.json (for Railway / Cloud)
    if os.environ.get("TELEGRAM_API_ID"):
        config["api_id"] = int(os.environ["TELEGRAM_API_ID"])
    if os.environ.get("TELEGRAM_API_HASH"):
        config["api_hash"] = os.environ["TELEGRAM_API_HASH"].strip()
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        config["bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"].strip()
    if os.environ.get("TELEGRAM_CHAT_IDS"):
        try:
            ids = [int(x.strip()) for x in os.environ["TELEGRAM_CHAT_IDS"].split(",") if x.strip()]
            config["allowed_users"] = ids
        except Exception:
            pass

    # Prompt if running interactively locally
    if not config.get("api_id") or not config.get("api_hash") or not config.get("bot_token"):
        if not sys.stdin.isatty():
            raise RuntimeError("Missing required Telegram API credentials in environment or config.json")
        print("\n" + "="*60)
        print("  MediaDownloaderBot — Setup")
        print("="*60)
        print("Please enter your Telegram API credentials:")
        try:
            if not config.get("api_id"):
                config["api_id"] = int(input("Enter API_ID: ").strip())
            if not config.get("api_hash"):
                config["api_hash"] = input("Enter API_HASH: ").strip()
            if not config.get("bot_token"):
                config["bot_token"] = input("Enter BOT_TOKEN: ").strip()
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            print("[+] Configuration saved successfully!\n")
        except Exception as e:
            print(f"[!] Error reading input: {e}")
            sys.exit(1)

    return config

config = load_config()
