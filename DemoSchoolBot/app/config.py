import os
from dotenv import load_dotenv
load_dotenv()

DEBUG = False

DB = {
    "engine": "sqlite",
    "name": "demo_local.db"
}

# CRITICAL SECURITY FIX: Remove hardcoded token
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is required")

ADMIN_IDS = [64210389, 1570881]
