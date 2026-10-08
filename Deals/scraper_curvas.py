#!/usr/bin/env python3
"""
scraper_curvas.py — Descarga el tablero de BYMA Educa (https://tablero.bymaeduca.com.ar/)
y extrae las ONs hard-dollar (segmento "hd": MEP / CCL, Ley Arg y Ley NY).

El tablero es un único HTML con todos los datos embebidos en
<script id="payload" type="application/json"> — no hay API, alcanza con un GET.

Guarda:
  curvas_on.csv                   (sobreescribe con la rueda más reciente)
  curvas_propias_historico.csv    (appendea IRSA 'IRC*' / Cresud 'CS<dígito>*', dedup por Fecha)

Precio_Clean: BYMA publica `px` como precio sucio sobre 100 de VN ORIGINAL; el clean por
100 de valor residual se calcula como (px - ai) / vr * 100  (ai = interés corrido en las
mismas unidades que px; vt = vr + ai). Validado contra el IAMC.

Uso:
    python scraper_curvas.py                # rueda más reciente
    python scraper_curvas.py --backfill     # además completa las ruedas faltantes de propias (hasta ~21 ruedas)
    python scraper_curvas.py --commit       # git commit + push tras guardar
    python scraper_curvas.py --from-file tablero.html   # usa un HTML ya descargado (pruebas)

Requiere:
    pip install requests
"""

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

BASE_DIR      = Path(__file__).parent
CSV_OUT       = BASE_DIR / "curvas_on.csv"
LOG_FILE      = BASE_DIR / "scraper_curvas.log"
PROPIAS_CSV   = BASE_DIR / "curvas_propias_historico.csv"
PROPIAS_FIELDNAMES = [
    "Fecha", "Ticker", "Emisor", "Vencimiento", "Precio_Clean", "YTM", "CY", "DM",
    "Var_Px_Pct", "Var_YTM_bps", "ADTV_USD", "Canje_Pct", "Paridad",
]

BYMA_URL = "https://tablero.bymaeduca.com.ar/"
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def _get(url, **kwargs):
    """requests.get con fallback a verify=False para redes con proxy SSL corporativo."""
    try:
        return requests.get(url, headers=HTTP_HEADERS, **kwargs)
    except requests.exceptions.SSLError:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return requests.get(url, headers=HTTP_HEADERS, verify=False, **kwargs)

FIELDNAMES = [
    "Fecha", "Ticker", "Emisor", "Industria", "Ley", "Moneda",
    "Cupon", "Vencimiento", "Prox_Cupon",
    "Precio_Clean", "YTM", "CY", "DM", "CX", "WAL",
    "Monto_Emitido", "ADTV_ARS",
    "Cierre_ARS", "Accr_Int", "VT", "VR",
    "Estructura", "Frec_Cupon", "Cuotas_Capital", "Frec_Capital", "Prox_Capital",
    # campos nuevos (BYMA)
    "Precio_Dirty", "Paridad", "Var_Px_Pct", "Var_YTM_bps", "ADTV_USD",
    "Canje_Pct", "MEP_Implicito", "CCL_Implicito",
]

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'))
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

# ── Sector lookup por prefijo de ticker ───────────────────────────────────────

