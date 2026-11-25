import sqlite3, random, string, re
from datetime import datetime

DB_PATH = 'quiz_bot.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
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
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id=?', (user_id,))
    r = c.fetchone()
    conn.close()
    return dict(r) if r else None

def save_user(user_id, full_name, phone, role='student'):
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO users(user_id,full_name,phone,role) VALUES(?,?,?,?)',
              (user_id, full_name, phone, role))
    conn.commit()
    conn.close()

def update_role(user_id, role):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET role=? WHERE user_id=?', (role, user_id))
    conn.commit()
    conn.close()

def gen_code():
    while True:
        code = ''.join(random.choices(string.digits, k=6))
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT id FROM tests WHERE code=?', (code,))
        if not c.fetchone():
            conn.close()
            return code
        conn.close()

def parse_questions(text):
    questions, errors = [], []
    blocks = re.split(r'\n(?=\?)', text.strip())
    for i, block in enumerate(blocks, 1):
        block = block.strip()
        if not block or not block.startswith('?'):
            continue
        lines = block.split('\n')
        q_text = lines[0][1:].strip()
        options, correct = [], -1
        for ln in lines[1:]:
            ln = ln.strip()
            if not ln: continue
            if ln.startswith('+'):
                correct = len(options)
                options.append(ln[1:].strip())
            elif ln.startswith('-'):
                options.append(ln[1:].strip())
        if not q_text:
            errors.append({'num': i, 'reason': 'Savol matni yo\'q'})
        elif len(options) < 2:
            errors.append({'num': i, 'question': q_text, 'reason': 'Kamida 2 javob kerak'})
        elif correct < 0:
            errors.append({'num': i, 'question': q_text, 'reason': 'To\'g\'ri javob (+) yo\'q'})
        else:
            questions.append({'question': q_text, 'options': options, 'correct': correct})
    return questions, errors

def create_test(teacher_id, subject, test_name, questions, time_limit=0):
    code = gen_code()
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO tests(code,teacher_id,subject,test_name,time_limit) VALUES(?,?,?,?,?)',
              (code, teacher_id, subject, test_name, time_limit))
    tid = c.lastrowid
    for n, q in enumerate(questions):
        c.execute('INSERT INTO questions(test_id,question_text,options,correct_index,order_num) VALUES(?,?,?,?,?)',
                  (tid, q['question'], '|||'.join(q['options']), q['correct'], n))
    conn.commit()
    conn.close()
    return code, tid

def get_test_by_code(code):
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT t.*, u.full_name AS teacher_name
                 FROM tests t JOIN users u ON t.teacher_id=u.user_id
                 WHERE t.code=?''', (code,))
    r = c.fetchone()
    conn.close()
    return dict(r) if r else None

def get_test_by_id(test_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT t.*, u.full_name AS teacher_name
                 FROM tests t JOIN users u ON t.teacher_id=u.user_id
                 WHERE t.id=?''', (test_id,))
    r = c.fetchone()
    conn.close()
    return dict(r) if r else None

def get_questions(test_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM questions WHERE test_id=? ORDER BY order_num', (test_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def already_attempted(test_id, student_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM results WHERE test_id=? AND student_id=?', (test_id, student_id))
    r = c.fetchone()
    conn.close()
    return r is not None

def save_result(test_id, student_id, score, total, answers, cheating_count=0):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO results(test_id,student_id,score,total,answers,cheating_count)
                 VALUES(?,?,?,?,?,?)''',
              (test_id, student_id, score, total, ','.join(map(str, answers)), cheating_count))
    conn.commit()
    conn.close()

def get_test_results(test_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT u.full_name, r.score, r.total, r.cheating_count, r.completed_at
                 FROM results r JOIN users u ON r.student_id=u.user_id
                 WHERE r.test_id=? ORDER BY r.score DESC''', (test_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_teacher_tests(teacher_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT t.*, COUNT(r.id) AS participants
                 FROM tests t LEFT JOIN results r ON t.id=r.test_id
                 WHERE t.teacher_id=?
                 GROUP BY t.id ORDER BY t.created_at DESC''', (teacher_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_student_results(student_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT t.test_name, t.subject, r.score, r.total, r.cheating_count, r.completed_at
                 FROM results r JOIN tests t ON r.test_id=t.id
                 WHERE r.student_id=? ORDER BY r.completed_at DESC''', (student_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]
