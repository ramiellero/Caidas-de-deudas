// Vercel Serverless Function — valida usuario/contraseña y emite la cookie de sesión.
// Usuario único (no hay tabla de usuarios): AUTH_USER + AUTH_PASSWORD_HASH vienen de env vars.
//
// AUTH_PASSWORD_HASH tiene el formato "saltHex:hashHex", PBKDF2-HMAC-SHA256 con 210.000
// iteraciones (recomendación OWASP 2023) y hash de 64 bytes — elegido en vez de scrypt/bcrypt
// porque se puede generar con PowerShell puro (sin instalar Node localmente), vía
// System.Security.Cryptography.Rfc2898DeriveBytes. Para generar un hash nuevo (PowerShell,
// nunca commitear el resultado, va directo a la env var de Vercel):
//   $salt = New-Object byte[] 16; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($salt)
//   $pbkdf2 = New-Object Security.Cryptography.Rfc2898DeriveBytes('tu_contraseña', $salt, 210000, [Security.Cryptography.HashAlgorithmName]::SHA256)
//   $hash = $pbkdf2.GetBytes(64)
//   "{0}:{1}" -f (($salt | % { $_.ToString('x2') }) -join ''), (($hash | % { $_.ToString('x2') }) -join '')
// (equivalente en Node si alguna vez hace falta: crypto.pbkdf2Sync(pass, salt, 210000, 64, 'sha256'))
//
// SESSION_SECRET: string random largo, compartido con middleware.js para firmar/verificar la
// cookie. Generar con PowerShell:
//   $b = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); ($b | % { $_.ToString('x2') }) -join ''
//
// Env vars requeridas (Vercel dashboard, no commitear): AUTH_USER, AUTH_PASSWORD_HASH, SESSION_SECRET.

const crypto = require('crypto');

const SESSION_MAX_AGE = 60 * 60 * 24 * 7; // 7 días
const PBKDF2_ITERATIONS = 210000;

function verifyPassword(password, stored) {
  const parts = (stored || '').split(':');
  if (parts.length !== 2) return false;
  const [saltHex, hashHex] = parts;
  try {
    const salt = Buffer.from(saltHex, 'hex');
    const expected = Buffer.from(hashHex, 'hex');
    const derived = crypto.pbkdf2Sync(password, salt, PBKDF2_ITERATIONS, expected.length, 'sha256');
    return derived.length === expected.length && crypto.timingSafeEqual(derived, expected);
  } catch {
    return false;
  }
}

function sign(payload, secret) {
  return crypto.createHmac('sha256', secret).update(payload).digest('hex');
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');

  if (req.method !== 'POST') {
    res.status(405).json({ ok: false, message: 'Method not allowed' });
    return;
  }

  const { AUTH_USER, AUTH_PASSWORD_HASH, SESSION_SECRET } = process.env;
  if (!AUTH_USER || !AUTH_PASSWORD_HASH || !SESSION_SECRET) {
    res.status(500).json({ ok: false, message: 'Auth no configurada en el servidor.' });
    return;
  }

  let body = req.body;
  if (typeof body === 'string') {
    try { body = JSON.parse(body); } catch { body = {}; }
  }
  const user = body && body.user;
  const password = body && body.password;

  if (!user || !password) {
    res.status(401).json({ ok: false, message: 'Usuario o contraseña incorrectos.' });
    return;
  }

  // Comparación de usuario timing-safe (no crítico ya que es público, pero mantiene el mismo patrón).
  const userBuf = Buffer.from(String(user));
  const expectedUserBuf = Buffer.from(AUTH_USER);
  const userOk = userBuf.length === expectedUserBuf.length && crypto.timingSafeEqual(userBuf, expectedUserBuf);
  const passOk = verifyPassword(String(password), AUTH_PASSWORD_HASH);

  if (!userOk || !passOk) {
    res.status(401).json({ ok: false, message: 'Usuario o contraseña incorrectos.' });
    return;
  }

  const expiry = Math.floor(Date.now() / 1000) + SESSION_MAX_AGE;
  const payload = `${AUTH_USER}.${expiry}`;
  const sig = sign(payload, SESSION_SECRET);
  const cookieValue = `${expiry}.${sig}`;

  res.setHeader(
    'Set-Cookie',
    `auth=${cookieValue}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${SESSION_MAX_AGE}`
  );
  res.status(200).json({ ok: true });
};
