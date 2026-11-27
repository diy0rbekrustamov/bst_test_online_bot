// Mahalliy sinov: soxta Telegram serveri + `wrangler dev --local` (D1 lokal).
// Ishga tushirish:  npm run db:local && npm test
// Talab: .dev.vars da TELEGRAM_API=http://127.0.0.1:8799, BOT_TOKEN=123456:TESTTOKEN,
//        TEACHER_CODE=maxfiy-kod, WEBHOOK_SECRET=test_secret_123, DEV_MODE=0
import http from 'node:http';
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';

const BASE = 'http://127.0.0.1:8787';
const TOKEN = '123456:TESTTOKEN';
const SECRET = 'test_secret_123';
const TEACHER_CODE = 'maxfiy-kod';

// ── soxta Telegram ──────────────────────────────────────────────────────────
const calls = [];
const mock = http.createServer((req, res) => {
  let body = '';
  req.on('data', (d) => (body += d));
  req.on('end', () => {
    const method = req.url.split('/').pop();
    let payload = {};
    try { payload = JSON.parse(body); } catch {}
    calls.push({ method, ...payload });
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ ok: true, result: true }));
  });
});

// ── yordamchilar ────────────────────────────────────────────────────────────
let passed = 0, failed = 0;
function check(name, cond, extra = '') {
  if (cond) { passed++; console.log(`  ✓ ${name}`); }
  else { failed++; console.log(`  ✗ ${name} ${extra}`); }
}

function initData(userId, { age = 0, token = TOKEN, tamper = false } = {}) {
  const p = new URLSearchParams({
    auth_date: String(Math.floor(Date.now() / 1000) - age),
    query_id: 'AAH' + userId,
    user: JSON.stringify({ id: userId, first_name: 'T' }),
  });
  const check = [...p.entries()].sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([k, v]) => `${k}=${v}`).join('\n');
  const secret = crypto.createHmac('sha256', 'WebAppData').update(token).digest();
  p.set('hash', crypto.createHmac('sha256', secret).update(check).digest('hex'));
  let s = p.toString();
  if (tamper) s = s.replace('T%22', 'X%22').replace('first_name', 'first_nam');
  return s;
}

async function api(uid, method, path, body, opts) {
  const r = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-Tg-Init-Data': uid === null ? '' : initData(uid, opts) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return { status: r.status, ...(await r.json().catch(() => ({}))) };
}

let updateId = 1;
async function bot(update, secret = SECRET) {
  const r = await fetch(BASE + '/telegram', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Telegram-Bot-Api-Secret-Token': secret },
    body: JSON.stringify({ update_id: updateId++, ...update }),
  });
  return r.status;
}
let msgId = 100;
const say = (uid, text, extra = {}) =>
  bot({ message: { message_id: msgId++, from: { id: uid }, chat: { id: uid, type: 'private' }, text, ...extra } });
const press = (uid, data) =>
  bot({ callback_query: { id: 'cb' + msgId++, from: { id: uid }, data, message: { message_id: 7, chat: { id: uid } } } });
const lastCall = (method) => [...calls].reverse().find((c) => c.method === method);
const sent = (uid) => calls.filter((c) => c.method === 'sendMessage' && c.chat_id === uid);
const lastText = (uid) => (sent(uid).at(-1) || {}).text || '';

async function waitFor(fn, ms = 20000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try { const r = await fn(); if (r) return r; } catch {}
    await new Promise((r) => setTimeout(r, 300));
  }
  return null;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ── asosiy ──────────────────────────────────────────────────────────────────
mock.listen(8799);
const wr = spawn('npx', ['wrangler', 'dev', '--local', '--port', '8787'], { stdio: ['ignore', 'pipe', 'pipe'] });
let wlog = '';
wr.stdout.on('data', (d) => (wlog += d));
wr.stderr.on('data', (d) => (wlog += d));
const stop = () => { try { wr.kill('SIGTERM'); } catch {} mock.close(); };
process.on('exit', stop);

