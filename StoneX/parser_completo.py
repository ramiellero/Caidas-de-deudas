import re
import pandas as pd
from pathlib import Path

CARPETA = Path(r"C:\Users\lgullo\OneDrive - IRSACORP\Downloads\Prueba_StoneX")
TXT_INPUT = CARPETA / "texto_extraido_stonex.txt"
CSV_OUTPUT = CARPETA / "deals.csv"

COLUMNAS = [
    "FECHA",
    "EMISOR",
    "MONEDA",
    "TASA",
    "TASA/MARGEN",
    "PLAZO (en meses)",
    "VN",
    "CALIFICACIÓN",
]

MESES = {
    "ene": "01", "feb": "02", "mar": "03", "abr": "04",
    "may": "05", "jun": "06", "jul": "07", "ago": "08",
    "sep": "09", "oct": "10", "nov": "11", "dic": "12",
}


def fecha_stonex_a_ddmmyyyy(txt):
    m = re.search(r"(\d{1,2})\s+([a-z]{3})", str(txt).lower())
    if not m:
        return ""

    dia = m.group(1).zfill(2)
    mes = MESES.get(m.group(2))

    if not mes:
        return ""

    return f"{dia}/{mes}/2026"


def limpiar_vn(txt):
    nums = re.findall(r"\d[\d\.]*", str(txt))

    if not nums:
        return None

    val = float(nums[0].replace(".", ""))

    if val > 1_000_000:
        return round(val / 1_000_000, 1)

    return round(val, 1)


def plazo_meses(maturity):
    try:
        return round(int(maturity) / 30.44)
    except:
        return None


def normalizar_moneda(moneda, emisor=""):
    t = f"{moneda} {emisor}".lower()

    if "ley ny" in t:
        return "USD Int"
    if "usd mep" in t:
        return "USD Mep"
    if "usd cable" in t:
        return "USD Cable"
    if "usd linked" in t:
        return "USD Linked"
    if "ars" in t:
        return "ARS"

    return str(moneda).strip()


def tasa_y_margen(cupon):
    c = str(cupon).upper().strip()

    if "TAMAR" in c or "T+" in c:
        m = re.search(r"(?:TAMAR\+|T\+)(\d+(?:,\d+)?)", c)

        if m:
            valor = float(m.group(1).replace(",", "."))
            margen = f"{valor:.2f}%".replace(".", ",")
        else:
            margen = ""

        return "TAMAR", margen

    m = re.search(r"(\d+(?:,\d+)?)%", c)

    if m:
        valor = float(m.group(1).replace(",", "."))
        tasa = f"{valor:.2f}%".replace(".", ",")
        return "Fija", tasa

    return "Fija", ""


def extraer_resultados(texto):
    parte = texto.split("Resultados", 1)[1] if "Resultados" in texto else texto

    if "Licita hoy" in parte:
        parte = parte.split("Licita hoy", 1)[0]

    return parte


def cumple_monto(moneda, vn):
    if vn is None:
        return False

    if moneda in ["USD Mep", "USD Cable", "USD Linked", "USD Int"]:
        return vn > 10

    if moneda == "ARS":
        return vn >= 10000

    return False


def parsear_bonar(resultados):
    filas = []

    patron = re.compile(
        r"(BONAR\s+\d{4}).*?"
        r"(AO\d+).*?"
        r"(-USD\s+Mep).*?"
        r"(USD\s+[\d\.]+).*?"
        r"(\d{1,2},\d{2}%).*?"
        r"(\d+)\s+"
        r"(\d{2}/\d{2}/\d{4}).*?"
        r"(SC).*?"
        r"(vie,\s+\d{1,2}\s+\w{3}\.)",
        re.DOTALL
    )

    for m in patron.finditer(resultados):
        tasa, margen = tasa_y_margen(m.group(5))

        filas.append({
            "FECHA": fecha_stonex_a_ddmmyyyy(m.group(9)),
            "EMISOR": f"{m.group(1)} ({m.group(2)})",
            "MONEDA": normalizar_moneda(m.group(3)),
            "TASA": tasa,
            "TASA/MARGEN": margen,
            "PLAZO (en meses)": plazo_meses(m.group(6)),
            "VN": limpiar_vn(m.group(4)),
            "CALIFICACIÓN": m.group(8),
        })

    return filas