# Orden: más específico primero (más largo primero por convención)
_SECTOR_RULES = [
    # Petróleo & Gas
    ('YM',    'Petróleo & Gas'),   # YPF
    ('VSC',   'Petróleo & Gas'),   # Vista Energy
    ('TTC',   'Petróleo & Gas'),   # Tecpetrol
    ('PLC',   'Petróleo & Gas'),   # Pluspetrol
    ('MCC',   'Petróleo & Gas'),   # Pecom (Pampa E&P)
    ('EMC',   'Petróleo & Gas'),   # Compañía Mega (gasoducto)
    ('PQC',   'Petróleo & Gas'),   # Petroquímica Comodoro
    ('PN',    'Petróleo & Gas'),   # Pan American Energy
    ('TSC',   'Petróleo & Gas'),   # Transportadora de Gas del Sur
    ('CP3',   'Petróleo & Gas'),   # CGC
    ('CP4',   'Petróleo & Gas'),   # CGC
    # Electricidad
    ('MGC',   'Electricidad'),     # Pampa Energía
    ('YFC',   'Electricidad'),     # YPF Energía Eléctrica
    ('GN',    'Electricidad'),     # Genneia
    ('LUC',   'Electricidad'),     # Luz de Tres Picos
    ('EAC',   'Electricidad'),     # MSU Green Energy
    ('CAC',   'Electricidad'),     # CAPEX
    ('GYC',   'Electricidad'),     # 360 Energy Solar
    # Real Estate
    ('IRC',   'Real Estate'),      # IRSA / Inversiones y Representaciones
    # Finanzas
    ('BF',    'Finanzas'),         # BBVA Argentina
    ('AFC',   'Finanzas'),         # Comafi
    ('BGC',   'Finanzas'),         # Patagonia
    ('HBC',   'Finanzas'),         # Hipotecario
    ('BPC',   'Finanzas'),         # Supervielle
    ('SBC',   'Finanzas'),         # Scania Credit
    ('BVC',   'Finanzas'),         # Banco de Servicios
    ('T64',   'Finanzas'),         # Tarjeta
    ('T66',   'Finanzas'),         # Tarjeta Naranja
    ('CIC',   'Finanzas'),         # CNH Industrial Capital
    ('SXC',   'Finanzas'),         # Mercado Pago
    # Agroindustria
    ('CS',    'Real Estate'),      # Cresud
    ('MSS',   'Agroindustria'),    # MSU S.A.
    ('RZ9',   'Agroindustria'),    # Rizobacter
    # Telecomunicaciones
    ('TLC',   'Telecomunicaciones'),  # Telecom Argentina
    ('OTS',   'Telecomunicaciones'),  # Otamérica
    # Alimentos y Bebidas
    ('RC1',   'Alimentos y Bebidas'),  # Arcor
    ('SNA',   'Alimentos y Bebidas'),  # San Miguel
    ('SNB',   'Alimentos y Bebidas'),  # San Miguel
    # Materiales Básicos
    ('LMS',   'Materiales Básicos'),   # Aluminio Argentino
    # Aerolíneas
    ('AER',   'Aerolíneas'),           # Aeropuertos Argentina 2000
    ('ARC',   'Aerolíneas'),           # Aeropuertos Argentina 2000 (ticker BYMA)
    # Construcción / Inmobiliario
    ('VES',   'Construcción'),         # Ricardo Venturino
    ('ZPC',   'Construcción'),         # Plaza Logística
    ('PZC',   'Construcción'),         # Plaza Logística (variante)
    ('JNC',   'Construcción'),         # Inversora Juramento
    ('LOC',   'Construcción'),         # Loma Negra
    # Electricidad (adicionales)
    ('DNC',   'Electricidad'),         # EDENOR
    ('RUC',   'Electricidad'),         # MSU Energy
    ('OZC',   'Electricidad'),         # EDEMSA
    ('NPC',   'Electricidad'),         # Central Puerto
    ('DEC',   'Electricidad'),         # EDESA
    # Petróleo & Gas (adicionales)
    ('OLC',   'Petróleo & Gas'),       # Oleoductos del Valle / Transandino
    ('ZZC',   'Petróleo & Gas'),       # Camuzzi Gas
    ('CWC',   'Petróleo & Gas'),       # Crown Point
    ('PUC',   'Petróleo & Gas'),       # Petróleos
    ('OT4',   'Petróleo & Gas'),       # Oiltanking
    ('PFC',   'Petróleo & Gas'),       # Profertil
    ('YCA',   'Petróleo & Gas'),       # YPF (variante)
    # Finanzas (adicionales)
    ('BAC',   'Finanzas'),             # Banco Macro
    ('BAH',   'Finanzas'),             # Banco Macro
    ('BYC',   'Finanzas'),             # Banco Galicia
    ('HJC',   'Finanzas'),             # John Deere Credit
    ('VBC',   'Finanzas'),             # Banco de Valores
    ('COC',   'Finanzas'),             # Banco de la Ciudad / COMAR
    ('FO4',   'Finanzas'),             # Futuros y Opciones
    # Alimentos y Bebidas (adicionales)
    ('MTC',   'Alimentos y Bebidas'),  # Mastellone
    ('RCC',   'Alimentos y Bebidas'),  # Arcor (variante)
    ('RC2',   'Alimentos y Bebidas'),  # Arcor (variante)
    ('HVS',   'Alimentos y Bebidas'),  # Havanna
    ('LDC',   'Agroindustria'),        # Ledesma
    ('RZA',   'Agroindustria'),        # Rizobacter (variante)
    ('VAC',   'Agroindustria'),        # Vitalcan
    ('VA1',   'Agroindustria'),        # Vitalcan
    # Materiales Básicos (adicionales)
    ('XMC',   'Materiales Básicos'),   # Minera Exar
    # Agregados al migrar a BYMA (tickers que el IAMC no traía)
    ('AEC',   'Electricidad'),         # AES Argentina
    ('LQC',   'Petróleo & Gas'),       # Petroquímica Comodoro Rivadavia
    ('TT1',   'Petróleo & Gas'),       # Tecpetrol
]
# Ordenar por longitud descendente para hacer match por prefijo más largo
_SECTOR_RULES.sort(key=lambda x: -len(x[0]))

