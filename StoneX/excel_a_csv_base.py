import pandas as pd
from pathlib import Path

EXCEL_INPUT = Path(r"C:\Users\lgullo\OneDrive - IRSACORP\Downloads\Prueba_StoneX\Deals.xlsx")
CSV_OUTPUT = Path(r"C:\Users\lgullo\OneDrive - IRSACORP\Downloads\Prueba_StoneX\deals.csv")

HOJA = "Deals V2"

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


def formato_porcentaje(x):
    """
    Convierte:
    0.06   -> 6,00%
    0.075  -> 7,50%
    6,00%  -> 6,00%
    """
    if pd.isna(x):
        return ""

    x_str = str(x).strip()

    if "%" in x_str:
        return x_str

    try:
        valor = float(x_str.replace(",", "."))
        return f"{valor * 100:.2f}%".replace(".", ",")
    except:
        return x_str


df = pd.read_excel(EXCEL_INPUT, sheet_name=HOJA, header=1)

df = df[COLUMNAS].copy()
df = df.dropna(how="all")

df["FECHA"] = pd.to_datetime(
    df["FECHA"],
    errors="coerce"
).dt.strftime("%d/%m/%Y")

df["TASA/MARGEN"] = df["TASA/MARGEN"].apply(formato_porcentaje)

df.to_csv(
    CSV_OUTPUT,
    index=False,
    encoding="utf-8-sig",
    sep=";"
)

print("CSV base generado:")
print(CSV_OUTPUT)

print("\nVista previa:")
print(df.head())

print("\nFilas:")
print(len(df))