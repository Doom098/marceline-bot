import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPERADMIN_ID = int(os.getenv("SUPERADMIN_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot.db")

# Fix for Heroku Postgres URL (needs postgresql:// instead of postgres://)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)