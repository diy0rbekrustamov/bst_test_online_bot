// Telegram Mini App `initData` imzosini tekshirish (WebCrypto)
import { hmacSha256, hex, safeEqual, now } from './util.js';

export const INIT_DATA_MAX_AGE_HOURS = 48;

/** To'g'ri bo'lsa foydalanuvchi id (son), aks holda null. */
export async function verifyInitData(initData, botToken) {
  if (!initData || !botToken) return null;
  let params;
  try {
    params = new URLSearchParams(initData);
  } catch {
    return null;
  }
  const received = params.get('hash');
  if (!received) return null;
  params.delete('hash');

  const pairs = [...params.entries()].sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  const check = pairs.map(([k, v]) => `${k}=${v}`).join('\n');

  const secret = new Uint8Array(await hmacSha256('WebAppData', botToken));
  const expected = hex(await hmacSha256(secret, check));
  if (!(await safeEqual(expected, received))) return null;

  const authDate = parseInt(params.get('auth_date') || '0', 10);
  if (!Number.isFinite(authDate) || now() - authDate > INIT_DATA_MAX_AGE_HOURS * 3600) return null;
  try {
    const id = Number(JSON.parse(params.get('user')).id);
    return Number.isSafeInteger(id) ? id : null;
  } catch {
    return null;
  }
}
