from telegram import Update
from telegram.ext import ContextTypes
from database import get_db
from models import VaultItem
from sqlalchemy import func

async def save_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Usage: Reply to msg -> /save keyword
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Reply to content with /save <keyword>")
        return

    keyword = context.args[0].lower()
    chat_id = update.effective_chat.id
    reply = update.message.reply_to_message

    # Determine type and content
    content = None
    item_type = "text"

    if reply.text:
        content = reply.text
    elif reply.photo:
        item_type = "photo"
        content = reply.photo[-1].file_id
    elif reply.video:
        item_type = "video"
        content = reply.video.file_id
    elif reply.document:
        item_type = "document"
        content = reply.document.file_id
    elif reply.voice:
        item_type = "voice"
        content = reply.voice.file_id
    elif reply.audio:
        item_type = "audio"
        content = reply.audio.file_id
    else:
        await update.message.reply_text("Unsupported content type.")
        return

    with next(get_db()) as db:
        # Check duplicate keyword globally in vault (for this group)
        exists = db.query(VaultItem).filter_by(chat_id=chat_id, keyword=keyword).first()
        if exists:
            await update.message.reply_text(f"Keyword '{keyword}' already exists. Pick another.")
            return

        item = VaultItem(chat_id=chat_id, keyword=keyword, item_type=item_type, content=content)
        db.add(item)
        db.commit()
        await update.message.reply_text(f"Saved as '{keyword}'.")

async def recall_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return
    keyword = context.args[0].lower()
    chat_id = update.effective_chat.id

    with next(get_db()) as db:
        item = db.query(VaultItem).filter_by(chat_id=chat_id, keyword=keyword).first()
        
        if not item:
            await update.message.reply_text("Keyword not found.")
            return

        if item.item_type == "text":
            await update.message.reply_text(item.content)
        elif item.item_type == "photo":
            await update.message.reply_photo(item.content)
        elif item.item_type == "video":
            await update.message.reply_video(item.content)
        elif item.item_type == "document":
            await update.message.reply_document(item.content)
        elif item.item_type == "voice":
            await update.message.reply_voice(item.content)
        elif item.item_type == "audio":
            await update.message.reply_audio(item.content)
        elif item.item_type == "sticker":
             await update.message.reply_sticker(item.content)

async def list_saves(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        items = db.query(VaultItem).filter(
            VaultItem.chat_id == chat_id, 
            VaultItem.item_type != 'sticker',
            VaultItem.item_type != 'excuse'
        ).all()
        
        if not items:
            await update.message.reply_text("No saved items.")
            return

        lines = []
        for i in items:
            preview = i.content[:20] + "..." if i.item_type == "text" else f"[{i.item_type}]"
            lines.append(f"{i.keyword} - {preview}")
        
        await update.message.reply_text("\n".join(lines))

async def delete_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    keyword = context.args[0].lower()
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        item = db.query(VaultItem).filter_by(chat_id=chat_id, keyword=keyword).first()
        if item:
            db.delete(item)
            db.commit()
            await update.message.reply_text(f"Deleted '{keyword}'.")
        else:
            await update.message.reply_text("Not found.")

# --- Stickers ---
async def save_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.sticker or not context.args:
        await update.message.reply_text("Reply to a sticker with /ssave <keyword>")
        return
    
    keyword = context.args[0].lower()
    chat_id = update.effective_chat.id
    file_id = update.message.reply_to_message.sticker.file_id

    with next(get_db()) as db:
        if db.query(VaultItem).filter_by(chat_id=chat_id, keyword=keyword).first():
            await update.message.reply_text("Keyword taken.")
            return
        
        item = VaultItem(chat_id=chat_id, keyword=keyword, item_type="sticker", content=file_id)
        db.add(item)
        db.commit()
        await update.message.reply_text("Sticker saved.")

async def recall_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    keyword = context.args[0].lower()
    chat_id = update.effective_chat.id
    
    with next(get_db()) as db:
        item = db.query(VaultItem).filter_by(chat_id=chat_id, keyword=keyword, item_type="sticker").first()
        if item:
            await update.message.reply_sticker(item.content)
        else:
            await update.message.reply_text("Sticker not found.")

# --- Excuses ---
async def save_excuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    keyword = context.args[0].lower()
    chat_id = update.effective_chat.id
    
    # Text from reply or args? Prompt says "Save by reply". 
    # Let's support both text reply or just saving the text after keyword?
    # Spec: "Save by reply: /exsave <keyword>"
    
    content = ""
    if update.message.reply_to_message and update.message.reply_to_message.text:
        content = update.message.reply_to_message.text
    else:
        # Fallback: if they typed /exsave lag It was lag
        if len(context.args) > 1:
            content = " ".join(context.args[1:])
        else:
            await update.message.reply_text("Reply to text or type text after keyword.")
            return

    with next(get_db()) as db:
        if db.query(VaultItem).filter_by(chat_id=chat_id, keyword=keyword).first():
            await update.message.reply_text("Keyword taken.")
            return
        
        item = VaultItem(chat_id=chat_id, keyword=keyword, item_type="excuse", content=content)
        db.add(item)
        db.commit()
        await update.message.reply_text("Excuse saved.")

async def random_excuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        item = db.query(VaultItem).filter_by(chat_id=chat_id, item_type="excuse").order_by(func.random()).first()
        if item:
            await update.message.reply_text(item.content)
        else:
            await update.message.reply_text("No excuses found. Add some!")