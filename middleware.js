// Vercel Edge Middleware — gate real de acceso al dashboard.
// Corre ANTES de servir cualquier archivo estático (index.html, los CSV de IRSA/Cresud/SGR/Padron,
// etc.) y antes de invocar cualquier función en /api/*. Sin una cookie de sesión válida, no se llega
// a nada de eso — a diferencia del login anterior, que era solo un overlay de JS en el cliente y no
// bloqueaba el acceso directo a los archivos.
//
// La cookie "auth" tiene el formato `${expiry}.${hmacHex}`, firmada con HMAC-SHA256 sobre
// `${AUTH_USER}.${expiry}` usando SESSION_SECRET. Se firma en api/login.js (Node runtime, usa el
// módulo `crypto` de Node) y se verifica acá con Web Crypto (`crypto.subtle`), que es lo único
// disponible en el Edge Runtime — por eso la lógica de firma/verificación está duplicada en vez de
// compartida en un helper común.
//
// Env vars requeridas (Vercel dashboard, no commitear): SESSION_SECRET, AUTH_USER.
// (AUTH_PASSWORD_HASH solo lo necesita api/login.js, no este archivo.)

export const config = {
  // Deja pasar sin auth: la página de login, el endpoint que la procesa, y logout (para poder
  // limpiar una cookie vencida/inválida incluso si ya no es válida).
  matcher: ['/((?!login\\.html|api/login|api/logout).*)'],
};

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

function getCookie(req, name) {
  const header = req.headers.get('cookie') || '';
  const match = header.match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export default async function middleware(req) {
  const SESSION_SECRET = process.env.SESSION_SECRET;
  const AUTH_USER = process.env.AUTH_USER;

  if (!SESSION_SECRET || !AUTH_USER) {
    return new Response('Auth no configurada en el servidor (faltan SESSION_SECRET / AUTH_USER en Vercel).', { status: 500 });
  }

  const cookie = getCookie(req, 'auth');
  if (cookie) {
    const dot = cookie.indexOf('.');
    if (dot > 0) {
      const expiryStr = cookie.slice(0, dot);
      const sig = cookie.slice(dot + 1);
      const expiry = parseInt(expiryStr, 10);
      const now = Math.floor(Date.now() / 1000);
      if (expiry && expiry > now && sig) {
        const payload = `${AUTH_USER}.${expiry}`;
        const ok = await verifySignature(SESSION_SECRET, payload, sig);
        if (ok) return; // cookie válida y vigente -> deja pasar el request tal cual
      }
    }
  }

  const url = new URL(req.url);
  if (url.pathname.startsWith('/api/')) {
    return new Response(JSON.stringify({ status: 'error', message: 'No autenticado' }), {
      status: 401,
      headers: { 'content-type': 'application/json' },
    });
  }

  const redirectUrl = new URL('/login.html', req.url);
  redirectUrl.searchParams.set('next', url.pathname + url.search);
  return Response.redirect(redirectUrl, 302);
}
