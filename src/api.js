// Mini App uchun API (app.py ning JavaScript varianti; endpointlar va xabarlar bir xil)
import { verifyInitData } from './auth.js';
import * as D from './db.js';
import { parseQuestions, validateQuestions } from './parser.js';
import { sendMessage } from './telegram.js';
import { json, fail, now, esc, gradeOf, pyRound, toInt, readJson } from './util.js';

const TIME_GRACE_SECONDS = 60;   // tarmoq kechikishi uchun zaxira
const CODE_RE = /^\d{6}$/;

const remainingSeconds = (test, startedAt) =>
  test.time_limit ? Math.trunc(startedAt + test.time_limit * 60 - now()) : null;

/** Natijani hisoblab saqlaydi va o'qituvchiga xabar yuboradi. Saqlanmasa null. */
async function finalizeResult(c, test, studentId, answers, cheating) {
  const qs = await D.getQuestions(c.env.DB, test.id);
  const score = qs.reduce((s, q, i) => s + (answers[i] === q.correct_index ? 1 : 0), 0);
  const total = qs.length;
  if (!(await D.saveResult(c.env.DB, test.id, studentId, score, total, answers, cheating))) return null;

  const student = await D.getUser(c.env.DB, studentId);
  if (student) {
    const pct = total ? (score / total) * 100 : 0;
    const cheat = cheating ? `\n⚠️ Qoidabuzarliklar (chiqish/skrinshot): ${cheating}` : '';
    // Javobni kutdirmaymiz: xabar fonda yuboriladi
    c.ctx.waitUntil(sendMessage(c.env, test.teacher_id,
      `📢 <b>Yangi natija!</b>\n\n` +
      `👤 ${esc(student.full_name)}\n` +
      `📚 ${esc(test.subject)} — ${esc(test.test_name)}\n` +
      `🎯 ${score}/${total} (${pct.toFixed(0)}%) — Baho: ${gradeOf(pct)}${cheat}`));
  }
  return { score, total, cheating_count: cheating };
}

// ── Endpointlar ──────────────────────────────────────────────────────────────
const me = async (c) => json({ ok: true, user: await D.getUser(c.env.DB, c.uid) });

async function parseEndpoint(c) {
  const d = await readJson(c.request);
  const { questions, errors } = parseQuestions(String(d.text ?? ''));
  return json({ ok: true, questions, errors });
}

async function createTestEndpoint(c) {
  const d = await readJson(c.request);
  const subject = String(d.subject ?? '').trim();
  const name = String(d.name ?? '').trim();
  const timeLimit = toInt(d.time_limit === undefined ? 0 : d.time_limit);
  if (Number.isNaN(timeLimit)) return fail("Vaqt chegarasi noto'g'ri");
  if (!subject || !name) return fail("Ma'lumotlar to'liq emas");
  if (name.length > 100 || subject.length > 50) return fail('Nom juda uzun');
  if (!(timeLimit >= 0 && timeLimit <= 300)) return fail("Vaqt chegarasi noto'g'ri");
  const err = validateQuestions(d.questions);
  if (err) return fail(err);
  const { code, testId } = await D.createTest(c.env.DB, c.uid, subject, name, d.questions, timeLimit);
  return json({ ok: true, code, test_id: testId });
}

const teacherTests = async (c) => json({ ok: true, tests: await D.getTeacherTests(c.env.DB, c.uid) });

async function testResults(c, id) {
  const test = await D.getTestById(c.env.DB, Number(id));
  if (!test || test.teacher_id !== c.uid) return fail('Test topilmadi', 404);   // boshqa o'qituvchining natijasi yopiq
  const [results, stats] = await Promise.all([D.getTestResults(c.env.DB, test.id), D.getTestStats(c.env.DB, test.id)]);
  return json({ ok: true, results, stats });
}

async function teacherOverview(c) {
  const tests = await D.getTeacherTests(c.env.DB, c.uid);
  await Promise.all(tests.map(async (t) => {
    const st = await D.getTestStats(c.env.DB, t.id);
    t.avg_pct = st.avg_pct;
    t.distribution = st.distribution;
  }));
  return json({ ok: true, overview: await D.getTeacherOverview(c.env.DB, c.uid), tests });
}

async function deleteTest(c, id) {
  if (!(await D.deleteTest(c.env.DB, Number(id), c.uid))) return fail('Test topilmadi', 404);
  return json({ ok: true });
}

async function getTest(c, code) {
  const test = CODE_RE.test(code) ? await D.getTestByCode(c.env.DB, code) : null;
  if (!test) return fail('Test topilmadi', 404);
  const info = {};
  for (const k of ['id', 'code', 'subject', 'test_name', 'time_limit', 'teacher_name', 'question_count']) info[k] = test[k];
  return json({ ok: true, test: info, done: await D.alreadyAttempted(c.env.DB, test.id, c.uid) });
}

