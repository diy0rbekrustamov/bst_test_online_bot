// Telegram bot (webhook): ro'yxatdan o'tkazadi, rol beradi, Mini App ni ochadi.
// Webhook har so'rovda alohida ishga tushadi, shuning uchun suhbat holati D1 dagi `bot_state` jadvalida.
//
// Oqim: /start (yangi) → ism-familiya → telefon → "O'qituvchimisiz yoki o'quvchimisiz?"
//   • O'quvchi   → ilova (faqat test yechadi va bahosini ko'radi)
//   • O'qituvchi → maxfiy kod; to'g'ri bo'lsa ilova (test yaratadi, statistikani ko'radi)
import { getUser, saveUser, updateRole } from './db.js';
import { tg, sendMessage } from './telegram.js';
import { esc, now, safeEqual } from './util.js';

const MAX_CODE_TRIES = 5;
const LOCK_SECONDS = 10 * 60;

// ── Tekshiruv yordamchilari ──────────────────────────────────────────────────
export function cleanName(text) {
  const name = String(text || '').split(/\s+/).filter(Boolean).join(' ');
  if (name.split(' ').length < 2 || name.length > 80 || /\d/.test(name)) return null;
  return name;
}

/** '90 123 45 67' → '+998901234567'. Yaroqsiz bo'lsa null. */
export function normalizePhone(text) {
  let digits = String(text || '').replace(/\D/g, '');
  if (digits.length === 9) digits = '998' + digits;       // O'zbekiston raqami kodsiz
  if (digits.length < 10 || digits.length > 15) return null;
  return '+' + digits;
}

// ── Holat (bot_state) ────────────────────────────────────────────────────────
const getState = (db, uid) => db.prepare('SELECT state, data FROM bot_state WHERE user_id=?').bind(uid).first()
  .then((r) => (r ? { state: r.state, data: r.data ? JSON.parse(r.data) : {} } : { state: null, data: {} }));

const setState = (db, uid, state, data = {}) =>
  db.prepare(`INSERT INTO bot_state(user_id,state,data,updated_at) VALUES(?,?,?,?)
              ON CONFLICT(user_id) DO UPDATE SET state=excluded.state, data=excluded.data, updated_at=excluded.updated_at`)
    .bind(uid, state, JSON.stringify(data), now()).run();

const clearState = (db, uid) => db.prepare('DELETE FROM bot_state WHERE user_id=?').bind(uid).run();

// ── O'qituvchi kodi himoyasi: ketma-ket xato qilganlar vaqtincha to'siladi ───
async function lockedFor(db, uid) {
  const r = await db.prepare('SELECT locked_until FROM code_attempts WHERE user_id=?').bind(uid).first();
  const left = r ? r.locked_until - now() : 0;
  return left > 0 ? left : 0;
}

async function triesLeft(db, uid) {
  const r = await db.prepare('SELECT fails FROM code_attempts WHERE user_id=?').bind(uid).first();
  return MAX_CODE_TRIES - (r ? r.fails : 0);
}

/** true — to'g'ri; false — noto'g'ri; null — hozir to'silgan. */
async function checkCode(env, uid, attempt) {
  if (await lockedFor(env.DB, uid)) return null;
  const secret = env.TEACHER_CODE;
  if (secret && (await safeEqual(attempt.trim(), secret))) {
    await env.DB.prepare('DELETE FROM code_attempts WHERE user_id=?').bind(uid).run();
    return true;
  }
  await env.DB.prepare(`INSERT INTO code_attempts(user_id,fails,locked_until) VALUES(?,1,0)
                        ON CONFLICT(user_id) DO UPDATE SET fails=fails+1`).bind(uid).run();
  if ((await triesLeft(env.DB, uid)) <= 0) {      // 5 ta xato — to'siq qo'yiladi
    await env.DB.prepare('UPDATE code_attempts SET fails=0, locked_until=? WHERE user_id=?')
      .bind(now() + LOCK_SECONDS, uid).run();
  }
  return false;
}

