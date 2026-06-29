#!/usr/bin/env python3
"""
scraper_curvas.py — Descarga el informe diario IAMC "Informe Diario Deuda Corporativa"
y extrae las tablas de bonos corporativos USD:
  - Ley NY  : páginas 1-2   (índices 0-1)
  - Ley Arg : páginas 5-13  (índices 4-12)

Guarda: curvas_on.csv  (sobreescribe con los datos del informe más reciente)

Uso:
    python scraper_curvas.py                          # informe más reciente de la web
    python scraper_curvas.py --fecha 24-06-2026       # fecha específica (DD-MM-YYYY)
    python scraper_curvas.py --commit                 # git commit + push tras guardar
    python scraper_curvas.py --debug                  # muestra texto raw de las páginas

Requiere:
    pip install pdfplumber requests beautifulsoup4
"""

import argparse
import csv
import io
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pdfplumber
import requests
from bs4 import BeautifulSoup

BASE_DIR    = Path(__file__).parent
CSV_OUT     = BASE_DIR / "curvas_on.csv"
LOG_FILE    = BASE_DIR / "scraper_curvas.log"
LOOKUP_CSV  = BASE_DIR / "curvas_moneda_lookup.csv"

IAMC_LISTING = "https://www.iamc.com.ar/curvarendimientoobligacionesnegociables/"
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
    # campos adicionales (pueden estar vacíos en algunos bonos)
    "Cierre_ARS", "Accr_Int", "VT", "VR",
    "Estructura", "Frec_Cupon", "Cuotas_Capital", "Frec_Capital", "Prox_Capital",
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
]
# Ordenar por longitud descendente para hacer match por prefijo más largo
_SECTOR_RULES.sort(key=lambda x: -len(x[0]))

def get_sector(ticker):
    for prefix, sector in _SECTOR_RULES:
        if ticker.startswith(prefix):
            return sector
    return 'Otros'

# ── Scraping de la página de listado IAMC ─────────────────────────────────────

def _get_all_listing_dates():
    """
    Scrapea la página de listado IAMC y retorna lista de (fecha_str, url_informe)
    donde fecha_str es 'DD-MM-YYYY' y url_informe es relativa al dominio.
    Ordenadas por fecha descendente.
    """
    try:
        r = _get(IAMC_LISTING, timeout=20)
        r.raise_for_status()
    except Exception as e:
        log(f"  [!!] Error descargando listado IAMC: {e}")
        return []

    soup = BeautifulSoup(r.text, 'html.parser')
    pattern = re.compile(r'/Informe/InformeDiarioDeudaCorporativa(\d{8})/', re.IGNORECASE)
    entries = []
    seen = set()
    for a in soup.find_all('a', href=True):
        m = pattern.search(a['href'])
        if m:
            raw = m.group(1)          # DDMMYYYY
            fecha_str = f"{raw[0:2]}-{raw[2:4]}-{raw[4:8]}"
            url = f"https://www.iamc.com.ar{m.group(0)}"
            if fecha_str not in seen:
                seen.add(fecha_str)
                entries.append((fecha_str, url))

    # Ordenar por fecha descendente
    entries.sort(key=lambda x: datetime.strptime(x[0], '%d-%m-%Y'), reverse=True)
    return entries


def get_informe_for_date(target_date_str):
    """
    Dado 'DD-MM-YYYY', busca esa fecha en el listado.
    Si no la encuentra exactamente, retorna None.
    """
    entries = _get_all_listing_dates()
    for fecha, url in entries:
        if fecha == target_date_str:
            return fecha, url
    return None, None


def get_latest_informe():
    """
    Retorna (fecha_str, url_informe) del informe más reciente disponible.
    """
    entries = _get_all_listing_dates()
    if entries:
        return entries[0]
    return None, None

# ── Obtención de la URL del PDF ───────────────────────────────────────────────

def get_pdf_url(informe_url):
    """
    Scrapea la página del informe y retorna la URL directa al PDF.
    Patrón: iamcweb.prod.ingecloud.com/TempFiles/{uuid}.pdf
    """
    try:
        r = _get(informe_url, timeout=20)
        r.raise_for_status()
    except Exception as e:
        log(f"  [!!] Error descargando página del informe: {e}")
        return None

    m = re.search(r'https://iamcweb\.prod\.ingecloud\.com/TempFiles/[^"\'>\s]+\.pdf', r.text)
    if m:
        return m.group(0)
    log("  [!!] No se encontró URL del PDF en la página del informe")
    return None

