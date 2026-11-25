# 🎓 Online Test Bot (Telegram Mini App)

O'qituvchi test yaratadi va 6 xonali kod beradi, o'quvchi shu kod bilan testni yechadi.
Natija o'qituvchiga Telegramga xabar bo'lib keladi.

## 🚀 Ishga tushirish

1. **Python 3.10+** o'rnating: https://python.org
2. **Bot token** oling: Telegramda `@BotFather` → `/newbot`
3. Shu papkada `.env` fayl yarating:
   ```
   BOT_TOKEN=1234567890:ABCdef...
   ```
   (`.env` GitHub ga yuklanmaydi — token xavfsiz qoladi. Tokenni `config.py` ga yozmang.)
4. *(ixtiyoriy)* [ngrok](https://ngrok.com) akkaunti bo'lsa, `.env` ga `NGROK_AUTHTOKEN=...` qo'shing.
5. Ishga tushiring:
   - Windows: `start.bat` ni ikki marta bosing
   - boshqa: `pip install -r requirements.txt` va `python run.py`

`run.py` Flask serverni, ngrok HTTPS manzilini va botni birga ishga tushiradi. Botga `/start` yuboring.

> ⚠️ ngrok bepul tarifida har safar yangi manzil beriladi — `run.py` botni avtomatik yangilaydi.
> Doimiy ishlashi uchun serverga joylab, `.env` ga `WEBAPP_URL=https://sizning-domen.uz` yozing (shunda ngrok kerak bo'lmaydi).

### Sozlamalar (`.env`)

| O'zgaruvchi | Ma'nosi |
|---|---|
| `BOT_TOKEN` | BotFather tokeni (majburiy) |
| `WEBAPP_URL` | Tayyor HTTPS manzil bo'lsa (ngrok o'rniga) |
| `PORT` | Server porti (standart 5000) |
| `NGROK_AUTHTOKEN` | ngrok tokeni |
| `DEV_MODE=1` | **Faqat o'z kompyuteringizda** brauzerda sinash uchun: `http://localhost:5000/?dev=123`. Serverda yoqmang! |

## 📝 Savol formati

```
?O'zbekistonning poytaxti qayer?
-Buxoro
-Samarqand
+Toshkent
-Andijon
```

- `?` savol, `+` to'g'ri javob (faqat **bitta**), `-` noto'g'ri javob
- Kamida 2 ta, ko'pi bilan 8 ta variant
- Uzun savol yoki variant keyingi qatorga o'tishi mumkin
- Xato bloklar "Tekshiruv" oynasida sababi bilan ko'rsatiladi, qolgan savollar saqlanadi

## ✨ Imkoniyatlar

- O'qituvchi: 15 ta fan, test yaratish, kodni nusxalash, natijalar (o'rtacha foiz, reyting), testni o'chirish
- O'quvchi: kod bilan kirish, savollar bo'ylab erkin yurish, natija va baho
- Vaqt chegarasi **serverda** nazorat qilinadi; ilovani yopib-ochsa vaqt to'xtamaydi, javoblar saqlanadi
- Ilovadan chiqib ketishlar sanaladi (3-marta test avtomatik topshiriladi) va o'qituvchiga ma'lum qilinadi
- Har bir so'rov Telegram imzosi bilan tekshiriladi — boshqa odamning nomidan kirib bo'lmaydi

## 🗄️ Ma'lumotlar bazasi

SQLite (`quiz_bot.db`): `users`, `tests`, `questions`, `results`, `attempts`.
Fayl foydalanuvchilarning telefon raqamlarini saqlaydi, shuning uchun u `.gitignore` da.
