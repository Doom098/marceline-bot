from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_db
from models import GameSession, User, Chat, ChatMember
from datetime import datetime, timedelta

from utils import ensure_user_and_chat  # ✅ added

# --- Helpers ---
def get_session_keyboard(session_data, session_type):
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
    pA = db_session.query(User).filter_by(user_id=session_data["pA"]).first()
    pA_name = pA.full_name if pA else "Unknown"

    if session_data["type"] == "1v1":
        pB = db_session.query(User).filter_by(user_id=session_data.get("pB")).first()
        pB_name = pB.full_name if pB else "Opponent"
        header = f"🎮 <b>1v1 Session</b>\n{pA_name} 🆚 {pB_name}\n"
    else:
        squad_ids = session_data.get("squad", [])
        squad_names = []
        for uid in squad_ids:
            u = db_session.query(User).filter_by(user_id=uid).first()
            if u:
                squad_names.append(u.full_name)
        header = f"🎮 <b>2v2 Session</b>\nSquad: {', '.join(squad_names)}\n"

    # Build lists safely (skip unknowns)
    in_list = []
    for uid in session_data.get("in", []):
        u = db_session.query(User).filter_by(user_id=uid).first()
        if u:
            in_list.append(u.full_name)

    out_list = []
    for uid in session_data.get("out", []):
        u = db_session.query(User).filter_by(user_id=uid).first()
        if u:
            out_list.append(u.full_name)

    status_text = ""
    status_text += f"\n✅ <b>In ({len(in_list)}):</b> {', '.join(in_list)}"
    status_text += f"\n❌ <b>Out ({len(out_list)}):</b> {', '.join(out_list)}"

    pending_list = []
    for uid_str, time_str in session_data.get("pending", {}).items():
        try:
            uid = int(uid_str)
        except ValueError:
            continue
        u = db_session.query(User).filter_by(user_id=uid).first()
        if u:
            pending_list.append(f"{u.full_name} ({time_str})")

    status_text += f"\n⌛ <b>Pending:</b> {', '.join(pending_list)}"

    return header + status_text


# --- Handlers ---

