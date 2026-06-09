#!/usr/bin/env python3
"""
scraper_curvas.py — Descarga el informe diario de PPI y extrae la tabla
de Bonos Corporativos en USD (páginas 12-13).

Guarda: curvas_on.csv  (sobreescribe con los datos del informe más reciente)
        curvas_last_id.txt  (ID del último informe descargado)

Uso:
    python scraper_curvas.py              # busca desde last_id + 1
    python scraper_curvas.py --id 24525  # fuerza un ID específico
    python scraper_curvas.py --commit    # hace git commit + push tras guardar
    python scraper_curvas.py --debug     # muestra texto raw de las páginas

PPI publica dos tipos de informes con IDs secuenciales:
  - Informe de cierre (closing): contiene tabla de Bonos Corporativos en p.12-13
  - Informe diario de mercados: no contiene esa tabla → se saltea automáticamente

Requiere:
    pip install pdfplumber requests
"""

import argparse
import csv
import io
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pdfplumber
import requests

BASE_DIR     = Path(__file__).parent
CSV_OUT      = BASE_DIR / "curvas_on.csv"
LAST_ID_FILE = BASE_DIR / "curvas_last_id.txt"
LOG_FILE     = BASE_DIR / "scraper_curvas.log"
BASE_URL             = "https://cdn1.portfoliopersonal.com/Attachs/{id}.pdf"
MAX_CONSECUTIVE_404  = 3   # para si hay N 404s seguidas (informe no publicado aún)
HTTP_HEADERS         = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

FIELDNAMES = [
    "Fecha", "ID", "Ticker", "Emisor", "Industria",
    "Cupon", "Vencimiento", "Prox_Cupon", "Calificacion",
    "Ley", "Moneda", "Precio_Dirty_MEP", "Precio_Clean_MEP",
    "TIR", "TNA", "CY", "MD", "Canje_CCL",
    "Precio_Dirty_Moneda", "Fecha_Rescate", "Precio_Rescate",
    "YTW", "Lamina_Min", "Monto_Circ",
    "Precio_Clean_BBG", "TIR_BBG",
]

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg):
    """Imprime y appendea al log file."""
    print(msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

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
    log(f"  [ID] Guardado last_id = {id_}")

# ── Descarga ──────────────────────────────────────────────────────────────────

def fetch_pdf(id_):
    """Descarga el PDF; retorna bytes si es un PDF válido, None si no existe."""
    url = BASE_URL.format(id=id_)
    try:
        r = requests.get(url, headers=HTTP_HEADERS, timeout=30)
        if r.status_code == 200 and r.content[:4] == b'%PDF':
            log(f"  [OK] {url}  ({len(r.content)//1024} KB)")
            return r.content
        log(f"  [--] {url} → HTTP {r.status_code}")
        return None
    except Exception as e:
        log(f"  [!!] {url} → {e}")
        return None

# ── Validación: informe de cierre ─────────────────────────────────────────────

def _is_cierre_pdf(pdf_bytes):
    """
    Verifica que el PDF sea el informe de cierre (tiene tabla de Bonos
    Corporativos en páginas 12-13). Los informes diarios de mercados no
    tienen esa sección y se saltean.
    """
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_idx in [11, 12]:
                if page_idx >= len(pdf.pages):
                    continue
                text = pdf.pages[page_idx].extract_text() or ''
                if 'Bonos Corporativos' in text:
                    return True
    except Exception:
        pass
    return False

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
    if s.startswith('US$'):
        s = s[3:]
    if re.match(r'^-?\d+\.\d{3}$', s):
        return s.replace('.', '')
    if ',' in s:
        return s.replace('.', '').replace(',', '.')
    return s

def find_industria(text):
    """Retorna (emisor, industria) separando por industria conocida."""
    for ind in sorted(INDUSTRIAS, key=len, reverse=True):
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

    m = re.match(r'^([A-Z][A-Z0-9]{3,5})\s+', line)
    if not m:
        return None
    ticker = m.group(1)
    rest = line[m.end():]

    lm = LEY_MON_RE.search(rest)
    if not lm:
        return None

    ley    = lm.group(1)
    moneda = lm.group(2)
    head   = rest[:lm.start()].strip()
    tail   = rest[lm.end():].strip()

    cupon_m = re.search(r'(\d+[,\.]\d{3}%)', head)
    if not cupon_m:
        return None
    cupon      = cupon_m.group(1).replace(',', '.')
    pre_cupon  = head[:cupon_m.start()].strip()
    post_cupon = head[cupon_m.end():].strip()

    emisor, industria = find_industria(pre_cupon)

    fechas = re.findall(r'\d{1,2}/\d{1,2}/\d{4}', post_cupon)
    vencimiento = fechas[0] if len(fechas) > 0 else ''
    prox_cupon  = fechas[1] if len(fechas) > 1 else ''

    calificacion = post_cupon
    for f in fechas:
        calificacion = calificacion.replace(f, '', 1)
    calificacion = re.sub(r'^\s*-?\s*', '', calificacion).strip()
    calificacion = re.sub(r'\s+', ' ', calificacion).strip()

    tokens = TOKEN_RE.findall(tail)

    def g(i):
        v = _g(tokens, i, '-')
        return '' if v == '-' else v

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
        log(f"  [PDF] {total} páginas")

        for page_idx in [11, 12]:
            if page_idx >= total:
                log(f"  [!] Página {page_idx+1} no existe en el PDF")
                continue

            page = pdf.pages[page_idx]

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
    log(f"  [CSV] {CSV_OUT.name}  ({len(rows)} bonos, fecha {fecha_str})")

# ── Git commit y push ─────────────────────────────────────────────────────────

def git_commit_push(report_id):
    """Hace git add + commit + push de los archivos actualizados."""
    try:
        subprocess.run(
            ['git', 'add', 'curvas_on.csv', 'curvas_last_id.txt'],
            cwd=BASE_DIR, check=True, capture_output=True
        )
        result = subprocess.run(
            ['git', 'commit', '-m', f'update curvas_on.csv — informe PPI {report_id}'],
            cwd=BASE_DIR, capture_output=True, text=True
        )
        if result.returncode != 0:
            # Puede ser "nothing to commit" si el CSV no cambió
            log(f"  [GIT] {result.stdout.strip() or result.stderr.strip()}")
            return
        subprocess.run(
            ['git', 'push'],
            cwd=BASE_DIR, check=True, capture_output=True
        )
        log(f"  [GIT] commit y push OK (ID {report_id})")
    except subprocess.CalledProcessError as e:
        log(f"  [GIT ERROR] {e}")
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or '')
        if stderr:
            log(f"  stderr: {stderr.strip()}")

