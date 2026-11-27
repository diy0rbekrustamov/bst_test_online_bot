// D1 bilan ishlash (database.py ning JavaScript varianti)
import { gradeOf, pyRound, now } from './util.js';

// ── Foydalanuvchilar ─────────────────────────────────────────────────────────
export const getUser = (db, id) => db.prepare('SELECT * FROM users WHERE user_id=?').bind(id).first();

export function saveUser(db, id, fullName, phone, role = 'student') {
  return db.prepare(`INSERT INTO users(user_id,full_name,phone,role) VALUES(?,?,?,?)
                     ON CONFLICT(user_id) DO UPDATE SET
                       full_name=excluded.full_name, phone=excluded.phone, role=excluded.role`)
    .bind(id, fullName, phone, role).run();
}

export const updateRole = (db, id, role) =>
  db.prepare('UPDATE users SET role=? WHERE user_id=?').bind(role, id).run();

// ── Testlar ──────────────────────────────────────────────────────────────────
function genCode() {
  const buf = new Uint32Array(6);
  crypto.getRandomValues(buf);
  return [...buf].map((n) => n % 10).join('');
}

export function decodeOptions(raw) {
  try {
    const v = JSON.parse(raw);
    if (Array.isArray(v)) return v.map(String);
  } catch { /* eski format */ }
  return String(raw).split('|||');
}

export async function createTest(db, teacherId, subject, name, questions, timeLimit) {
  for (let attempt = 0; attempt < 10; attempt++) {
    const code = genCode();
    let testId;
    try {
      const r = await db.prepare('INSERT INTO tests(code,teacher_id,subject,test_name,time_limit) VALUES(?,?,?,?,?)')
        .bind(code, teacherId, subject, name, timeLimit).run();
      testId = r.meta.last_row_id;
    } catch (e) {
      if (/UNIQUE/i.test(String(e.message || e))) continue;   // kod to'qnashdi — qayta urinamiz
      throw e;
    }
    try {
      const ins = db.prepare('INSERT INTO questions(test_id,question_text,options,correct_index,order_num) VALUES(?,?,?,?,?)');
      await db.batch(questions.map((q, n) =>
        ins.bind(testId, q.question.trim(), JSON.stringify(q.options.map((o) => o.trim())), q.correct, n)));
    } catch (e) {
      await db.prepare('DELETE FROM tests WHERE id=?').bind(testId).run();   // yarim qolgan test qolmasin
      throw e;
    }
    return { code, testId };
  }
  throw new Error("Test kodi yaratib bo'lmadi");
}

const TEST_SELECT = `SELECT t.*, COALESCE(u.full_name, '—') AS teacher_name,
                            (SELECT COUNT(*) FROM questions q WHERE q.test_id=t.id) AS question_count
                     FROM tests t LEFT JOIN users u ON t.teacher_id=u.user_id`;

export const getTestByCode = (db, code) => db.prepare(`${TEST_SELECT} WHERE t.code=?`).bind(code).first();
export const getTestById = (db, id) => db.prepare(`${TEST_SELECT} WHERE t.id=?`).bind(id).first();

export async function getQuestions(db, testId) {
  const { results } = await db.prepare('SELECT * FROM questions WHERE test_id=? ORDER BY order_num, id').bind(testId).all();
  return results.map((r) => ({ ...r, options: decodeOptions(r.options) }));
}

export async function deleteTest(db, testId, teacherId) {
  const own = await db.prepare('SELECT id FROM tests WHERE id=? AND teacher_id=?').bind(testId, teacherId).first();
  if (!own) return false;
  await db.batch([
    db.prepare('DELETE FROM results WHERE test_id=?').bind(testId),
    db.prepare('DELETE FROM attempts WHERE test_id=?').bind(testId),
    db.prepare('DELETE FROM questions WHERE test_id=?').bind(testId),
    db.prepare('DELETE FROM tests WHERE id=?').bind(testId),
  ]);
  return true;
}

// ── Urinishlar va natijalar ──────────────────────────────────────────────────
export async function alreadyAttempted(db, testId, studentId) {
  return !!(await db.prepare('SELECT 1 AS x FROM results WHERE test_id=? AND student_id=?').bind(testId, studentId).first());
}

