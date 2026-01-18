from telegram import Update
from telegram.ext import ContextTypes
from database import get_db
from models import VaultItem
from sqlalchemy import func

# --- Generic Save/Recall ---
async def save_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Reply to content with /save <keyword>")
        return
    keyword = context.args[0].lower()
    chat_id = update.effective_chat.id
    reply = update.message.reply_to_message
    
    content = None
    item_type = "text"
    
    if reply.text: content = reply.text
    elif reply.photo: item_type, content = "photo", reply.photo[-1].file_id
    elif reply.video: item_type, content = "video", reply.video.file_id
    elif reply.document: item_type, content = "document", reply.document.file_id
    elif reply.voice: item_type, content = "voice", reply.voice.file_id
    elif reply.audio: item_type, content = "audio", reply.audio.file_id
    else:
        await update.message.reply_text("Unsupported content.")
        return

    with next(get_db()) as db:
        if db.query(VaultItem).filter_by(chat_id=chat_id, keyword=keyword).first():
            await update.message.reply_text("Keyword taken.")
            return
        db.add(VaultItem(chat_id=chat_id, keyword=keyword, item_type=item_type, content=content))
        db.commit()
        await update.message.reply_text(f"Saved '{keyword}'.")

async def recall_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    keyword = context.args[0].lower()
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        item = db.query(VaultItem).filter_by(chat_id=chat_id, keyword=keyword).first()
        if not item:
            await update.message.reply_text("Not found.")
            return
        
        try:
            if item.item_type == "text": await update.message.reply_text(item.content)
            elif item.item_type == "photo": await update.message.reply_photo(item.content)
            elif item.item_type == "video": await update.message.reply_video(item.content)
            elif item.item_type == "document": await update.message.reply_document(item.content)
            elif item.item_type == "voice": await update.message.reply_voice(item.content)
            elif item.item_type == "audio": await update.message.reply_audio(item.content)
            elif item.item_type == "sticker": await update.message.reply_sticker(item.content)
        except Exception:
            await update.message.reply_text("Error sending media (file too old?).")

async def list_saves(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        items = db.query(VaultItem).filter(VaultItem.chat_id==chat_id, VaultItem.item_type.notin_(['sticker', 'excuse'])).all()
        if not items:
            await update.message.reply_text("No saves.")
            return
        lines = [f"{i.keyword} ({i.item_type})" for i in items]
        await update.message.reply_text("📁 <b>Saved Items:</b>\n" + "\n".join(lines), parse_mode="HTML")

async def delete_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    key = context.args[0].lower()
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        item = db.query(VaultItem).filter_by(chat_id=chat_id, keyword=key).first()
        if item:
            db.delete(item)
            db.commit()
            await update.message.reply_text(f"Deleted '{key}'.")
        else:
            await update.message.reply_text("Not found.")

# --- Stickers ---
async def save_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.sticker or not context.args:
        await update.message.reply_text("Reply to sticker with /ssave <key>")
        return
    keyword = context.args[0].lower()
    chat_id = update.effective_chat.id
    file_id = update.message.reply_to_message.sticker.file_id
    
    with next(get_db()) as db:
        if db.query(VaultItem).filter_by(chat_id=chat_id, keyword=keyword).first():
            await update.message.reply_text("Keyword taken.")
            return
        db.add(VaultItem(chat_id=chat_id, keyword=keyword, item_type="sticker", content=file_id))
        db.commit()
        await update.message.reply_text("Sticker saved.")

async def recall_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    keyword = context.args[0].lower()
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        item = db.query(VaultItem).filter_by(chat_id=chat_id, keyword=keyword, item_type="sticker").first()
        if item: await update.message.reply_sticker(item.content)
        else: await update.message.reply_text("Sticker not found.")

async def list_stickers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        items = db.query(VaultItem).filter_by(chat_id=chat_id, item_type="sticker").all()
        if not items:
            await update.message.reply_text("No saved stickers.")
            return
        lines = [f"• {i.keyword}" for i in items]
        await update.message.reply_text("🖼 <b>Stickers:</b>\n" + "\n".join(lines), parse_mode="HTML")

async def delete_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    key = context.args[0].lower()
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        item = db.query(VaultItem).filter_by(chat_id=chat_id, keyword=key, item_type="sticker").first()
        if item:
            db.delete(item)
            db.commit()
            await update.message.reply_text(f"Deleted sticker '{key}'.")
        else:
            await update.message.reply_text("Not found.")

# --- Excuses ---
async def save_excuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: 
        await update.message.reply_text("Usage: /exsave <keyword> [text] OR Reply with /exsave <keyword>")
        return
    keyword = context.args[0].lower()
    chat_id = update.effective_chat.id
    
    # 1. Check Reply content
    if update.message.reply_to_message and update.message.reply_to_message.text:
        content = update.message.reply_to_message.text
    # 2. Check inline arguments
    elif len(context.args) > 1:
        content = " ".join(context.args[1:])
    else:
        await update.message.reply_text("Provide text or reply to a message.")
        return

    with next(get_db()) as db:
        if db.query(VaultItem).filter_by(chat_id=chat_id, keyword=keyword).first():
            await update.message.reply_text("Keyword taken.")
            return
        db.add(VaultItem(chat_id=chat_id, keyword=keyword, item_type="excuse", content=content))
        db.commit()
        await update.message.reply_text("Excuse saved.")

async def random_excuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        item = db.query(VaultItem).filter_by(chat_id=chat_id, item_type="excuse").order_by(func.random()).first()
        if item: await update.message.reply_text(item.content)
        else: await update.message.reply_text("No excuses found.")

async def list_excuses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        items = db.query(VaultItem).filter_by(chat_id=chat_id, item_type="excuse").all()
        if not items:
            await update.message.reply_text("No excuses saved.")
            return
        lines = [f"{i.keyword}: {i.content[:30]}..." for i in items]
        await update.message.reply_text("🤥 <b>Excuses:</b>\n" + "\n".join(lines), parse_mode="HTML")

async def delete_excuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    key = context.args[0].lower()
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        item = db.query(VaultItem).filter_by(chat_id=chat_id, keyword=key, item_type="excuse").first()
        if item:
            db.delete(item)
            db.commit()
            await update.message.reply_text(f"Deleted excuse '{key}'.")
        else:
            await update.message.reply_text("Not found.")
