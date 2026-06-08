#!/usr/bin/env python3
"""
scraper_curvas.py — Descarga el informe diario de PPI y extrae la tabla
de Bonos Corporativos en USD (páginas 12-13).

Guarda: curvas_on.csv  (sobreescribe con los datos del informe más reciente)
        curvas_last_id.txt  (ID del último informe descargado)

Uso:
    python scraper_curvas.py              # prueba desde last_id + 1
    python scraper_curvas.py --id 24521  # fuerza un ID específico
    python scraper_curvas.py --debug     # muestra texto raw de las páginas

Requiere:
    pip install pdfplumber requests
"""

import argparse
import csv
import io
import re
import sys
from datetime import date, datetime
from pathlib import Path

import pdfplumber
import requests

BASE_DIR     = Path(__file__).parent
CSV_OUT      = BASE_DIR / "curvas_on.csv"
LAST_ID_FILE = BASE_DIR / "curvas_last_id.txt"
BASE_URL     = "https://cdn1.portfoliopersonal.com/Attachs/{id}.pdf"
MAX_TRIES    = 7
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

FIELDNAMES = [
    "Fecha", "ID", "Ticker", "Emisor", "Industria",
    "Cupon", "Vencimiento", "Prox_Cupon", "Calificacion",
    "Ley", "Moneda", "Precio_Dirty_MEP", "Precio_Clean_MEP",
    "TIR", "TNA", "CY", "MD", "Canje_CCL",
    "Precio_Dirty_Moneda", "Fecha_Rescate", "Precio_Rescate",
    "YTW", "Lamina_Min", "Monto_Circ",
    "Precio_Clean_BBG", "TIR_BBG",
]

# ── ID tracking ───────────────────────────────────────────────────────────────

def read_last_id():
    if LAST_ID_FILE.exists():
        try:
            return int(LAST_ID_FILE.read_text().strip())
        except ValueError:
            pass
    return None

def write_last_id(id_):
    LAST_ID_FILE.write_text(str(id_))
    print(f"  [ID] Guardado last_id = {id_}")

# ── Descarga ──────────────────────────────────────────────────────────────────

def fetch_pdf(id_):
    """Descarga el PDF; retorna bytes si es un PDF válido, None si no existe."""
    url = BASE_URL.format(id=id_)
    try:
        r = requests.get(url, headers=HTTP_HEADERS, timeout=30)
        if r.status_code == 200 and r.content[:4] == b'%PDF':
            print(f"  [OK] {url}  ({len(r.content)//1024} KB)")
            return r.content
        print(f"  [--] {url} → HTTP {r.status_code}")
        return None
    except Exception as e:
        print(f"  [!!] {url} → {e}")
        return None

# ── Parser de filas ───────────────────────────────────────────────────────────

# Industrias conocidas para separar emisor de industria
INDUSTRIAS = [
    "Real Estate",
    "Finanzas",
    "Telecomunicaciones",
    "Electricidad",
    "Agroindustria",
    "Construcci",      # prefix: Construcción
    "Alimentos",       # prefix: Alimentos Y Bebidas
    "Materiales",      # prefix: Materiales Básicos
    "Petr",            # prefix: Petróleo & Gas
    "Aerol",           # prefix: Aerolíneas
]

# Regex: "Arg MEP", "Arg CCL", "NY MEP", "NY CCL"
LEY_MON_RE = re.compile(r'\b(Arg|NY)\s+(MEP|CCL)\b')

# Tokenizador para la parte numérica posterior al Ley+Moneda
# Orden importa: primero los más específicos
TOKEN_RE = re.compile(
    r'US\$[\d,.]+(?:\.\d{3})*'   # precios: US$104,5 / US$1.000
    r'|-?\d+[,\.]\d+%'           # porcentajes con decimal: -64,2% / 5,9%
    r'|\d{1,2}/\d{1,2}/\d{4}'   # fechas: 9/6/2026
    r'|-?\d+[,\.]\d+'            # números con decimal: 0,0 / 2,6 / -0,4
    r'|\d+(?:\.\d{3})+'          # enteros con miles: 1.000 / 10.000
    r'|\d+'                       # enteros simples: 1 / 23 / 400
    r'|-'                         # guiones
)

def _g(tokens, i, default=''):
    return tokens[i] if i < len(tokens) else default

def _clean(s):
    """Normaliza número: quita puntos de miles, reemplaza coma decimal por punto."""
    if not s or s == '-':
        return s
    # Si es US$xxx,x → quitar "US$", convertir coma a punto
    if s.startswith('US$'):
        s = s[3:]
    # Detectar si es número europeo (coma decimal): tiene una sola coma y la coma está antes del final
    # "104,5" → "104.5"; "1.000" → "1000"
    if re.match(r'^-?\d+\.\d{3}$', s):
        return s.replace('.', '')  # quitar separador de miles
    if ',' in s:
        return s.replace('.', '').replace(',', '.')
    return s

