import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / os.getenv("DB_NAME", "database.db")
BACKUP_DIR = BASE_DIR / "backups"

TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1193808132"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "-1003878040002"))
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN", "")