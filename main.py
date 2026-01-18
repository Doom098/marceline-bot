import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from config import BOT_TOKEN
from database import init_db

# Feature Imports
from features.general import (
    track_activity, mention_all, exclude_member, include_member, 
    all_list, who_all, help_command, about_command, set_about
)
from features.vault import (
    save_item, recall_item, list_saves, delete_save,
    save_sticker, recall_sticker, save_excuse, random_excuse
)
from features.roast import (
    roast_command, start_add_roast, save_roast, show_roasts, del_roast, ADD_ROAST_TEXT
)
from features.session import (
    start_play, handle_callback
)
from features.stats import (
    show_leaderboard, handle_stats_callback
)
from features.admin import (
    reset_all, list_groups
)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    # Initialize DB
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # --- Handlers ---
    
    # 1. General & Tracking
    app.add_handler(MessageHandler(filters.ALL, track_activity), group=1)

    
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
    
    app.add_handler(CommandHandler("exsave", save_excuse))
    app.add_handler(CommandHandler("excuse", random_excuse))

    # 3. Roast
    app.add_handler(CommandHandler("roast", roast_command))
    app.add_handler(CommandHandler("roastshow", show_roasts))
    app.add_handler(CommandHandler("roastdel", del_roast))
    
    conv_roast = ConversationHandler(
        entry_points=[CommandHandler("roastadd", start_add_roast)],
        states={
            ADD_ROAST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_roast)]
        },
        fallbacks=[]
    )
    app.add_handler(conv_roast)

    # 4. Sessions & Stats
    app.add_handler(CommandHandler("play", start_play))
    app.add_handler(CommandHandler("stats", show_leaderboard))
    
    # Unified Callback Handler for Sessions and Stats
    # We split them by pattern in the function or use multiple handlers with pattern regex
    app.add_handler(CallbackQueryHandler(handle_stats_callback, pattern=r"^stat_"))
    app.add_handler(CallbackQueryHandler(handle_callback)) # Catch-all for session buttons

    # 5. Admin
    app.add_handler(CommandHandler("resetall", reset_all))
    app.add_handler(CommandHandler("groups", list_groups))

    print("Marceline is waking up...")
    app.run_polling()

if __name__ == '__main__':
    main()