/** Testni boshlaydi: boshlanish vaqtini serverda belgilaydi va savollarni beradi. */
async function startTest(c, code) {
  const db = c.env.DB;
  const test = CODE_RE.test(code) ? await D.getTestByCode(db, code) : null;
  if (!test) return fail('Test topilmadi', 404);
  if (await D.alreadyAttempted(db, test.id, c.uid)) return fail('Allaqachon yechilgan', 400, { done: true });

  const startedAt = await D.startAttempt(db, test.id, c.uid);
  const left = remainingSeconds(test, startedAt);
  const qs = await D.getQuestions(db, test.id);
  if (left !== null && left <= -TIME_GRACE_SECONDS) {
    // Ilovani yopib ketgan, vaqt tugagan: bo'sh javob bilan yakunlanadi
    await finalizeResult(c, test, c.uid, qs.map(() => -1), 0);
    return fail('Vaqt tugagan, test yakunlandi', 400, { expired: true });
  }
  const safe = qs.map((q) => ({ id: q.id, question_text: q.question_text, options: q.options }));
  const info = {};
  for (const k of ['id', 'subject', 'test_name', 'time_limit']) info[k] = test[k];
  return json({ ok: true, test: info, questions: safe, remaining: left === null ? null : Math.max(left, 0) });
}

async function submitResult(c) {
  const db = c.env.DB;
  const d = await readJson(c.request);
  const testId = toInt(d.test_id);
  let cheating = toInt(d.cheating_count === undefined ? 0 : d.cheating_count);
  if (Number.isNaN(testId) || Number.isNaN(cheating)) return fail("So'rov noto'g'ri");
  cheating = Math.max(0, Math.min(cheating, 99));
  let answers = d.answers;

  const test = await D.getTestById(db, testId);
  if (!test) return fail('Test topilmadi', 404);
  if (await D.alreadyAttempted(db, testId, c.uid)) return fail('Allaqachon yechilgan', 400, { done: true });
  const startedAt = await D.getAttemptStart(db, testId, c.uid);
  if (startedAt === null) return fail('Test boshlanmagan');

  const qs = await D.getQuestions(db, testId);
  if (!Array.isArray(answers) || answers.length !== qs.length ||
      !answers.every((a, i) => Number.isInteger(a) && a >= -1 && a < qs[i].options.length)) {
    return fail("Javoblar noto'g'ri");
  }

  const left = remainingSeconds(test, startedAt);
  const late = left !== null && left < -TIME_GRACE_SECONDS;
  if (late) answers = qs.map(() => -1);          // vaqtdan keyin kelgan javoblar hisobga olinmaydi

  const res = await finalizeResult(c, test, c.uid, answers, cheating);
  if (!res) return fail('Allaqachon yechilgan', 400, { done: true });
  return json({ ok: true, ...res, late });
}

async function studentResults(c) {
  const results = await D.getStudentResults(c.env.DB, c.uid);
  const pcts = results.map((r) => (r.total ? pyRound((r.score / r.total) * 100) : 0));
  const avg = pcts.length ? pyRound(pcts.reduce((s, x) => s + x, 0) / pcts.length) : 0;
  return json({ ok: true, results, summary: { count: results.length, avg_pct: avg, avg_grade: pcts.length ? gradeOf(avg) : null } });
}

// ── Marshrutlar: [metod, yo'l, rol, ishlovchi] ───────────────────────────────
const ROUTES = [
  ['GET',    /^\/api\/me$/,                          null,      me],
  ['POST',   /^\/api\/parse-questions$/,             'teacher', parseEndpoint],
  ['POST',   /^\/api\/tests$/,                       'teacher', createTestEndpoint],
  ['GET',    /^\/api\/teacher\/tests$/,              'teacher', teacherTests],
  ['GET',    /^\/api\/teacher\/results\/(\d+)$/,     'teacher', testResults],
  ['GET',    /^\/api\/teacher\/overview$/,           'teacher', teacherOverview],
  ['DELETE', /^\/api\/teacher\/tests\/(\d+)$/,       'teacher', deleteTest],
  ['GET',    /^\/api\/tests\/([^/]+)$/,              'student', getTest],
  ['POST',   /^\/api\/tests\/([^/]+)\/start$/,       'student', startTest],
  ['POST',   /^\/api\/results$/,                     'student', submitResult],
  ['GET',    /^\/api\/student\/results$/,            'student', studentResults],
];

async function authenticate(request, env) {
  if (env.DEV_MODE === '1') {
    const dev = request.headers.get('X-Dev-User') || '';
    if (/^\d+$/.test(dev)) return Number(dev);
  }
  return verifyInitData(request.headers.get('X-Tg-Init-Data') || '', env.BOT_TOKEN);
}

export async function handleApi(request, env, ctx) {
  try {
    const path = new URL(request.url).pathname.replace(/(.)\/+$/, '$1');
    let pathMatched = false;
    for (const [method, re, role, handler] of ROUTES) {
      const m = path.match(re);
      if (!m) continue;
      pathMatched = true;
      if (method !== request.method) continue;

      const uid = await authenticate(request, env);
      if (uid === null) return fail('Telegram orqali kiring (autentifikatsiya xatosi)', 401);
      const c = { request, env, ctx, uid, user: null };
      if (role) {
        const user = await D.getUser(env.DB, uid);
        if (!user) return fail("Avval botda ro'yxatdan o'ting", 403, { unregistered: true });
        if (user.role !== role) return fail("Bu amal uchun ruxsat yo'q", 403);
        c.user = user;
      }
      return await handler(c, ...m.slice(1).map((x) => decodeURIComponent(x)));
    }
    return pathMatched ? fail('Metod ruxsat etilmagan', 405) : fail('Topilmadi', 404);
  } catch (e) {
    console.log('API xatosi:', e && e.stack || e);
    return fail('Serverda xatolik yuz berdi', 500);
  }
}
