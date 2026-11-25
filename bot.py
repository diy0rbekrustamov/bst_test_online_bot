"""
Telegram bot — Mini App ni ochadi. PTB 22.x
"""
import html
import logging

from telegram import (Update, InlineKeyboardMarkup, InlineKeyboardButton,
                      WebAppInfo, MenuButtonWebApp)
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

import config
from database import init_db, get_user

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
# httpx har so'rovni bot tokeni bilan birga loglaydi — token log orqali sizib chiqmasin
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


def webapp_markup():
    """Mini App tugmasi. URL hali yo'q bo'lsa None."""
    url = config.WEBAPP_URL
    if not url or not url.startswith('https://') or '.' not in url:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎓 Testni ochish", web_app=WebAppInfo(url=url))]])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    markup = webapp_markup()

    if markup is None:
        await update.message.reply_text(
            "⚙️ Bot hali sozlanmoqda. Birozdan keyin /start ni qayta yuboring.")
        return

    if user:
        text = (f"👋 Xush kelibsiz, <b>{html.escape(user['full_name'])}</b>!\n\n"
                "Testlarga kirish uchun tugmani bosing.")
    else:
        text = ("🎓 <b>Online Test botiga xush kelibsiz!</b>\n\n"
                "O'qituvchi test yaratadi va 6 xonali kod beradi. "
                "O'quvchi shu kod bilan testni yechadi.\n\n"
                "Boshlash uchun tugmani bosing.")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 <b>Yordam</b>\n\n"
        "/start — ilovani ochish\n\n"
        "<b>O'qituvchi:</b> fan tanlaydi, savollarni yozadi, 6 xonali kodni o'quvchilarga beradi. "
        "Natijalar shu yerga xabar bo'lib keladi.\n"
        "<b>O'quvchi:</b> kodni kiritadi va testni yechadi.\n\n"
        "<b>Savol formati:</b>\n"
        "<pre>?2+2 nechaga teng?\n-3\n+4\n-5</pre>\n"
        "<code>?</code> savol, <code>+</code> to'g'ri javob, <code>-</code> noto'g'ri javob.",
        parse_mode=ParseMode.HTML)


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    log.error("Bot xatosi", exc_info=context.error)


async def post_init(app: Application):
    """Chatdagi pastki menyu tugmasini Mini App ga ulaydi."""
    if config.WEBAPP_URL.startswith('https://') and '.' in config.WEBAPP_URL:
        try:
            await app.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="Test", web_app=WebAppInfo(url=config.WEBAPP_URL)))
        except Exception as e:
            log.warning("Menyu tugmasini o'rnatib bo'lmadi: %s", e)


def run_bot():
    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_cmd))
    app.add_error_handler(on_error)
    print("🤖 Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    init_db()
    run_bot()
