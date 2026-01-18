from telegram import Update
from telegram.ext import ContextTypes
from database import get_db
from models import ChatMember, User, Chat
from utils import ensure_user_and_chat, get_chat_member_name

async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Middleware to track user activity."""
    if update.effective_chat.type in ['group', 'supergroup']:
        with next(get_db()) as db:
            ensure_user_and_chat(update, db)

async def mention_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        members = db.query(ChatMember).filter(
            ChatMember.chat_id == chat_id,
            ChatMember.is_excluded == False
        ).all()
        
        if not members:
            await update.message.reply_text("No one to mention yet.")
            return

        mentions = []
        for m in members:
            user = db.query(User).filter(User.user_id == m.user_id).first()
            if user:
                mentions.append(f"<a href='tg://user?id={user.user_id}'>{user.full_name}</a>")
        
        # Chunking to avoid limits
        chunk_size = 30 # conservative limit
        chunks = [mentions[i:i + chunk_size] for i in range(0, len(mentions), chunk_size)]
        
        for chunk in chunks:
            await update.message.reply_text(" ".join(chunk), parse_mode="HTML")

async def exclude_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    target_ids = []
    
    # Check reply
    if update.message.reply_to_message:
        target_ids.append(update.message.reply_to_message.from_user.id)
    
    # Check mentions in command args (if entities exist)
    if not target_ids and not context.args:
         await update.message.reply_text("Reply to a user or mention them to exclude.")
         return

    # Process entities if simple mention fails, but usually reply is best.
    # We will stick to Reply logic for strictness or @mention text parsing if needed.
    # Simple reply implementation as requested.

    with next(get_db()) as db:
        count = 0
        for uid in target_ids:
            member = db.query(ChatMember).filter_by(chat_id=chat_id, user_id=uid).first()
            if member:
                member.is_excluded = True
                count += 1
        db.commit()
        if count > 0:
            await update.message.reply_text(f"Excluded {count} member(s) from /all.")

async def include_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Logic similar to exclude, simplified for brevity: works on reply
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a user to include them.")
        return
        
    chat_id = update.effective_chat.id
    uid = update.message.reply_to_message.from_user.id
    
    with next(get_db()) as db:
        member = db.query(ChatMember).filter_by(chat_id=chat_id, user_id=uid).first()
        if member:
            member.is_excluded = False
            db.commit()
            await update.message.reply_text("User included back in /all.")

async def all_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        members = db.query(ChatMember).filter_by(chat_id=chat_id).all()
        total = len(members)
        excluded = [m for m in members if m.is_excluded]
        
        excluded_names = []
        for m in excluded:
            u = db.query(User).filter_by(user_id=m.user_id).first()
            excluded_names.append(u.full_name)
            
        msg = (f"📊 <b>Member Stats</b>\n"
               f"Total Tracked: {total}\n"
               f"Included: {total - len(excluded)}\n"
               f"Excluded: {len(excluded)}\n")
        
        if excluded_names:
            msg += f"Excluded: {', '.join(excluded_names)}"
            
        await update.message.reply_text(msg, parse_mode="HTML")

async def who_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        members = db.query(ChatMember).filter(ChatMember.chat_id == chat_id, ChatMember.is_excluded == False).all()
        names = []
        for m in members:
            u = db.query(User).filter_by(user_id=m.user_id).first()
            names.append(u.full_name)
    
    await update.message.reply_text(f"Will ping: {', '.join(names)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
<b>Marceline Commands</b>

<b>General</b>
/all - Mention everyone
/exclude - (Reply) Exclude user from /all
/include - (Reply) Include user back
/alllist - Show stats
/about - Bot info

<b>Vault (Save/Recall)</b>
/save [key] - (Reply) Save text/media
/q [key] - Recall saved item
/sshow, /sdel [key] - Manage saves
/ssave [key] - (Reply) Save sticker
/s [key] - Recall sticker
/stshow, /stdel [key] - Manage stickers
/exsave [key], /excuse - Excuses

<b>Roast</b>
/roast - Roast someone
/roastadd, /roastshow, /roastdel - Manage custom roasts

<b>Gaming</b>
/play - Start 1v1 or 2v2 session
/stats - Check stats
    """
    await update.message.reply_text(text, parse_mode="HTML")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        chat = db.query(Chat).filter_by(chat_id=chat_id).first()
        about = chat.about_text if chat and chat.about_text else "No about info set."
    await update.message.reply_text(f"ℹ️ <b>About:</b>\n{about}", parse_mode="HTML")

async def set_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return
    text = " ".join(context.args)
    chat_id = update.effective_chat.id
    from config import SUPERADMIN_ID
    if update.effective_user.id != SUPERADMIN_ID:
        return
        
    with next(get_db()) as db:
        chat = db.query(Chat).filter_by(chat_id=chat_id).first()
        if chat:
            chat.about_text = text
            db.commit()
            await update.message.reply_text("About updated.")