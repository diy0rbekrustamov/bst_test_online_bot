import json
import re
import secrets
import sqlite3
import time

import config

DB_PATH = config.DB_PATH

MAX_OPTIONS = 8
MAX_QUESTIONS = 200


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        full_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        role TEXT DEFAULT 'student',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        teacher_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        test_name TEXT NOT NULL,
        time_limit INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        options TEXT NOT NULL,
        correct_index INTEGER NOT NULL,
        order_num INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        total INTEGER NOT NULL,
        answers TEXT,
        cheating_count INTEGER DEFAULT 0,
        completed_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(test_id, student_id)
    )''')
    # Testni boshlash vaqti SERVERDA saqlanadi: vaqt chegarasini aldab bo'lmasin
    # va ilovani yopib-ochib savollarni qayta ko'rib bo'lmasin.
    c.execute('''CREATE TABLE IF NOT EXISTS attempts (
        test_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        started_at INTEGER NOT NULL,
        PRIMARY KEY (test_id, student_id)
    )''')
    _migrate(c)
    c.execute('CREATE INDEX IF NOT EXISTS idx_questions_test ON questions(test_id, order_num)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_results_student ON results(student_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_tests_teacher ON tests(teacher_id)')
    conn.commit()
    conn.close()


def _migrate(c):
    """Eski versiyada yaratilgan bazaga yetishmayotgan ustunlarni qo'shadi (ma'lumotlar saqlanadi)."""
    wanted = {
        'users':     {'role': "TEXT DEFAULT 'student'", 'created_at': 'TEXT'},
        'tests':     {'time_limit': 'INTEGER DEFAULT 0', 'created_at': 'TEXT'},
        'questions': {'order_num': 'INTEGER DEFAULT 0'},
        'results':   {'answers': 'TEXT', 'cheating_count': 'INTEGER DEFAULT 0', 'completed_at': 'TEXT'},
    }
    for table, cols in wanted.items():
        have = {r[1] for r in c.execute(f'PRAGMA table_info({table})')}
        for name, ddl in cols.items():
            if name not in have:
                c.execute(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}')
    # Eski bazada UNIQUE cheklovi bo'lmasligi mumkin: bir o'quvchi bir testni ikki marta topshirmasin
    for ddl in ('CREATE UNIQUE INDEX IF NOT EXISTS uq_results ON results(test_id, student_id)',
                'CREATE UNIQUE INDEX IF NOT EXISTS uq_tests_code ON tests(code)'):
        try:
            c.execute(ddl)
        except sqlite3.IntegrityError:
            pass    # eski bazada takror yozuvlar bor — indeks qo'yilmaydi, bot baribir ishlaydi


# ── Foydalanuvchilar ─────────────────────────────────────────────────────────
def get_user(user_id):
    conn = get_db()
    r = conn.execute('SELECT * FROM users WHERE user_id=?', (user_id,)).fetchone()
    conn.close()
    return dict(r) if r else None


def save_user(user_id, full_name, phone, role='student'):
    conn = get_db()
    # INSERT OR REPLACE created_at ni qayta yozib yuborardi
    conn.execute('''INSERT INTO users(user_id,full_name,phone,role) VALUES(?,?,?,?)
                    ON CONFLICT(user_id) DO UPDATE SET
                      full_name=excluded.full_name, phone=excluded.phone, role=excluded.role''',
                 (user_id, full_name, phone, role))
    conn.commit()
    conn.close()


def update_role(user_id, role):
    conn = get_db()
    conn.execute('UPDATE users SET role=? WHERE user_id=?', (role, user_id))
    conn.commit()
    conn.close()


# ── Savollarni o'qish (parser) ───────────────────────────────────────────────
def gen_code():
    conn = get_db()
    try:
        while True:
            code = ''.join(secrets.choice('0123456789') for _ in range(6))
            if not conn.execute('SELECT 1 FROM tests WHERE code=?', (code,)).fetchone():
                return code
    finally:
        conn.close()


def parse_questions(text):
    """
    Format:
        ?Savol
        -noto'g'ri
        +to'g'ri
    Savol yoki variant bir necha qatorga cho'zilsa, keyingi qatorlar oldingisiga qo'shiladi.
    """
    questions, errors = [], []
    text = (text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not text:
        return questions, errors

    blocks = [b.strip() for b in re.split(r'\n(?=[ \t]*\?)', text)]
    for i, block in enumerate([b for b in blocks if b], 1):
        if not block.startswith('?'):
            errors.append({'num': i, 'question': block.split('\n')[0][:60],
                           'reason': "Savol '?' belgisi bilan boshlanishi kerak"})
            continue

        lines = block.split('\n')
        q_text = lines[0][1:].strip()
        options, correct_idxs = [], []
        for ln in lines[1:]:
            ln = ln.strip()
            if not ln:
                continue
            if ln[0] == '+':
                correct_idxs.append(len(options))
                options.append(ln[1:].strip())
            elif ln[0] == '-':
                options.append(ln[1:].strip())
            elif options:            # variantning davomi
                options[-1] += ' ' + ln
            else:                    # savol matnining davomi
                q_text += ' ' + ln

        if not q_text:
            errors.append({'num': i, 'reason': "Savol matni yo'q"})
        elif any(not o for o in options):
            errors.append({'num': i, 'question': q_text, 'reason': "Bo'sh variant bor"})
        elif len(options) < 2:
            errors.append({'num': i, 'question': q_text, 'reason': "Kamida 2 ta variant kerak"})
        elif len(options) > MAX_OPTIONS:
            errors.append({'num': i, 'question': q_text, 'reason': f"{MAX_OPTIONS} tadan ko'p variant bo'lmaydi"})
        elif len(correct_idxs) == 0:
            errors.append({'num': i, 'question': q_text, 'reason': "To'g'ri javob (+) belgilanmagan"})
        elif len(correct_idxs) > 1:
            errors.append({'num': i, 'question': q_text, 'reason': "To'g'ri javob (+) faqat bitta bo'lishi kerak"})
        elif len({o.casefold() for o in options}) != len(options):
            errors.append({'num': i, 'question': q_text, 'reason': "Bir xil variantlar bor"})
        else:
            questions.append({'question': q_text, 'options': options, 'correct': correct_idxs[0]})
    return questions, errors


def validate_questions(questions):
    """Klientdan kelgan savollarni qayta tekshiradi. Xato bo'lsa matn qaytaradi."""
    if not isinstance(questions, list) or not questions:
        return "Savollar yo'q"
    if len(questions) > MAX_QUESTIONS:
        return f"Eng ko'pi bilan {MAX_QUESTIONS} ta savol"
    for q in questions:
        if not isinstance(q, dict):
            return "Savol formati noto'g'ri"
        text, opts, correct = q.get('question'), q.get('options'), q.get('correct')
        if not isinstance(text, str) or not text.strip():
            return "Savol matni bo'sh"
        if not isinstance(opts, list) or not (2 <= len(opts) <= MAX_OPTIONS):
            return "Variantlar soni noto'g'ri"
        if not all(isinstance(o, str) and o.strip() for o in opts):
            return "Bo'sh variant bor"
        if not isinstance(correct, int) or isinstance(correct, bool) or not (0 <= correct < len(opts)):
            return "To'g'ri javob indeksi noto'g'ri"
    return None


# ── Testlar ──────────────────────────────────────────────────────────────────
def _encode_options(options):
    return json.dumps(options, ensure_ascii=False)


def decode_options(raw):
    """Yangi testlar JSON, eskilari '|||' bilan saqlangan — ikkalasini o'qiydi."""
    try:
        v = json.loads(raw)
        if isinstance(v, list):
            return [str(x) for x in v]
    except (ValueError, TypeError):
        pass
    return raw.split('|||')


def create_test(teacher_id, subject, test_name, questions, time_limit=0):
    conn = get_db()
    try:
        for _ in range(10):
            code = gen_code()
            try:
                c = conn.cursor()
                c.execute('INSERT INTO tests(code,teacher_id,subject,test_name,time_limit) VALUES(?,?,?,?,?)',
                          (code, teacher_id, subject, test_name, time_limit))
                tid = c.lastrowid
                c.executemany(
                    'INSERT INTO questions(test_id,question_text,options,correct_index,order_num) VALUES(?,?,?,?,?)',
                    [(tid, q['question'].strip(), _encode_options([o.strip() for o in q['options']]),
                      q['correct'], n) for n, q in enumerate(questions)])
                conn.commit()
                return code, tid
            except sqlite3.IntegrityError:   # kod to'qnashdi — qayta urinib ko'ramiz
                conn.rollback()
        raise RuntimeError("Test kodi yaratib bo'lmadi")
    finally:
        conn.close()


def _test_query(where, param):
    conn = get_db()
    r = conn.execute(f'''SELECT t.*, COALESCE(u.full_name, "—") AS teacher_name,
                                (SELECT COUNT(*) FROM questions q WHERE q.test_id=t.id) AS question_count
                         FROM tests t LEFT JOIN users u ON t.teacher_id=u.user_id
                         WHERE {where}''', (param,)).fetchone()
    conn.close()
    return dict(r) if r else None


def get_test_by_code(code):
    return _test_query('t.code=?', code)


def get_test_by_id(test_id):
    return _test_query('t.id=?', test_id)


def get_questions(test_id):
    conn = get_db()
    rows = conn.execute('SELECT * FROM questions WHERE test_id=? ORDER BY order_num, id', (test_id,)).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d['options'] = decode_options(d['options'])
        out.append(d)
    return out


def delete_test(test_id, teacher_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM tests WHERE id=? AND teacher_id=?', (test_id, teacher_id))
    if not c.fetchone():
        conn.close()
        return False
    for table in ('results', 'attempts', 'questions'):
        c.execute(f'DELETE FROM {table} WHERE test_id=?', (test_id,))
    c.execute('DELETE FROM tests WHERE id=?', (test_id,))
    conn.commit()
    conn.close()
    return True


# ── Urinishlar va natijalar ──────────────────────────────────────────────────
def already_attempted(test_id, student_id):
    conn = get_db()
    r = conn.execute('SELECT 1 FROM results WHERE test_id=? AND student_id=?', (test_id, student_id)).fetchone()
    conn.close()
    return r is not None


def start_attempt(test_id, student_id):
    """Boshlanish vaqtini (epoch, soniya) qaytaradi. Qayta chaqirilsa eskisini beradi."""
    conn = get_db()
    conn.execute('INSERT OR IGNORE INTO attempts(test_id,student_id,started_at) VALUES(?,?,?)',
                 (test_id, student_id, int(time.time())))
    conn.commit()
    r = conn.execute('SELECT started_at FROM attempts WHERE test_id=? AND student_id=?',
                     (test_id, student_id)).fetchone()
    conn.close()
    return r['started_at']


def get_attempt_start(test_id, student_id):
    conn = get_db()
    r = conn.execute('SELECT started_at FROM attempts WHERE test_id=? AND student_id=?',
                     (test_id, student_id)).fetchone()
    conn.close()
    return r['started_at'] if r else None


def save_result(test_id, student_id, score, total, answers, cheating_count=0):
    """Natija saqlansa True; allaqachon bor bo'lsa (parallel so'rov) False."""
    conn = get_db()
    try:
        conn.execute('''INSERT INTO results(test_id,student_id,score,total,answers,cheating_count)
                        VALUES(?,?,?,?,?,?)''',
                     (test_id, student_id, score, total, ','.join(map(str, answers)), cheating_count))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_test_results(test_id):
    conn = get_db()
    rows = conn.execute('''SELECT u.full_name, r.score, r.total, r.cheating_count, r.completed_at
                           FROM results r LEFT JOIN users u ON r.student_id=u.user_id
                           WHERE r.test_id=? ORDER BY r.score DESC, r.cheating_count ASC, r.completed_at ASC''',
                        (test_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_teacher_tests(teacher_id):
    conn = get_db()
    rows = conn.execute('''SELECT t.*, COUNT(r.id) AS participants,
                                  (SELECT COUNT(*) FROM questions q WHERE q.test_id=t.id) AS question_count
                           FROM tests t LEFT JOIN results r ON t.id=r.test_id
                           WHERE t.teacher_id=?
                           GROUP BY t.id ORDER BY t.created_at DESC, t.id DESC''', (teacher_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_student_results(student_id):
    conn = get_db()
    rows = conn.execute('''SELECT t.test_name, t.subject, r.score, r.total, r.cheating_count, r.completed_at
                           FROM results r JOIN tests t ON r.test_id=t.id
                           WHERE r.student_id=? ORDER BY r.completed_at DESC, r.id DESC''',
                        (student_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Statistika ───────────────────────────────────────────────────────────────
def grade_of(pct):
    return 5 if pct >= 86 else 4 if pct >= 71 else 3 if pct >= 56 else 2


def _summarize(rows):
    pcts = [round(r['score'] / r['total'] * 100) if r['total'] else 0 for r in rows]
    dist = {5: 0, 4: 0, 3: 0, 2: 0}
    for p in pcts:
        dist[grade_of(p)] += 1
    return pcts, dist


def get_test_stats(test_id):
    """Bitta test bo'yicha: topshirganlar, o'rtacha foiz, baholar taqsimoti, eng yuqori/past."""
    conn = get_db()
    rows = conn.execute('SELECT score, total, cheating_count FROM results WHERE test_id=?', (test_id,)).fetchall()
    conn.close()
    pcts, dist = _summarize(rows)
    return {
        'count': len(rows),
        'avg_pct': round(sum(pcts) / len(pcts)) if pcts else 0,
        'max_pct': max(pcts) if pcts else 0,
        'min_pct': min(pcts) if pcts else 0,
        'distribution': dist,
        'cheaters': sum(1 for r in rows if r['cheating_count']),
    }


def get_teacher_overview(teacher_id):
    """O'qituvchining barcha testlari bo'yicha umumiy statistika."""
    conn = get_db()
    tests = conn.execute('SELECT COUNT(*) AS n FROM tests WHERE teacher_id=?', (teacher_id,)).fetchone()['n']
    rows = conn.execute('''SELECT r.student_id, r.score, r.total
                           FROM results r JOIN tests t ON r.test_id=t.id
                           WHERE t.teacher_id=?''', (teacher_id,)).fetchall()
    conn.close()
    pcts, dist = _summarize(rows)
    return {
        'tests': tests,
        'results': len(rows),
        'students': len({r['student_id'] for r in rows}),
        'avg_pct': round(sum(pcts) / len(pcts)) if pcts else 0,
        'distribution': dist,
    }
