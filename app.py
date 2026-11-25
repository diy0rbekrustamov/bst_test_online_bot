"""
Flask API server - Telegram Mini App backend
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests as req
import os, json
from database import (
    init_db, get_user, save_user, update_role,
    parse_questions, create_test, get_test_by_code, get_test_by_id,
    get_questions, already_attempted, save_result,
    get_test_results, get_teacher_tests, get_student_results
)

app = Flask(__name__, static_folder='webapp', static_url_path='')
CORS(app)

# ── Telegram bildirishnomasi ──────────────────────────────────────────────────
def notify_teacher(teacher_id, text):
    try:
        from config import BOT_TOKEN
        req.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={'chat_id': teacher_id, 'text': text, 'parse_mode': 'Markdown'},
            timeout=5
        )
    except Exception as e:
        print(f"Bildirishnoma xatosi: {e}")

# ── Static fayllar ────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('webapp', 'index.html')

# ── API endpoints ─────────────────────────────────────────────────────────────

@app.route('/api/user/<int:user_id>')
def api_get_user(user_id):
    user = get_user(user_id)
    if user:
        return jsonify({'ok': True, 'user': user})
    return jsonify({'ok': False, 'message': 'Topilmadi'}), 404

@app.route('/api/register', methods=['POST'])
def api_register():
    d = request.json
    user_id  = d.get('user_id')
    fullname = d.get('full_name', '').strip()
    phone    = d.get('phone', '').strip()
    role     = d.get('role', 'student')
    if not user_id or not fullname or not phone:
        return jsonify({'ok': False, 'message': 'Ma\'lumotlar to\'liq emas'}), 400
    if len(fullname.split()) < 2:
        return jsonify({'ok': False, 'message': 'To\'liq ism-familiya kiriting'}), 400
    save_user(user_id, fullname, phone, role)
    return jsonify({'ok': True, 'user': get_user(user_id)})

@app.route('/api/role', methods=['POST'])
def api_update_role():
    d = request.json
    update_role(d['user_id'], d['role'])
    return jsonify({'ok': True})

@app.route('/api/parse-questions', methods=['POST'])
def api_parse():
    text = request.json.get('text', '')
    questions, errors = parse_questions(text)
    return jsonify({'ok': True, 'questions': questions, 'errors': errors})

@app.route('/api/tests', methods=['POST'])
def api_create_test():
    d = request.json
    teacher_id = d.get('teacher_id')
    subject    = d.get('subject', '')
    name       = d.get('name', '').strip()
    questions  = d.get('questions', [])
    time_limit = int(d.get('time_limit', 0))
    if not teacher_id or not subject or not name or not questions:
        return jsonify({'ok': False, 'message': 'Ma\'lumotlar to\'liq emas'}), 400
    code, test_id = create_test(teacher_id, subject, name, questions, time_limit)
    return jsonify({'ok': True, 'code': code, 'test_id': test_id})

@app.route('/api/tests/<code>')
def api_get_test(code):
    test = get_test_by_code(code)
    if not test:
        return jsonify({'ok': False, 'message': 'Test topilmadi'}), 404
    qs = get_questions(test['id'])
    # O'quvchiga faqat savol va variantlarni ber (to'g'ri javobsiz)
    safe_qs = [{'id': q['id'], 'question_text': q['question_text'],
                 'options': q['options'].split('|||'), 'order_num': q['order_num']} for q in qs]
    return jsonify({'ok': True, 'test': test, 'questions': safe_qs})

@app.route('/api/results', methods=['POST'])
def api_submit_result():
    d = request.json
    test_id       = d.get('test_id')
    student_id    = d.get('student_id')
    answers       = d.get('answers', [])      # list of chosen indices
    cheating_count= int(d.get('cheating_count', 0))

    if already_attempted(test_id, student_id):
        return jsonify({'ok': False, 'message': 'Allaqachon yechilgan'}), 400

    # To'g'ri javoblarni server tomonida tekshir
    qs = get_questions(test_id)
    if len(answers) != len(qs):
        return jsonify({'ok': False, 'message': 'Javoblar soni noto\'g\'ri'}), 400

    score = sum(1 for q, a in zip(qs, answers) if int(a) == q['correct_index'])
    total = len(qs)
    save_result(test_id, student_id, score, total, answers, cheating_count)

    # O'qituvchiga xabar
    test = get_test_by_id(test_id)
    student = get_user(student_id)
    if test and student:
        pct = score/total*100 if total else 0
        grade = "5" if pct>=86 else "4" if pct>=71 else "3" if pct>=56 else "2"
        cheat_note = f"\n⚠️ Chit urinishlari: {cheating_count}" if cheating_count > 0 else ""
        notify_teacher(
            test['teacher_id'],
            f"📢 *Yangi natija!*\n\n"
            f"👤 {student['full_name']}\n"
            f"📚 {test['subject']} — {test['test_name']}\n"
            f"🎯 {score}/{total} ({pct:.0f}%) — Baho: {grade}{cheat_note}"
        )

    return jsonify({'ok': True, 'score': score, 'total': total, 'cheating_count': cheating_count})

@app.route('/api/teacher/tests/<int:teacher_id>')
def api_teacher_tests(teacher_id):
    tests = get_teacher_tests(teacher_id)
    return jsonify({'ok': True, 'tests': tests})

@app.route('/api/teacher/results/<int:test_id>')
def api_test_results(test_id):
    results = get_test_results(test_id)
    return jsonify({'ok': True, 'results': results})

@app.route('/api/student/results/<int:student_id>')
def api_student_results(student_id):
    results = get_student_results(student_id)
    return jsonify({'ok': True, 'results': results})

if __name__ == '__main__':
    init_db()
    app.run(port=5000, debug=False)