// ── Klaviaturalar va matnlar ─────────────────────────────────────────────────
const ROLE_QUESTION = 'Siz kimsiz?';
const ROLE_HINT = "🎓 <b>O'quvchi</b> — kod bilan test yechadi va bahosini ko'radi\n" +
                  "👨‍🏫 <b>O'qituvchi</b> — test yaratadi va statistikani ko'radi (maxfiy kod kerak)";
const ROLE_TEXT = `<b>${ROLE_QUESTION}</b>\n\n${ROLE_HINT}`;

const roleMarkup = () => ({ inline_keyboard: [
  [{ text: "🎓 O'quvchiman", callback_data: 'role:student' }],
  [{ text: "👨‍🏫 O'qituvchiman", callback_data: 'role:teacher' }],
] });
const backMarkup = () => ({ inline_keyboard: [[{ text: '⬅️ Orqaga', callback_data: 'role:back' }]] });

function webappUrl(env, origin) {
  const url = env.WEBAPP_URL || origin;
  if (env.DEV_MODE === '1') return url;                  // mahalliy sinov uchun http ham mumkin
  return url && url.startsWith('https://') && url.includes('.') ? url : null;
}

async function sendApp(c, chatId, user) {
  const url = webappUrl(c.env, c.origin);
  if (!url) return sendMessage(c.env, chatId, '⚙️ Ilova hali sozlanmoqda. Birozdan keyin /start ni qayta yuboring.');
  const teacher = user.role === 'teacher';
  const text = `${teacher ? '👨‍🏫' : '🎓'} <b>${esc(user.full_name)}</b>\n` +
    (teacher ? "Test yaratish va statistikani ko'rish uchun ilovani oching."
             : 'Test kodini kiritib, testni yechish uchun ilovani oching.') +
    "\n\n<i>Rolni almashtirish: /role</i>";
  return sendMessage(c.env, chatId, text, {
    reply_markup: { inline_keyboard: [[{ text: '🚀 Ilovani ochish', web_app: { url } }]] },
  });
}

const lockText = (wait) => `🔒 Ko'p marta xato kiritdingiz. ${Math.floor(wait / 60) + 1} daqiqadan keyin urinib ko'ring.`;

// ── Buyruqlar ────────────────────────────────────────────────────────────────
async function cmdStart(c, uid, chatId) {
  const user = await getUser(c.env.DB, uid);
  if (user) {
    await clearState(c.env.DB, uid);
    return sendApp(c, chatId, user);
  }
  await setState(c.env.DB, uid, 'name');
  return sendMessage(c.env, chatId,
    '👋 <b>Assalomu alaykum!</b>\n\nOnline Test botiga xush kelibsiz. Avval tanishib olaylik.\n\n' +
    'Ism va familiyangizni yozing:\n<i>Masalan: Karimov Jasur</i>',
    { reply_markup: { remove_keyboard: true } });
}

async function cmdRole(c, uid, chatId) {
  if (!(await getUser(c.env.DB, uid))) {
    await clearState(c.env.DB, uid);
    return sendMessage(c.env, chatId, "Avval ro'yxatdan o'ting: /start");
  }
  await setState(c.env.DB, uid, 'role');
  return sendMessage(c.env, chatId, ROLE_TEXT, { reply_markup: roleMarkup() });
}

const cmdCancel = async (c, uid, chatId) => {
  await clearState(c.env.DB, uid);
  return sendMessage(c.env, chatId, 'Bekor qilindi. Qayta boshlash: /start', { reply_markup: { remove_keyboard: true } });
};

const cmdHelp = (c, chatId) => sendMessage(c.env, chatId,
  '📌 <b>Yordam</b>\n\n' +
  "/start — ilovani ochish (yangi bo'lsangiz — ro'yxatdan o'tish)\n" +
  '/role — rolni almashtirish\n\n' +
  "<b>O'quvchi:</b> o'qituvchi bergan 6 xonali kod bilan testni yechadi va bahosini ko'radi.\n" +
  "<b>O'qituvchi:</b> test yaratadi, kodni o'quvchilarga beradi, natija va statistikani ko'radi.\n\n" +
  "<b>Savol formati:</b>\n<pre>?2+2 nechaga teng?\n-3\n+4\n-5</pre>\n" +
  "<code>?</code> savol, <code>+</code> to'g'ri javob, <code>-</code> noto'g'ri javob.");

