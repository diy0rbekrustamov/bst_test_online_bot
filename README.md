# 🎓 Online Test Bot (Telegram Mini App)

O'qituvchi test yaratadi va 6 xonali kod beradi, o'quvchi shu kod bilan testni yechadi va bahosini ko'radi.

## Qanday ishlaydi

1. Foydalanuvchi botga `/start` yuboradi.
2. Bot **ism-familiya** va **telefon raqam** so'raydi (raqamni tugma bilan yuborish mumkin) va saqlaydi.
3. Bot so'raydi: **o'qituvchimisiz yoki o'quvchimisiz?**
   - **O'quvchi** → ilova ochiladi: faqat kod bilan test yechadi va bahosini ko'radi.
   - **O'qituvchi** → bot **maxfiy kod** so'raydi. Kod to'g'ri bo'lsa ilova ochiladi: test yaratadi, natijalar va statistikani ko'radi. Kod xato bo'lsa — rad etiladi, 5 marta xato qilgan 10 daqiqaga to'siladi.
4. Rolni keyin `/role` bilan almashtirish mumkin (o'qituvchi bo'lish uchun yana kod kerak).

Ro'yxatdan o'tish va rol faqat botda hal qilinadi; veb-ilova buni o'zgartira olmaydi. O'qituvchi test yecha olmaydi, o'quvchi esa test yarata olmaydi va natijalarni ko'ra olmaydi — bu server tomonda tekshiriladi.

## 🚀 Ishga tushirish

1. **Python 3.10+** o'rnating: https://python.org
2. **Bot token** oling: Telegramda `@BotFather` → `/newbot`
3. Shu papkada `.env` fayl yarating:
   ```
   BOT_TOKEN=1234567890:ABCdef...
   TEACHER_CODE=oqituvchilar_uchun_maxfiy_kod
   ```
   `TEACHER_CODE` ni o'zingiz o'ylab toping va faqat o'qituvchilarga bering. Kod yo'q bo'lsa hech kim o'qituvchi bo'la olmaydi.
4. Ishga tushiring:
   - Windows: `start.bat` ni ikki marta bosing
   - boshqa: `pip install -r requirements.txt` va `python run.py`

`run.py` hammasini birga ishga tushiradi: server, **Cloudflare tunnel** (akkaunt va token kerak emas, ngrok'dagi "visiting" ogohlantirish sahifasi yo'q) va bot. Birinchi marta `cloudflared` (~40 MB) o'zi yuklab olinadi.

> ⚠️ Tunnel manzili har ishga tushganda **yangi** bo'ladi. Botdagi pastki **«Ilova»** tugmasi har safar yangi manzilga ulanadi. Eski xabardagi tugma «offline» desa — botga `/start` yuboring.
> Manzil o'zgarmasligi uchun serverga joylab, `.env` ga `WEBAPP_URL=https://sizning-domen.uz` yozing.

### Sozlamalar (`.env`)

| O'zgaruvchi | Ma'nosi |
|---|---|
| `BOT_TOKEN` | BotFather tokeni (majburiy) |
| `TEACHER_CODE` | O'qituvchilar uchun maxfiy kod (majburiy, aks holda o'qituvchi bo'lib bo'lmaydi) |
| `WEBAPP_URL` | Tayyor HTTPS manzil bo'lsa (tunnel kerak bo'lmaydi) |
| `PORT` | Server porti (standart 5000) |
| `NGROK_AUTHTOKEN` | Ixtiyoriy: Cloudflare ishlamasa ngrok zaxira |
| `DEV_MODE=1` | **Faqat o'z kompyuteringizda** brauzerda sinash uchun. Serverda yoqmang! |

## 📝 Savol formati

```
?O'zbekistonning poytaxti qayer?
-Buxoro
-Samarqand
+Toshkent
-Andijon
```

`?` savol, `+` to'g'ri javob (faqat **bitta**), `-` noto'g'ri javob. 2–8 ta variant. Xato bloklar tekshiruv oynasida sababi bilan ko'rsatiladi, qolgan savollar saqlanadi.

## ✨ Imkoniyatlar

- **O'qituvchi:** 15 ta fan, test yaratish, kodni nusxalash, har test bo'yicha reyting va baholar diagrammasi, umumiy statistika, testni o'chirish; har natija Telegramga xabar bo'lib keladi
- **O'quvchi:** kod bilan kirish, savollar bo'ylab erkin yurish, baho va natijalar tarixi
- Vaqt chegarasi **serverda** nazorat qilinadi; ilovani yopib-ochsa vaqt to'xtamaydi, javoblar saqlanadi
- Ilovadan chiqib ketishlar sanaladi (3-marta test avtomatik topshiriladi) va o'qituvchiga ma'lum qilinadi
- Har bir so'rov Telegram imzosi bilan tekshiriladi
- Telegram mavzusiga moslashadigan och/qorong'i rejim

## 🗄️ Ma'lumotlar bazasi

SQLite (`quiz_bot.db`): `users`, `tests`, `questions`, `results`, `attempts`. Eski baza avtomatik yangilanadi.
Fayl telefon raqamlarni saqlaydi, shuning uchun u `.gitignore` da.
