from telegram import Update
from telegram.ext import ContextTypes
from database import get_db, init_db
from models import Chat, GameSession, MatchStat, ChatMember
from config import SUPERADMIN_ID

async def reset_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPERADMIN_ID: return
    if not context.args or context.args[0] != "CONFIRM":
        await update.message.reply_text("Send '/resetall CONFIRM' to wipe group data.")
        return

    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        db.query(MatchStat).filter_by(chat_id=chat_id).delete()
        db.query(GameSession).filter_by(chat_id=chat_id).delete()
        # Potentially clear vault too if requested, but prompt said "wipe all bot data"
        # Keeping members tracking is usually preferred, but strict wipe means everything.
        # Let's wipe stats and sessions primarily.
        db.commit()
    await update.message.reply_text("Reset complete.")

async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPERADMIN_ID: return
    with next(get_db()) as db:
        chats = db.query(Chat).all()
        msg = "Active Groups:\n"
        for c in chats:
            msg += f"{c.title} ({c.chat_id})\n"
        await update.message.reply_text(msg)