const ready = await waitFor(async () => (await fetch(BASE + '/')).status === 200, 60000);
if (!ready) { console.log('Worker ishga tushmadi:\n' + wlog.slice(-2000)); stop(); process.exit(1); }

const T = 5001, S = 5002, S2 = 5003, T2 = 5004;

console.log('\n[Webhook himoyasi]');
check('maxfiy sarlavhasiz so\'rov rad etiladi (403)', (await bot({ message: {} }, 'wrong')) === 403);
check('GET /telegram → 405', (await fetch(BASE + '/telegram')).status === 405);
check('/setup noto\'g\'ri kalit bilan → 403', (await fetch(BASE + '/setup?key=bad')).status === 403);
{
  const r = await (await fetch(BASE + '/setup?key=' + SECRET)).json();
  check('menyu tugmasi WEBAPP_URL ga ulandi', true);
  check('/setup ishlaydi', r.ok && r.teacher_code_set);
  const wh = lastCall('setWebhook');
  check('setWebhook: url + secret_token', wh && wh.url.endsWith('/telegram') && wh.secret_token === SECRET);
  check('setChatMenuButton: https manzil', lastCall('setChatMenuButton')?.menu_button?.web_app?.url === 'https://bst-test.example.workers.dev');
}

console.log('\n[Bot: ro\'yxatdan o\'tish]');
await say(T, '/start');
check('/start ism so\'raydi', /Ism va familiya/.test(lastText(T)));
await say(T, 'Karim');
check('bitta so\'z rad etiladi', /to'liq yozing/.test(lastText(T)));
await say(T, 'Karimov Jasur');
check('ismdan keyin telefon so\'raydi', /telefon/.test(lastText(T)));
check('telefon tugmasi (request_contact)', sent(T).at(-1).reply_markup.keyboard[0][0].request_contact === true);
await say(T, '12');
check('noto\'g\'ri raqam rad etiladi', /Raqam noto'g'ri/.test(lastText(T)));
await bot({ message: { message_id: msgId++, from: { id: T }, chat: { id: T, type: 'private' },
  contact: { phone_number: '998901112233', user_id: 999 } } });
check('begonaning kontakti rad etiladi', /o'zingizning raqamingizni/.test(lastText(T)));
await say(T, '90 111 22 33');
check('raqamdan keyin rol so\'raladi', /Siz kimsiz/.test(lastText(T)));
check('rol tugmalari bor', sent(T).at(-1).reply_markup.inline_keyboard.length === 2);
check('foydalanuvchi bazada (student)', (await api(T, 'GET', '/api/me')).user?.role === 'student'
  && (await api(T, 'GET', '/api/me')).user?.phone === '+998901112233');

console.log('\n[Bot: o\'qituvchi kodi]');
await press(T, 'role:teacher');
check('kod so\'raladi', /maxfiy kodni/.test(lastCall('editMessageText').text));
await say(T, 'xato-kod');
check('kod xabari o\'chiriladi', !!lastCall('deleteMessage'));
check('noto\'g\'ri kod: qolgan urinishlar 4', /Qolgan urinishlar: 4/.test(lastText(T)));
check('hali o\'qituvchi emas', (await api(T, 'GET', '/api/teacher/tests')).status === 403);
await press(T, 'role:back');
check('"Orqaga" rol tanlashga qaytaradi', /Siz kimsiz/.test(lastCall('editMessageText').text));
await press(T, 'role:teacher');
for (let i = 0; i < 4; i++) await say(T, 'yana-xato');
check('5-xatodan keyin to\'siqlanadi', /Ko'p marta xato/.test(lastText(T)));
await say(T, TEACHER_CODE);
check('to\'siq paytida to\'g\'ri kod ham o\'tmaydi', (await api(T, 'GET', '/api/teacher/tests')).status === 403);

// to'siq tugagandek: bazada vaqtni orqaga suramiz
await new Promise((resolve) => {
  const p = spawn('npx', ['wrangler', 'd1', 'execute', 'bst-test-db', '--local', '--command',
    'UPDATE code_attempts SET locked_until=0'], { stdio: 'ignore' });
  p.on('close', resolve);
});
await press(T, 'role:teacher');
await say(T, '  ' + TEACHER_CODE + ' ');
check('to\'g\'ri kod → tasdiqlandi', /Tasdiqlandi/.test(sent(T).at(-2).text));
check('web-app tugmasi yuborildi', !!sent(T).at(-1).reply_markup?.inline_keyboard[0][0].web_app);
check('endi o\'qituvchi', (await api(T, 'GET', '/api/teacher/tests')).status === 200);

// o'quvchi
await say(S, '/start'); await say(S, 'Aliyev Vali'); await say(S, '+998 93 555 44 33');
await press(S, 'role:student');
check('o\'quvchi roli', (await api(S, 'GET', '/api/me')).user?.role === 'student');
check('o\'quvchiga tugma yuborildi', !!sent(S).at(-1).reply_markup?.inline_keyboard[0][0].web_app);
await say(S, 'salom');
check('ro\'yxatdan o\'tgan: har qanday matnga ilova tugmasi', !!sent(S).at(-1).reply_markup);
await say(9999, 'salom');
check('notanish: /start ni taklif qiladi', /\/start/.test(lastText(9999)));

console.log('\n[API: autentifikatsiya]');
check('initData yo\'q → 401', (await api(null, 'GET', '/api/me')).status === 401);
check('buzilgan imzo → 401', (await api(T, 'GET', '/api/me', undefined, { tamper: true })).status === 401);
check('boshqa token bilan imzolangan → 401', (await api(T, 'GET', '/api/me', undefined, { token: '1:OTHER' })).status === 401);
check('eskirgan initData (3 kun) → 401', (await api(T, 'GET', '/api/me', undefined, { age: 3 * 86400 })).status === 401);
check('ro\'yxatdan o\'tmagan → 403 unregistered', (await api(7777, 'GET', '/api/student/results')).unregistered === true);
check('X-Dev-User DEV_MODE o\'chiq bo\'lsa ishlamaydi',
  (await (await fetch(BASE + '/api/me', { headers: { 'X-Dev-User': String(T) } })).status) === 401);
check('noma\'lum endpoint → 404 JSON', (await api(T, 'GET', '/api/yoq')).status === 404);
check('noto\'g\'ri metod → 405', (await api(T, 'PUT', '/api/tests')).status === 405);

console.log('\n[API: parser va test yaratish]');
const text = `?2+2 nechaga teng?\n-3\n+4\n-5\n\n?Poytaxt\n-Buxoro\n+Toshkent\n\n?Xato savol\n-a\n-b\n\n?Ikki to'g'ri\n+a\n+b`;
const pr = await api(T, 'POST', '/api/parse-questions', { text });
check('parser: 2 ta to\'g\'ri savol', pr.questions?.length === 2);
check('parser: 2 ta xato sababi bilan', pr.errors?.length === 2 && /belgilanmagan/.test(pr.errors[0].reason)
  && /faqat bitta/.test(pr.errors[1].reason), JSON.stringify(pr.errors));
check('o\'quvchi parser ishlata olmaydi', (await api(S, 'POST', '/api/parse-questions', { text })).status === 403);
check('bo\'sh savollar rad', (await api(T, 'POST', '/api/tests', { subject: 'Mat', name: 'X', questions: [] })).ok === false);
check('noto\'g\'ri vaqt rad', (await api(T, 'POST', '/api/tests', { subject: 'Mat', name: 'X', time_limit: 999, questions: pr.questions })).ok === false);
check('o\'quvchi test yarata olmaydi', (await api(S, 'POST', '/api/tests', { subject: 'Mat', name: 'X', questions: pr.questions })).status === 403);
const created = await api(T, 'POST', '/api/tests', { subject: 'Matematika', name: 'Sinov <b>1</b>', time_limit: 10, questions: pr.questions });
check('test yaratildi (6 xonali kod)', created.ok && /^\d{6}$/.test(created.code));
const CODE = created.code;

console.log('\n[API: o\'quvchi testni yechadi]');
check('noto\'g\'ri kod → 404', (await api(S, 'GET', '/api/tests/12345')).status === 404);
const info = await api(S, 'GET', '/api/tests/' + CODE);
check('test haqida ma\'lumot (savolsiz)', info.ok && info.test.question_count === 2 && !info.test.questions && info.done === false);
check('o\'qituvchi test yecha olmaydi', (await api(T, 'POST', `/api/tests/${CODE}/start`)).status === 403);
check('boshlamasdan topshirib bo\'lmaydi', (await api(S, 'POST', '/api/results', { test_id: info.test.id, answers: [0, 0] })).message === 'Test boshlanmagan');
const st = await api(S, 'POST', `/api/tests/${CODE}/start`);
check('start: savollar to\'g\'ri javobsiz', st.ok && st.questions.length === 2 && !('correct_index' in st.questions[0]) && !JSON.stringify(st).includes('correct'));
check('start: remaining ≈ 600s', st.remaining > 590 && st.remaining <= 600, String(st.remaining));
const st2 = await api(S, 'POST', `/api/tests/${CODE}/start`);
check('qayta start: vaqt yangilanmaydi', st2.ok && st2.remaining <= st.remaining);
check('noto\'g\'ri uzunlikdagi javoblar rad', (await api(S, 'POST', '/api/results', { test_id: st.test.id, answers: [0] })).ok === false);
check('diapazondan tashqari javob rad', (await api(S, 'POST', '/api/results', { test_id: st.test.id, answers: [0, 9] })).ok === false);
const nCalls = calls.length;
const res = await api(S, 'POST', '/api/results', { test_id: st.test.id, answers: [1, 1], cheating_count: 2 });
check('natija: 2/2', res.ok && res.score === 2 && res.total === 2 && res.late === false, JSON.stringify(res));
const note = await waitFor(() => calls.slice(nCalls).find((c) => c.method === 'sendMessage' && c.chat_id === T));
check('o\'qituvchiga xabar keldi', !!note && /Yangi natija/.test(note.text) && /Baho: 5/.test(note.text) && /Chiqib ketishlar: 2/.test(note.text));
check('xabarda HTML ekranlangan', note && note.text.includes('&lt;b&gt;1&lt;/b&gt;') && !note.text.includes('<b>1</b>'));
check('qayta topshirib bo\'lmaydi', (await api(S, 'POST', '/api/results', { test_id: st.test.id, answers: [1, 1] })).done === true);
check('qayta start → done', (await api(S, 'POST', `/api/tests/${CODE}/start`)).done === true);
check('info.done = true', (await api(S, 'GET', '/api/tests/' + CODE)).done === true);

console.log('\n[API: statistika]');
await say(S2, '/start'); await say(S2, 'Karimov Sardor'); await say(S2, '901234567'); await press(S2, 'role:student');
const s2 = await api(S2, 'POST', `/api/tests/${CODE}/start`);
const r2 = await api(S2, 'POST', '/api/results', { test_id: s2.test.id, answers: [0, 1] });
check('S2: 1/2', r2.score === 1);
const sr = await api(S, 'GET', '/api/student/results');
check('o\'quvchi natijalari + baho', sr.summary.count === 1 && sr.summary.avg_pct === 100 && sr.summary.avg_grade === 5);
check('o\'quvchi teacher endpointga kira olmaydi', (await api(S, 'GET', '/api/teacher/overview')).status === 403);
const tr = await api(T, 'GET', `/api/teacher/results/${st.test.id}`);
check('reyting tartibi (eng yuqori birinchi)', tr.results.length === 2 && tr.results[0].score === 2 && tr.results[0].full_name === 'Aliyev Vali');
check('stats: o\'rtacha 75%, baholar, chiqib ketganlar',
  tr.stats.count === 2 && tr.stats.avg_pct === 75 && tr.stats.distribution['5'] === 1 && tr.stats.distribution['3'] === 0
  && tr.stats.distribution['4'] === 0 && tr.stats.cheaters === 1 && tr.stats.max_pct === 100 && tr.stats.min_pct === 50,
  JSON.stringify(tr.stats));
const ov = await api(T, 'GET', '/api/teacher/overview');
check('overview', ov.overview.tests === 1 && ov.overview.results === 2 && ov.overview.students === 2 && ov.tests[0].participants === 2
  && ov.tests[0].avg_pct === 75);

// boshqa o'qituvchi
await say(T2, '/start'); await say(T2, 'Rahimov Anvar'); await say(T2, '+998 99 000 11 22');
await press(T2, 'role:teacher'); await say(T2, TEACHER_CODE);
check('boshqa o\'qituvchi natijani ko\'ra olmaydi', (await api(T2, 'GET', `/api/teacher/results/${st.test.id}`)).status === 404);
check('boshqa o\'qituvchi o\'chira olmaydi', (await api(T2, 'DELETE', `/api/teacher/tests/${st.test.id}`)).status === 404);
check('boshqa o\'qituvchining ro\'yxati bo\'sh', (await api(T2, 'GET', '/api/teacher/tests')).tests.length === 0);

console.log('\n[API: vaqt nazorati]');
const q2 = await api(T, 'POST', '/api/tests', { subject: 'Fizika', name: 'Vaqtli', time_limit: 1, questions: pr.questions });
const sv = await api(S2, 'POST', `/api/tests/${q2.code}/start`);
check('1 daqiqalik test boshlandi', sv.ok && sv.remaining <= 60);
const rawDb = (sql) => new Promise((resolve) => {
  const p = spawn('npx', ['wrangler', 'd1', 'execute', 'bst-test-db', '--local', '--command', sql], { stdio: 'ignore' });
  p.on('close', resolve);
});
await rawDb(`UPDATE attempts SET started_at=started_at-300 WHERE test_id=${sv.test.id}`);
const late = await api(S2, 'POST', '/api/results', { test_id: sv.test.id, answers: [1, 1] });
check('kech topshirilsa: 0 ball + late', late.ok && late.score === 0 && late.late === true, JSON.stringify(late));

// o'quvchi ilovani yopib ketgan, vaqt tugagan
const sOld = await api(S, 'POST', `/api/tests/${q2.code}/start`);
await rawDb(`UPDATE attempts SET started_at=started_at-300 WHERE test_id=${sv.test.id} AND student_id=${S}`);
// (S uchun start yuqorida allaqachon yaratilgan; endi qayta start → expired)
const exp = await api(S, 'POST', `/api/tests/${q2.code}/start`);
check('start paytida vaqt o\'tib ketgan → expired va yakunlangan', exp.expired === true || exp.done === true, JSON.stringify(exp));
const sres = await api(S, 'GET', '/api/student/results');
check('expired natija 0 ball bilan saqlangan', sres.results.some((r) => r.test_name === 'Vaqtli' && r.score === 0));

console.log('\n[API: o\'chirish]');
check('o\'qituvchi testini o\'chiradi', (await api(T, 'DELETE', `/api/teacher/tests/${st.test.id}`)).ok === true);
check('o\'chirilgan test topilmaydi', (await api(S, 'GET', '/api/tests/' + CODE)).status === 404);
check('natijalar ham o\'chgan', (await api(S, 'GET', '/api/student/results')).results.every((r) => r.test_name !== 'Sinov <b>1</b>'));

console.log('\n[Statik ilova]');
const page = await fetch(BASE + '/');
const html = await page.text();
check('/ → veb-ilova HTML', page.status === 200 && html.includes('telegram-web-app.js') && html.length > 20000);

console.log(`\n${passed} o'tdi, ${failed} yiqildi`);
stop();
process.exit(failed ? 1 : 0);