# ── Descarga del PDF ──────────────────────────────────────────────────────────

def fetch_pdf(pdf_url):
    try:
        r = _get(pdf_url, timeout=60)
        if r.status_code == 200 and r.content[:4] == b'%PDF':
            log(f"  [OK] PDF descargado  ({len(r.content)//1024} KB)")
            return r.content
        log(f"  [--] {pdf_url} → HTTP {r.status_code}")
    except Exception as e:
        log(f"  [!!] {pdf_url} → {e}")
    return None

# ── Parser de filas del PDF ───────────────────────────────────────────────────

MONTHS_EN = {
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
    'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12
}

DATE_RE  = re.compile(r'\d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2,4}', re.IGNORECASE)
MONTO_RE = re.compile(r'([\d,]+(?:\.\d+)?)M\b')
PCT_RE   = re.compile(r'-?\d+[.,]\d+%')
NUM_RE   = re.compile(r'-?\d+[.,]\d+|-?\d+')


def _norm_date(s):
    """'17-Jan-34' → '17-Jan-2034'  (año 2 dígitos → 4 dígitos)"""
    parts = s.split('-')
    if len(parts) == 3 and len(parts[2]) == 2:
        yr = int(parts[2])
        parts[2] = str(2000 + yr)
    return '-'.join(parts)


def _parse_float(s):
    """
    '7,38'     → '7.38'     (coma decimal, 2 dígitos → decimal)
    '1,100'    → '1100'     (coma miles, 3 dígitos → miles)
    '1,355.63' → '1355.63'  (coma miles + punto decimal anglosajón)
    '103.6'    → '103.6'    (sin coma)
    """
    s = s.strip()
    if not s or s == '-':
        return ''
    if ',' in s and '.' in s:
        # Anglosajón: 1,355.63 → coma = miles
        return s.replace(',', '')
    elif ',' in s:
        after = s.split(',')[-1]
        if len(after) == 3:
            # Miles: 1,100 → 1100
            return s.replace(',', '')
        else:
            # Decimal: 7,38 → 7.38
            return s.replace(',', '.')
    return s


