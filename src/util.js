// Umumiy yordamchilar

const encoder = new TextEncoder();

export function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' },
  });
}

export function fail(message, status = 400, extra = {}) {
  return json({ ok: false, message, ...extra }, status);
}

export const now = () => Math.floor(Date.now() / 1000);

export function hex(buf) {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function sha256(str) {
  return new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(str)));
}

export async function hmacSha256(key, data) {
  const k = typeof key === 'string' ? encoder.encode(key) : key;
  const cryptoKey = await crypto.subtle.importKey('raw', k, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return crypto.subtle.sign('HMAC', cryptoKey, encoder.encode(data));
}

/** Vaqtga bog'liq bo'lmagan taqqoslash (ikkalasini ham xeshlab, uzunlik sirini ham yashiradi). */
export async function safeEqual(a, b) {
  const [ha, hb] = await Promise.all([sha256(String(a)), sha256(String(b))]);
  let diff = 0;
  for (let i = 0; i < ha.length; i++) diff |= ha[i] ^ hb[i];
  return diff === 0;
}

export function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
}

/** Python round() bilan bir xil (yarim qiymatlar juftga) — musbat sonlar uchun. */
export function pyRound(x) {
  const r = Math.round(x);
  return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
}

/** Python int() ga o'xshash: son yoki butun son matni; aks holda NaN. */
export function toInt(v) {
  if (typeof v === 'number' && Number.isFinite(v)) return Math.trunc(v);
  if (typeof v === 'string' && /^\s*[+-]?\d+\s*$/.test(v)) return parseInt(v, 10);
  return NaN;
}

export function gradeOf(pct) {
  return pct >= 86 ? 5 : pct >= 71 ? 4 : pct >= 56 ? 3 : 2;
}

export async function readJson(request) {
  try {
    const d = await request.json();
    return d && typeof d === 'object' && !Array.isArray(d) ? d : {};
  } catch {
    return {};
  }
}