def find_industria(text):
    """Retorna (emisor, industria) separando por industria conocida."""
    for ind in sorted(INDUSTRIAS, key=len, reverse=True):
        # Requiere límite de palabra antes del match (no en medio de una palabra)
        pattern = r'(?<!\S)' + re.escape(ind)
        m = re.search(pattern, text, re.IGNORECASE)
        if m and m.start() > 0:
            return text[:m.start()].strip(), text[m.start():].strip()
    return text.strip(), ''

def parse_row(line):
    """
    Parsea una línea de bono. Retorna dict con los campos o None si no es válida.

    Estructura de cada fila:
      TICKER EMISOR INDUSTRIA CUPON VENCIMIENTO [PROX_CUPON|-] CALIFICACION LEY MONEDA
      [PRECIO_DIRTY] [PRECIO_CLEAN] [TIR] [TNA] [CY] [MD] [CANJE_CCL]
      [PRECIO_DIRTY_MONEDA] [FECHA_RESCATE|-] [PRECIO_RESCATE|-] [YTW|-]
      LAMINA MONTO [BBG_PRECIO|-] [BBG_TIR|-]
    """
    line = line.strip()

    # Debe empezar con ticker: 5-6 chars mayúsculas/dígitos terminados en O
    m = re.match(r'^([A-Z][A-Z0-9]{3,5})\s+', line)
    if not m:
        return None
    ticker = m.group(1)
    rest = line[m.end():]

    # Localizar "Ley Moneda" que divide la cabecera del bloque numérico
    lm = LEY_MON_RE.search(rest)
    if not lm:
        return None

    ley    = lm.group(1)
    moneda = lm.group(2)
    head   = rest[:lm.start()].strip()
    tail   = rest[lm.end():].strip()

    # ── Parsear head: EMISOR INDUSTRIA CUPON VENCIMIENTO [PROX_CUPON] CALIFICACION ──

    # Cupón: único patrón X,XXX% (3 decimales fijos)
    cupon_m = re.search(r'(\d+[,\.]\d{3}%)', head)
    if not cupon_m:
        return None
    cupon      = cupon_m.group(1).replace(',', '.')
    pre_cupon  = head[:cupon_m.start()].strip()
    post_cupon = head[cupon_m.end():].strip()

    emisor, industria = find_industria(pre_cupon)

    # Fechas en post_cupon: vencimiento y próximo cupón
    fechas = re.findall(r'\d{1,2}/\d{1,2}/\d{4}', post_cupon)
    vencimiento = fechas[0] if len(fechas) > 0 else ''
    prox_cupon  = fechas[1] if len(fechas) > 1 else ''

    # Calificación: lo que queda tras quitar fechas y el guión de "sin próx. cupón"
    calificacion = post_cupon
    for f in fechas:
        calificacion = calificacion.replace(f, '', 1)
    calificacion = re.sub(r'^\s*-?\s*', '', calificacion).strip()
    # Normalizar: quitar espacios internos extra
    calificacion = re.sub(r'\s+', ' ', calificacion).strip()

    # ── Parsear tail (bloque numérico) ──
    tokens = TOKEN_RE.findall(tail)

    # Posiciones fijas del tail:
    # 0  Precio Dirty MEP
    # 1  Precio Clean MEP
    # 2  TIR Efectiva
    # 3  TNA
    # 4  CY
    # 5  MD
    # 6  Canje CCL  (% o -)
    # 7  Precio Dirty Moneda Pago
    # 8  Fecha Rescate  (date o -)
    # 9  Precio Rescate (US$ o -)
    # 10 YTW
    # 11 Lámina Mínima
    # 12 Monto en Circulación
    # 13 BBG Precio Clean  (opcional)
    # 14 BBG TIR           (opcional)

    def g(i):
        v = _g(tokens, i, '-')
        return '' if v == '-' else v

    # Detectar si posición 8 es fecha o dash
    t8 = _g(tokens, 8, '-')
    is_date_t8 = bool(re.match(r'\d{1,2}/\d{1,2}/\d{4}', t8))

    return {
        'Ticker':             ticker,
        'Emisor':             emisor,
        'Industria':          industria,
        'Cupon':              cupon,
        'Vencimiento':        vencimiento,
        'Prox_Cupon':         prox_cupon,
        'Calificacion':       calificacion,
        'Ley':                ley,
        'Moneda':             moneda,
        'Precio_Dirty_MEP':   _clean(g(0)),
        'Precio_Clean_MEP':   _clean(g(1)),
        'TIR':                g(2).replace('%', '').replace(',', '.'),
        'TNA':                g(3).replace('%', '').replace(',', '.'),
        'CY':                 g(4).replace('%', '').replace(',', '.'),
        'MD':                 g(5).replace(',', '.'),
        'Canje_CCL':          g(6).replace('%', '').replace(',', '.'),
        'Precio_Dirty_Moneda':_clean(g(7)),
        'Fecha_Rescate':      t8 if is_date_t8 else '',
        'Precio_Rescate':     _clean(g(9)) if is_date_t8 else _clean(g(9)),
        'YTW':                g(10).replace('%', '').replace(',', '.'),
        'Lamina_Min':         _clean(g(11)),
        'Monto_Circ':         _clean(g(12)),
        'Precio_Clean_BBG':   _clean(g(13)),
        'TIR_BBG':            g(14).replace('%', '').replace(',', '.'),
    }