def parse_row(line, ley):
    """
    Parsea una línea de bono del PDF IAMC. Retorna dict o None si no es válida.

    Estructura del texto extraído (extract_words por Y):
      TICKER EMISOR MONTO FECHA_EMISION FECHA_VTO ESTRUCTURA FREC_CPN PROX_CPN
      TASA% CY% ACCR VR CUOTAS FREC_CAP PROX_CAP CIERRE_ARS PARIDAD VT YTM% DM CX WAL ADTV_M
    """
    line = line.strip()

    # Ticker: 4-6 chars mayúsculas al inicio
    m = re.match(r'^([A-Z][A-Z0-9]{3,5})\s+', line)
    if not m:
        return None
    ticker = m.group(1)
    rest = line[m.end():]

    # Monto emitido: primer NUMBER+M (ej: "1,100M", "500M", "46M")
    monto_m = MONTO_RE.search(rest)
    if not monto_m:
        return None
    monto = float(_parse_float(monto_m.group(1)) or 0)
    tail  = rest[monto_m.end():].strip()

    # Extraer todos los elementos del tail
    dates    = DATE_RE.findall(tail)
    # dates: [Fecha_Emision, Fecha_Vto, Prox_Cupon, Prox_Capital]

    estructura_m = re.search(r'Tasa\s+(Fija|Variable)', tail)
    estructura   = ('Tasa ' + estructura_m.group(1)) if estructura_m else ''

    freqs = re.findall(r'\b(Semestral|Trimestral|Anual|Vencimiento)\b', tail)
    # freqs[0] = Frec_Cupon, freqs[1] = Frec_Capital

    # Limpiar el tail para extraer números
    num_tail = DATE_RE.sub(' ', tail)
    num_tail = re.sub(r'Tasa\s+(?:Fija|Variable)', ' ', num_tail)
    num_tail = re.sub(r'\b(?:Semestral|Trimestral|Anual|Vencimiento)\b', ' ', num_tail)

    # ADTV: último NUMBER+M en num_tail
    adtv_m = re.search(r'([\d,]+(?:\.\d+)?)M\s*$', num_tail.rstrip())
    adtv   = float(_parse_float(adtv_m.group(1)) or 0) if adtv_m else ''
    if adtv_m:
        num_tail = num_tail[:adtv_m.start()]

    # Porcentajes (en orden): Tasa, CY, YTM
    pcts = PCT_RE.findall(num_tail)
    num_tail_nopct = PCT_RE.sub(' ', num_tail)

    # Números planos (en orden): Accr_Int, VR, Cuotas, Cierre_ARS, Paridad, VT, DM, CX, WAL
    nums = [n for n in NUM_RE.findall(num_tail_nopct) if n.strip()]

    def _g(lst, i):
        v = lst[i] if i < len(lst) else ''
        return _parse_float(v.replace('%','')) if v else ''

    def _pct(lst, i):
        v = lst[i] if i < len(lst) else ''
        return _parse_float(v.replace('%','')) if v else ''

    # Mapeo posicional de nums: Accr_Int, VR, Cuotas, Cierre_ARS, Paridad, VT, DM, CX, WAL
    # Para bonos sin YTM los últimos campos quedan vacíos (bonos al vencimiento)
    accr_int   = _g(nums, 0)
    vr         = _g(nums, 1)
    cuotas     = _g(nums, 2)
    cierre_ars = _g(nums, 3)
    paridad    = _g(nums, 4)   # Precio_Clean (Paridad %)
    vt         = _g(nums, 5)   # Precio sucio (VT)
    dm         = _g(nums, 6)
    cx         = _g(nums, 7)
    wal        = _g(nums, 8)

    # YTM puede no existir para bonos al vencimiento inmediato
    ytm = _pct(pcts, 2)

    emisor_raw = rest[:monto_m.start()].strip()

    return {
        'Ticker':         ticker,
        'Emisor':         emisor_raw,  # se sobreescribe con lookup si existe
        'Industria':      get_sector(ticker),
        'Ley':            ley,
        'Cupon':          _pct(pcts, 0),
        'Vencimiento':    _norm_date(dates[1]) if len(dates) > 1 else '',
        'Prox_Cupon':     _norm_date(dates[2]) if len(dates) > 2 else '',
        'Precio_Clean':   paridad,
        'YTM':            ytm,
        'CY':             _pct(pcts, 1),
        'DM':             dm,
        'CX':             cx,
        'WAL':            wal,
        'Monto_Emitido':  monto,
        'ADTV_ARS':       adtv,
        'Cierre_ARS':     cierre_ars,
        'Accr_Int':       accr_int,
        'VT':             vt,
        'VR':             vr,
        'Estructura':     estructura,
        'Frec_Cupon':     freqs[0] if len(freqs) > 0 else '',
        'Cuotas_Capital': cuotas,
        'Frec_Capital':   freqs[1] if len(freqs) > 1 else '',
        'Prox_Capital':   _norm_date(dates[3]) if len(dates) > 3 else '',
    }

# ── Emisor lookup (nombre completo por ticker) ────────────────────────────────
# Complementa la extracción del PDF, que a veces trunca el nombre de la empresa.
# Si el ticker no está en el mapa, se usa lo extraído del texto.

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


def enrich_emisor(row):
    """Completa el campo Emisor desde EMISOR_MAP si el ticker está en el mapa."""
    ticker = row['Ticker']
    if ticker in EMISOR_MAP:
        row['Emisor'] = EMISOR_MAP[ticker]
    return row

# ── Extracción de páginas del PDF ─────────────────────────────────────────────

# Páginas a extraer (índices 0-based):
#   0-1  → Ley NY  (páginas 1-2 del PDF)
#   4-12 → Ley Arg (páginas 5-13 del PDF)
PAGE_GROUPS = [
    (range(0, 2),   'NY'),
    (range(4, 13),  'Arg'),
]

# Páginas que son continuación de tabla (misma ley que el grupo)
# No necesitamos detectarlos: iteramos directamente sobre los rangos.

TICKER_RE = re.compile(r'^[A-Z][A-Z0-9]{3,5}\s')


