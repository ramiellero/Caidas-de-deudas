// Cloudflare Pages Function — valida usuario/contraseña y emite la cookie de sesión.
// Usuario único (no hay tabla de usuarios): AUTH_USER + AUTH_PASSWORD_HASH vienen de env vars.
//
// AUTH_PASSWORD_HASH tiene el formato "saltHex:hashHex": PBKDF2-HMAC-SHA256 de 32 bytes sobre
// `${AUTH_PEPPER}:${contraseña}`, con 10.000 iteraciones.
// Por qué tan liviano: el plan gratis de Workers da 10 ms de CPU por request, y PBKDF2 con 100.000+
// iteraciones (el máximo que permite Workers) no entra. Para compensar las pocas iteraciones, la
// contraseña se mezcla con AUTH_PEPPER (secreto que vive solo en el servidor): un hash filtrado solo
// no alcanza para un ataque offline. Con el plan Workers Paid se pueden subir las iteraciones
// (env AUTH_PBKDF2_ITERATIONS, hasta 100000) y regenerar el hash con ese mismo valor.
// Para generar el hash (PowerShell; nunca commitear el resultado, va directo a la env var):
//   $pepper = '<el valor de AUTH_PEPPER>'
//   $salt = New-Object byte[] 16; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($salt)
//   $pbkdf2 = New-Object Security.Cryptography.Rfc2898DeriveBytes(($pepper + ':' + 'tu_contraseña'), $salt, 10000, [Security.Cryptography.HashAlgorithmName]::SHA256)
//   $hash = $pbkdf2.GetBytes(32)
//   "{0}:{1}" -f (($salt | % { $_.ToString('x2') }) -join ''), (($hash | % { $_.ToString('x2') }) -join '')
//
// SESSION_SECRET y AUTH_PEPPER: strings random largos. Generar cada uno con PowerShell:
//   $b = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); ($b | % { $_.ToString('x2') }) -join ''
// SESSION_SECRET se comparte con _middleware.js y con Vercel (proxy del padrón); AUTH_PEPPER es solo de este login.
//
// Env vars requeridas (Cloudflare dashboard, como Secrets): AUTH_USER, AUTH_PASSWORD_HASH, AUTH_PEPPER, SESSION_SECRET.

const SESSION_MAX_AGE = 60 * 60 * 24 * 7; // 7 días
const DEFAULT_PBKDF2_ITERATIONS = 10000;

const enc = new TextEncoder();

function json(status, body, extraHeaders) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'Cache-Control': 'no-store', ...(extraHeaders || {}) },
  });
}

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

function bytesToHex(buf) {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

async function verifyPassword(password, stored, pepper, iterations) {
  const parts = (stored || '').split(':');
  if (parts.length !== 2) return false;
  const salt = hexToBytes(parts[0]);
  const expected = hexToBytes(parts[1]);
  if (!salt || !expected) return false;
  try {
    const key = await crypto.subtle.importKey('raw', enc.encode(`${pepper}:${password}`), 'PBKDF2', false, ['deriveBits']);
    const derived = new Uint8Array(
      await crypto.subtle.deriveBits(
        { name: 'PBKDF2', salt, iterations, hash: 'SHA-256' },
        key,
        expected.length * 8
      )
    );
    return timingSafeEqual(derived, expected);
  } catch {
    return false;
  }
}

async function sign(payload, secret) {
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return bytesToHex(await crypto.subtle.sign('HMAC', key, enc.encode(payload)));
}

export async function onRequest({ request, env }) {
  if (request.method !== 'POST') return json(405, { ok: false, message: 'Method not allowed' });

  const { AUTH_USER, AUTH_PASSWORD_HASH, AUTH_PEPPER, SESSION_SECRET } = env;
  const iterations = Math.min(parseInt(env.AUTH_PBKDF2_ITERATIONS, 10) || DEFAULT_PBKDF2_ITERATIONS, 100000);
  if (!AUTH_USER || !AUTH_PASSWORD_HASH || !AUTH_PEPPER || !SESSION_SECRET) {
    return json(500, { ok: false, message: 'Auth no configurada en el servidor.' });
  }

  let body = {};
  try { body = await request.json(); } catch { body = {}; }
  const user = body && body.user;
  const password = body && body.password;

  if (!user || !password) return json(401, { ok: false, message: 'Usuario o contraseña incorrectos.' });

  const userOk = timingSafeEqual(enc.encode(String(user)), enc.encode(AUTH_USER));
  const passOk = await verifyPassword(String(password), AUTH_PASSWORD_HASH, AUTH_PEPPER, iterations);
  if (!userOk || !passOk) return json(401, { ok: false, message: 'Usuario o contraseña incorrectos.' });

  const expiry = Math.floor(Date.now() / 1000) + SESSION_MAX_AGE;
  const sig = await sign(`${AUTH_USER}.${expiry}`, SESSION_SECRET);

  return json(200, { ok: true }, {
    'Set-Cookie': `auth=${expiry}.${sig}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${SESSION_MAX_AGE}`,
  });
}
