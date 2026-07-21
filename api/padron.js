// Vercel Serverless Function — proxy para la API de Custodia BYMA (Custody Issuers, endpoint /holdings)
// Contrato real (ver página de docs de la API, no solo el openapi.json): GET /holdings.csv/?balanceDate=YYYY-MM-DD&issuerCode=XXXX
// es ASINCRÓNICA: la primera solicitud dispara la tarea y devuelve un uuid; hay que reconsultar
// pasando el header X-UUID hasta que la tarea termine, y la respuesta final es CSV.
// Env vars requeridas (configurar en el dashboard de Vercel, no commitear):
//   BYMA_OKTA_TOKEN_URL, BYMA_CLIENT_ID, BYMA_CLIENT_SECRET, BYMA_SCOPE, BYMA_API_BASE

let _cachedToken = null; // { value, exp } — cache en memoria mientras la instancia esté "warm"

function _decodeJwtExp(jwt) {
  try {
    const payload = JSON.parse(Buffer.from(jwt.split('.')[1], 'base64').toString('utf8'));
    return payload.exp || 0;
  } catch {
    return 0;
  }
}

async function _getAccessToken() {
  const now = Math.floor(Date.now() / 1000);
  if (_cachedToken && _cachedToken.exp > now + 30) {
    return _cachedToken.value;
  }

  const { BYMA_OKTA_TOKEN_URL, BYMA_CLIENT_ID, BYMA_CLIENT_SECRET, BYMA_SCOPE } = process.env;
  if (!BYMA_OKTA_TOKEN_URL || !BYMA_CLIENT_ID || !BYMA_CLIENT_SECRET) {
    throw new Error('Faltan variables de entorno BYMA_OKTA_TOKEN_URL / BYMA_CLIENT_ID / BYMA_CLIENT_SECRET');
  }

  const body = new URLSearchParams({
    grant_type: 'client_credentials',
    client_id: BYMA_CLIENT_ID,
    client_secret: BYMA_CLIENT_SECRET,
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
  _cachedToken = { value: token, exp: _decodeJwtExp(token) || now + 3600 };
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
    const token = await _getAccessToken();
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
