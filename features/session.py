from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_db
from models import GameSession, User, Chat, ChatMember, MatchStat
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm.attributes import flag_modified
import json

# --- Helpers ---
def get_session_keyboard(session_data, session_type):
    # Check if we should switch to "Game On" mode (Minimal UI)
    pA = session_data.get('pA')
    pB = session_data.get('pB')
    in_list = session_data.get('in', [])
    
    is_ready_1v1 = (
        session_type == "1v1" 
        and pB is not None 
        and pA in in_list 
        and pB in in_list
    )

    if is_ready_1v1:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🛑 Stop Session", callback_data="stop_session"),
             InlineKeyboardButton("📊 Update Match Stats", callback_data="stats_input")]
        ])

    # --- Standard RSVP Keyboard ---
    rsvp_row = [
        InlineKeyboardButton("✅ In", callback_data="rsvp_in"),
        InlineKeyboardButton("❌ Out", callback_data="rsvp_out"),
        InlineKeyboardButton("⌛ Pending", callback_data="rsvp_pending"),
    ]
    
    action_row = [InlineKeyboardButton("🛑 Stop Session", callback_data="stop_session")]
    if session_type == "1v1":
        action_row.append(InlineKeyboardButton("📊 Update Match Stats", callback_data="stats_input"))
    
    config_row = []
    if session_type == "1v1":
        config_row.append(InlineKeyboardButton("Change Opponent", callback_data="pick_opp"))
    elif session_type == "2v2":
        config_row.append(InlineKeyboardButton("Edit Squad", callback_data="edit_squad"))

    return InlineKeyboardMarkup([rsvp_row, action_row, config_row])

def format_session_text(session_data, db_session):
    pA = db_session.query(User).filter_by(user_id=session_data['pA']).first()
    pA_link = f"<a href='tg://user?id={pA.user_id}'>{pA.full_name}</a>" if pA else "Unknown"
    
    status_text = ""
    
    if session_data['type'] == '1v1':
        pB = db_session.query(User).filter_by(user_id=session_data.get('pB')).first()
        pB_link = f"<a href='tg://user?id={pB.user_id}'>{pB.full_name}</a>" if pB else "Opponent"
        header = f"🎮 <b>1v1 Session</b>\n{pA_link} 🆚 {pB_link}\n"
    else:
        squad_ids = session_data.get('squad', [])
        squad_names = []
        for uid in squad_ids:
            u = db_session.query(User).filter_by(user_id=uid).first()
            if u: squad_names.append(u.full_name)
        header = f"🎮 <b>2v2 Session</b>\nSquad: {', '.join(squad_names)}\n"

    in_list = []
    for uid in session_data.get('in', []):
        u = db_session.query(User).filter_by(user_id=uid).first()
        if u: in_list.append(u.full_name)
        
    out_list = []
    for uid in session_data.get('out', []):
        u = db_session.query(User).filter_by(user_id=uid).first()
        if u: out_list.append(u.full_name)
    
    status_text += f"\n✅ <b>In ({len(in_list)}):</b> {', '.join(in_list)}"
    status_text += f"\n❌ <b>Out ({len(out_list)}):</b> {', '.join(out_list)}"
    
    pending_list = []
    for uid, time_str in session_data.get('pending', {}).items():
        u = db_session.query(User).filter_by(user_id=int(uid)).first()
        if u: pending_list.append(f"{u.full_name} ({time_str})")
    
    status_text += f"\n⌛ <b>Pending:</b> {', '.join(pending_list)}"
    
    return header + status_text

# --- Commands ---

async def set_squad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Identify users from message entities (Mentions)
    ids = set()
    
    if update.message.entities:
        for entity in update.message.entities:
            if entity.type == "text_mention":
                # User object available directly
                ids.add(entity.user.id)
            elif entity.type == "mention":
                # Username mention - lookup in DB
                username = update.message.text[entity.offset:entity.offset+entity.length]
                username = username.lstrip('@')
                
                with next(get_db()) as db:
                    u = db.query(User).filter(User.username.ilike(username)).first()
                    if u: ids.add(u.user_id)
    
    if not ids:
         await update.message.reply_text("⚠️ Please mention the users you want in the squad.\nExample: <code>/setsquad @User1 @User2 @User3</code>", parse_mode="HTML")
         return

    with next(get_db()) as db:
        chat = db.query(Chat).filter_by(chat_id=chat_id).first()
        chat.primary_squad = list(ids)
        flag_modified(chat, "primary_squad")
        db.commit()
        
    await update.message.reply_text(f"✅ <b>Squad Saved!</b>\nAdded {len(ids)} players to 2v2 list.", parse_mode="HTML")


# --- Handlers ---

