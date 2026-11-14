// Cloudflare Pages Function — proxy de /api/padron hacia el backend del padrón que sigue en Vercel
// (api/padron.js, que habla con la API de Custodia BYMA y tiene las credenciales BYMA).
//
// Flujo: el browser (o el .ps1) llama a /api/padron en Cloudflare -> functions/_middleware.js valida la
// cookie de sesión -> esta función reenvía la consulta a Vercel firmando una cookie `auth` de corta
// duración con el mismo SESSION_SECRET / AUTH_USER (el middleware de Vercel exige esa cookie).
// Por eso SESSION_SECRET y AUTH_USER deben tener el MISMO valor en Cloudflare y en Vercel.
//
// Contrato (sin cambios): GET /api/padron?issuerCode=XXXX&balanceDate=YYYY-MM-DD&uuid=(opcional)
//   -> {status:'pending', uuid} | {status:'ready', csv} | {status:'error', message}
//
// Env vars en Cloudflare: SESSION_SECRET, AUTH_USER, PADRON_UPSTREAM (ej. https://caidas-de-deudas.vercel.app).
// Las credenciales BYMA (BYMA_*) viven solo en Vercel.

const HEADERS = {
  'content-type': 'application/json',
  'Cache-Control': 'no-store, no-cache, must-revalidate',
};

function json(body, status) {
  return new Response(JSON.stringify(body), { status: status || 200, headers: HEADERS });
}

async function sign(payload, secret) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(payload));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export async function onRequest({ request, env }) {
  if (request.method !== 'GET') return json({ status: 'error', message: 'Method not allowed' }, 405);

  const { SESSION_SECRET, AUTH_USER, PADRON_UPSTREAM } = env;
  if (!SESSION_SECRET || !AUTH_USER || !PADRON_UPSTREAM) {
    return json({ status: 'error', message: 'Faltan SESSION_SECRET / AUTH_USER / PADRON_UPSTREAM en Cloudflare.' }, 500);
  }

  try {
    const upstream = new URL('/api/padron', PADRON_UPSTREAM);
    upstream.search = new URL(request.url).search;

    const expiry = Math.floor(Date.now() / 1000) + 300;
    const sig = await sign(`${AUTH_USER}.${expiry}`, SESSION_SECRET);

    const resp = await fetch(upstream.toString(), { headers: { Cookie: `auth=${expiry}.${sig}` } });

    // Se reenvía el body en streaming (el CSV puede pesar decenas de MB).
    return new Response(resp.body, {
      status: resp.status,
      headers: { ...HEADERS, 'content-type': resp.headers.get('content-type') || 'application/json' },
    });
  } catch (err) {
    return json({ status: 'error', message: `No se pudo contactar al backend del padrón: ${err.message || err}` });
  }
}
