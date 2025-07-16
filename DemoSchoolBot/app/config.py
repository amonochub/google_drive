import os
from dotenv import load_dotenv
load_dotenv()

DEBUG = False

DB = {
    "engine": "sqlite",
    "name": "demo_local.db"
}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8152775753:AAHJDIYZTutzSvti9OHCaBJU897kOtCx1nM")
ADMIN_IDS = [64210389, 1570881]
