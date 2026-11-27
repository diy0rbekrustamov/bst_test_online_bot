// Telegram Bot API bilan ishlash

export function apiBase(env) {
  return (env.TELEGRAM_API || 'https://api.telegram.org').replace(/\/$/, '');
}

/** Bot API metodini chaqiradi. Xatoda ham yiqilmaydi: {ok:false, description} qaytaradi. */
export async function tg(env, method, payload = {}) {
  try {
    const r = await fetch(`${apiBase(env)}/bot${env.BOT_TOKEN}/${method}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await r.json().catch(() => ({}));
    if (!data.ok) console.log(`Telegram ${method} xatosi: ${r.status} ${String(data.description || '').slice(0, 200)}`);
    return data;
  } catch (e) {
    console.log(`Telegram ${method} tarmoq xatosi: ${e && e.message}`);
    return { ok: false, description: String(e && e.message) };
  }
}

export const sendMessage = (env, chatId, text, extra = {}) =>
  tg(env, 'sendMessage', { chat_id: chatId, text, parse_mode: 'HTML', ...extra });
