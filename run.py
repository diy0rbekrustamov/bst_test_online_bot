"""
run.py — Hamma narsani ishga tushiradi:
  1. Flask serveri (webapp + API)
  2. Ngrok tunnel (HTTPS URL)
  3. Telegram boti
"""
import threading, sys, time
import config
from database import init_db

def start_flask():
    from app import app
    init_db()
    app.run(port=config.PORT, debug=False, use_reloader=False)

def start_ngrok():
    try:
        from pyngrok import ngrok
        tunnel = ngrok.connect(config.PORT, "http")
        url = tunnel.public_url.replace("http://", "https://")
        config.WEBAPP_URL = url
        import bot as bot_module
        bot_module.WEBAPP_URL = url
        print(f"\n✅ Ngrok URL: {url}")
        print(f"   Mini App URL: {url}\n")
        return url
    except ImportError:
        print("\n⚠️  pyngrok topilmadi. Qo'lda URL kiriting.")
        url = input("HTTPS URL (ngrok/localtunnel): ").strip()
        if not url.startswith("https://"):
            url = "https://" + url
        config.WEBAPP_URL = url
        return url
    except Exception as e:
        print(f"\n❌ Ngrok xatosi: {e}")
        url = input("HTTPS URL kiriting: ").strip()
        config.WEBAPP_URL = url
        return url

if __name__ == '__main__':
    print("=" * 50)
    print("🎓 Online Test Bot — Ishga tushmoqda...")
    print("=" * 50)

    # 1. Flask serverni fon oqimida boshlash
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)
    print("✅ Flask server: http://localhost:5000")

    # 2. Ngrok tunnel
    webapp_url = start_ngrok()

    # 3. Telegram boti
    import bot as bot_module
    bot_module.config.WEBAPP_URL = webapp_url
    print(f"✅ Bot token: {config.BOT_TOKEN[:10]}...")
    print("✅ Botni ishga tushirish...")
    bot_module.run_bot()
