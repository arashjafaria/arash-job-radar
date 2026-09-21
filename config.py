import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


if (
    not BOT_TOKEN
    or not CHAT_ID
    or not SUPABASE_URL
    or not SUPABASE_SECRET_KEY
):
    try:
        from config_local import (
            BOT_TOKEN as LOCAL_BOT_TOKEN,
            CHAT_ID as LOCAL_CHAT_ID,
            SUPABASE_URL as LOCAL_SUPABASE_URL,
            SUPABASE_SECRET_KEY as LOCAL_SUPABASE_SECRET_KEY,
        )

        BOT_TOKEN = (
            BOT_TOKEN
            or LOCAL_BOT_TOKEN
        )

        CHAT_ID = (
            CHAT_ID
            or LOCAL_CHAT_ID
        )

        SUPABASE_URL = (
            SUPABASE_URL
            or LOCAL_SUPABASE_URL
        )

        SUPABASE_SECRET_KEY = (
            SUPABASE_SECRET_KEY
            or LOCAL_SUPABASE_SECRET_KEY
        )

    except ImportError:
        pass