# ── Extracción del PDF ────────────────────────────────────────────────────────

def extract_rows_from_pdf(pdf_bytes, debug=False):
    """
    Extrae las filas de bonos de las páginas 12 y 13 (índices 11 y 12).
    Usa extract_words agrupados por coordenada Y para reconstruir cada fila.
    """
    rows = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        total = len(pdf.pages)
        print(f"  [PDF] {total} páginas")

        for page_idx in [11, 12]:
            if page_idx >= total:
                print(f"  [!] Página {page_idx+1} no existe en el PDF")
                continue

            page = pdf.pages[page_idx]

            # Agrupar palabras por Y (misma línea = Y similar)
            words = page.extract_words(x_tolerance=4, y_tolerance=4)
            line_map = {}
            for w in words:
                y_key = round(w['top'] / 3) * 3
                line_map.setdefault(y_key, []).append((w['x0'], w['text']))

            page_lines = []
            for y in sorted(line_map):
                tokens_in_line = [t for _, t in sorted(line_map[y])]
                line_str = ' '.join(tokens_in_line)
                page_lines.append(line_str)

            if debug:
                print(f"\n=== Página {page_idx+1} ({len(page_lines)} líneas) ===")
                for ln in page_lines:
                    print(f"  {ln}")

            # Filtrar solo las líneas que empiezan con ticker
            ticker_re = re.compile(r'^[A-Z][A-Z0-9]{3,5}\s')
            for ln in page_lines:
                if ticker_re.match(ln):
                    parsed = parse_row(ln)
                    if parsed:
                        rows.append(parsed)
                    elif debug:
                        print(f"  [!] No parseada: {ln[:80]}")

    return rows

# ── Guardar CSV ───────────────────────────────────────────────────────────────

def save_csv(rows, report_id, report_date):
    """Sobreescribe curvas_on.csv con los datos del informe más reciente."""
    fecha_str = report_date.strftime('%d/%m/%Y')
    with open(CSV_OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for r in rows:
            row = {'Fecha': fecha_str, 'ID': report_id}
            row.update(r)
            w.writerow(row)
    print(f"  [CSV] {CSV_OUT.name}  ({len(rows)} bonos, fecha {fecha_str})")

# ── Main ──────────────────────────────────────────────────────────────────────

def run(args):
    if args.id:
        ids_to_try = [args.id]
    else:
        last = read_last_id()
        if last is None:
            print("[!] No hay curvas_last_id.txt — usá --id XXXXX para arrancar")
            sys.exit(1)
        start = last + 1
        ids_to_try = list(range(start, start + MAX_TRIES))
        print(f"[BUSCA] IDs {start}..{start + MAX_TRIES - 1}  (last_id={last})")

    pdf_bytes = None
    found_id  = None
    for id_ in ids_to_try:
        pdf_bytes = fetch_pdf(id_)
        if pdf_bytes:
            found_id = id_
            break

    if not pdf_bytes:
        print(f"[!] No se encontró ningún PDF en los IDs probados.")
        sys.exit(0)

    print(f"\n[PARSE] ID {found_id}")
    rows = extract_rows_from_pdf(pdf_bytes, debug=args.debug)
    print(f"  -> {len(rows)} bonos extraidos")

    if not rows:
        print("[!] Sin filas — verificá el PDF con --debug")
        sys.exit(1)

    save_csv(rows, found_id, date.today())
    write_last_id(found_id)
    print(f"\n[OK] Listo. Próximo ID a probar: {found_id + 1}")


def main():
    p = argparse.ArgumentParser(description="Scraper curvas ONs — PPI Daily")
    p.add_argument('--id',    type=int, default=None, help='ID específico del informe')
    p.add_argument('--debug', action='store_true',    help='Muestra texto raw de páginas')
    args = p.parse_args()
    run(args)


if __name__ == '__main__':
    main()
