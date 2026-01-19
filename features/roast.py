import random
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import get_db
from models import RoastLine

# Load seed roasts (Your existing logic)
try:
    with open("roasts_seed.txt", "r", encoding="utf-8") as f:
        SEED_ROASTS = [line.strip() for line in f if line.strip()]
except FileNotFoundError:
    SEED_ROASTS = ["You are bad."]

async def roast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # --- 1. TARGETING FIX STARTS HERE ---
    # Priority: Roast the person you replied to. If no reply, roast the sender.
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    else:
        target = update.effective_user
    # --- TARGETING FIX ENDS HERE ---

    # Mix seed + db roasts (Your existing logic)
    with next(get_db()) as db:
        db_roasts = db.query(RoastLine).filter_by(chat_id=chat_id).all()
        custom_lines = [r.text for r in db_roasts]
    
    # Combine lists and pick one
    pool = SEED_ROASTS + custom_lines
    if not pool:
        pool = ["I have no roasts loaded."]
        
    roast = random.choice(pool)
    
    # Send with the target's name
    await update.message.reply_text(f"{target.first_name}, {roast}")

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
        await update.message.reply_text("Usage: /roastdel <number>")
        return
    try:
        idx = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a valid number.")
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
