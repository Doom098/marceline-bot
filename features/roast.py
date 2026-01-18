import random
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import get_db
from models import RoastLine

# Load seed roasts
try:
    with open("roasts_seed.txt", "r") as f:
        SEED_ROASTS = [line.strip() for line in f if line.strip()]
except FileNotFoundError:
    SEED_ROASTS = ["You are bad."]

async def roast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Mix seed + db roasts
    with next(get_db()) as db:
        db_roasts = db.query(RoastLine).filter_by(chat_id=chat_id).all()
        custom_lines = [r.text for r in db_roasts]
    
    pool = SEED_ROASTS + custom_lines
    roast = random.choice(pool)
    
    await update.message.reply_text(roast)

# Conversation for adding roast
ADD_ROAST_TEXT = 1

async def start_add_roast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Input roasting line:")
    return ADD_ROAST_TEXT

async def save_roast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    
    with next(get_db()) as db:
        new_roast = RoastLine(chat_id=chat_id, text=text)
        db.add(new_roast)
        db.commit()
        
    await update.message.reply_text("Roast added.")
    return ConversationHandler.END

async def show_roasts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        roasts = db.query(RoastLine).filter_by(chat_id=chat_id).all()
        if not roasts:
            await update.message.reply_text("No user-added roasts.")
            return
        
        msg = "User Roasts:\n"
        for idx, r in enumerate(roasts, 1):
            msg += f"{idx}. {r.text}\n"
        await update.message.reply_text(msg)

async def del_roast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return
    try:
        idx = int(context.args[0])
    except ValueError:
        return

    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        roasts = db.query(RoastLine).filter_by(chat_id=chat_id).all()
        if 1 <= idx <= len(roasts):
            target = roasts[idx-1]
            db.delete(target)
            db.commit()
            await update.message.reply_text(f"Deleted roast #{idx}")
        else:
            await update.message.reply_text("Invalid number.")