// ── Ro'yxatdan o'tish bosqichlari ────────────────────────────────────────────
async function gotName(c, uid, chatId, msg) {
  const name = cleanName(msg.text);
  if (!name) {
    return sendMessage(c.env, chatId, "Ism va familiyani to'liq yozing (raqamsiz), masalan: <i>Karimov Jasur</i>");
  }
  await setState(c.env.DB, uid, 'phone', { name });
  return sendMessage(c.env, chatId,
    `Rahmat, <b>${esc(name)}</b>! 🙂\n\nEndi telefon raqamingizni yuboring. Pastdagi tugmani bosing yoki raqamni yozing.`,
    { reply_markup: { keyboard: [[{ text: '📱 Raqamimni yuborish', request_contact: true }]],
                      resize_keyboard: true, one_time_keyboard: true } });
}

async function gotPhone(c, uid, chatId, msg, data) {
  let phone;
  if (msg.contact) {
    if (msg.contact.user_id !== uid) {
      return sendMessage(c.env, chatId, "Iltimos, o'zingizning raqamingizni yuboring (pastdagi tugma orqali).");
    }
    phone = normalizePhone(msg.contact.phone_number);
  } else if (typeof msg.text === 'string') {
    phone = normalizePhone(msg.text);
  } else {
    return;
  }
  if (!phone) return sendMessage(c.env, chatId, "Raqam noto'g'ri. Masalan: <code>+998 90 123 45 67</code>");
  if (!data.name) {
    await clearState(c.env.DB, uid);
    return sendMessage(c.env, chatId, 'Qaytadan boshlaymiz: /start', { reply_markup: { remove_keyboard: true } });
  }
  await saveUser(c.env.DB, uid, data.name, phone, 'student');   // eng past huquq; rolni keyin tanlaydi
  await setState(c.env.DB, uid, 'role');
  await sendMessage(c.env, chatId, "✅ Ma'lumotlaringiz saqlandi.", { reply_markup: { remove_keyboard: true } });
  return sendMessage(c.env, chatId, ROLE_TEXT, { reply_markup: roleMarkup() });
}

async function gotCode(c, uid, chatId, msg) {
  const attempt = msg.text || '';
  await tg(c.env, 'deleteMessage', { chat_id: chatId, message_id: msg.message_id });   // kod chatda qolmasin
  const result = await checkCode(c.env, uid, attempt);

  if (result === true) {
    await updateRole(c.env.DB, uid, 'teacher');
    await clearState(c.env.DB, uid);
    await sendMessage(c.env, chatId, "✅ <b>Tasdiqlandi!</b> Siz endi o'qituvchisiz.");
    return sendApp(c, chatId, await getUser(c.env.DB, uid));
  }
  const wait = await lockedFor(c.env.DB, uid);
  if (result === null || wait) {
    await setState(c.env.DB, uid, 'role');
    return sendMessage(c.env, chatId, lockText(wait), { reply_markup: roleMarkup() });
  }
  return sendMessage(c.env, chatId, `❌ Kod noto'g'ri. Qolgan urinishlar: ${await triesLeft(c.env.DB, uid)}`,
    { reply_markup: backMarkup() });
}

