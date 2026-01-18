from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from database import Base

class Chat(Base):
    __tablename__ = "chats"
    chat_id = Column(BigInteger, primary_key=True)
    title = Column(String)
    about_text = Column(Text, nullable=True)
    session_ttl = Column(Integer, default=360) # minutes (6 hours)
    primary_squad = Column(JSON, nullable=True) # List of user_ids for 2v2

class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    full_name = Column(String)
    username = Column(String, nullable=True)

class ChatMember(Base):
    __tablename__ = "chat_members"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id"))
    user_id = Column(BigInteger, ForeignKey("users.user_id"))
    is_excluded = Column(Boolean, default=False)
    last_active = Column(DateTime(timezone=True), server_default=func.now())

class VaultItem(Base):
    __tablename__ = "vault_items"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id"))
    keyword = Column(String)
    item_type = Column(String) # text, photo, video, sticker, excuse, etc.
    content = Column(String) # file_id or text content
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RoastLine(Base):
    __tablename__ = "roasts"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id"))
    text = Column(Text)

class GameSession(Base):
    __tablename__ = "sessions"
    message_id = Column(BigInteger, primary_key=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id"))
    session_type = Column(String) # 1v1, 2v2
    initiator_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    state_data = Column(JSON) # Stores players, rsvp status, timer choice, etc.

class MatchStat(Base):
    __tablename__ = "match_stats"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id"))
    player_a_id = Column(BigInteger, ForeignKey("users.user_id"))
    player_b_id = Column(BigInteger, ForeignKey("users.user_id"))
    score_a = Column(Integer)
    score_b = Column(Integer)
    is_draw = Column(Boolean, default=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())