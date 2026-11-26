"""
Sozlamalar. Qiymatlar avval muhit o'zgaruvchilaridan, keyin .env fayldan olinadi.

Eng oson yo'l: shu papkada `.env` fayl yarating:

    BOT_TOKEN=1234567890:ABCdef...
    TEACHER_CODE=oqituvchilar_uchun_maxfiy_kod

`.env` fayl .gitignore da — token GitHub ga chiqib ketmaydi.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_env_file():
    path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")   # @BotFather dan oling
# O'qituvchi bo'lmoqchi bo'lganlardan bot shu kodni so'raydi. Faqat o'qituvchilarga bering.
TEACHER_CODE = os.getenv("TEACHER_CODE", "").strip()
PORT = int(os.getenv("PORT", "5000"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "")                    # run.py ngrok URL bilan to'ldiradi
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "quiz_bot.db"))

# Faqat o'zingizning kompyuteringizda brauzerda sinash uchun (Telegramsiz).
# Serverda HECH QACHON yoqmang: DEV_MODE=1 bo'lsa autentifikatsiya o'chadi.
DEV_MODE = os.getenv("DEV_MODE") == "1"

# initData necha soat yaroqli hisoblanadi
INIT_DATA_MAX_AGE_HOURS = 48
