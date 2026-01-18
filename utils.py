from telegram import Update, User as TgUser
from sqlalchemy.orm import Session
from models import User, Chat, ChatMember
from datetime import datetime

def ensure_user_and_chat(update: Update, db: Session):
    """
    Updates User and Chat tables, and links them in ChatMember.
    Call this at the start of most handlers.
    """
    if not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # 1. Ensure Chat
    chat = db.query(Chat).filter_by(chat_id=chat_id).first()
    if not chat:
        chat = Chat(chat_id=chat_id, title=update.effective_chat.title)
        db.add(chat)
    else:
        # Update title if changed
        if chat.title != update.effective_chat.title:
            chat.title = update.effective_chat.title

    # 2. Ensure User
    user = db.query(User).filter_by(user_id=user_id).first()
    full_name = update.effective_user.full_name
    username = update.effective_user.username
    
    if not user:
        user = User(user_id=user_id, full_name=full_name, username=username)
        db.add(user)
    else:
        # Update details if changed
        if user.full_name != full_name or user.username != username:
            user.full_name = full_name
            user.username = username

    # 3. Ensure ChatMember Link & Update Activity
    member = db.query(ChatMember).filter_by(chat_id=chat_id, user_id=user_id).first()
    if not member:
        member = ChatMember(chat_id=chat_id, user_id=user_id)
        db.add(member)
    
    member.last_active = datetime.now()
    
    db.commit()

def get_chat_member_name(user: User):
    if user.username:
        return f"@{user.username}"
    return user.full_name

async def safe_delete(context, chat_id, message_id):
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass