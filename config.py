from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN          = os.getenv("BOT_TOKEN")
SIMPLESWAP_API_KEY = os.getenv("SIMPLESWAP_API_KEY")  # legacy — still used by hidden "buy with card" flow
# FixedFloat (ff.io) — primary crypto exchange provider
FIXEDFLOAT_API_KEY    = os.getenv("FIXEDFLOAT_API_KEY", "")
FIXEDFLOAT_API_SECRET = os.getenv("FIXEDFLOAT_API_SECRET", "")
ADMIN_ID           = int(os.getenv("ADMIN_ID", "0"))

# Webhook
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL  = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else ""

# Channels (optional — leave empty to disable)
# PUBLIC_CHANNEL_ID  — posts successful swaps (e.g. @mychannel or -1001234567890)
# PRIVATE_CHANNEL_ID — posts all status updates for admin monitoring
PUBLIC_CHANNEL_ID  = os.getenv("PUBLIC_CHANNEL_ID", "")
PRIVATE_CHANNEL_ID = os.getenv("PRIVATE_CHANNEL_ID", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env")