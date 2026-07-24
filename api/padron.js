// Vercel Serverless Function — proxy para la API de Custodia BYMA (Custody Issuers, endpoint /holdings)
// Contrato real (ver página de docs de la API, no solo el openapi.json): GET /holdings.csv/?balanceDate=YYYY-MM-DD&issuerCode=XXXX
// es ASINCRÓNICA: la primera solicitud dispara la tarea y devuelve un uuid; hay que reconsultar
// pasando el header X-UUID hasta que la tarea termine, y la respuesta final es CSV.
//
// Credenciales por emisor: IRSA y Cresud pueden tener client_id/client_secret distintos
// (cuentas API separadas del lado de BYMA). Por cada issuerCode se busca primero
// BYMA_CLIENT_ID_<ISSUERCODE> / BYMA_CLIENT_SECRET_<ISSUERCODE> (ej. BYMA_CLIENT_ID_IRSA,
// BYMA_CLIENT_ID_CRES); si no están seteadas, cae a BYMA_CLIENT_ID / BYMA_CLIENT_SECRET
// genéricas. BYMA_OKTA_TOKEN_URL, BYMA_SCOPE y BYMA_API_BASE se asumen compartidas.
// Env vars (configurar en el dashboard de Vercel, no commitear):
//   BYMA_OKTA_TOKEN_URL, BYMA_SCOPE, BYMA_API_BASE
//   BYMA_CLIENT_ID / BYMA_CLIENT_SECRET (genéricas, fallback)
//   BYMA_CLIENT_ID_IRSA / BYMA_CLIENT_SECRET_IRSA (opcionales, específicas de IRSA)
//   BYMA_CLIENT_ID_CRES / BYMA_CLIENT_SECRET_CRES (opcionales, específicas de Cresud)

let _cachedTokens = {}; // { [issuerCode]: { value, exp } } — cache en memoria mientras la instancia esté "warm"

function _decodeJwtExp(jwt) {
  try {
    const payload = JSON.parse(Buffer.from(jwt.split('.')[1], 'base64').toString('utf8'));
    return payload.exp || 0;
  } catch {
    return 0;
  }
}

function _credsForIssuer(issuerCode) {
  const suffix = (issuerCode || '').toUpperCase();
  const clientId = process.env[`BYMA_CLIENT_ID_${suffix}`] || process.env.BYMA_CLIENT_ID;
  const clientSecret = process.env[`BYMA_CLIENT_SECRET_${suffix}`] || process.env.BYMA_CLIENT_SECRET;
  return { clientId, clientSecret };
}

async function _getAccessToken(issuerCode) {
  const now = Math.floor(Date.now() / 1000);
  const cacheKey = issuerCode || 'default';
  const cached = _cachedTokens[cacheKey];
  if (cached && cached.exp > now + 30) {
    return cached.value;
  }

  const { BYMA_OKTA_TOKEN_URL, BYMA_SCOPE } = process.env;
  const { clientId, clientSecret } = _credsForIssuer(issuerCode);
  if (!BYMA_OKTA_TOKEN_URL || !clientId || !clientSecret) {
    const suffix = (issuerCode || '').toUpperCase();
    throw new Error(`Faltan credenciales BYMA para issuerCode=${issuerCode}: BYMA_OKTA_TOKEN_URL y (BYMA_CLIENT_ID_${suffix} / BYMA_CLIENT_SECRET_${suffix} o BYMA_CLIENT_ID / BYMA_CLIENT_SECRET)`);
  }

  const body = new URLSearchParams({
    grant_type: 'client_credentials',
    client_id: clientId,
    client_secret: clientSecret,
    scope: BYMA_SCOPE || 'custodyissuers.read',
  });

  const resp = await fetch(BYMA_OKTA_TOKEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });

  if (!resp.ok) {
    throw new Error(`Error obteniendo token OAuth (${resp.status}): ${await resp.text()}`);
  }

  const data = await resp.json();
  const token = data.access_token;
  _cachedTokens[cacheKey] = { value: token, exp: _decodeJwtExp(token) || now + 3600 };
  return token;
}

function _parseHoldingsCsv(text) {
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length === 0) return { columns: [], rows: [] };
  const columns = lines[0].split(';').map((c) => c.trim());
  const rows = lines.slice(1).map((line) => {
    const cells = line.split(';');
    const row = {};
    columns.forEach((col, i) => {
      row[col] = (cells[i] || '').trim();
    });
    return row;
  });
  return { columns, rows };
}

module.exports = async (req, res) => {
  if (req.method !== 'GET') {
    res.status(405).json({ status: 'error', message: 'Method not allowed' });
    return;
  }

  const { issuerCode, balanceDate, uuid } = req.query;

  if (!issuerCode || !balanceDate) {
    res.status(400).json({ status: 'error', message: 'Faltan parámetros issuerCode y/o balanceDate' });
    return;
  }

  const BYMA_API_BASE = process.env.BYMA_API_BASE;
  if (!BYMA_API_BASE) {
    res.status(500).json({ status: 'error', message: 'Falta variable de entorno BYMA_API_BASE' });
    return;
  }

  try {
    const token = await _getAccessToken(issuerCode);
    const url = `${BYMA_API_BASE}/holdings.csv/?balanceDate=${encodeURIComponent(balanceDate)}&issuerCode=${encodeURIComponent(issuerCode)}`;

    const headers = { Authorization: `Bearer ${token}` };
    if (uuid) headers['X-UUID'] = uuid;

    const resp = await fetch(url, { headers });

    // La API BYMA (docs oficiales) es asincrónica: primera respuesta trae un uuid,
    // hay que reconsultar con X-UUID hasta que la tarea termine.
    const contentType = resp.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const data = await resp.json();
      if (data.uuid) {
        res.status(200).json({ status: 'pending', uuid: data.uuid });
        return;
      }
      if (!resp.ok) {
        res.status(200).json({ status: 'error', message: `BYMA API respondió ${resp.status}: ${JSON.stringify(data)}` });
        return;
      }
    }

    if (resp.status === 409) {
      const data = await resp.json();
      res.status(200).json({ status: 'pending', uuid: data.uuid });
      return;
    }

    if (!resp.ok) {
      res.status(200).json({ status: 'error', message: `BYMA API respondió ${resp.status}: ${await resp.text()}` });
      return;
    }

    const csvText = await resp.text();
    const { columns, rows } = _parseHoldingsCsv(csvText);
    res.status(200).json({ status: 'ready', columns, rows });
  } catch (err) {
    res.status(200).json({ status: 'error', message: err.message || String(err) });
  }
};
