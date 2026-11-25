"""
run.py — hammasini ishga tushiradi:
  1. Flask serveri (webapp + API)
  2. Ngrok tunnel (HTTPS URL)
  3. Telegram boti
"""
import os
import sys
import threading
import time
import urllib.request

import config
from database import init_db


def start_flask():
    from app import app
    app.run(host='127.0.0.1', port=config.PORT, debug=False, use_reloader=False)


def wait_for_flask(timeout=15):
    """Server haqiqatan javob bera boshlaguncha kutadi (oldin shunchaki 2 soniya kutilardi)."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{config.PORT}/", timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def start_tunnel():
    # Tayyor URL berilgan bo'lsa (masalan, serverda) tunnel kerak emas
    if config.WEBAPP_URL.startswith("https://"):
        return config.WEBAPP_URL

    try:
        from pyngrok import ngrok
        token = os.getenv("NGROK_AUTHTOKEN")
        if token:
            ngrok.set_auth_token(token)
        tunnel = ngrok.connect(config.PORT, "http")
        url = tunnel.public_url.replace("http://", "https://")
        print(f"\n✅ Ngrok URL: {url}\n")
        return url
    except Exception as e:
        print(f"\n❌ Ngrok ishlamadi: {e}")
        url = input("HTTPS URL kiriting (ngrok/cloudflared/localtunnel), bo'sh qoldirsangiz chiqiladi: ").strip()
        if not url:
            sys.exit(1)
        return url if url.startswith("https://") else "https://" + url


if __name__ == '__main__':
    print("=" * 50)
    print("🎓 Online Test Bot — ishga tushmoqda...")
    print("=" * 50)

    if "YOUR_BOT_TOKEN_HERE" in config.BOT_TOKEN:
        print("❌ Bot tokeni kiritilmagan.\n"
              "   Shu papkada .env fayl yarating va ichiga yozing:\n"
              "   BOT_TOKEN=1234567890:ABCdef...")
        sys.exit(1)

    init_db()
    threading.Thread(target=start_flask, daemon=True).start()
    if not wait_for_flask():
        print("❌ Flask server ishga tushmadi (port band bo'lishi mumkin: PORT o'zgartiring).")
        sys.exit(1)
    print(f"✅ Flask server: http://localhost:{config.PORT}")

    config.WEBAPP_URL = start_tunnel()
    print(f"✅ Mini App URL: {config.WEBAPP_URL}")

    import bot as bot_module
    print(f"✅ Bot token: {config.BOT_TOKEN[:10]}...")
    bot_module.run_bot()
