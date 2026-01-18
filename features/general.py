from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
from telegram.ext import ContextTypes
from database import get_db
from models import ChatMember, User, Chat
from utils import ensure_user_and_chat, get_chat_member_name

async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Middleware to track user activity."""
    if update.effective_chat.type in ['group', 'supergroup']:
        with next(get_db()) as db:
            ensure_user_and_chat(update, db)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Personal DM Flow
    if update.effective_chat.type == 'private':
        keyboard = [
            [InlineKeyboardButton("📜 Commands", callback_data="dm_commands")],
            [InlineKeyboardButton("ℹ️ About", callback_data="dm_about")],
            [InlineKeyboardButton("📦 Repo", url="https://github.com/Doom098/marceline-bot")]
        ]
        await update.message.reply_text(
            "👋 <b>I'm Marceline!</b>\nYour Telegram Group Helper.\n\nChoose an option:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    else:
        # Group Flow
        await update.message.reply_text("I'm ready! Use /help to see what I can do.")

async def handle_dm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    
    if data == "dm_commands":
        # Reuse help text but formatted for DM
        text = """
<b>🤖 Command List</b>

<b>Group Basics</b>
/all - Mention everyone
/exclude @user - Stop mentioning someone
/include @user - Include them again
/alllist - Show mention stats

<b>Vault</b>
/save [key] - Save (Reply)
/q [key] - Recall
/exsave [key] - Save Excuse (Reply)
/excuse - Random Excuse
/ssave [key] - Save Sticker (Reply)
/s [key] - Recall Sticker

<b>Fun & Games</b>
/roast - Burn someone
/play - Start 1v1 / 2v2
/stats - Leaderboards
/stats @user - Player Profile
"""
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="dm_back")]]))

    elif data == "dm_about":
        text = "<b>Marceline Bot</b>\nBuilt with Python + SQLAlchemy.\nManaged by @Doom098."
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="dm_back")]]))

    elif data == "dm_back":
        # Restore Main Menu
        keyboard = [
            [InlineKeyboardButton("📜 Commands", callback_data="dm_commands")],
            [InlineKeyboardButton("ℹ️ About", callback_data="dm_about")],
            [InlineKeyboardButton("📦 Repo", url="https://github.com/Doom098/marceline-bot")]
        ]
        await query.message.edit_text(
            "👋 <b>I'm Marceline!</b>\nYour Telegram Group Helper.\n\nChoose an option:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

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
        
        chunk_size = 30 
        chunks = [mentions[i:i + chunk_size] for i in range(0, len(mentions), chunk_size)]
        
        for chunk in chunks:
            await update.message.reply_text(" ".join(chunk), parse_mode="HTML")

async def get_target_users(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Helper to find users from replies OR mentions"""
    targets = []
    
    # 1. Reply
    if update.message.reply_to_message:
        targets.append(update.message.reply_to_message.from_user)
    
    # 2. Mentions (Entities)
    if update.message.entities:
        for entity in update.message.entities:
            if entity.type == "text_mention":
                targets.append(entity.user)
            elif entity.type == "mention":
                # Username lookup
                username = update.message.text[entity.offset:entity.offset+entity.length].lstrip('@')
                user = db.query(User).filter(User.username.ilike(username)).first()
                if user:
                    # Create a dummy object with id/name for consistency
                    class MockUser:
                        def __init__(self, uid, name):
                            self.id = uid
                            self.full_name = name
                    targets.append(MockUser(user.user_id, user.full_name))
    
    return targets

async def exclude_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        targets = await get_target_users(update, context, db)
        
        if not targets:
            await update.message.reply_text("Reply to or mention users to exclude.")
            return

        count = 0
        names = []
        for t in targets:
            member = db.query(ChatMember).filter_by(chat_id=chat_id, user_id=t.id).first()
            if member:
                member.is_excluded = True
                count += 1
                names.append(t.full_name)
        
        db.commit()
        if count > 0:
            await update.message.reply_text(f"🚫 Excluded: {', '.join(names)}")
        else:
            await update.message.reply_text("Users not found in tracking list.")

async def include_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        targets = await get_target_users(update, context, db)
        
        if not targets:
            await update.message.reply_text("Reply to or mention users to include.")
            return

        count = 0
        names = []
        for t in targets:
            member = db.query(ChatMember).filter_by(chat_id=chat_id, user_id=t.id).first()
            if member:
                member.is_excluded = False
                count += 1
                names.append(t.full_name)
        
        db.commit()
        if count > 0:
            await update.message.reply_text(f"✅ Included: {', '.join(names)}")

async def all_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        members = db.query(ChatMember).filter_by(chat_id=chat_id).all()
        total = len(members)
        excluded = [m for m in members if m.is_excluded]
        
        excluded_names = []
        for m in excluded:
            u = db.query(User).filter_by(user_id=m.user_id).first()
            if u: excluded_names.append(u.full_name)
            
        msg = (f"📊 <b>Member Stats</b>\n"
               f"Total Tracked: {total}\n"
               f"Included: {total - len(excluded)}\n"
               f"Excluded: {len(excluded)}\n")
        
        if excluded_names:
            msg += f"Names: {', '.join(excluded_names)}"
            
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
/exclude @user - Exclude from /all
/include @user - Include back
/alllist - Show stats

<b>Vault</b>
/save [key] - (Reply) Save media/text
/q [key] - Recall
/ssave [key] - (Reply) Save sticker
/s [key] - Recall sticker
/exsave [key] - Save excuse (Reply or Type)
/excuse - Random excuse
/exshow, /exdel - Manage excuses
/stshow, /stdel - Manage stickers

<b>Gaming</b>
/play - Start session
/stats - Leaderboards
/stats @user - Player Profile
    """
    await update.message.reply_text(text, parse_mode="HTML")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with next(get_db()) as db:
        chat = db.query(Chat).filter_by(chat_id=chat_id).first()
        about = chat.about_text if chat and chat.about_text else "No about info set."
    await update.message.reply_text(f"ℹ️ <b>About:</b>\n{about}", parse_mode="HTML")

async def set_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    text = " ".join(context.args)
    chat_id = update.effective_chat.id
    from config import SUPERADMIN_ID
    if update.effective_user.id != SUPERADMIN_ID: return
    with next(get_db()) as db:
        chat = db.query(Chat).filter_by(chat_id=chat_id).first()
        if chat:
            chat.about_text = text
            db.commit()
            await update.message.reply_text("About updated.")
