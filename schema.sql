-- D1 sxemasi (hammasi IF NOT EXISTS: qayta ishga tushirsa ham xavfsiz)
-- Qo'llash:  npx wrangler d1 execute bst-test-db --remote --file=schema.sql

CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  full_name TEXT NOT NULL,
  phone TEXT NOT NULL,
  role TEXT DEFAULT 'student',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE NOT NULL,
  teacher_id INTEGER NOT NULL,
  subject TEXT NOT NULL,
  test_name TEXT NOT NULL,
  time_limit INTEGER DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  test_id INTEGER NOT NULL,
  question_text TEXT NOT NULL,
  options TEXT NOT NULL,
  correct_index INTEGER NOT NULL,
  order_num INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  test_id INTEGER NOT NULL,
  student_id INTEGER NOT NULL,
  score INTEGER NOT NULL,
  total INTEGER NOT NULL,
  answers TEXT,
  cheating_count INTEGER DEFAULT 0,
  completed_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(test_id, student_id)
);

-- Testni boshlash vaqti SERVERDA saqlanadi (vaqt chegarasini aldab bo'lmasin)
CREATE TABLE IF NOT EXISTS attempts (
  test_id INTEGER NOT NULL,
  student_id INTEGER NOT NULL,
  started_at INTEGER NOT NULL,
  PRIMARY KEY (test_id, student_id)
);

-- Bot suhbat holati (webhook har so'rovda yangi ishga tushadi, shuning uchun holat bazada)
CREATE TABLE IF NOT EXISTS bot_state (
  user_id INTEGER PRIMARY KEY,
  state TEXT NOT NULL,
  data TEXT,
  updated_at INTEGER NOT NULL
);

-- O'qituvchi kodini taxmin qilib topishdan himoya
CREATE TABLE IF NOT EXISTS code_attempts (
  user_id INTEGER PRIMARY KEY,
  fails INTEGER NOT NULL DEFAULT 0,
  locked_until INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_questions_test ON questions(test_id, order_num);
CREATE INDEX IF NOT EXISTS idx_results_student ON results(student_id);
CREATE INDEX IF NOT EXISTS idx_tests_teacher ON tests(teacher_id);
