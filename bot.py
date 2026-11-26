"""
Telegram bot — ro'yxatdan o'tkazadi, rol beradi va Mini App ni ochadi. PTB 22.x

Oqim:
  /start (yangi foydalanuvchi) → ism-familiya → telefon → "O'qituvchimisiz yoki o'quvchimisiz?"
    • O'quvchi  → Mini App (faqat test yechadi va bahosini ko'radi)
    • O'qituvchi → maxfiy kod so'raladi; to'g'ri bo'lsa Mini App (test yaratadi, statistikani ko'radi)
"""
import hmac
import html
import logging
import re
import time

from telegram import (Update, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton,
                      ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo, MenuButtonWebApp, BotCommand)
from telegram.constants import ParseMode
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler, ContextTypes,
                          ConversationHandler, MessageHandler, filters)

import config
from database import init_db, get_user, save_user, update_role

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
# httpx har so'rovni bot tokeni bilan birga loglaydi — token log orqali sizib chiqmasin
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

NAME, PHONE, ROLE, CODE = range(4)

MAX_CODE_TRIES = 5
LOCK_SECONDS = 10 * 60


# ── Tekshiruv yordamchilari (alohida, sinash oson bo'lsin) ───────────────────
def clean_name(text):
    name = ' '.join((text or '').split())
    if len(name.split()) < 2 or len(name) > 80 or any(ch.isdigit() for ch in name):
        return None
    return name


def normalize_phone(text):
    """'90 123 45 67' → '+998901234567'. Yaroqsiz bo'lsa None."""
    digits = re.sub(r'\D', '', text or '')
    if len(digits) == 9:                 # O'zbekiston raqami kod'siz
        digits = '998' + digits
    if not 10 <= len(digits) <= 15:
        return None
    return '+' + digits


class TeacherGate:
    """O'qituvchi kodini tekshiradi. Ketma-ket xato qilganlarni vaqtincha to'sadi (taxmin qilib topmasin)."""
    def __init__(self):
        self.fails = {}      # user_id → (xatolar soni, to'siq tugash vaqti)

    def locked_for(self, uid):
        count, until = self.fails.get(uid, (0, 0))
        left = until - time.time()
        return int(left) if left > 0 else 0

    def tries_left(self, uid):
        return MAX_CODE_TRIES - self.fails.get(uid, (0, 0))[0]

    def check(self, uid, attempt):
        """True — to'g'ri; False — noto'g'ri; None — hozir to'silgan."""
        if self.locked_for(uid):
            return None
        secret = config.TEACHER_CODE
        if secret and hmac.compare_digest(attempt.strip().encode(), secret.encode()):
            self.fails.pop(uid, None)
            return True
        count = self.fails.get(uid, (0, 0))[0] + 1
        self.fails[uid] = (0, time.time() + LOCK_SECONDS) if count >= MAX_CODE_TRIES else (count, 0)
        return False


gate = TeacherGate()


# ── Klaviaturalar ────────────────────────────────────────────────────────────
def app_markup():
    """Mini App tugmasi. URL hali yo'q bo'lsa None."""
    url = config.WEBAPP_URL
    if not url or not url.startswith('https://') or '.' not in url:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Ilovani ochish", web_app=WebAppInfo(url=url))]])


def role_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎓 O'quvchiman", callback_data='role:student')],
        [InlineKeyboardButton("👨‍🏫 O'qituvchiman", callback_data='role:teacher')],
    ])


def back_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data='role:back')]])


ROLE_QUESTION = "Siz kimsiz?"
ROLE_HINT = ("🎓 <b>O'quvchi</b> — kod bilan test yechadi va bahosini ko'radi\n"
             "👨‍🏫 <b>O'qituvchi</b> — test yaratadi va statistikani ko'radi (maxfiy kod kerak)")


async def send_app(target, user):
    """Ro'yxatdan o'tgan foydalanuvchiga ilovani ochish tugmasini yuboradi.
    target — Message yoki Chat."""
    send = getattr(target, 'reply_text', None) or target.send_message
    markup = app_markup()
    if markup is None:
        await send("⚙️ Ilova hali sozlanmoqda. Birozdan keyin /start ni qayta yuboring.")
        return
    teacher = user['role'] == 'teacher'
    text = (f"{'👨‍🏫' if teacher else '🎓'} <b>{html.escape(user['full_name'])}</b>\n"
            + ("Test yaratish va statistikani ko'rish uchun ilovani oching."
               if teacher else "Test kodini kiritib, testni yechish uchun ilovani oching.")
            + "\n\n<i>Rolni almashtirish: /role</i>")
    await send(text, parse_mode=ParseMode.HTML, reply_markup=markup)