def get_sector(ticker):
    for prefix, sector in _SECTOR_RULES:
        if ticker.startswith(prefix):
            return sector
    return 'Otros'

# ── Emisor lookup (nombre completo por ticker) ────────────────────────────────
# Normaliza el nombre del emisor por ticker. Si no está en el mapa, se usa el nombre de BYMA.

EMISOR_MAP = {
    # YPF
    'YM34O': 'YPF S.A.',  'YMCXO': 'YPF S.A.',  'YM42O': 'YPF S.A.',
    'YM38O': 'YPF S.A.',  'YM43O': 'YPF S.A.',  'YM40O': 'YPF S.A.',
    'YMCTO': 'YPF S.A.',  'YMCWO': 'YPF S.A.',
    # Vista Energy
    'VSCXO': 'Vista Energy Argentina S.A.U.',  'VSCVO': 'Vista Energy Argentina S.A.U.',
    'VSCTO': 'Vista Energy Argentina S.A.U.',  'VSCRO': 'Vista Energy Argentina S.A.U.',
    'VSCUO': 'Vista Energy Argentina S.A.U.',  'VSCPO': 'Vista Energy Argentina S.A.U.',
    'VSCMO': 'Vista Energy Argentina S.A.U.',  'VSCQO': 'Vista Energy Argentina S.A.U.',
    'VSCJO': 'Vista Energy Argentina S.A.U.',
    # Pampa Energía
    'MGCRO': 'Pampa Energía S.A.',  'MGCNO': 'Pampa Energía S.A.',
    'MGCEO': 'Pampa Energía S.A.',
    # Pan American Energy
    'PN43O': 'Pan American Energy S.A.',  'PNRCO': 'Pan American Energy S.A.',
    'PNRMO': 'Pan American Energy S.A.',
    # TGS
    'TSC3O': 'Transportadora de Gas del Sur S.A.',
    # CGC
    'CP38O': 'Compañía General de Combustibles S.A.',
    # Tecpetrol
    'TTCDO': 'Tecpetrol S.A.',  'TTCEO': 'Tecpetrol S.A.',  'TTCBO': 'Tecpetrol S.A.',
    # Pluspetrol
    'PLC4O': 'Pluspetrol S.A.',  'PLC2O': 'Pluspetrol S.A.',
    'PLC3O': 'Pluspetrol S.A.',  'PLC1O': 'Pluspetrol S.A.',
    # Pecom
    'MCC3O': 'Pecom Servicios Energía S.A.U.',  'MCC2O': 'Pecom Servicios Energía S.A.U.',
    # Compañía Mega
    'EMC1O': 'Compañía Mega S.A.',
    # Petroquímica Comodoro
    'PQCOO': 'Petroquímica Comodoro Rivadavia S.A.',
    # YPF Energía Eléctrica
    'YFCOO': 'YPF Energía Eléctrica S.A.',  'YFCLO': 'YPF Energía Eléctrica S.A.',
    'YFCIO': 'YPF Energía Eléctrica S.A.',
    # Pampa Energía / Electricidad (Genneia etc.)
    'GN43O': 'Genneia S.A.',  'GN39O': 'Genneia S.A.',
    'GN38O': 'Genneia S.A.',  'GN46O': 'Genneia S.A.',
    'LUC5O': 'Luz de Tres Picos S.A.',
    'EAC3O': 'MSU Green Energy S.A.U.',  'EAC2O': 'MSU Green Energy S.A.U.',
    'CACAO': 'CAPEX S.A.',
    'GYC3O': '360 Energy Solar S.A.',
    # IRSA
    'IRCPO': 'Inversiones y Representaciones S.A.',
    'IRCOO': 'Inversiones y Representaciones S.A.',
    'IRCNO': 'Inversiones y Representaciones S.A.',
    'IRCLO': 'Inversiones y Representaciones S.A.',
    'IRCJO': 'Inversiones y Representaciones S.A.',
    'IRCFO': 'Inversiones y Representaciones S.A.',
    # Cresud
    'CS44O': 'Cresud S.A.C.I.F.A.',  'CS45O': 'Cresud S.A.C.I.F.A.',
    'CS47O': 'Cresud S.A.C.I.F.A.',  'CS48O': 'Cresud S.A.C.I.F.A.',
    'CS50O': 'Cresud S.A.C.I.F.A.',  'CS52O': 'Cresud S.A.C.I.F.A.',
    'CS53O': 'Cresud S.A.C.I.F.A.',
    # Bancos
    'BF39O': 'Banco BBVA Argentina S.A.',  'BF44O': 'Banco BBVA Argentina S.A.',
    'BF40O': 'Banco BBVA Argentina S.A.',
    'AFCIO': 'Banco Comafi S.A.',  'AFCHO': 'Banco Comafi S.A.',
    'BGC4O': 'Banco Patagonia S.A.',
    'HBCDO': 'Banco Hipotecario S.A.',  'HBCEO': 'Banco Hipotecario S.A.',
    'BPCTO': 'Banco Supervielle S.A.',  'BPCSO': 'Banco Supervielle S.A.',
    'BPCVO': 'Banco Supervielle S.A.',
    'BVCOO': 'Banco de Servicios y Transacciones S.A.',
    # Finanzas
    'SBC2O': 'Scania Credit Argentina S.A.U.',
    'CICBO': 'CNH Industrial Capital Argentina S.A.',
    'SXC1O': 'Mercado Pago S.R.L.',
    'T641O': 'Tarjeta Naranja S.A.U.',  'T661O': 'Tarjeta Naranja S.A.U.',
    # Arcor
    'RC1CO': 'Arcor S.A.I.C.',
    # San Miguel
    'SNABO': 'San Miguel A.G.I.C.I. y F.',  'SNAAO': 'San Miguel A.G.I.C.I. y F.',
    # MSU
    'MSSFO': 'MSU S.A.',  'MSSGO': 'MSU S.A.',
    # Rizobacter
    'RZ9BO': 'Rizobacter Argentina S.A.',
    # Aluminio Argentino
    'LMS8O': 'Aluminio Argentino S.A.I.C.',
    # Telecom
    'TLCFO': 'Telecom Argentina S.A.',
    # Otamérica
    'OTS3O': 'Otamérica Ebytem S.A.',
    # Aeropuertos
    'AER9O': 'Aeropuertos Argentina 2000 S.A.',
    # Construcción
    'VES2L': 'Ricardo Venturino S.A.',
    'JNC5O': 'Inversora Juramento S.A.',
    'ZPC1O': 'Plaza Logística S.R.L.',
}



