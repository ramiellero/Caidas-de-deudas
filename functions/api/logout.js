// Cloudflare Pages Function — limpia la cookie de sesión.
export async function onRequest() {
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: {
      'content-type': 'application/json',
      'Cache-Control': 'no-store',
      'Set-Cookie': 'auth=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0',
    },
  });
}
