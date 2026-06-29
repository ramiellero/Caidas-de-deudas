#!/usr/bin/env python3
"""
enrich_curvas_moneda.py — Enriquecimiento one-time de curvas_on.csv con columna Moneda.

Reglas:
  - Ley NY  → Moneda = 'USD Int'
  - Ley Arg → match contra emisiones_obligaciones_negociables.csv
              por cupón (±0.2%) + vencimiento computado FECHA+PLAZO (±60 días)

Outputs:
  - curvas_moneda_lookup.csv   (Ticker, Moneda) — lookup persistente; editar manualmente
  - curvas_on.csv              actualizado con columna Moneda

Uso:
    python enrich_curvas_moneda.py
"""

import calendar
import csv
from datetime import date
from pathlib import Path

BASE_DIR      = Path(__file__).parent
CURVAS_CSV    = BASE_DIR / "curvas_on.csv"
EMISIONES_CSV = BASE_DIR / "emisiones_obligaciones_negociables.csv"
LOOKUP_CSV    = BASE_DIR / "curvas_moneda_lookup.csv"

MES_ES = {
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
}
MONTHS_EN = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

# Normalización de MONEDA en emisiones (mismo criterio que el frontend)
MONEDA_NORM = {
    'USD':        'USD Mep',
    'USD Mep':    'USD Mep',
    'USD Cable':  'USD Cable',
    'USD Int':    'USD Int',
    'USD - Int':  'USD Int',
    'USD - CCL':  'USD Cable',
    'USD - Linked': 'USD Linked',
    'USD Linked': 'USD Linked',
}

COUPON_TOL = 0.2   # ±0.2%
DATE_TOL   = 60    # ±60 días


def add_months(d, months):
    """Suma months meses a una fecha sin dependencias externas."""
    total = d.month - 1 + months
    year  = d.year + total // 12
    month = total % 12 + 1
    day   = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def parse_emisiones_date(s):
    """'14-abr-26' → date(2026, 4, 14)"""
    parts = s.strip().lower().split('-')
    if len(parts) != 3:
        return None
    try:
        day   = int(parts[0])
        month = MES_ES.get(parts[1][:3])
        yr    = int(parts[2])
        year  = 2000 + yr if yr < 100 else yr
        return date(year, month, day) if month else None
    except (ValueError, TypeError):
        return None


def parse_curvas_date(s):
    """'17-Jan-2034' → date(2034, 1, 17)"""
    parts = s.strip().split('-')
    if len(parts) != 3:
        return None
    try:
        day   = int(parts[0])
        month = MONTHS_EN.get(parts[1].lower())
        year  = int(parts[2])
        return date(year, month, day) if month else None
    except (ValueError, TypeError):
        return None


def parse_pct(s):
    """'7,55%' o '7.55%' → 7.55"""
    try:
        return float(s.strip().replace('%', '').replace(',', '.'))
    except (ValueError, AttributeError):
        return None


def load_emisiones():
    """
    Carga emisiones USD del CSV.
    Retorna lista de dicts: {maturity, coupon, moneda, emisor}.
    """
    entries = []
    with open(EMISIONES_CSV, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            moneda_raw = row['MONEDA'].strip()
            moneda = MONEDA_NORM.get(moneda_raw)
            if moneda is None:
                continue  # ARS, UVA, resultado pendiente, etc.

            try:
                plazo = int(row['PLAZO (en meses)'].strip())
            except (ValueError, TypeError):
                continue

            fecha = parse_emisiones_date(row['FECHA'])
            if fecha is None:
                continue

            coupon = parse_pct(row['TASA/MARGEN'])
            if coupon is None:
                continue

            entries.append({
                'maturity': add_months(fecha, plazo),
                'coupon':   coupon,
                'moneda':   moneda,
                'emisor':   row['EMISOR'].strip(),
            })
    return entries


def match_moneda(cupon_raw, vto_raw, emisiones):
    """
    Busca la moneda de un bono Ley Arg cruzando cupón y vencimiento.
    Retorna string de moneda o '' si no hay match.
    """
    cupon = parse_pct(str(cupon_raw)) if cupon_raw else None
    vto   = parse_curvas_date(str(vto_raw)) if vto_raw else None

    if cupon is None or vto is None:
        return ''

    candidates = []
    for e in emisiones:
        coupon_diff = abs(e['coupon'] - cupon)
        date_diff   = abs((e['maturity'] - vto).days)
        if coupon_diff <= COUPON_TOL and date_diff <= DATE_TOL:
            candidates.append((date_diff, coupon_diff, e))

    if not candidates:
        return ''

    candidates.sort(key=lambda x: (x[0], x[1]))

    # Avisar si hay ambigüedad (dos candidatos muy distintos)
    if len(candidates) >= 2:
        top2_monedas = {c[2]['moneda'] for c in candidates[:2]}
        if len(top2_monedas) > 1:
            print(f"    [!] Ambiguedad: {candidates[0][2]['emisor']} vs "
                  f"{candidates[1][2]['emisor']} - se elige el mas cercano")

    return candidates[0][2]['moneda']


def main():
    print("Cargando emisiones USD...")
    emisiones = load_emisiones()
    print(f"  {len(emisiones)} emisiones USD cargadas")

    print("\nCargando curvas_on.csv...")
    with open(CURVAS_CSV, encoding='utf-8') as f:
        reader    = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows      = [dict(r) for r in reader]
    print(f"  {len(rows)} bonos")

    # Insertar columna Moneda tras Ley (si no existe ya)
    if 'Moneda' not in fieldnames:
        idx = fieldnames.index('Ley') + 1
        fieldnames.insert(idx, 'Moneda')

    print("\nAsignando moneda...")
    matched_ny  = 0
    matched_arg = 0
    unmatched   = []

    for row in rows:
        ley    = row.get('Ley', '').strip()
        ticker = row.get('Ticker', '')

        if ley == 'NY':
            row['Moneda'] = 'USD Int'
            matched_ny += 1
        elif ley == 'Arg':
            moneda = match_moneda(row.get('Cupon'), row.get('Vencimiento'), emisiones)
            row['Moneda'] = moneda
            if moneda:
                matched_arg += 1
                print(f"  {ticker:8s}  {row.get('Cupon',''):5s}%  {row.get('Vencimiento',''):13s}  ->  {moneda}")
            else:
                row['Moneda'] = ''
                unmatched.append(ticker)
        else:
            row['Moneda'] = ''

    # Guardar lookup persistente
    with open(LOOKUP_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Ticker', 'Moneda'])
        for row in rows:
            w.writerow([row['Ticker'], row.get('Moneda', '')])
    print(f"\n[OK] Lookup guardado: {LOOKUP_CSV.name}")

    # Guardar curvas_on.csv enriquecido
    with open(CURVAS_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"[OK] curvas_on.csv actualizado con columna Moneda")

    total_matched = matched_ny + matched_arg
    total         = len(rows)
    print(f"\nResumen:")
    print(f"  NY  matched : {matched_ny}")
    print(f"  Arg matched : {matched_arg}")
    print(f"  Total       : {total_matched}/{total} ({100*total_matched//total}%)")
    if unmatched:
        print(f"\n  Sin match (Ley Arg) — completar manualmente en {LOOKUP_CSV.name}:")
        for t in unmatched:
            print(f"    {t}")


if __name__ == '__main__':
    main()