# ── Descarga y parseo del payload BYMA ────────────────────────────────────────

_PAYLOAD_RE = re.compile(r'<script id="payload" type="application/json">(.*?)</script>', re.S)
_MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
# BYMA Educa trae el segmento 'hd' (hard dollar). dlf/dlz/ars quedan afuera (no son curva USD).
SEG_OK = {'hd'}


def fetch_payload(from_file=None):
    if from_file:
        html = Path(from_file).read_text(encoding='utf-8')
    else:
        r = _get(BYMA_URL, timeout=60)
        r.raise_for_status()
        html = r.content.decode('utf-8', errors='replace')
    m = _PAYLOAD_RE.search(html)
    if not m:
        raise RuntimeError('No se encontró <script id="payload"> — BYMA cambió el formato del tablero')
    return json.loads(m.group(1))


def _fdate(iso):
    """'2028-06-22' → '22-Jun-2028' (formato que espera el frontend)."""
    if not iso:
        return ''
    y, m, d = iso.split('-')
    return f"{int(d):02d}-{_MON[int(m) - 1]}-{y}"


def _dmy(iso):
    y, m, d = iso.split('-')
    return f"{d}-{m}-{y}"


def _n(v, nd=4):
    return '' if v is None else round(v, nd)


def clean_price(px, ai, vr):
    """Precio limpio por 100 de valor residual. px/ai están por 100 de VN original."""
    if px is None or ai is None or not vr:
        return None
    return (px - ai) / vr * 100