// ── Rol tanlash (inline tugmalar) ────────────────────────────────────────────
async function onCallback(c, q) {
  const uid = q.from.id;
  await tg(c.env, 'answerCallbackQuery', { callback_query_id: q.id });
  const m = /^role:(student|teacher|back)$/.exec(q.data || '');
  if (!m || !q.message) return;
  const chatId = q.message.chat.id;
  const edit = (text, extra = {}) => tg(c.env, 'editMessageText',
    { chat_id: chatId, message_id: q.message.message_id, text, parse_mode: 'HTML', ...extra });

  const user = await getUser(c.env.DB, uid);
  if (!user) {
    await clearState(c.env.DB, uid);
    return edit("Avval ro'yxatdan o'ting: /start");
  }
  const choice = m[1];

  if (choice === 'back') {
    await setState(c.env.DB, uid, 'role');
    return edit(ROLE_TEXT, { reply_markup: roleMarkup() });
  }
  if (choice === 'student') {
    await updateRole(c.env.DB, uid, 'student');
    await clearState(c.env.DB, uid);
    await edit("✅ Siz <b>o'quvchi</b> sifatida davom etasiz.");
    return sendApp(c, chatId, await getUser(c.env.DB, uid));
  }

  // o'qituvchi
  if (!c.env.TEACHER_CODE) {
    await setState(c.env.DB, uid, 'role');
    return edit("⚠️ O'qituvchi kodi hali sozlanmagan. Bot egasi Cloudflare'da <code>TEACHER_CODE</code> maxfiy qiymatini " +
                "kiritishi kerak.\n\nHozircha o'quvchi sifatida davom eting.", { reply_markup: roleMarkup() });
  }
  const wait = await lockedFor(c.env.DB, uid);
  if (wait) {
    await setState(c.env.DB, uid, 'role');
    return edit(lockText(wait), { reply_markup: roleMarkup() });
  }
  await setState(c.env.DB, uid, 'code');
  return edit("🔐 <b>O'qituvchi ekanligingizni tasdiqlang</b>\n\nSizga berilgan maxfiy kodni yuboring. " +
              'Xavfsizlik uchun kod yuborilgach, xabar chatdan o\'chiriladi.', { reply_markup: backMarkup() });
}

// ── Xabarlar ─────────────────────────────────────────────────────────────────
async function onMessage(c, msg) {
  if (!msg.from || !msg.chat || msg.chat.type !== 'private') return;
  const uid = msg.from.id;
  const chatId = msg.chat.id;
  const text = typeof msg.text === 'string' ? msg.text : '';

  const cmd = /^\/(\w+)(?:@\w+)?(?:\s|$)/.exec(text);
  if (cmd) {
    switch (cmd[1].toLowerCase()) {
      case 'start': return cmdStart(c, uid, chatId);
      case 'role': return cmdRole(c, uid, chatId);
      case 'cancel': return cmdCancel(c, uid, chatId);
      case 'help': return cmdHelp(c, chatId);
      default: return;                                   // noma'lum buyruq e'tiborsiz
    }
  }

  const { state, data } = await getState(c.env.DB, uid);
  switch (state) {
    case 'name': return text ? gotName(c, uid, chatId, msg) : undefined;
    case 'phone': return gotPhone(c, uid, chatId, msg, data);
    case 'role': return text ? sendMessage(c.env, chatId, 'Yuqoridagi tugmalardan birini tanlang 👆') : undefined;
    case 'code': return text ? gotCode(c, uid, chatId, msg) : undefined;
    default: {
      if (!text) return;
      const user = await getUser(c.env.DB, uid);
      return user ? sendApp(c, chatId, user) : sendMessage(c.env, chatId, 'Boshlash uchun /start ni bosing.');
    }
  }
}

export async function handleUpdate(update, env, origin) {
  const c = { env, origin };
  if (update.callback_query) return onCallback(c, update.callback_query);
  if (update.message) return onMessage(c, update.message);
}

/** /setup: webhook, buyruqlar ro'yxati va menyu tugmasini o'rnatadi. */
export async function setupBot(env, origin) {
  const url = webappUrl(env, origin) || origin;
  const out = {};
  out.webhook = await tg(env, 'setWebhook', {
    url: `${origin}/telegram`,
    secret_token: env.WEBHOOK_SECRET,
    allowed_updates: ['message', 'callback_query'],
    drop_pending_updates: true,
  });
  out.commands = await tg(env, 'setMyCommands', { commands: [
    { command: 'start', description: 'Ilovani ochish' },
    { command: 'role', description: 'Rolni almashtirish' },
    { command: 'help', description: 'Yordam' },
  ] });
  out.menu = await tg(env, 'setChatMenuButton', { menu_button: { type: 'web_app', text: 'Ilova', web_app: { url } } });
  return out;
}
