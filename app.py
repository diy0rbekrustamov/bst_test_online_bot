"""
Flask API server — Telegram Mini App backend.

Har bir so'rov Telegram `initData` imzosi bilan tekshiriladi: foydalanuvchi kimligi
klient yuborgan `user_id` dan emas, imzolangan ma'lumotdan olinadi.
"""
import gzip
import hashlib
import hmac
import html
import json
import threading
import time
from functools import wraps
from urllib.parse import parse_qsl

import requests as req
from flask import Flask, g, jsonify, request, send_from_directory

import config
from database import (
    init_db, get_user,
    parse_questions, validate_questions, create_test, get_test_by_code, get_test_by_id,
    get_questions, already_attempted, start_attempt, get_attempt_start, save_result,
    get_test_results, get_teacher_tests, get_student_results, delete_test,
    get_test_stats, get_teacher_overview,
)

app = Flask(__name__, static_folder='webapp', static_url_path='')

TIME_GRACE_SECONDS = 60       # tarmoq kechikishi uchun zaxira
MAX_NAME_LEN = 80
ALLOWED_ROLES = ('teacher', 'student')


def fail(message, status=400, **extra):
    return jsonify({'ok': False, 'message': message, **extra}), status


# ── Autentifikatsiya ─────────────────────────────────────────────────────────
def verify_init_data(init_data):
    """Telegram Mini App initData imzosini tekshiradi. To'g'ri bo'lsa user id, aks holda None."""
    if not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None
    received = pairs.pop('hash', None)
    if not received:
        return None
    check = '\n'.join(f'{k}={v}' for k, v in sorted(pairs.items()))
    secret = hmac.new(b'WebAppData', config.BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        return None
    try:
        if time.time() - int(pairs.get('auth_date', 0)) > config.INIT_DATA_MAX_AGE_HOURS * 3600:
            return None
        return int(json.loads(pairs['user'])['id'])
    except (KeyError, ValueError, TypeError):
        return None


def auth(role=None):
    """Himoyalangan endpoint. role='teacher' bo'lsa faqat o'qituvchi kira oladi."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            uid = None
            if config.DEV_MODE and request.headers.get('X-Dev-User', '').isdigit():
                uid = int(request.headers['X-Dev-User'])
            else:
                uid = verify_init_data(request.headers.get('X-Tg-Init-Data', ''))
            if uid is None:
                return fail("Telegram orqali kiring (autentifikatsiya xatosi)", 401)
            g.uid = uid
            if role:
                user = get_user(uid)
                if not user:
                    return fail("Avval botda ro'yxatdan o'ting", 403, unregistered=True)
                if user['role'] != role:
                    return fail("Bu amal uchun ruxsat yo'q", 403)
                g.user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ── Yordamchilar ─────────────────────────────────────────────────────────────
def grade_for(pct):
    return '5' if pct >= 86 else '4' if pct >= 71 else '3' if pct >= 56 else '2'


def _send_message(chat_id, text):
    try:
        r = req.post(f'https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage',
                     json={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}, timeout=8)
        if not r.ok:
            print(f"Bildirishnoma yuborilmadi: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"Bildirishnoma xatosi: {e}")


def notify_teacher(teacher_id, text):
    # So'rovni kutib o'tirmaslik uchun alohida oqimda
    threading.Thread(target=_send_message, args=(teacher_id, text), daemon=True).start()


def finalize_result(test, student_id, answers, cheating_count):
    """Natijani hisoblab saqlaydi va o'qituvchiga xabar yuboradi. Saqlanmasa None."""
    qs = get_questions(test['id'])
    score = sum(1 for q, a in zip(qs, answers) if a == q['correct_index'])
    total = len(qs)
    if not save_result(test['id'], student_id, score, total, answers, cheating_count):
        return None
    student = get_user(student_id)
    if student:
        pct = score / total * 100 if total else 0
        cheat = f"\n⚠️ Chiqib ketishlar: {cheating_count}" if cheating_count else ""
        notify_teacher(
            test['teacher_id'],
            f"📢 <b>Yangi natija!</b>\n\n"
            f"👤 {html.escape(student['full_name'])}\n"
            f"📚 {html.escape(test['subject'])} — {html.escape(test['test_name'])}\n"
            f"🎯 {score}/{total} ({pct:.0f}%) — Baho: {grade_for(pct)}{cheat}"
        )
    return {'score': score, 'total': total, 'cheating_count': cheating_count}


def remaining_seconds(test, started_at):
    if not test['time_limit']:
        return None
    return int(started_at + test['time_limit'] * 60 - time.time())


# ── Sahifa ───────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    resp = send_from_directory('webapp', 'index.html')
    resp.headers['Cache-Control'] = 'no-cache'   # har safar tekshiradi, o'zgarmagan bo'lsa 304 (tez)
    return resp


# ── Foydalanuvchi ────────────────────────────────────────────────────────────
# Ro'yxatdan o'tish va rol tanlash faqat Telegram bot orqali (o'qituvchi uchun kod bilan).
# Veb-ilova rolni o'zgartira olmaydi — shuning uchun o'zini o'qituvchi qilib qo'yib bo'lmaydi.
@app.route('/api/me')
@auth()
def api_me():
    return jsonify({'ok': True, 'user': get_user(g.uid)})


# ── O'qituvchi: test yaratish ────────────────────────────────────────────────
@app.route('/api/parse-questions', methods=['POST'])
@auth('teacher')
def api_parse():
    text = (request.get_json(silent=True) or {}).get('text', '')
    questions, errors = parse_questions(str(text))
    return jsonify({'ok': True, 'questions': questions, 'errors': errors})


@app.route('/api/tests', methods=['POST'])
@auth('teacher')
def api_create_test():
    d = request.get_json(silent=True) or {}
    subject = str(d.get('subject', '')).strip()
    name = str(d.get('name', '')).strip()
    questions = d.get('questions', [])
    try:
        time_limit = int(d.get('time_limit', 0))
    except (TypeError, ValueError):
        return fail("Vaqt chegarasi noto'g'ri")
    if not subject or not name:
        return fail("Ma'lumotlar to'liq emas")
    if len(name) > 100 or len(subject) > 50:
        return fail("Nom juda uzun")
    if not (0 <= time_limit <= 300):
        return fail("Vaqt chegarasi noto'g'ri")
    err = validate_questions(questions)
    if err:
        return fail(err)
    code, test_id = create_test(g.uid, subject, name, questions, time_limit)
    return jsonify({'ok': True, 'code': code, 'test_id': test_id})


@app.route('/api/teacher/tests')
@auth('teacher')
def api_teacher_tests():
    return jsonify({'ok': True, 'tests': get_teacher_tests(g.uid)})


@app.route('/api/teacher/results/<int:test_id>')
@auth('teacher')
def api_test_results(test_id):
    test = get_test_by_id(test_id)
    if not test or test['teacher_id'] != g.uid:      # boshqa o'qituvchining natijasi yopiq
        return fail("Test topilmadi", 404)
    return jsonify({'ok': True, 'results': get_test_results(test_id), 'stats': get_test_stats(test_id)})


@app.route('/api/teacher/overview')
@auth('teacher')
def api_teacher_overview():
    tests = get_teacher_tests(g.uid)
    for t in tests:
        st = get_test_stats(t['id'])
        t['avg_pct'], t['distribution'] = st['avg_pct'], st['distribution']
    return jsonify({'ok': True, 'overview': get_teacher_overview(g.uid), 'tests': tests})


@app.route('/api/teacher/tests/<int:test_id>', methods=['DELETE'])
@auth('teacher')
def api_delete_test(test_id):
    if not delete_test(test_id, g.uid):
        return fail("Test topilmadi", 404)
    return jsonify({'ok': True})


# ── O'quvchi: test yechish ───────────────────────────────────────────────────
@app.route('/api/tests/<code>')
@auth('student')
def api_get_test(code):
    """Test haqida ma'lumot (savollarsiz)."""
    test = get_test_by_code(code) if code.isdigit() and len(code) == 6 else None
    if not test:
        return fail("Test topilmadi", 404)
    info = {k: test[k] for k in ('id', 'code', 'subject', 'test_name', 'time_limit',
                                 'teacher_name', 'question_count')}
    return jsonify({'ok': True, 'test': info, 'done': already_attempted(test['id'], g.uid)})


@app.route('/api/tests/<code>/start', methods=['POST'])
@auth('student')
def api_start_test(code):
    """Testni boshlaydi: boshlanish vaqtini serverda belgilaydi va savollarni beradi."""
    test = get_test_by_code(code) if code.isdigit() and len(code) == 6 else None
    if not test:
        return fail("Test topilmadi", 404)
    if already_attempted(test['id'], g.uid):
        return fail("Allaqachon yechilgan", done=True)

    started_at = start_attempt(test['id'], g.uid)
    left = remaining_seconds(test, started_at)
    if left is not None and left <= -TIME_GRACE_SECONDS:
        # Ilovani yopib ketgan, vaqt tugagan: bo'sh javob bilan yakunlanadi
        qs = get_questions(test['id'])
        finalize_result(test, g.uid, [-1] * len(qs), 0)
        return fail("Vaqt tugagan, test yakunlandi", expired=True)

    qs = get_questions(test['id'])
    safe_qs = [{'id': q['id'], 'question_text': q['question_text'], 'options': q['options']} for q in qs]
    info = {k: test[k] for k in ('id', 'subject', 'test_name', 'time_limit')}
    return jsonify({'ok': True, 'test': info, 'questions': safe_qs,
                    'remaining': None if left is None else max(left, 0)})


@app.route('/api/results', methods=['POST'])
@auth('student')
def api_submit_result():
    d = request.get_json(silent=True) or {}
    try:
        test_id = int(d.get('test_id'))
        cheating_count = max(0, min(int(d.get('cheating_count', 0)), 99))
    except (TypeError, ValueError):
        return fail("So'rov noto'g'ri")
    answers = d.get('answers')

    test = get_test_by_id(test_id)
    if not test:
        return fail("Test topilmadi", 404)
    if already_attempted(test_id, g.uid):
        return fail("Allaqachon yechilgan", done=True)
    started_at = get_attempt_start(test_id, g.uid)
    if started_at is None:
        return fail("Test boshlanmagan")

    qs = get_questions(test_id)
    if (not isinstance(answers, list) or len(answers) != len(qs)
            or not all(isinstance(a, int) and not isinstance(a, bool) and -1 <= a < len(q['options'])
                       for a, q in zip(answers, qs))):
        return fail("Javoblar noto'g'ri")

    left = remaining_seconds(test, started_at)
    if left is not None and left < -TIME_GRACE_SECONDS:
        answers = [-1] * len(qs)       # vaqtdan keyin kelgan javoblar hisobga olinmaydi

    res = finalize_result(test, g.uid, answers, cheating_count)
    if res is None:
        return fail("Allaqachon yechilgan", done=True)
    return jsonify({'ok': True, **res, 'late': left is not None and left < -TIME_GRACE_SECONDS})


@app.route('/api/student/results')
@auth('student')
def api_student_results():
    results = get_student_results(g.uid)
    pcts = [round(r['score'] / r['total'] * 100) if r['total'] else 0 for r in results]
    avg = round(sum(pcts) / len(pcts)) if pcts else 0
    return jsonify({'ok': True, 'results': results,
                    'summary': {'count': len(results), 'avg_pct': avg, 'avg_grade': int(grade_for(avg)) if pcts else None}})


# ── Siqish: sahifa va JSON ~5 marta kichrayadi (sekin internetda tezroq ochiladi) ──
@app.after_request
def compress(resp):
    if (resp.status_code != 200 or 'Content-Encoding' in resp.headers
            or resp.mimetype not in ('text/html', 'application/json')
            or 'gzip' not in request.headers.get('Accept-Encoding', '')):
        return resp
    resp.direct_passthrough = False
    data = resp.get_data()
    if len(data) < 800:
        return resp
    resp.set_data(gzip.compress(data, 5))
    resp.headers['Content-Encoding'] = 'gzip'
    resp.headers['Vary'] = 'Accept-Encoding'
    return resp


# ── Xatolar JSON qaytarsin ───────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith('/api/'):
        return fail("Topilmadi", 404)
    return "Not found", 404


@app.errorhandler(Exception)
def server_error(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return fail(e.description, e.code) if request.path.startswith('/api/') else e
    app.logger.exception("Server xatosi")
    return fail("Serverda xatolik yuz berdi", 500)


if __name__ == '__main__':
    init_db()
    app.run(port=config.PORT, debug=False)