def _moneda(r):
    """Etiqueta de moneda de liquidación (mismos valores que usaba curvas_moneda_lookup.csv)."""
    if r['mp'] == 'MEP':
        return 'USD Mep'
    return 'USD Int' if r['ley'] == 'NY' else 'USD Cable'


_INDUSTRIA_FALLBACK = {
    'Servicios Financieros': 'Finanzas', 'Bienes Raices': 'Real Estate',
    'Comunicaciones': 'Telecomunicaciones', 'Consumo Masivo': 'Alimentos y Bebidas',
    'Materiales': 'Materiales Básicos',
}


def _industria(r):
    s = get_sector(r['tk'])
    if s == 'Otros':
        s = _INDUSTRIA_FALLBACK.get(r.get('sec'), 'Otros')
    return s


def build_rows(payload):
    on = payload['on']
    fecha = _dmy(on['fecha'])
    out = []
    for r in on['rows']:
        if r.get('seg') not in SEG_OK or r.get('px') is None:
            continue
        fxi = r.get('fxi') or {}
        prox_cap = next((a[0] for a in (r.get('amo') or []) if a[0] >= on['fecha']), '')
        cl = clean_price(r['px'], r.get('ai'), r.get('vr'))
        out.append({
            'Fecha': fecha, 'Ticker': r['tk'],
            'Emisor': EMISOR_MAP.get(r['tk']) or (r.get('em') or '').replace(',', ' '),
            'Industria': _industria(r),
            'Ley': 'NY' if r['ley'] == 'NY' else 'Arg',
            'Moneda': _moneda(r),
            'Cupon': _n(r['cup'] * 100) if r.get('cup') is not None else '',
            'Vencimiento': _fdate(r.get('fv')), 'Prox_Cupon': _fdate(r.get('pc')),
            'Precio_Clean': _n(cl), 'YTM': _n(r.get('ytm')), 'CY': _n(r.get('cy')),
            'DM': _n(r.get('dm')), 'CX': _n(r.get('cx')), 'WAL': _n(r.get('wal')),
            'Monto_Emitido': _n(r['mto'] / 1e6, 1) if r.get('mto') else '',
            'ADTV_ARS': _n(r['adtv'] / 1e6, 2) if r.get('adtv') is not None else '',
            'Cierre_ARS': _n(r.get('pxa'), 2), 'Accr_Int': _n(r.get('ai')),
            'VT': _n(r.get('vt')), 'VR': _n(r.get('vr')),
            'Estructura': r.get('est') or '', 'Frec_Cupon': r.get('fc') or '',
            'Cuotas_Capital': int(r['cuo']) if r.get('cuo') is not None else '', 'Frec_Capital': r.get('fam') or '',
            'Prox_Capital': _fdate(prox_cap),
            'Precio_Dirty': _n(r['px']), 'Paridad': _n(r.get('par')),
            'Var_Px_Pct': _n(r.get('pxd'), 3), 'Var_YTM_bps': _n(r.get('dytm'), 1),
            'ADTV_USD': _n(r.get('adtvu'), 0), 'Canje_Pct': _n(fxi.get('canje'), 3),
            'MEP_Implicito': _n(fxi.get('mep'), 2), 'CCL_Implicito': _n(fxi.get('ccl'), 2),
        })
    otros = [x['Ticker'] for x in out if x['Industria'] == 'Otros']
    if otros:
        log(f"  [!] {len(otros)} tickers sin industria (agregar a _SECTOR_RULES): {', '.join(otros)}")
    return out, fecha

