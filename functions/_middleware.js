// Cloudflare Pages Functions middleware — gate real de acceso al dashboard.
// Corre ANTES de servir cualquier archivo estático (index.html, los CSV de IRSA/Cresud/SGR/Padron,
// etc.) y antes de cualquier función en /api/*. Sin una cookie de sesión válida no se llega a nada.
//
// La cookie "auth" tiene el formato `${expiry}.${hmacHex}`, firmada con HMAC-SHA256 sobre
// `${AUTH_USER}.${expiry}` usando SESSION_SECRET (se firma en functions/api/login.js).
//
// Env vars requeridas (Cloudflare dashboard → Pages → Settings → Variables and Secrets):
// SESSION_SECRET, AUTH_USER.

// Rutas públicas. Cloudflare Pages sirve /login.html como /login (redirige 308), así que van ambas.
const PUBLIC_PATHS = new Set(['/login', '/login.html', '/api/login', '/api/logout']);

function hexToBytes(hex) {
  if (!hex || hex.length % 2 !== 0) return null;
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    const b = parseInt(hex.substr(i * 2, 2), 16);
    if (Number.isNaN(b)) return null;
    bytes[i] = b;
  }
  return bytes;
}

async function verifySignature(secret, payload, sigHex) {
  const sigBytes = hexToBytes(sigHex);
  if (!sigBytes) return false;
  try {
    const key = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(secret),
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['verify']
    );
    return await crypto.subtle.verify('HMAC', key, sigBytes, new TextEncoder().encode(payload));
  } catch {
    return false;
  }
}

function getCookie(request, name) {
  const header = request.headers.get('cookie') || '';
  const match = header.match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export async function onRequest(context) {
  const { request, env, next } = context;
  const url = new URL(request.url);

  if (PUBLIC_PATHS.has(url.pathname)) return next();

  const { SESSION_SECRET, AUTH_USER } = env;
  if (!SESSION_SECRET || !AUTH_USER) {
    return new Response('Auth no configurada en el servidor (faltan SESSION_SECRET / AUTH_USER en Cloudflare).', { status: 500 });
  }

  const cookie = getCookie(request, 'auth');
  if (cookie) {
    const dot = cookie.indexOf('.');
    if (dot > 0) {
      const expiry = parseInt(cookie.slice(0, dot), 10);
      const sig = cookie.slice(dot + 1);
      const now = Math.floor(Date.now() / 1000);
      if (expiry && expiry > now && sig) {
        const ok = await verifySignature(SESSION_SECRET, `${AUTH_USER}.${expiry}`, sig);
        if (ok) return next(); // cookie válida y vigente -> sirve el recurso pedido
      }
    }
  }

  if (url.pathname.startsWith('/api/')) {
    return new Response(JSON.stringify({ status: 'error', message: 'No autenticado' }), {
      status: 401,
      headers: { 'content-type': 'application/json' },
    });
  }

  const redirectUrl = new URL('/login', request.url);
  redirectUrl.searchParams.set('next', url.pathname + url.search);
  return Response.redirect(redirectUrl.toString(), 302);
}
