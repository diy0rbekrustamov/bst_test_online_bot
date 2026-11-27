// Savollarni o'qish va tekshirish (database.py dagi parse_questions / validate_questions)

export const MAX_OPTIONS = 8;
export const MAX_QUESTIONS = 200;

/**
 * Format:
 *   ?Savol
 *   -noto'g'ri
 *   +to'g'ri
 * Savol yoki variant bir necha qatorga cho'zilsa, keyingi qatorlar oldingisiga qo'shiladi.
 */
export function parseQuestions(input) {
  const questions = [];
  const errors = [];
  const text = String(input || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
  if (!text) return { questions, errors };

  const blocks = text.split(/\n(?=[ \t]*\?)/).map((b) => b.trim()).filter(Boolean);
  blocks.forEach((block, idx) => {
    const i = idx + 1;
    if (!block.startsWith('?')) {
      errors.push({ num: i, question: block.split('\n')[0].slice(0, 60), reason: "Savol '?' belgisi bilan boshlanishi kerak" });
      return;
    }
    const lines = block.split('\n');
    let qText = lines[0].slice(1).trim();
    const options = [];
    const correct = [];
    for (let raw of lines.slice(1)) {
      const ln = raw.trim();
      if (!ln) continue;
      if (ln[0] === '+') {
        correct.push(options.length);
        options.push(ln.slice(1).trim());
      } else if (ln[0] === '-') {
        options.push(ln.slice(1).trim());
      } else if (options.length) {
        options[options.length - 1] += ' ' + ln;     // variantning davomi
      } else {
        qText += ' ' + ln;                             // savol matnining davomi
      }
    }

    const err = (reason, withQ = true) => errors.push(withQ ? { num: i, question: qText, reason } : { num: i, reason });
    if (!qText) err("Savol matni yo'q", false);
    else if (options.some((o) => !o)) err("Bo'sh variant bor");
    else if (options.length < 2) err('Kamida 2 ta variant kerak');
    else if (options.length > MAX_OPTIONS) err(`${MAX_OPTIONS} tadan ko'p variant bo'lmaydi`);
    else if (correct.length === 0) err("To'g'ri javob (+) belgilanmagan");
    else if (correct.length > 1) err("To'g'ri javob (+) faqat bitta bo'lishi kerak");
    else if (new Set(options.map((o) => o.toLowerCase())).size !== options.length) err('Bir xil variantlar bor');
    else questions.push({ question: qText, options, correct: correct[0] });
  });
  return { questions, errors };
}

/** Klientdan kelgan savollarni qayta tekshiradi. Xato bo'lsa matn, aks holda null. */
export function validateQuestions(questions) {
  if (!Array.isArray(questions) || !questions.length) return "Savollar yo'q";
  if (questions.length > MAX_QUESTIONS) return `Eng ko'pi bilan ${MAX_QUESTIONS} ta savol`;
  for (const q of questions) {
    if (!q || typeof q !== 'object' || Array.isArray(q)) return "Savol formati noto'g'ri";
    const { question, options, correct } = q;
    if (typeof question !== 'string' || !question.trim()) return "Savol matni bo'sh";
    if (!Array.isArray(options) || options.length < 2 || options.length > MAX_OPTIONS) return "Variantlar soni noto'g'ri";
    if (!options.every((o) => typeof o === 'string' && o.trim())) return "Bo'sh variant bor";
    if (!Number.isInteger(correct) || correct < 0 || correct >= options.length) return "To'g'ri javob indeksi noto'g'ri";
  }
  return null;
}
