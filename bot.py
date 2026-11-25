"""
Telegram Bot - Mini App ochish + bildirishnomalar
PTB 22.x mos
"""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import config
from database import init_db, get_user, save_user

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

WEBAPP_URL = config.WEBAPP_URL  # run.py dan o'rnatiladi

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user = get_user(user_id)

    # Mini App tugmasi
    webapp_btn = InlineKeyboardButton(
        "🎓 Online Test ochish",
        web_app=WebAppInfo(url=config.WEBAPP_URL)
    )
    keyboard = InlineKeyboardMarkup([[webapp_btn]])

    if user:
        await update.message.reply_text(
            f"👋 Xush kelibsiz, *{user['full_name']}*!\n\n"
            f"Quyidagi tugmani bosib botni ishlating:",
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            "🎓 *Online Test Botga xush kelibsiz!*\n\n"
            "Botdan foydalanish uchun quyidagi tugmani bosing:",
            parse_mode='Markdown',
            reply_markup=keyboard
        )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 *Yordam:*\n\n"
        "• /start — Botni boshlash\n"
        "• Web App ni ochib barcha funksiyalardan foydalaning\n\n"
        "*O'qituvchi:* test yaratish, natijalarni ko'rish\n"
        "*O'quvchi:* test yechish, natijalarni ko'rish",
        parse_mode='Markdown'
    )

def run_bot():
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_cmd))
    print("🤖 Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    init_db()
    run_bot()
