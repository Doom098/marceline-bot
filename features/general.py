from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
from telegram.ext import ContextTypes
from database import get_db
from models import ChatMember, User, Chat, BotSetting
from utils import ensure_user_and_chat, get_chat_member_name
from config import SUPERADMIN_ID

# --- CONSTANTS ---
FULL_COMMAND_LIST = """<b>🤖 Marceline Commands</b>

<b>🎮 Gaming</b>
/play - Start 1v1 / 2v2 Session
/setsquad - Set 2v2 Primary Squad
/stats - View Leaderboards
/stats @user - View Player Profile

<b>📣 Group</b>
/all - Mention all members
/exclude - Hide me from /all
/include - Show me in /all
/alllist - Member stats
/whoall - Who gets pinged

<b>🔐 Vault</b>
/save [key] - Save (Reply)
/q [key] - Recall
/sshow, /sdel - Manage saves
/ssave [key] - Save sticker
/s [key] - Recall sticker
/stshow, /stdel - Manage stickers
/exsave [key] - Save excuse
/excuse - Get excuse
/exshow, /exdel - Manage excuses

<b>🔥 Fun</b>
/roast - Roast someone
/roastadd - Add roast
/roastshow - List roasts
/roastdel - Delete roast

<b>ℹ️ Info</b>
/help - Show this list
/about - Group info"""

async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Middleware to track user activity."""
    if update.effective_chat.type in ['group', 'supergroup']:
        with next(get_db()) as db:
            ensure_user_and_chat(update, db)

# --- Helpers to get Settings ---
def get_setting(db, key, default_val):
    setting = db.query(BotSetting).filter_by(key=key).first()
    return setting.value if setting else default_val

def set_setting(db, key, val):
    setting = db.query(BotSetting).filter_by(key=key).first()
    if not setting:
        setting = BotSetting(key=key, value=val)
        db.add(setting)
    else:
        setting.value = val
    db.commit()

# --- Start & DM Menu ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        with next(get_db()) as db:
            repo_url = get_setting(db, "dm_repo", "https://github.com/Doom098/marceline-bot")
        
        keyboard = [
            [InlineKeyboardButton("📜 Commands", callback_data="dm_commands")],
            [InlineKeyboardButton("ℹ️ About", callback_data="dm_about")],
            [InlineKeyboardButton("📦 Repo", url=repo_url)]
        ]
        await update.message.reply_text(
            "👋 <b>I'm Marceline!</b>\nYour Telegram Group Helper.\n\nChoose an option:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("I'm ready! Use /help to see what I can do.")

async def handle_dm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    
    with next(get_db()) as db:
        repo_url = get_setting(db, "dm_repo", "https://github.com/Doom098/marceline-bot")
        
        # Updated Default Texts using the Full List
        default_cmds = FULL_COMMAND_LIST
        default_about = "<b>Marceline Bot</b>\nBuilt with Python."
        
        if data == "dm_commands":
            text = get_setting(db, "dm_commands", default_cmds)
            await query.message.edit_text(
                text, 
                parse_mode="HTML", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="dm_back")]])
            )

        elif data == "dm_about":
            text = get_setting(db, "dm_about", default_about)
            await query.message.edit_text(
                text, 
                parse_mode="HTML", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="dm_back")]])
            )

        elif data == "dm_back":
            keyboard = [
                [InlineKeyboardButton("📜 Commands", callback_data="dm_commands")],
                [InlineKeyboardButton("ℹ️ About", callback_data="dm_about")],
                [InlineKeyboardButton("📦 Repo", url=repo_url)]
            ]
            await query.message.edit_text(
                "👋 <b>I'm Marceline!</b>\nYour Telegram Group Helper.\n\nChoose an option:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )

# --- Super Admin Setters ---
async def set_dm_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPERADMIN_ID: return
    if not context.args:
        await update.message.reply_text("Usage: /setdmcommands <text (supports HTML)>")
        return
    
    text = update.message.text.split(" ", 1)[1]
    with next(get_db()) as db:
        set_setting(db, "dm_commands", text)
    await update.message.reply_text("✅ Commands menu updated.")

async def set_dm_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPERADMIN_ID: return
    if not context.args:
        await update.message.reply_text("Usage: /setdmabout <text (supports HTML)>")
        return
        
    text = update.message.text.split(" ", 1)[1]
    with next(get_db()) as db:
        set_setting(db, "dm_about", text)
    await update.message.reply_text("✅ About menu updated.")

async def set_dm_repo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != SUPERADMIN_ID: return
    if not context.args:
        await update.message.reply_text("Usage: /setdmrepo <url>")
        return
        
    url = context.args[0]
    with next(get_db()) as db:
        set_setting(db, "dm_repo", url)
    await update.message.reply_text("✅ Repo URL updated.")

# --- Existing Group Logic ---
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
    targets = []
    if update.message.reply_to_message:
        targets.append(update.message.reply_to_message.from_user)
    
    if update.message.entities:
        for entity in update.message.entities:
            if entity.type == "text_mention":
                targets.append(entity.user)
            elif entity.type == "mention":
                username = update.message.text[entity.offset:entity.offset+entity.length].lstrip('@')
                user = db.query(User).filter(User.username.ilike(username)).first()
                if user:
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
        if count > 0: await update.message.reply_text(f"🚫 Excluded: {', '.join(names)}")
        else: await update.message.reply_text("Users not found.")

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
        if count > 0: await update.message.reply_text(f"✅ Included: {', '.join(names)}")

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
            
        msg = (f"📊 <b>Member Stats</b>\nTotal: {total}\nIncluded: {total - len(excluded)}\nExcluded: {len(excluded)}\n")
        if excluded_names: msg += f"Names: {', '.join(excluded_names)}"
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
    # Updated to show full list in groups
    await update.message.reply_text(FULL_COMMAND_LIST, parse_mode="HTML")

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
    if update.effective_user.id != SUPERADMIN_ID: return
    with next(get_db()) as db:
        chat = db.query(Chat).filter_by(chat_id=chat_id).first()
        if chat:
            chat.about_text = text
            db.commit()
            await update.message.reply_text("About updated.")
