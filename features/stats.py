from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import get_db
from models import User, MatchStat
from sqlalchemy import func
import datetime

# --- Stats Collection Flow States ---
(ASK_MATCHES, ASK_WINS_A, ASK_WINS_B, ASK_DRAWS) = range(4)

# Temporary storage for the conversation (simple dict keyed by user_id)
# In production, use context.user_data
STATS_CACHE = {} 

async def start_stats_input(context, chat_id, pA_id, pB_id):
    # This is called programmatically from session.py
    # We send a message that triggers the conversation? 
    # Actually, conversation handlers usually start with a command or specific message filter.
    # Since we are triggering from a callback, we can send a message with a specific text 
    # that forces a reply, OR we just handle it via buttons purely.
    
    # Let's use a pure Button Flow for data input as requested in prompt "Buttons 1-20"
    
    # We need to store who is A and B in context.bot_data or similar to persist across callbacks
    context.chat_data['current_stats'] = {'pA': pA_id, 'pB': pB_id, 'chat_id': chat_id}
    
    # Send "Matches Played?"
    keyboard = []
    # Grid of numbers 1-10
    row1 = [InlineKeyboardButton(str(i), callback_data=f"stat_matches_{i}") for i in range(1, 6)]
    row2 = [InlineKeyboardButton(str(i), callback_data=f"stat_matches_{i}") for i in range(6, 11)]
    keyboard = [row1, row2]
    
    await context.bot.send_message(
        chat_id=chat_id, 
        text="📊 <b>Stats Input</b>\nHow many matches played?", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def handle_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    
    if 'current_stats' not in context.chat_data:
        await query.message.edit_text("Stats session expired/lost.")
        return

    stats = context.chat_data['current_stats']

    if data.startswith("stat_matches_"):
        val = int(data.split("_")[-1])
        stats['played'] = val
        
        # Ask Wins A
        keys = [InlineKeyboardButton(str(i), callback_data=f"stat_winsA_{i}") for i in range(val + 1)]
        # Chunk keys
        rows = [keys[i:i+5] for i in range(0, len(keys), 5)]
        
        await query.message.edit_text(f"Matches: {val}\n\nHow many wins for Player A?", reply_markup=InlineKeyboardMarkup(rows))
        context.chat_data['current_stats'] = stats
        return

    if data.startswith("stat_winsA_"):
        val = int(data.split("_")[-1])
        stats['winsA'] = val
        
        # Ask Wins B (Max possible is played - winsA)
        remaining = stats['played'] - val
        keys = [InlineKeyboardButton(str(i), callback_data=f"stat_winsB_{i}") for i in range(remaining + 1)]
        rows = [keys[i:i+5] for i in range(0, len(keys), 5)]
        
        await query.message.edit_text(f"Matches: {stats['played']}\nA Wins: {val}\n\nHow many wins for Player B?", reply_markup=InlineKeyboardMarkup(rows))
        context.chat_data['current_stats'] = stats
        return

    if data.startswith("stat_winsB_"):
        val = int(data.split("_")[-1])
        stats['winsB'] = val
        
        # Calculate Draws automatically
        draws = stats['played'] - stats['winsA'] - stats['winsB']
        stats['draws'] = draws
        
        # Save to DB
        with next(get_db()) as db:
            match = MatchStat(
                chat_id=stats['chat_id'],
                player_a_id=stats['pA'],
                player_b_id=stats['pB'],
                score_a=stats['winsA'],
                score_b=stats['winsB'],
                is_draw=(draws > 0) # Technicality: storing aggregate match, but schema supports single. 
                # Prompt implies aggregation "Matches played? -> 1-20". 
                # We should probably store X individual match records or 1 aggregate record?
                # Schema `MatchStat` looks like single match. 
                # Better approach: Create 'played' number of records? 
                # Or just store the aggregate in `score_a` / `score_b`?
                # Let's treat MatchStat as a "Session Result" for simplicity given the inputs.
            )
            # Actually, for Leaderboards, we need total matches.
            # Let's repurpose MatchStat to store the aggregate session result:
            # score_a = wins for A, score_b = wins for B. 
            # We need a field for draws or played? 
            # I'll update schema model logic: 
            # We will store 1 row per SESSION, adding a 'draws' column or repurpose 'is_draw'
        
            # Wait, Schema `MatchStat` has `is_draw`. 
            # Let's insert multiple rows to keep stats granular and correct for win% formula?
            # Creating 5 rows for 5 matches is cleaner for "Total Matches" counts later.
            
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
            
            # Fetch Names
            ua = db.query(User).filter_by(user_id=stats['pA']).first()
            ub = db.query(User).filter_by(user_id=stats['pB']).first()
            name_a = ua.full_name if ua else "Player A"
            name_b = ub.full_name if ub else "Player B"
            
            receipt = (f"✅ <b>Stats Saved</b>\n"
                       f"{name_a} vs {name_b}\n"
                       f"Played: {stats['played']}\n"
                       f"A Wins: {stats['winsA']}\n"
                       f"B Wins: {stats['winsB']}\n"
                       f"Draws: {stats['draws']}")
            
            await query.message.edit_text(receipt, parse_mode="HTML")
            del context.chat_data['current_stats']

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Calculate stats
    with next(get_db()) as db:
        # Get all stats for this chat
        stats = db.query(MatchStat).filter_by(chat_id=chat_id).all()
        
        # Aggregation
        data = {} # user_id -> {wins: 0, draws: 0, total: 0}
        
        for s in stats:
            # Player A processing
            if s.player_a_id not in data: data[s.player_a_id] = {'wins': 0, 'draws': 0, 'total': 0}
            data[s.player_a_id]['total'] += 1
            if s.score_a > s.score_b: data[s.player_a_id]['wins'] += 1
            if s.is_draw: data[s.player_a_id]['draws'] += 1
            
            # Player B processing
            if s.player_b_id not in data: data[s.player_b_id] = {'wins': 0, 'draws': 0, 'total': 0}
            data[s.player_b_id]['total'] += 1
            if s.score_b > s.score_a: data[s.player_b_id]['wins'] += 1
            if s.is_draw: data[s.player_b_id]['draws'] += 1
            
        # Filter < 10 matches and sort by win%
        leaderboard = []
        for uid, d in data.items():
            if d['total'] < 10: continue
            win_pct = (d['wins'] + 0.5 * d['draws']) / d['total'] * 100
            user = db.query(User).filter_by(user_id=uid).first()
            name = user.full_name if user else str(uid)
            leaderboard.append((name, win_pct, d['total'], d['wins'], d['draws']))
            
        leaderboard.sort(key=lambda x: x[1], reverse=True)
        
        msg = "🏆 <b>Leaderboard (Min 10 matches)</b>\n\n"
        for i, row in enumerate(leaderboard, 1):
            msg += f"{i}. {row[0]} - <b>{row[1]:.1f}%</b> ({row[3]}W/{row[4]}D/{row[2]}T)\n"
            
        await update.message.reply_text(msg, parse_mode="HTML")