def parsear_on_manual(resultados):
    filas = []

    # Mercado Pago clase 4, 5 y 6
    patron_mp = re.compile(
        r"ON Mercado Pago\s+-\s*(?P<clase>\d+).*?"
        r"(?P<moneda>USD\s+Mep|ARS).*?"
        r"(?P<vn>(?:USD|\$)\s+[\d\.]+).*?"
        r"(?P<cupon>\d{1,2},\d{2}%|TAMAR\+\d+(?:,\d+)?%).*?"
        r"(?P<maturity>\d+)\s+"
        r"(?P<ultima>\d{2}/\d{2}/\d{4})\s+"
        r"(?P<rating>A1\+\s+\(Fix SCR\)).*?"
        r"(?P<liq>lun,\s+\d{1,2}\s+\w{3}\.)",
        re.DOTALL
    )

    for m in patron_mp.finditer(resultados):
        moneda = normalizar_moneda(m.group("moneda"))
        vn = limpiar_vn(m.group("vn"))

        if not cumple_monto(moneda, vn):
            continue

        tasa, margen = tasa_y_margen(m.group("cupon"))

        filas.append({
            "FECHA": fecha_stonex_a_ddmmyyyy(m.group("liq")),
            "EMISOR": f"Mercado Pago – {m.group('clase')}",
            "MONEDA": moneda,
            "TASA": tasa,
            "TASA/MARGEN": margen,
            "PLAZO (en meses)": plazo_meses(m.group("maturity")),
            "VN": vn,
            "CALIFICACIÓN": m.group("rating").replace("\n", " ").strip(),
        })

    # Pampa Energía Ley NY
    patron_pampa = re.compile(
        r"ON Pampa Energía\s+\[Ley NY\].*?"
        r"(?P<clase>26\s+Adicionales).*?"
        r"(?P<moneda>USD\s+Cable).*?"
        r"(?P<vn>USD\s+[\d\.]+).*?"
        r"(?P<cupon>\d{1,2},\d{3}%).*?"
        r"(?P<maturity>\d+)\s+"
        r"(?P<ultima>\d{2}/\d{2}/\d{4})\s+"
        r"(?P<rating>B-\s+\(S&P\)\s*/\s*B\+\s+\(Fitch Ratings\)).*?"
        r"(?P<liq>jue,\s+\d{1,2}\s+\w{3}\.)",
        re.DOTALL
    )

    for m in patron_pampa.finditer(resultados):
        moneda = normalizar_moneda(m.group("moneda"), "Ley NY")
        vn = limpiar_vn(m.group("vn"))

        if not cumple_monto(moneda, vn):
            continue

        tasa, margen = tasa_y_margen(m.group("cupon"))

        filas.append({
            "FECHA": fecha_stonex_a_ddmmyyyy(m.group("liq")),
            "EMISOR": "Pampa Energía (Ley NY) – 26 Adicionales",
            "MONEDA": moneda,
            "TASA": tasa,
            "TASA/MARGEN": margen,
            "PLAZO (en meses)": plazo_meses(m.group("maturity")),
            "VN": vn,
            "CALIFICACIÓN": m.group("rating").replace("\n", " ").strip(),
        })

    return filas


def crear_key(df):
    return (
        df["FECHA"].astype(str) + "|" +
        df["EMISOR"].astype(str) + "|" +
        df["MONEDA"].astype(str) + "|" +
        df["TASA/MARGEN"].astype(str) + "|" +
        df["PLAZO (en meses)"].astype(str) + "|" +
        df["VN"].astype(str)
    )


def main():
    texto = TXT_INPUT.read_text(encoding="utf-8", errors="ignore")
    resultados = extraer_resultados(texto)

    filas = []
    filas.extend(parsear_bonar(resultados))
    filas.extend(parsear_on_manual(resultados))

    df_nuevo = pd.DataFrame(filas, columns=COLUMNAS)

    if CSV_OUTPUT.exists():
        df_existente = pd.read_csv(CSV_OUTPUT, sep=";")
    else:
        df_existente = pd.DataFrame(columns=COLUMNAS)

    df_existente["KEY"] = crear_key(df_existente)
    df_nuevo["KEY"] = crear_key(df_nuevo)

    keys_existentes = set(df_existente["KEY"])

    df_agregar = df_nuevo[
        ~df_nuevo["KEY"].isin(keys_existentes)
    ]

    final = pd.concat([
        df_existente.drop(columns=["KEY"], errors="ignore"),
        df_agregar.drop(columns=["KEY"], errors="ignore")
    ], ignore_index=True)

    final["FECHA_ORD"] = pd.to_datetime(
        final["FECHA"],
        format="%d/%m/%Y",
        errors="coerce"
    )

    final = final.sort_values(
        "FECHA_ORD",
        ascending=False
    ).drop(columns=["FECHA_ORD"])

    final.to_csv(
        CSV_OUTPUT,
        index=False,
        encoding="utf-8-sig",
        sep=";"
    )

    print("\nDetectadas en reporte:")
    print(len(df_nuevo))

    print("\nNuevas emisiones agregadas:")
    print(len(df_agregar))

    print("\nYa existentes:")
    print(len(df_nuevo) - len(df_agregar))

    print("\nNuevas filas:")
    print(df_agregar.drop(columns=["KEY"], errors="ignore"))

    print("\nTotal filas:")
    print(len(final))


if __name__ == "__main__":
    main()