# ── Guardar CSV ───────────────────────────────────────────────────────────────

def save_csv(rows, report_date_str):
    with open(CSV_OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    log(f"  [CSV] {CSV_OUT.name}  ({len(rows)} bonos, fecha {report_date_str})")

# ── Histórico ONs propias (IRSA / Cresud) — tab "Propias" ─────────────────────
# Se appendea (no se sobreescribe) cada corrida, a diferencia de curvas_on.csv.

def _is_propia(ticker):
    return ticker.startswith('IRC') or re.match(r'^CS\d', ticker)


def _load_propias():
    """Lee el histórico migrando filas viejas (sin columnas nuevas) al esquema actual."""
    if not PROPIAS_CSV.exists():
        return []
    with open(PROPIAS_CSV, encoding='utf-8') as f:
        return [{k: r.get(k, '') for k in PROPIAS_FIELDNAMES} for r in csv.DictReader(f)]


def _write_propias(rows):
    with open(PROPIAS_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=PROPIAS_FIELDNAMES, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def _propias_row(r):
    return {
        'Fecha': r['Fecha'], 'Ticker': r['Ticker'],
        'Emisor': 'IRSA' if r['Ticker'].startswith('IRC') else 'Cresud',
        'Vencimiento': r['Vencimiento'], 'Precio_Clean': r['Precio_Clean'],
        'YTM': r['YTM'], 'CY': r['CY'], 'DM': r['DM'],
        'Var_Px_Pct': r.get('Var_Px_Pct', ''), 'Var_YTM_bps': r.get('Var_YTM_bps', ''),
        'ADTV_USD': r.get('ADTV_USD', ''), 'Canje_Pct': r.get('Canje_Pct', ''),
        'Paridad': r.get('Paridad', ''),
    }


def append_propias_historico(rows, report_date_str):
    propias = [r for r in rows if _is_propia(r['Ticker'])]
    if not propias:
        return
    existing = _load_propias()
    if report_date_str in {r['Fecha'] for r in existing}:
        log(f"  [PROPIAS] {report_date_str} ya está en {PROPIAS_CSV.name}, no se appendea de nuevo")
        _write_propias(existing)   # igual migra el esquema si hacía falta
        return
    existing.extend(_propias_row(r) for r in propias)
    _write_propias(existing)
    log(f"  [PROPIAS] {PROPIAS_CSV.name}  (+{len(propias)} filas, fecha {report_date_str})")

# ── Backfill de ruedas faltantes (propias) ────────────────────────────────────
# `histi` trae ~21 ruedas de TIR / CY / precio sucio por ticker. El interés corrido de cada
# fecha se reconstruye hacia atrás desde el `ai` de hoy (dato de BYMA) restando el devengo
# 30/360 al cupón vigente, con liquidación T+1 hábil (sin calendario de feriados). Si el
# resultado es negativo, hubo un pago de cupón entre esa rueda y hoy → la fila se omite.

def _d360(a, b):
    return (b.year - a.year) * 360 + (b.month - a.month) * 30 + (min(b.day, 30) - min(a.day, 30))


def _pd(s):
    y, m, d = map(int, s.split('-'))
    return date(y, m, d)


def _settle(d):
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def accrued_at(r, d, liq_today):
    """Interés corrido (por 100 de VN original) a la fecha d. None si no se puede estimar."""
    if r.get('est') != 'Tasa Fija' or r.get('cup') is None or r.get('ai') is None:
        return None
    ai = r['ai'] - r['vr'] * r['cup'] * _d360(_settle(d), _pd(liq_today)) / 360
    return ai if ai >= 0 else None


def backfill_propias(payload):
    on = payload['on']
    h = on['histi']
    existing = _load_propias()
    have = {r['Fecha'] for r in existing}
    by_tk = {r['tk']: r for r in on['rows'] if _is_propia(r['tk'])}
    added = 0
    for i, f in enumerate(h['f']):
        fecha = _dmy(f)
        if fecha in have or f == on['fecha']:
            continue
        d = _pd(f)
        for tk, r in sorted(by_tk.items()):
            if tk not in h['px'] or h['px'][tk][i] is None or h['v'].get(tk, [None] * (i + 1))[i] is None:
                continue
            if h['u'].get(tk) != 'TIR':
                continue
            if any(on['fecha'] >= a[0] > f for a in (r.get('amo') or [])):
                continue                   # amortizó entre esa rueda y hoy: vr distinto, no confiable
            ai = accrued_at(r, d, on['fecha_liq'])
            cl = clean_price(h['px'][tk][i], ai, r['vr']) if ai is not None else None
            existing.append({
                'Fecha': fecha, 'Ticker': tk, 'Emisor': 'IRSA' if tk.startswith('IRC') else 'Cresud',
                'Vencimiento': _fdate(r['fv']), 'Precio_Clean': _n(cl), 'YTM': _n(h['v'][tk][i]),
                'CY': _n(h['cy'][tk][i]) if tk in h['cy'] else '', 'DM': '',
                'Var_Px_Pct': '', 'Var_YTM_bps': '', 'ADTV_USD': '', 'Canje_Pct': '', 'Paridad': '',
            })
            added += 1
    if added:
        existing.sort(key=lambda r: (datetime.strptime(r['Fecha'], '%d-%m-%Y'), r['Ticker']))
        _write_propias(existing)
    log(f"  [BACKFILL] +{added} filas en {PROPIAS_CSV.name}")

# ── Git commit y push ─────────────────────────────────────────────────────────

def git_commit_push(report_date_str):
    try:
        subprocess.run(
            ['git', 'add', 'curvas_on.csv', 'curvas_propias_historico.csv'],
            cwd=BASE_DIR, check=True, capture_output=True
        )
        result = subprocess.run(
            ['git', 'commit', '-m', f'update curvas ONs — BYMA {report_date_str}'],
            cwd=BASE_DIR, capture_output=True, text=True
        )
        if result.returncode != 0:
            log(f"  [GIT] {result.stdout.strip() or result.stderr.strip()}")
            return
        subprocess.run(['git', 'push'], cwd=BASE_DIR, check=True, capture_output=True)
        log(f"  [GIT] commit y push OK ({report_date_str})")
    except subprocess.CalledProcessError as e:
        log(f"  [GIT ERROR] {e}")

# ── Main ──────────────────────────────────────────────────────────────────────

def run(args):
    ts = date.today().strftime('%Y-%m-%d')
    log(f"\n[{ts}] === Iniciando scraper BYMA Educa ===")
    try:
        payload = fetch_payload(args.from_file)
    except Exception as e:
        log(f"[ERROR] No se pudo obtener el tablero BYMA: {e}")
        sys.exit(1)

    rows, fecha = build_rows(payload)
    log(f"[TOTAL] {len(rows)} ONs hard-dollar — rueda {fecha}")
    if not rows:
        log("[!] Sin filas — BYMA cambió el formato del payload?")
        sys.exit(1)

    save_csv(rows, fecha)
    if args.backfill:
        backfill_propias(payload)
    append_propias_historico(rows, fecha)
    log("\n[OK] Listo.")

    if args.commit:
        git_commit_push(fecha)


def main():
    p = argparse.ArgumentParser(description="Scraper curvas ONs — BYMA Educa")
    p.add_argument('--backfill', action='store_true', help='Completa ruedas faltantes de ONs propias desde el histórico del payload')
    p.add_argument('--commit', action='store_true', help='Hace git commit y push tras guardar')
    p.add_argument('--from-file', default=None, help='HTML del tablero ya descargado (pruebas)')
    run(p.parse_args())


if __name__ == '__main__':
    main()