async def start_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("1v1", callback_data="new_1v1"),
            InlineKeyboardButton("2v2", callback_data="new_2v2"),
        ]
    ]
    await update.message.reply_text("Select Mode:", reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.message:
        return

    data = query.data or ""
    chat_id = update.effective_chat.id
    user_id = query.from_user.id
    msg_id = query.message.message_id

    await query.answer()

    with next(get_db()) as db:
        # ✅ Track user/chat even on button clicks
        ensure_user_and_chat(update, db)

        # --- NEW SESSION FLOW ---
        if data == "new_1v1":
            members = (
                db.query(ChatMember)
                .filter(ChatMember.chat_id == chat_id, ChatMember.user_id != user_id)
                .order_by(ChatMember.last_active.desc())
                .limit(50)
                .all()
            )

            if not members:
                await query.edit_message_text(
                    "No members found yet.\n\n"
                    "✅ Ask your friends to send ONE message or run /play once so I can track them.\n"
                    "Then try /play again."
                )
                return

            buttons = []
            for m in members:
                u = db.query(User).filter_by(user_id=m.user_id).first()
                if u:
                    buttons.append([InlineKeyboardButton(u.full_name, callback_data=f"sel_opp_{u.user_id}")])

            await query.edit_message_text("Select Opponent:", reply_markup=InlineKeyboardMarkup(buttons))
            return

        if data.startswith("sel_opp_"):
            opp_id = int(data.split("_")[-1])

            chat = db.query(Chat).filter_by(chat_id=chat_id).first()
            ttl_min = chat.session_ttl if chat else 360  # fallback 6 hours (minutes) if missing
            expiry = datetime.utcnow() + timedelta(minutes=ttl_min)

            session_data = {
                "type": "1v1",
                "pA": user_id,
                "pB": opp_id,
                "in": [],
                "out": [],
                "pending": {},
            }

            await query.message.delete()  # clean up picker

            sent_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=format_session_text(session_data, db),
                parse_mode="HTML",
                reply_markup=get_session_keyboard(session_data, "1v1"),
            )

            new_sess = GameSession(
                message_id=sent_msg.message_id,
                chat_id=chat_id,
                session_type="1v1",
                initiator_id=user_id,
                expires_at=expiry,
                state_data=session_data,
            )
            db.add(new_sess)
            db.commit()
            return

        if data == "new_2v2":
            chat = db.query(Chat).filter_by(chat_id=chat_id).first()
            squad = chat.primary_squad if chat else None

            if not squad:
                await query.edit_message_text(
                    "No primary squad set yet.\n"
                    "This will be implemented when we add the 2v2 squad setup/edit flow."
                )
                return

            ttl_min = chat.session_ttl
            expiry = datetime.utcnow() + timedelta(minutes=ttl_min)

            session_data = {
                "type": "2v2",
                "pA": user_id,
                "squad": squad,
                "in": [],
                "out": [],
                "pending": {},
            }

            await query.message.delete()
            sent_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=format_session_text(session_data, db),
                parse_mode="HTML",
                reply_markup=get_session_keyboard(session_data, "2v2"),
            )

            new_sess = GameSession(
                message_id=sent_msg.message_id,
                chat_id=chat_id,
                session_type="2v2",
                initiator_id=user_id,
                expires_at=expiry,
                state_data=session_data,
            )
            db.add(new_sess)
            db.commit()
            return

        # --- EXISTING SESSION INTERACTION ---
        session = db.query(GameSession).filter_by(message_id=msg_id).first()
        if not session:
            await query.message.edit_text("❌ Session not found or deleted from DB.")
            return

        if datetime.utcnow() > session.expires_at:
            await query.message.edit_text("❌ Session Expired.")
            db.delete(session)
            db.commit()
            return

        s_data = dict(session.state_data)

        # RSVP Logic
        if data in ["rsvp_in", "rsvp_out"]:
            if user_id in s_data["in"]:
                s_data["in"].remove(user_id)
            if user_id in s_data["out"]:
                s_data["out"].remove(user_id)
            if str(user_id) in s_data["pending"]:
                del s_data["pending"][str(user_id)]

            if data == "rsvp_in":
                s_data["in"].append(user_id)
            else:
                s_data["out"].append(user_id)

            session.state_data = s_data
            db.commit()
            await query.message.edit_text(
                format_session_text(s_data, db),
                parse_mode="HTML",
                reply_markup=get_session_keyboard(s_data, session.session_type),
            )
            return

        if data == "rsvp_pending":
            timers = [
                [
                    InlineKeyboardButton("5m", callback_data="time_5m"),
                    InlineKeyboardButton("10m", callback_data="time_10m"),
                ],
                [
                    InlineKeyboardButton("15m", callback_data="time_15m"),
                    InlineKeyboardButton("30m", callback_data="time_30m"),
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="time_back")],
            ]
            await query.message.edit_reply_markup(InlineKeyboardMarkup(timers))
            return

        if data.startswith("time_"):
            if data == "time_back":
                await query.message.edit_reply_markup(get_session_keyboard(s_data, session.session_type))
                return

            label = data.split("_")[1]  # 5m, 10m...
            if user_id in s_data["in"]:
                s_data["in"].remove(user_id)
            if user_id in s_data["out"]:
                s_data["out"].remove(user_id)

            s_data["pending"][str(user_id)] = f"in {label}"

            session.state_data = s_data
            db.commit()
            await query.message.edit_text(
                format_session_text(s_data, db),
                parse_mode="HTML",
                reply_markup=get_session_keyboard(s_data, session.session_type),
            )
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
            await start_stats_input(context, chat_id, s_data["pA"], s_data["pB"])
            return
