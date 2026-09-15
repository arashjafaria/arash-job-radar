import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    try:
        from config_local import BOT_TOKEN as LOCAL_BOT_TOKEN
        from config_local import CHAT_ID as LOCAL_CHAT_ID

        BOT_TOKEN = BOT_TOKEN or LOCAL_BOT_TOKEN
        CHAT_ID = CHAT_ID or LOCAL_CHAT_ID

    except ImportError:
        pass