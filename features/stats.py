from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_db
from models import User, MatchStat
from sqlalchemy import func

# --- Stats Collection Flow States ---
# We use a pure callback flow, no ConversationHandler states needed here.

async def start_stats_input(context, chat_id, pA_id, pB_id):
    # Fetch names immediately to use in the questions
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
        
        # Ask Wins for Player A (Using Name)
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
        
        # Ask Wins for Player B (Using Name)
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

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    with next(get_db()) as db:
        stats = db.query(MatchStat).filter_by(chat_id=chat_id).all()
        
        data = {} 
        for s in stats:
            # Process A
            if s.player_a_id not in data: data[s.player_a_id] = {'wins': 0, 'draws': 0, 'total': 0}
            data[s.player_a_id]['total'] += 1
            if s.score_a > s.score_b: data[s.player_a_id]['wins'] += 1
            if s.is_draw: data[s.player_a_id]['draws'] += 1
            
            # Process B
            if s.player_b_id not in data: data[s.player_b_id] = {'wins': 0, 'draws': 0, 'total': 0}
            data[s.player_b_id]['total'] += 1
            if s.score_b > s.score_a: data[s.player_b_id]['wins'] += 1
            if s.is_draw: data[s.player_b_id]['draws'] += 1
            
        leaderboard = []
        for uid, d in data.items():
            if d['total'] < 5: continue # Lowered min matches to 5 for testing
            win_pct = (d['wins'] + 0.5 * d['draws']) / d['total'] * 100
            user = db.query(User).filter_by(user_id=uid).first()
            name = user.full_name if user else str(uid)
            leaderboard.append((name, win_pct, d['total'], d['wins'], d['draws']))
            
        leaderboard.sort(key=lambda x: x[1], reverse=True)
        
        if not leaderboard:
            await update.message.reply_text("📉 No stats recorded yet (min 5 matches).")
            return

        msg = "🏆 <b>Leaderboard</b>\n\n"
        for i, row in enumerate(leaderboard, 1):
            msg += f"{i}. {row[0]} - <b>{row[1]:.1f}%</b> ({row[3]}W/{row[4]}D/{row[2]}T)\n"
            
        await update.message.reply_text(msg, parse_mode="HTML")
