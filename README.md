# 🎓 Online Test Bot (Telegram)

O'qituvchi va o'quvchi uchun test platformasi.

## 🚀 O'rnatish

### 1. Python o'rnating
Python 3.10+ kerak: https://python.org

### 2. Kutubxonalarni o'rnating
```bash
cd C:\Users\user\.gemini\antigravity\scratch\quiz_bot
pip install -r requirements.txt
```

### 3. Bot tokeni oling
1. Telegramda `@BotFather` ga yozing
2. `/newbot` buyrug'ini yuboring
3. Bot nomini kiriting (misol: `Online Test Bot`)
4. Bot username kiriting (misol: `my_quiz_bot`)
5. Token beriladi: `1234567890:ABCdef...`

### 4. Tokenni sozlang
`bot.py` faylini oching va:
```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
```
o'rniga botfather bergan tokenni qo'ying:
```python
BOT_TOKEN = "1234567890:ABCdef..."
```

### 5. Botni ishga tushiring
```bash
python bot.py
```

---

## 📱 Foydalanish

### 👨‍🏫 O'qituvchi uchun:
1. `/start` - Ro'yxatdan o'tish
2. **O'qituvchi** rolini tanlash
3. **➕ Test yaratish** → Fan tanlash → Test nomi → Savollarni kiritish
4. Test kodi olinadi (6 xonali)
5. Kodni o'quvchilarga yuborish
6. **📊 Mening testlarim** - natijalarni ko'rish

### 👨‍🎓 O'quvchi uchun:
1. `/start` - Ro'yxatdan o'tish
2. **O'quvchi** rolini tanlash
3. **📝 Test yechish** → 6 xonali kod kiritish
4. Savollarni yechish
5. Natija ko'rsatiladi

---

## 📝 Savol formati

Savollarni quyidagi formatda kiriting:

```
?O'zbekistonning poytaxti qayer?
-Buxoro
-Samarqand
+Toshkent
-Andijon

?2+2 nechaga teng?
-3
+4
-5
-6
```

**Qoidalar:**
- `?` - savol boshlanishi
- `+` - TO'G'RI javob (faqat 1 ta bo'lishi kerak)
- `-` - NOTO'G'RI javob
- Kamida 2 ta javob variant bo'lishi shart

---

## ✨ Xususiyatlar

- ✅ Ro'yxatdan o'tish (ism + telefon)
- ✅ O'qituvchi / O'quvchi rollari
- ✅ 15 ta fan tanlash
- ✅ Test yaratish va kodni ulashish
- ✅ Vaqt belgilash (ixtiyoriy)
- ✅ Test yechish (inline buttons)
- ✅ Natija: to'g'ri/noto'g'ri/foiz/baho
- ✅ O'qituvchiga avtomatik xabar
- ✅ Statistika ko'rish
- ✅ Profil sahifasi

---

## 🗄️ Ma'lumotlar bazasi

SQLite (quiz_bot.db) faylida saqlanadi:
- `users` - foydalanuvchilar
- `tests` - testlar
- `questions` - savollar
- `results` - natijalar
