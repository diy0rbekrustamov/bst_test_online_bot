// Cloudflare Worker kirish nuqtasi
//   /api/*     — Mini App API
//   /telegram  — Telegram webhook (maxfiy sarlavha bilan himoyalangan)
//   /setup     — bir martalik sozlash: webhook + menyu tugmasi
//   boshqasi   — statik veb-ilova (webapp/)
import { handleApi } from './api.js';
import { handleUpdate, setupBot } from './bot.js';
import { json, safeEqual } from './util.js';

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const { pathname } = url;

    if (pathname.startsWith('/api/')) return handleApi(request, env, ctx);

    if (pathname === '/telegram') {
      if (request.method !== 'POST') return new Response('Method Not Allowed', { status: 405 });
      const given = request.headers.get('X-Telegram-Bot-Api-Secret-Token') || '';
      if (!env.WEBHOOK_SECRET || !(await safeEqual(given, env.WEBHOOK_SECRET))) {
        return new Response('Forbidden', { status: 403 });
      }
      try {
        await handleUpdate(await request.json(), env, url.origin);
      } catch (e) {
        // Telegram xatoda so'rovni qayta-qayta yuboraveradi; xatoni yozib, 200 qaytaramiz
        console.log('Bot xatosi:', e && e.stack || e);
      }
      return new Response('ok');
    }

    if (pathname === '/setup') {
      if (!env.WEBHOOK_SECRET || !env.BOT_TOKEN) {
        return json({ ok: false, message: 'BOT_TOKEN va WEBHOOK_SECRET maxfiy qiymatlari kiritilmagan' }, 500);
      }
      if (!(await safeEqual(url.searchParams.get('key') || '', env.WEBHOOK_SECRET))) {
        return new Response('Forbidden', { status: 403 });
      }
      return json({ ok: true, teacher_code_set: !!env.TEACHER_CODE, ...(await setupBot(env, url.origin)) });
    }

    return env.ASSETS.fetch(request);
  },
};
