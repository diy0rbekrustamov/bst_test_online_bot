"""
run.py — hammasini ishga tushiradi:
  1. Flask serveri (webapp + API)
  2. Tunnel (HTTPS manzil): Cloudflare — akkaunt va token kerak emas, ogohlantirish sahifasi yo'q
  3. Telegram boti

Tunnel tartibi:
  • .env da WEBAPP_URL bo'lsa — o'sha ishlatiladi (doimiy manzil, tunnel kerak emas)
  • aks holda cloudflared avtomatik yuklab olinadi va ishga tushiriladi
  • cloudflared ishlamasa va NGROK_AUTHTOKEN bo'lsa — ngrok
"""
import atexit
import os
import platform
import re
import stat
import subprocess
import sys
import threading
import time
import urllib.request

import config
from database import init_db

HERE = os.path.dirname(os.path.abspath(__file__))
CF_URLS = {
    ("windows", "amd64"): "cloudflared-windows-amd64.exe",
    ("windows", "x86"): "cloudflared-windows-386.exe",
    ("linux", "amd64"): "cloudflared-linux-amd64",
    ("linux", "arm64"): "cloudflared-linux-arm64",
    ("darwin", "amd64"): None,   # macOS: faqat arxiv (.tgz) — brew install cloudflared
    ("darwin", "arm64"): None,
}
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
_procs = []


def start_flask():
    from app import app
    app.run(host='127.0.0.1', port=config.PORT, debug=False, use_reloader=False, threaded=True)


def wait_for_flask(timeout=15):
    """Server haqiqatan javob bera boshlaguncha kutadi."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{config.PORT}/", timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


# ── Cloudflare ───────────────────────────────────────────────────────────────
def _arch():
    m = platform.machine().lower()
    if m in ("amd64", "x86_64"):
        return "amd64"
    if m in ("arm64", "aarch64"):
        return "arm64"
    return "x86"


def find_cloudflared():
    """PATH dan yoki shu papkadan topadi; topilmasa yuklab oladi."""
    from shutil import which
    found = which("cloudflared")
    if found:
        return found
    system = platform.system().lower()
    local = os.path.join(HERE, "cloudflared.exe" if system == "windows" else "cloudflared")
    if os.path.exists(local):
        return local
    asset = CF_URLS.get((system, _arch()))
    if not asset:
        print("ℹ️  cloudflared topilmadi. O'rnating: brew install cloudflared")
        return None
    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{asset}"
    print("⬇️  cloudflared yuklanmoqda (bir martalik, ~40 MB)...")
    tmp = local + ".part"
    try:
        urllib.request.urlretrieve(url, tmp)
        os.replace(tmp, local)
        if system != "windows":
            os.chmod(local, os.stat(local).st_mode | stat.S_IEXEC)
        return local
    except Exception as e:
        print(f"❌ cloudflared yuklab bo'lmadi: {e}")
        if os.path.exists(tmp):
            os.remove(tmp)
        return None


def start_cloudflare(timeout=40):
    exe = find_cloudflared()
    if not exe:
        return None
    flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
    proc = subprocess.Popen(
        [exe, "tunnel", "--url", f"http://127.0.0.1:{config.PORT}", "--no-autoupdate"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
        creationflags=flags)
    _procs.append(proc)
    found = []

    def reader():
        for line in proc.stdout:           # quvur to'lib qolmasligi uchun doim o'qiymiz
            m = URL_RE.search(line)
            if m and not found:
                found.append(m.group(0))
    threading.Thread(target=reader, daemon=True).start()

    end = time.time() + timeout
    while time.time() < end and not found:
        if proc.poll() is not None:
            return None
        time.sleep(0.3)
    if not found:
        return None
    url = found[0]
    # Yangi manzil DNS ga tarqalguncha 5-20 soniya ketadi: tayyor bo'lguncha kutamiz,
    # aks holda foydalanuvchi birinchi bosishda xato ko'radi.
    print("⏳ Manzil tayyorlanmoqda...")
    while time.time() < end + 40:
        try:
            r = urllib.request.urlopen(url + "/", timeout=5)
            if r.status == 200:
                return url
        except Exception:
            pass
        time.sleep(1.5)
    return url


def start_ngrok():
    token = os.getenv("NGROK_AUTHTOKEN")
    if not token:
        return None
    try:
        from pyngrok import ngrok
        ngrok.set_auth_token(token)
        return ngrok.connect(config.PORT, "http").public_url.replace("http://", "https://")
    except Exception as e:
        print(f"❌ Ngrok ishlamadi: {e}")
        return None


def start_tunnel():
    if config.WEBAPP_URL.startswith("https://"):
        return config.WEBAPP_URL
    url = start_cloudflare() or start_ngrok()
    if not url:
        print("\n❌ Tunnel ochib bo'lmadi.\n"
              "   • Internet borligini tekshiring va qayta urinib ko'ring\n"
              "   • yoki serverga joylab, .env ga WEBAPP_URL=https://sizning-domen.uz yozing")
        sys.exit(1)
    return url


def _cleanup():
    for p in _procs:
        try:
            p.terminate()
        except Exception:
            pass


if __name__ == '__main__':
    print("=" * 50)
    print("🎓 Online Test Bot — ishga tushmoqda...")
    print("=" * 50)

    if "YOUR_BOT_TOKEN_HERE" in config.BOT_TOKEN:
        print("❌ Bot tokeni kiritilmagan.\n"
              "   Shu papkada .env fayl yarating va ichiga yozing:\n"
              "   BOT_TOKEN=1234567890:ABCdef...")
        sys.exit(1)
    if not config.TEACHER_CODE:
        print("⚠️  TEACHER_CODE kiritilmagan: hech kim o'qituvchi bo'la olmaydi.\n"
              "   .env fayliga qo'shing:  TEACHER_CODE=oqituvchilar_uchun_maxfiy_kod\n")

    atexit.register(_cleanup)
    init_db()
    threading.Thread(target=start_flask, daemon=True).start()
    if not wait_for_flask():
        print("❌ Flask server ishga tushmadi (port band bo'lishi mumkin: .env ga PORT=5001 yozing).")
        sys.exit(1)
    print(f"✅ Flask server: http://localhost:{config.PORT}")

    config.WEBAPP_URL = start_tunnel()
    print(f"✅ Mini App manzili: {config.WEBAPP_URL}")
    print("ℹ️  Manzil har ishga tushganda yangilanadi. Botdagi pastki «Ilova» tugmasi doim yangi manzilga ulanadi;\n"
          "   eski xabardagi tugma ishlamasa, botga /start yuboring.\n")

    import bot as bot_module
    bot_module.run_bot()