async def start_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("1v1", callback_data="new_1v1"), 
                 InlineKeyboardButton("2v2", callback_data="new_2v2")]]
    await update.message.reply_text("Select Mode:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat_id = update.effective_chat.id
    user_id = query.from_user.id
    msg_id = query.message.message_id
    
    await query.answer()

    with next(get_db()) as db:
        
        # --- NEW SESSION FLOW ---
        if data == "new_1v1":
            members = db.query(ChatMember).filter(ChatMember.chat_id==chat_id, ChatMember.user_id!=user_id).limit(20).all()
            buttons = []
            for m in members:
                u = db.query(User).filter_by(user_id=m.user_id).first()
                if u: buttons.append([InlineKeyboardButton(u.full_name, callback_data=f"sel_opp_{u.user_id}")])
            
            if not buttons:
                 await query.edit_message_text("No other members tracked yet. Ask them to speak!")
                 return

            await query.edit_message_text("Select Opponent:", reply_markup=InlineKeyboardMarkup(buttons))
            return

        if data.startswith("sel_opp_"):
            opp_id = int(data.split("_")[-1])
            ttl_min = db.query(Chat).filter_by(chat_id=chat_id).first().session_ttl
            expiry = datetime.now(timezone.utc) + timedelta(minutes=ttl_min)
            
            session_data = {
                "type": "1v1",
                "pA": user_id,
                "pB": opp_id,
                "in": [], "out": [], "pending": {}
            }
            
            await query.message.delete()
            sent_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=format_session_text(session_data, db),
                parse_mode="HTML",
                reply_markup=get_session_keyboard(session_data, "1v1")
            )
            
            new_sess = GameSession(
                message_id=sent_msg.message_id,
                chat_id=chat_id,
                session_type="1v1",
                initiator_id=user_id,
                expires_at=expiry,
                state_data=session_data
            )
            db.add(new_sess)
            db.commit()
            return

        if data == "new_2v2":
            chat = db.query(Chat).filter_by(chat_id=chat_id).first()
            squad = chat.primary_squad
            
            if not squad:
                await query.edit_message_text("⚠️ No squad set!\nUse <code>/setsquad @p1 @p2 @p3</code> to set it.", parse_mode="HTML")
                return
            
            ttl_min = chat.session_ttl
            expiry = datetime.now(timezone.utc) + timedelta(minutes=ttl_min)
            
            session_data = {
                "type": "2v2",
                "pA": user_id,
                "squad": squad,
                "in": [], "out": [], "pending": {}
            }
            
            await query.message.delete()
            sent_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=format_session_text(session_data, db),
                parse_mode="HTML",
                reply_markup=get_session_keyboard(session_data, "2v2")
            )
            
            new_sess = GameSession(
                message_id=sent_msg.message_id,
                chat_id=chat_id,
                session_type="2v2",
                initiator_id=user_id,
                expires_at=expiry,
                state_data=session_data
            )
            db.add(new_sess)
            db.commit()
            return

        # --- EXISTING SESSION INTERACTION ---
        session = db.query(GameSession).filter_by(message_id=msg_id).first()
        
        if not session:
            await query.message.edit_text("❌ Session not found or deleted.")
            return
            
        if datetime.now(timezone.utc) > session.expires_at:
            await query.message.edit_text("❌ Session Expired.")
            db.delete(session)
            db.commit()
            return

        s_data = dict(session.state_data)
        
        # --- PERMISSION CHECKS ---
        is_player = (user_id == s_data.get('pA') or user_id == s_data.get('pB'))
        
        if session.session_type == "1v1" and not is_player and data in ["stop_session", "stats_input"]:
             await context.bot.answer_callback_query(query.id, "🚫 Only players can do this.", show_alert=True)
             return

        if data == "pick_opp":
            if user_id != s_data.get('pA'):
                await context.bot.answer_callback_query(query.id, "🚫 Only the host can change opponent.", show_alert=True)
                return
            db.delete(session)
            db.commit()
            members = db.query(ChatMember).filter(ChatMember.chat_id==chat_id, ChatMember.user_id!=user_id).limit(20).all()
            buttons = []
            for m in members:
                u = db.query(User).filter_by(user_id=m.user_id).first()
                if u: buttons.append([InlineKeyboardButton(u.full_name, callback_data=f"sel_opp_{u.user_id}")])
            await query.edit_message_text("Select New Opponent:", reply_markup=InlineKeyboardMarkup(buttons))
            return
            
        if data == "edit_squad":
            await context.bot.answer_callback_query(query.id, "Use /setsquad @p1 @p2... to change squad", show_alert=True)
            return

        # RSVP Logic
        if data in ["rsvp_in", "rsvp_out"]:
            if user_id in s_data['in']: s_data['in'].remove(user_id)
            if user_id in s_data['out']: s_data['out'].remove(user_id)
            if str(user_id) in s_data['pending']: del s_data['pending'][str(user_id)]
            
            if data == "rsvp_in": s_data['in'].append(user_id)
            else: s_data['out'].append(user_id)
            
            session.state_data = s_data
            flag_modified(session, "state_data")
            db.commit()
            
            await query.message.edit_text(format_session_text(s_data, db), parse_mode="HTML", reply_markup=get_session_keyboard(s_data, session.session_type))
            return

        if data == "rsvp_pending":
            timers = [
                [InlineKeyboardButton("5m", callback_data="time_5m"), InlineKeyboardButton("10m", callback_data="time_10m")],
                [InlineKeyboardButton("15m", callback_data="time_15m"), InlineKeyboardButton("30m", callback_data="time_30m")],
                [InlineKeyboardButton("🔙 Back", callback_data="time_back")]
            ]
            await query.message.edit_reply_markup(InlineKeyboardMarkup(timers))
            return

        if data.startswith("time_"):
            if data == "time_back":
                await query.message.edit_reply_markup(get_session_keyboard(s_data, session.session_type))
                return
                
            label = data.split("_")[1] # 5m, 10m...
            
            if user_id in s_data['in']: s_data['in'].remove(user_id)
            if user_id in s_data['out']: s_data['out'].remove(user_id)
            
            if 'pending' not in s_data: s_data['pending'] = {}
            s_data['pending'][str(user_id)] = f"in {label}"
            
            session.state_data = s_data
            flag_modified(session, "state_data")
            db.commit()
            
            await query.message.edit_text(format_session_text(s_data, db), parse_mode="HTML", reply_markup=get_session_keyboard(s_data, session.session_type))
            return

        if data == "stop_session":
            await query.message.delete()
            db.delete(session)
            db.commit()
            return

        if data == "stats_input":
            from features.stats import start_stats_input
            await query.message.delete()
            db.delete(session)
            db.commit()
            await start_stats_input(context, chat_id, s_data['pA'], s_data.get('pB'))
            return
