from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_db
from models import User, MatchStat
from sqlalchemy import func, or_, and_
from datetime import datetime, timezone
import calendar

# --- Helper: Calculate Leaderboard Data ---
def calculate_leaderboard(db, chat_id, since_date=None):
    query = db.query(MatchStat).filter(MatchStat.chat_id == chat_id)
    if since_date:
        query = query.filter(MatchStat.timestamp >= since_date)
    
    stats = query.all()
    data = {} 
    
    for s in stats:
        # A
        if s.player_a_id not in data: data[s.player_a_id] = {'wins': 0, 'draws': 0, 'total': 0}
        data[s.player_a_id]['total'] += 1
        if s.score_a > s.score_b: data[s.player_a_id]['wins'] += 1
        if s.is_draw: data[s.player_a_id]['draws'] += 1
        
        # B
        if s.player_b_id not in data: data[s.player_b_id] = {'wins': 0, 'draws': 0, 'total': 0}
        data[s.player_b_id]['total'] += 1
        if s.score_b > s.score_a: data[s.player_b_id]['wins'] += 1
        if s.is_draw: data[s.player_b_id]['draws'] += 1
        
    leaderboard = []
    for uid, d in data.items():
        if d['total'] < 3: continue # Min matches
        win_pct = (d['wins'] + 0.5 * d['draws']) / d['total'] * 100
        user = db.query(User).filter_by(user_id=uid).first()
        name = user.full_name if user else str(uid)
        leaderboard.append({'name': name, 'pct': win_pct, 'w': d['wins'], 'd': d['draws'], 't': d['total']})
        
    leaderboard.sort(key=lambda x: x['pct'], reverse=True)
    return leaderboard

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # If @user argument provided -> Show Individual Stats
    if context.args or (update.message and update.message.entities):
        await show_individual_stats(update, context)
        return

    # Default -> Show Leaderboard Menu
    keyboard = [[InlineKeyboardButton("📅 Monthly", callback_data="lb_monthly"),
                 InlineKeyboardButton("♾️ Overall", callback_data="lb_overall")]]
    
    await update.message.reply_text("🏆 <b>Leaderboards</b>\nSelect duration:", 
                                    reply_markup=InlineKeyboardMarkup(keyboard),
                                    parse_mode="HTML")

async def show_individual_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    target_id = None
    target_name = "User"

    # Identify user
    from features.general import get_target_users
    with next(get_db()) as db:
        targets = await get_target_users(update, context, db)
        if targets:
            target_id = targets[0].id
            target_name = targets[0].full_name
        else:
            # Self stats?
            target_id = update.effective_user.id
            target_name = update.effective_user.full_name
            
        if not target_id: return

        # Fetch Stats
        matches = db.query(MatchStat).filter(
            MatchStat.chat_id == chat_id,
            or_(MatchStat.player_a_id == target_id, MatchStat.player_b_id == target_id)
        ).all()
        
        if not matches:
            await update.message.reply_text(f"No stats for {target_name}.")
            return

        total = 0; wins = 0; losses = 0; draws = 0
        opponents = {} # uid -> {total, w, l, d}

        for m in matches:
            total += 1
            is_a = (m.player_a_id == target_id)
            opp_id = m.player_b_id if is_a else m.player_a_id
            
            # Setup opponent dict
            if opp_id not in opponents: opponents[opp_id] = {'t':0, 'w':0, 'l':0, 'd':0}
            opponents[opp_id]['t'] += 1

            if m.is_draw:
                draws += 1
                opponents[opp_id]['d'] += 1
            elif (is_a and m.score_a > m.score_b) or (not is_a and m.score_b > m.score_a):
                wins += 1
                opponents[opp_id]['w'] += 1
            else:
                losses += 1
                opponents[opp_id]['l'] += 1

        # Calc Favorite (Highest Win %)
        fav_opp = "None"
        best_pct = -1
        
        detail_txt = ""
        for oid, d in opponents.items():
            u = db.query(User).filter_by(user_id=oid).first()
            name = u.full_name if u else "Unknown"
            
            # Details
            detail_txt += f"vs {name}: {d['t']} (W{d['w']}/L{d['l']}/D{d['d']})\n"
            
            # Fav Calc (Min 3 games)
            if d['t'] >= 3:
                pct = (d['w'] / d['t']) * 100
                if pct > best_pct:
                    best_pct = pct
                    fav_opp = f"{name} ({pct:.0f}%)"

        msg = (f"👤 <b>Player Stats: {target_name}</b>\n"
               f"Total: {total} | W: {wins} | L: {losses} | D: {draws}\n"
               f"🦆 <b>Favorite Opponent:</b> {fav_opp}\n\n"
               f"⚔️ <b>Head-to-Head:</b>\n{detail_txt}")
        
        await update.message.reply_text(msg, parse_mode="HTML")

async def handle_lb_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat_id = update.effective_chat.id
    
    with next(get_db()) as db:
        if data == "lb_monthly":
            now = datetime.now(timezone.utc)
            start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            lb = calculate_leaderboard(db, chat_id, start_month)
            title = f"📅 <b>Monthly Leaderboard ({now.strftime('%B')})</b>"
        else:
            lb = calculate_leaderboard(db, chat_id, None)
            title = "♾️ <b>Overall Leaderboard</b>"
            
        if not lb:
            await query.edit_message_text(f"{title}\nNo stats yet.", parse_mode="HTML")
            return

        txt = f"{title}\n\n"
        for i, row in enumerate(lb, 1):
            icon = "🏆 " if i == 1 else f"{i}. "
            txt += f"{icon}<b>{row['name']}</b>: {row['pct']:.1f}% ({row['w']}W/{row['d']}D/{row['t']}T)\n"
            
        await query.edit_message_text(txt, parse_mode="HTML")
