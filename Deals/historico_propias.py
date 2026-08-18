#!/usr/bin/env python3
"""
historico_propias.py — Recorre los últimos N informes diarios IAMC disponibles
y extrae la serie histórica de Precio_Clean y YTM para TODAS las ONs propias
(IRSA: tickers IRC*, Cresud: tickers CS<dígito>*).

Genera/reescribe: curvas_propias_historico.csv (no toca curvas_on.csv, que
siempre refleja solo el informe más reciente para el resto del dashboard).

Uso:
    python historico_propias.py              # últimos 30 informes disponibles
    python historico_propias.py --n 15        # últimos 15
"""

import argparse
import csv
import re
from pathlib import Path

import scraper_curvas as sc

BASE_DIR = Path(__file__).parent
OUT_CSV = BASE_DIR / "curvas_propias_historico.csv"

FIELDNAMES = ["Fecha", "Ticker", "Emisor", "Vencimiento", "Precio_Clean", "YTM", "CY", "DM"]


def _is_propia(ticker):
    return ticker.startswith("IRC") or re.match(r"^CS\d", ticker)


def run(n):
    entries = sc._get_all_listing_dates()  # más reciente primero
    entries = entries[:n]
    print(f"[INFO] {len(entries)} informes a procesar")

    results = []
    for i, (fecha_str, informe_url) in enumerate(entries, 1):
        print(f"[{i}/{len(entries)}] {fecha_str} ...")
        pdf_url = sc.get_pdf_url(informe_url)
        if not pdf_url:
            print("   [!] sin URL de PDF, salteando")
            continue
        pdf_bytes = sc.fetch_pdf(pdf_url)
        if not pdf_bytes:
            print("   [!] no se pudo descargar el PDF, salteando")
            continue

        rows = sc.extract_rows_from_pdf(pdf_bytes)
        found = [r for r in rows if _is_propia(r["Ticker"])]
        if not found:
            print("   [!] sin ONs propias en este informe")
        for r in found:
            results.append({
                "Fecha": fecha_str,
                "Ticker": r["Ticker"],
                "Emisor": "IRSA" if r["Ticker"].startswith("IRC") else "Cresud",
                "Vencimiento": r["Vencimiento"],
                "Precio_Clean": r["Precio_Clean"],
                "YTM": r["YTM"],
                "CY": r["CY"],
                "DM": r["DM"],
            })
            print(f"   [OK] {r['Ticker']}: Precio={r['Precio_Clean']} YTM={r['YTM']}")

    results.sort(key=lambda r: (r["Ticker"], r["Fecha"]))

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(results)

    print(f"\n[OK] {len(results)} filas guardadas en {OUT_CSV.name}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=30, help="Cantidad de informes recientes a procesar")
    args = p.parse_args()
    run(args.n)


if __name__ == "__main__":
    main()