/** Boshlanish vaqti (epoch, soniya). Qayta chaqirilsa eskisini qaytaradi. */
export async function startAttempt(db, testId, studentId) {
  await db.prepare('INSERT OR IGNORE INTO attempts(test_id,student_id,started_at) VALUES(?,?,?)')
    .bind(testId, studentId, now()).run();
  return getAttemptStart(db, testId, studentId);
}

export async function getAttemptStart(db, testId, studentId) {
  const r = await db.prepare('SELECT started_at FROM attempts WHERE test_id=? AND student_id=?').bind(testId, studentId).first();
  return r ? r.started_at : null;
}

/** Saqlansa true; allaqachon bor bo'lsa (parallel so'rov) false. */
export async function saveResult(db, testId, studentId, score, total, answers, cheating) {
  const r = await db.prepare(`INSERT OR IGNORE INTO results(test_id,student_id,score,total,answers,cheating_count)
                              VALUES(?,?,?,?,?,?)`)
    .bind(testId, studentId, score, total, answers.join(','), cheating).run();
  return r.meta.changes > 0;
}

export async function getTestResults(db, testId) {
  const { results } = await db.prepare(`SELECT u.full_name, r.score, r.total, r.cheating_count, r.completed_at
                                        FROM results r LEFT JOIN users u ON r.student_id=u.user_id
                                        WHERE r.test_id=? ORDER BY r.score DESC, r.cheating_count ASC, r.completed_at ASC`)
    .bind(testId).all();
  return results;
}

export async function getTeacherTests(db, teacherId) {
  const { results } = await db.prepare(`SELECT t.*, COUNT(r.id) AS participants,
                                               (SELECT COUNT(*) FROM questions q WHERE q.test_id=t.id) AS question_count
                                        FROM tests t LEFT JOIN results r ON t.id=r.test_id
                                        WHERE t.teacher_id=?
                                        GROUP BY t.id ORDER BY t.created_at DESC, t.id DESC`).bind(teacherId).all();
  return results;
}

export async function getStudentResults(db, studentId) {
  const { results } = await db.prepare(`SELECT t.test_name, t.subject, r.score, r.total, r.cheating_count, r.completed_at
                                        FROM results r JOIN tests t ON r.test_id=t.id
                                        WHERE r.student_id=? ORDER BY r.completed_at DESC, r.id DESC`).bind(studentId).all();
  return results;
}

// ── Statistika ───────────────────────────────────────────────────────────────
function summarize(rows) {
  const pcts = rows.map((r) => (r.total ? pyRound((r.score / r.total) * 100) : 0));
  const dist = { 5: 0, 4: 0, 3: 0, 2: 0 };
  for (const p of pcts) dist[gradeOf(p)]++;
  return { pcts, dist };
}
const avg = (a) => (a.length ? pyRound(a.reduce((s, x) => s + x, 0) / a.length) : 0);

export async function getTestStats(db, testId) {
  const { results: rows } = await db.prepare('SELECT score, total, cheating_count FROM results WHERE test_id=?').bind(testId).all();
  const { pcts, dist } = summarize(rows);
  return {
    count: rows.length,
    avg_pct: avg(pcts),
    max_pct: pcts.length ? Math.max(...pcts) : 0,
    min_pct: pcts.length ? Math.min(...pcts) : 0,
    distribution: dist,
    cheaters: rows.filter((r) => r.cheating_count).length,
  };
}

export async function getTeacherOverview(db, teacherId) {
  const t = await db.prepare('SELECT COUNT(*) AS n FROM tests WHERE teacher_id=?').bind(teacherId).first();
  const { results: rows } = await db.prepare(`SELECT r.student_id, r.score, r.total
                                              FROM results r JOIN tests t ON r.test_id=t.id
                                              WHERE t.teacher_id=?`).bind(teacherId).all();
  const { pcts, dist } = summarize(rows);
  return {
    tests: t.n,
    results: rows.length,
    students: new Set(rows.map((r) => r.student_id)).size,
    avg_pct: avg(pcts),
    distribution: dist,
  };
}

export { avg as averagePct };