# ── Ro'yxatdan o'tish ────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if user:
        await send_app(update.message, user)
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text(
        "👋 <b>Assalomu alaykum!</b>\n\nOnline Test botiga xush kelibsiz. Avval tanishib olaylik.\n\n"
        "Ism va familiyangizni yozing:\n<i>Masalan: Karimov Jasur</i>",
        parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
    return NAME


async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = clean_name(update.message.text)
    if not name:
        await update.message.reply_text(
            "Ism va familiyani to'liq yozing (raqamsiz), masalan: <i>Karimov Jasur</i>", parse_mode=ParseMode.HTML)
        return NAME
    context.user_data['name'] = name
    kb = ReplyKeyboardMarkup([[KeyboardButton("📱 Raqamimni yuborish", request_contact=True)]],
                             resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        f"Rahmat, <b>{html.escape(name)}</b>! 🙂\n\nEndi telefon raqamingizni yuboring. "
        "Pastdagi tugmani bosing yoki raqamni yozing.",
        parse_mode=ParseMode.HTML, reply_markup=kb)
    return PHONE


async def got_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.contact:
        if msg.contact.user_id != update.effective_user.id:
            await msg.reply_text("Iltimos, o'zingizning raqamingizni yuboring (pastdagi tugma orqali).")
            return PHONE
        phone = normalize_phone(msg.contact.phone_number)
    else:
        phone = normalize_phone(msg.text)
    if not phone:
        await msg.reply_text("Raqam noto'g'ri. Masalan: <code>+998 90 123 45 67</code>", parse_mode=ParseMode.HTML)
        return PHONE
    name = context.user_data.get('name')
    if not name:                      # bot qayta ishga tushgan bo'lishi mumkin
        await msg.reply_text("Qaytadan boshlaymiz: /start", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    save_user(update.effective_user.id, name, phone, 'student')   # eng past huquq; rolni keyin tanlaydi
    await msg.reply_text("✅ Ma'lumotlaringiz saqlandi.", reply_markup=ReplyKeyboardRemove())
    await msg.reply_text(f"<b>{ROLE_QUESTION}</b>\n\n{ROLE_HINT}", parse_mode=ParseMode.HTML, reply_markup=role_markup())
    return ROLE


# ── Rol tanlash ──────────────────────────────────────────────────────────────
async def change_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not get_user(update.effective_user.id):
        await update.message.reply_text("Avval ro'yxatdan o'ting: /start")
        return ConversationHandler.END
    await update.message.reply_text(f"<b>{ROLE_QUESTION}</b>\n\n{ROLE_HINT}", parse_mode=ParseMode.HTML,
                                    reply_markup=role_markup())
    return ROLE


async def role_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    user = get_user(uid)
    if not user:
        await q.edit_message_text("Avval ro'yxatdan o'ting: /start")
        return ConversationHandler.END
    choice = q.data.split(':')[1]

    if choice == 'back':
        await q.edit_message_text(f"<b>{ROLE_QUESTION}</b>\n\n{ROLE_HINT}", parse_mode=ParseMode.HTML,
                                  reply_markup=role_markup())
        return ROLE

    if choice == 'student':
        update_role(uid, 'student')
        await q.edit_message_text("✅ Siz <b>o'quvchi</b> sifatida davom etasiz.", parse_mode=ParseMode.HTML)
        await send_app(q.message, get_user(uid))
        return ConversationHandler.END

    # o'qituvchi
    if not config.TEACHER_CODE:
        await q.edit_message_text(
            "⚠️ O'qituvchi kodi hali sozlanmagan. Bot egasi <code>.env</code> fayliga "
            "<code>TEACHER_CODE=...</code> qo'shishi kerak.\n\nHozircha o'quvchi sifatida davom eting.",
            parse_mode=ParseMode.HTML, reply_markup=role_markup())
        return ROLE
    wait = gate.locked_for(uid)
    if wait:
        await q.edit_message_text(f"🔒 Ko'p marta xato kiritdingiz. {wait // 60 + 1} daqiqadan keyin urinib ko'ring.",
                                  reply_markup=role_markup())
        return ROLE
    await q.edit_message_text(
        "🔐 <b>O'qituvchi ekanligingizni tasdiqlang</b>\n\nSizga berilgan maxfiy kodni yuboring. "
        "Xavfsizlik uchun kod yuborilgach, xabar chatdan o'chiriladi.",
        parse_mode=ParseMode.HTML, reply_markup=back_markup())
    return CODE


async def got_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    attempt = update.message.text or ''
    try:
        await update.message.delete()      # kod chatda qolib ketmasin
    except Exception:
        pass
    chat = update.effective_chat
    result = gate.check(uid, attempt)

    if result is True:
        update_role(uid, 'teacher')
        await chat.send_message("✅ <b>Tasdiqlandi!</b> Siz endi o'qituvchisiz.", parse_mode=ParseMode.HTML)
        await send_app(chat, get_user(uid))
        return ConversationHandler.END

    wait = gate.locked_for(uid)
    if result is None or wait:
        await chat.send_message(f"🔒 Ko'p marta xato kiritdingiz. {wait // 60 + 1} daqiqadan keyin urinib ko'ring.",
                                reply_markup=role_markup())
        return ROLE
    await chat.send_message(f"❌ Kod noto'g'ri. Qolgan urinishlar: {gate.tries_left(uid)}",
                            reply_markup=back_markup())
    return CODE


async def remind_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Yuqoridagi tugmalardan birini tanlang 👆")
    return ROLE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bekor qilindi. Qayta boshlash: /start", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ── Boshqa buyruqlar ─────────────────────────────────────────────────────────
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 <b>Yordam</b>\n\n"
        "/start — ilovani ochish (yangi bo'lsangiz — ro'yxatdan o'tish)\n"
        "/role — rolni almashtirish\n\n"
        "<b>O'quvchi:</b> o'qituvchi bergan 6 xonali kod bilan testni yechadi va bahosini ko'radi.\n"
        "<b>O'qituvchi:</b> test yaratadi, kodni o'quvchilarga beradi, natija va statistikani ko'radi.\n\n"
        "<b>Savol formati:</b>\n"
        "<pre>?2+2 nechaga teng?\n-3\n+4\n-5</pre>\n"
        "<code>?</code> savol, <code>+</code> to'g'ri javob, <code>-</code> noto'g'ri javob.",
        parse_mode=ParseMode.HTML)


async def other_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if user:
        await send_app(update.message, user)
    else:
        await update.message.reply_text("Boshlash uchun /start ni bosing.")


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    log.error("Bot xatosi", exc_info=context.error)


async def post_init(app: Application):
    """Buyruqlar ro'yxati va chatdagi pastki menyu tugmasi."""
    try:
        await app.bot.set_my_commands([BotCommand("start", "Ilovani ochish"),
                                       BotCommand("role", "Rolni almashtirish"),
                                       BotCommand("help", "Yordam")])
    except Exception as e:
        log.warning("Buyruqlarni o'rnatib bo'lmadi: %s", e)
    if config.WEBAPP_URL.startswith('https://') and '.' in config.WEBAPP_URL:
        try:
            await app.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="Ilova", web_app=WebAppInfo(url=config.WEBAPP_URL)))
        except Exception as e:
            log.warning("Menyu tugmasini o'rnatib bo'lmadi: %s", e)


def build_application():
    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start), CommandHandler('role', change_role),
                      # bot qayta ishga tushganda ham eski xabardagi tugmalar ishlasin
                      CallbackQueryHandler(role_chosen, pattern=r'^role:(student|teacher|back)$')],
        states={
            NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            PHONE: [MessageHandler((filters.CONTACT | filters.TEXT) & ~filters.COMMAND, got_phone)],
            ROLE:  [CallbackQueryHandler(role_chosen, pattern=r'^role:(student|teacher|back)$'),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, remind_buttons)],
            CODE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_code),
                    CallbackQueryHandler(role_chosen, pattern=r'^role:back$')],
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start), CommandHandler('role', change_role)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler('help', help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, other_text))
    app.add_error_handler(on_error)
    return app


def run_bot():
    app = build_application()
    print("🤖 Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    init_db()
    run_bot()
