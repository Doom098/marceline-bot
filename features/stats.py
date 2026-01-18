from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_db
from models import User, MatchStat
from sqlalchemy import func, or_
from datetime import datetime, timezone

# =========================================
#  PART 1: STATS INPUT (Entering Scores)
# =========================================

async def start_stats_input(context, chat_id, pA_id, pB_id):
    # Fetch names immediately
    with next(get_db()) as db:
        uA = db.query(User).filter_by(user_id=pA_id).first()
        uB = db.query(User).filter_by(user_id=pB_id).first()
        name_A = uA.full_name if uA else "Player A"
        name_B = uB.full_name if uB else "Player B"

    # Store names in context for the next steps
    context.chat_data['current_stats'] = {
        'pA': pA_id, 'pB': pB_id, 
        'nameA': name_A, 'nameB': name_B,
        'chat_id': chat_id
    }
    
    # Send "Matches Played?"
    keyboard = []
    row1 = [InlineKeyboardButton(str(i), callback_data=f"stat_matches_{i}") for i in range(1, 6)]
    row2 = [InlineKeyboardButton(str(i), callback_data=f"stat_matches_{i}") for i in range(6, 11)]
    keyboard = [row1, row2]
    
    await context.bot.send_message(
        chat_id=chat_id, 
        text=f"📊 <b>Stats Input</b>\n{name_A} vs {name_B}\n\nHow many matches played in total?", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def handle_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    
    if 'current_stats' not in context.chat_data:
        await query.message.edit_text("❌ Stats session expired. Please start over.")
        return

    stats = context.chat_data['current_stats']
    name_A = stats['nameA']
    name_B = stats['nameB']

    if data.startswith("stat_matches_"):
        val = int(data.split("_")[-1])
        stats['played'] = val
        
        # Ask Wins for Player A
        keys = [InlineKeyboardButton(str(i), callback_data=f"stat_winsA_{i}") for i in range(val + 1)]
        rows = [keys[i:i+5] for i in range(0, len(keys), 5)]
        
        await query.message.edit_text(
            f"Matches Played: {val}\n\n🏆 How many wins for <b>{name_A}</b>?", 
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode="HTML"
        )
        context.chat_data['current_stats'] = stats
        return

    if data.startswith("stat_winsA_"):
        val = int(data.split("_")[-1])
        stats['winsA'] = val
        
        # Ask Wins for Player B
        remaining = stats['played'] - val
        keys = [InlineKeyboardButton(str(i), callback_data=f"stat_winsB_{i}") for i in range(remaining + 1)]
        rows = [keys[i:i+5] for i in range(0, len(keys), 5)]
        
        await query.message.edit_text(
            f"Matches: {stats['played']}\n{name_A} Wins: {val}\n\n🏆 How many wins for <b>{name_B}</b>?", 
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode="HTML"
        )
        context.chat_data['current_stats'] = stats
        return

    if data.startswith("stat_winsB_"):
        val = int(data.split("_")[-1])
        stats['winsB'] = val
        
        # Calculate Draws
        draws = stats['played'] - stats['winsA'] - stats['winsB']
        stats['draws'] = draws
        
        # Save to DB
        with next(get_db()) as db:
            # Insert Wins A
            for _ in range(stats['winsA']):
                db.add(MatchStat(chat_id=stats['chat_id'], player_a_id=stats['pA'], player_b_id=stats['pB'], score_a=1, score_b=0, is_draw=False))
            # Insert Wins B
            for _ in range(stats['winsB']):
                db.add(MatchStat(chat_id=stats['chat_id'], player_a_id=stats['pA'], player_b_id=stats['pB'], score_a=0, score_b=1, is_draw=False))
            # Insert Draws
            for _ in range(stats['draws']):
                db.add(MatchStat(chat_id=stats['chat_id'], player_a_id=stats['pA'], player_b_id=stats['pB'], score_a=0, score_b=0, is_draw=True))
            
            db.commit()
            
            receipt = (f"✅ <b>Stats Saved</b>\n"
                       f"👤 {name_A} vs 👤 {name_B}\n\n"
                       f"🎮 Played: {stats['played']}\n"
                       f"🥇 {name_A}: {stats['winsA']}\n"
                       f"🥈 {name_B}: {stats['winsB']}\n"
                       f"🤝 Draws: {stats['draws']}")
            
            await query.message.edit_text(receipt, parse_mode="HTML")
            del context.chat_data['current_stats']

# =========================================
#  PART 2: LEADERBOARDS & VIEWING STATS
# =========================================

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

        matches = db.query(MatchStat).filter(
            MatchStat.chat_id == chat_id,
            or_(MatchStat.player_a_id == target_id, MatchStat.player_b_id == target_id)
        ).all()
        
        if not matches:
            await update.message.reply_text(f"No stats for {target_name}.")
            return

        total = 0; wins = 0; losses = 0; draws = 0
        opponents = {} 

        for m in matches:
            total += 1
            is_a = (m.player_a_id == target_id)
            opp_id = m.player_b_id if is_a else m.player_a_id
            
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

        # Calc Favorite
        fav_opp = "None"
        best_pct = -1
        
        detail_txt = ""
        for oid, d in opponents.items():
            u = db.query(User).filter_by(user_id=oid).first()
            name = u.full_name if u else "Unknown"
            
            detail_txt += f"vs {name}: {d['t']} (W{d['w']}/L{d['l']}/D{d['d']})\n"
            
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
