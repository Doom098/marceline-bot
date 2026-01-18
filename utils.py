from telegram import Update
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from models import User, Chat, ChatMember
from datetime import datetime

def ensure_user_and_chat(update: Update, db: Session):
    """
    Updates User and Chat tables safely. 
    Handles race conditions/errors by rolling back if needed.
    """
    if not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    chat_title = update.effective_chat.title or "Unknown Chat"
    
    user = update.effective_user
    full_name = user.full_name
    username = user.username

    try:
        # 1. Ensure Chat
        chat_db = db.query(Chat).filter_by(chat_id=chat_id).first()
        if not chat_db:
            chat_db = Chat(chat_id=chat_id, title=chat_title)
            db.add(chat_db)
        else:
            if chat_db.title != chat_title:
                chat_db.title = chat_title

        # 2. Ensure User
        user_db = db.query(User).filter_by(user_id=user_id).first()
        if not user_db:
            user_db = User(user_id=user_id, full_name=full_name, username=username)
            db.add(user_db)
        else:
            if user_db.full_name != full_name or user_db.username != username:
                user_db.full_name = full_name
                user_db.username = username

        # 3. Ensure Member Link
        member = db.query(ChatMember).filter_by(chat_id=chat_id, user_id=user_id).first()
        if not member:
            member = ChatMember(chat_id=chat_id, user_id=user_id)
            db.add(member)
        
        member.last_active = datetime.now()
        
        db.commit()
    except SQLAlchemyError:
        # If anything goes wrong (race condition), rollback to keep session clean
        db.rollback()

def get_chat_member_name(user: User):
    if user.username:
        return f"@{user.username}"
    return user.full_name

async def safe_delete(context, chat_id, message_id):
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass
