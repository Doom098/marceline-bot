from telegram import Update
from telegram.ext import ContextTypes
from database import get_db, init_db
from models import Chat, GameSession, MatchStat
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

async def leave_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Usage: /groupdel [chat_id] (or current if empty)
    if update.effective_user.id != SUPERADMIN_ID: return
    
    target_id = update.effective_chat.id
    if context.args:
        try: target_id = int(context.args[0])
        except: return

    try:
        await context.bot.leave_chat(target_id)
        await update.message.reply_text(f"Left group {target_id}.")
        # Optional: Remove from DB logic here if strict
        with next(get_db()) as db:
            c = db.query(Chat).filter_by(chat_id=target_id).first()
            if c: 
                db.delete(c)
                db.commit()
    except Exception as e:
        await update.message.reply_text(f"Error leaving: {e}")