# ── Main ──────────────────────────────────────────────────────────────────────

def run(args):
    ts = date.today().strftime('%Y-%m-%d')
    log(f"\n[{ts}] === Iniciando scraper ===")

    # Modo ID fijo: prueba solo ese ID
    if args.id:
        raw = fetch_pdf(args.id)
        if raw is None:
            log("[--] ID especificado no existe o no se pudo descargar.")
            sys.exit(0)
        if not _is_cierre_pdf(raw):
            log(f"  [SKIP] ID {args.id} → informe diario (sin tabla de Bonos Corporativos en p.12-13)")
            sys.exit(0)
        log(f"\n[PARSE] ID {args.id}")
        rows = extract_rows_from_pdf(raw, debug=args.debug)
        log(f"  -> {len(rows)} bonos extraidos")
        if not rows:
            log("[!] Sin filas — el PDF pasó la validación pero no se extrajeron bonos. Verificá con --debug")
            sys.exit(1)
        save_csv(rows, args.id, date.today())
        write_last_id(args.id)
        log(f"\n[OK] Listo. Próximo ID a probar: {args.id + 1}")
        if args.commit:
            git_commit_push(args.id)
        return

    # Modo automático: itera IDs desde last_id+1, salta informes diarios,
    # para cuando hay MAX_CONSECUTIVE_404 seguidas (informe aún no publicado).
    last = read_last_id()
    if last is None:
        log("[!] No hay curvas_last_id.txt — usá --id XXXXX para arrancar")
        sys.exit(1)

    log(f"[BUSCA] desde ID {last + 1}  (last_id={last})")
    consecutive_404 = 0
    id_ = last + 1
    while True:
        raw = fetch_pdf(id_)
        if raw is None:
            consecutive_404 += 1
            if consecutive_404 >= MAX_CONSECUTIVE_404:
                log(f"[--] {MAX_CONSECUTIVE_404} IDs consecutivos sin respuesta (ID {id_ - MAX_CONSECUTIVE_404 + 1}–{id_}). Informe no publicado aún.")
                sys.exit(0)
            id_ += 1
            continue

        # Encontró un PDF — resetear contador 404
        consecutive_404 = 0

        if not _is_cierre_pdf(raw):
            log(f"  [SKIP] ID {id_} → informe diario (sin tabla de Bonos Corporativos en p.12-13)")
            id_ += 1
            continue

        # Es el informe de cierre
        log(f"\n[PARSE] ID {id_}")
        rows = extract_rows_from_pdf(raw, debug=args.debug)
        log(f"  -> {len(rows)} bonos extraidos")
        if not rows:
            log("[!] Sin filas — el PDF pasó la validación pero no se extrajeron bonos. Verificá con --debug")
            id_ += 1
            continue

        save_csv(rows, id_, date.today())
        write_last_id(id_)
        log(f"\n[OK] Listo. Próximo ID a probar: {id_ + 1}")
        if args.commit:
            git_commit_push(id_)
        return


def main():
    p = argparse.ArgumentParser(description="Scraper curvas ONs — PPI Daily")
    p.add_argument('--id',     type=int, default=None, help='ID específico del informe')
    p.add_argument('--commit', action='store_true',    help='Hace git commit y push tras guardar el CSV')
    p.add_argument('--debug',  action='store_true',    help='Muestra texto raw de páginas')
    args = p.parse_args()
    run(args)


if __name__ == '__main__':
    main()