def extract_rows_from_pdf(pdf_bytes, debug=False):
    rows = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        total = len(pdf.pages)
        log(f"  [PDF] {total} páginas")

        for page_range, ley in PAGE_GROUPS:
            for page_idx in page_range:
                if page_idx >= total:
                    log(f"  [!] Página {page_idx+1} no existe")
                    continue

                page = pdf.pages[page_idx]

                # Reconstruir líneas agrupando words por coordenada Y
                words = page.extract_words(x_tolerance=4, y_tolerance=4)
                line_map = {}
                for w in words:
                    y_key = round(w['top'] / 3) * 3
                    line_map.setdefault(y_key, []).append((w['x0'], w['text']))

                page_lines = []
                for y in sorted(line_map):
                    tokens = [t for _, t in sorted(line_map[y])]
                    page_lines.append(' '.join(tokens))

                if debug:
                    print(f"\n=== Página {page_idx+1} — Ley {ley} ({len(page_lines)} líneas) ===")
                    for ln in page_lines:
                        print(f"  {ln}")

                page_rows = 0
                for ln in page_lines:
                    if TICKER_RE.match(ln):
                        parsed = parse_row(ln, ley)
                        if parsed:
                            parsed = enrich_emisor(parsed)
                            rows.append(parsed)
                            page_rows += 1
                        elif debug:
                            print(f"  [!] No parseada: {ln[:100]}")

                log(f"  [p{page_idx+1}] Ley {ley}: {page_rows} bonos")

    return rows

# ── Moneda lookup ─────────────────────────────────────────────────────────────

def load_moneda_lookup():
    """Lee curvas_moneda_lookup.csv → dict Ticker → Moneda."""
    if not LOOKUP_CSV.exists():
        return {}
    with open(LOOKUP_CSV, encoding='utf-8') as f:
        return {row['Ticker']: row['Moneda'] for row in csv.DictReader(f)}


# ── Guardar CSV ───────────────────────────────────────────────────────────────

def save_csv(rows, report_date_str):
    lookup = load_moneda_lookup()
    with open(CSV_OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            r['Fecha']  = report_date_str
            r['Moneda'] = lookup.get(r['Ticker'], '')
            w.writerow(r)
    log(f"  [CSV] {CSV_OUT.name}  ({len(rows)} bonos, fecha {report_date_str})")

# ── Git commit y push ─────────────────────────────────────────────────────────

def git_commit_push(report_date_str):
    try:
        subprocess.run(
            ['git', 'add', 'curvas_on.csv'],
            cwd=BASE_DIR, check=True, capture_output=True
        )
        result = subprocess.run(
            ['git', 'commit', '-m', f'update curvas ONs — IAMC {report_date_str}'],
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
    log(f"\n[{ts}] === Iniciando scraper IAMC ===")

    if args.fecha:
        fecha_str = args.fecha
        log(f"[FECHA] Buscando informe del {fecha_str}")
        informe_fecha, informe_url = get_informe_for_date(fecha_str)
        if not informe_url:
            log(f"[--] No se encontró informe para la fecha {fecha_str} en el listado IAMC.")
            sys.exit(0)
    else:
        log("[BUSCA] Informe más reciente en listado IAMC...")
        informe_fecha, informe_url = get_latest_informe()
        if not informe_url:
            log("[--] No se pudo obtener el listado IAMC.")
            sys.exit(1)

    log(f"[INFO] Informe: {informe_fecha}  →  {informe_url}")

    pdf_url = get_pdf_url(informe_url)
    if not pdf_url:
        sys.exit(1)
    log(f"[PDF] {pdf_url}")

    pdf_bytes = fetch_pdf(pdf_url)
    if not pdf_bytes:
        sys.exit(1)

    rows = extract_rows_from_pdf(pdf_bytes, debug=args.debug)
    log(f"[TOTAL] {len(rows)} bonos extraídos")

    if not rows:
        log("[!] Sin filas — verificar con --debug")
        sys.exit(1)

    save_csv(rows, informe_fecha)
    log(f"\n[OK] Listo.")

    if args.commit:
        git_commit_push(informe_fecha)


def main():
    p = argparse.ArgumentParser(description="Scraper curvas ONs — IAMC Deuda Corporativa")
    p.add_argument('--fecha',  default=None,        help='Fecha del informe: DD-MM-YYYY')
    p.add_argument('--commit', action='store_true', help='Hace git commit y push tras guardar')
    p.add_argument('--debug',  action='store_true', help='Muestra texto raw de páginas')
    args = p.parse_args()
    run(args)


if __name__ == '__main__':
    main()
