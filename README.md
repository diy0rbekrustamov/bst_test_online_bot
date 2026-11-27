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

## 🚀 Cloudflare'ga joylash (24/7, kompyuter kerak emas)

Loyiha **Cloudflare Workers + D1** da ishlaydi: doimiy HTTPS manzil, tunnel va ngrok kerak emas.

1. `npm install`
2. Bazani yarating (bir marta) va `wrangler.jsonc` dagi `database_id` ni yozing:
   `npx wrangler d1 create bst-test-db` → `npm run db:remote`
3. Maxfiy qiymatlar (kodda saqlanmaydi):
   ```
   npx wrangler secret put BOT_TOKEN        # BotFather tokeni
   npx wrangler secret put TEACHER_CODE     # o'qituvchilar uchun maxfiy kod
   npx wrangler secret put WEBHOOK_SECRET   # o'zingiz o'ylab toping: faqat A-Z a-z 0-9 _ -
   ```
4. `npx wrangler deploy`
5. Brauzerda **bir marta** oching: `https://<worker-manzili>/setup?key=<WEBHOOK_SECRET>` — webhook, buyruqlar va «Ilova» tugmasi o'rnatiladi.

Git bilan avtomatik deploy: Cloudflare Dashboard → Workers → loyihani GitHub repoga ulang (Worker nomi `wrangler.jsonc` dagi `name` bilan bir xil bo'lsin).
Maxsus domen ishlatsangiz Dashboard'da Variables ga `WEBAPP_URL=https://domen.uz` qo'shing.

### Mahalliy sinov
```
cp .dev.vars.example .dev.vars
npm run db:local
npm run dev        # http://127.0.0.1:8787
npm test           # soxta Telegram bilan 77 ta tekshiruv (.dev.vars sinov qiymatlari bilan)
```

### Eski (Python) variant
`app.py`, `bot.py`, `run.py` — kompyuterda ishga tushirish uchun saqlangan (`pip install -r requirements.txt`, `python run.py`). Cloudflare variantini ishlatsangiz kerak emas.

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

Cloudflare D1 (SQLite): `users`, `tests`, `questions`, `results`, `attempts`, `bot_state`, `code_attempts` (`schema.sql`).
Baza telefon raqamlarni saqlaydi — repoga qo'shmang.
