import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from config import BOT_TOKEN
from database import init_db, get_db
from models import GameSession
from datetime import datetime, timezone

# Feature Imports
from features.general import (
    track_activity, mention_all, exclude_member, include_member, 
    all_list, who_all, help_command, about_command, set_about, start_command, handle_dm_callback,
    set_dm_commands, set_dm_about, set_dm_repo # <--- Imported new functions
)
from features.vault import (
    save_item, recall_item, list_saves, delete_save,
    save_sticker, recall_sticker, list_stickers, delete_sticker,
    save_excuse, random_excuse, list_excuses, delete_excuse
)
from features.roast import (
    roast_command, start_add_roast, save_roast, show_roasts, del_roast, ADD_ROAST_TEXT
)
from features.session import (
    start_play, handle_callback, set_squad
)
from features.stats import (
    show_leaderboard, handle_lb_callback
)
from features.admin import (
    reset_all, list_groups, leave_group
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def cleanup_sessions(context):
    """Job to delete expired sessions from DB and Chat"""
    with next(get_db()) as db:
        now = datetime.now(timezone.utc)
        expired = db.query(GameSession).filter(GameSession.expires_at < now).all()
        for session in expired:
            try:
                await context.bot.delete_message(chat_id=session.chat_id, message_id=session.message_id)
            except Exception:
                pass
            db.delete(session)
        db.commit()

def main():
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # --- Job Queue (Auto Delete) ---
    jq = app.job_queue
    jq.run_repeating(cleanup_sessions, interval=21600, first=60) 

    # --- Handlers ---
    
    # 1. General & DM Management
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_dm_callback, pattern=r"^dm_"))
    
    # Super Admin DM Setters
    app.add_handler(CommandHandler("setdmcommands", set_dm_commands))
    app.add_handler(CommandHandler("setdmabout", set_dm_about))
    app.add_handler(CommandHandler("setdmrepo", set_dm_repo))

    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), track_activity), group=1)
    
    app.add_handler(CommandHandler("all", mention_all))
    app.add_handler(CommandHandler("exclude", exclude_member))
    app.add_handler(CommandHandler("include", include_member))
    app.add_handler(CommandHandler("alllist", all_list))
    app.add_handler(CommandHandler("whoall", who_all))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("aboutset", set_about))

    # 2. Vault
    app.add_handler(CommandHandler("save", save_item))
    app.add_handler(CommandHandler("q", recall_item))
    app.add_handler(CommandHandler("sshow", list_saves))
    app.add_handler(CommandHandler("sdel", delete_save))
    
    app.add_handler(CommandHandler("ssave", save_sticker))
    app.add_handler(CommandHandler("s", recall_sticker))
    app.add_handler(CommandHandler("stshow", list_stickers)) 
    app.add_handler(CommandHandler("stdel", delete_sticker)) 
    
    app.add_handler(CommandHandler("exsave", save_excuse))
    app.add_handler(CommandHandler("excuse", random_excuse))
    app.add_handler(CommandHandler("exshow", list_excuses)) 
    app.add_handler(CommandHandler("exdel", delete_excuse)) 

    # 3. Roast
    app.add_handler(CommandHandler("roast", roast_command))
    app.add_handler(CommandHandler("roastshow", show_roasts))
    app.add_handler(CommandHandler("roastdel", del_roast))
    
    conv_roast = ConversationHandler(
        entry_points=[CommandHandler("roastadd", start_add_roast)],
        states={ADD_ROAST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_roast)]},
        fallbacks=[]
    )
    app.add_handler(conv_roast)

    # 4. Sessions & Stats
    app.add_handler(CommandHandler("play", start_play))
    app.add_handler(CommandHandler("setsquad", set_squad))
    app.add_handler(CommandHandler("stats", show_leaderboard))
    
    app.add_handler(CallbackQueryHandler(handle_lb_callback, pattern=r"^lb_"))
    app.add_handler(CallbackQueryHandler(handle_callback)) 

    # 5. Admin
    app.add_handler(CommandHandler("resetall", reset_all))
    app.add_handler(CommandHandler("groups", list_groups))
    app.add_handler(CommandHandler("groupdel", leave_group))

    print("Marceline is waking up...")
    app.run_polling()

if __name__ == '__main__':
    main()
