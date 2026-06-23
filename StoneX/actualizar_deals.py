import re
import time
import datetime
import io
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
import win32com.client
from playwright.sync_api import sync_playwright
import os

try:
    import pdfplumber
    import requests as _requests
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

BASE_DIR = Path(__file__).resolve().parent
REPO_GIT = BASE_DIR.parent

CARPETA = BASE_DIR

TXT_OUTPUT = CARPETA / "texto_extraido_stonex.txt"
CSV_OUTPUT = CARPETA / "deals.csv"
CSV_DIFUSION = CARPETA / "difusion.csv"

CSV_WEB = REPO_GIT / "emisiones_obligaciones_negociables.csv"
SCREENSHOT = CARPETA / "screenshot_stonex.png"

ASUNTO_BUSCADO = "AGENDA DE EMISIONES"
REMITENTE_BUSCADO = "stonex"

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

COLUMNAS_DIFUSION = [
    "FECHA LICITACIÓN",
    "FECHA LIQUIDACIÓN",
    "EMISOR",
    "MONEDA",
    "TASA",
    "TASA/MARGEN",
    "PLAZO (en meses)",
    "CALIFICACIÓN",
]

MESES = {
    "ene": "01", "feb": "02", "mar": "03", "abr": "04",
    "may": "05", "jun": "06", "jul": "07", "ago": "08",
    "sep": "09", "oct": "10", "nov": "11", "dic": "12",
}

MESES_WEB = {
    "01": "ene", "02": "feb", "03": "mar", "04": "abr",
    "05": "may", "06": "jun", "07": "jul", "08": "ago",
    "09": "sep", "10": "oct", "11": "nov", "12": "dic",
}


def fecha_para_web(fecha):
    try:
        d, m, y = str(fecha).split("/")
        return f"{int(d)}-{MESES_WEB[m]}-{y[-2:]}"
    except:
        return fecha

DIA = r"(?:lun|mar|mié|jue|vie),\s+\d{1,2}\s+\w{3}\."

def numero_para_web(x):
    try:
        return f"{float(x):.2f}".replace(".", ",")
    except:
        return x
    
# ==========================================
# GIT PULL
# ==========================================

import subprocess

def git(args, **kwargs):
    result = subprocess.run(
        ["git"] + args,
        cwd=str(REPO_GIT),
        capture_output=True,
        text=True,
        **kwargs,
    )

    if result.stdout.strip():
        print(result.stdout.strip())

    if result.stderr.strip():
        print("[stderr]", result.stderr.strip())

    return result.returncode

    
# =========================================================
# OUTLOOK / STONEX
# =========================================================

def buscar_mail_stonex():
    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    inbox = outlook.GetDefaultFolder(6)
    messages = inbox.Items
    messages.Sort("[ReceivedTime]", True)

    for mail in messages:
        try:
            subject = str(mail.Subject or "")
            sender = str(mail.SenderEmailAddress or "")
            html = str(mail.HTMLBody or "")
            body = str(mail.Body or "")

            if ASUNTO_BUSCADO.lower() in subject.lower() and REMITENTE_BUSCADO.lower() in sender.lower():
                print("\nMAIL ENCONTRADO")
                print("Asunto:", subject)
                print("Remitente:", sender)
                print("Fecha:", mail.ReceivedTime)
                return {"subject": subject, "sender": sender, "html": html, "body": body}
        except Exception as e:
            print("Error leyendo mail:", e)

    return None


def extraer_links(html, body):
    links = []
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        links.append({"texto": a.get_text(" ", strip=True), "href": a["href"]})

    for u in re.findall(r"https?://[^\s]+", body):
        links.append({"texto": "", "href": u})

    return links


def elegir_link_stonex(links):
    for l in links:
        if "licitaciones primarias" in l["texto"].lower():
            return l["href"]

    for l in links:
        if "intel.stonex.com/article-landing" in l["href"]:
            return l["href"]

    return None


def abrir_y_extraer_texto(url):
    print("\nABRIENDO LINK STONEX:")
    print(url)

    pdf_url_capturada = None
    cookies_sesion = []
    texto_total = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            accept_downloads=True,
            viewport={"width": 1600, "height": 900},
        )
        page = context.new_page()

        # Interceptar respuestas para capturar URL del PDF embebido
        def on_response(response):
            nonlocal pdf_url_capturada
            if pdf_url_capturada:
                return
            ct = response.headers.get("content-type", "")
            if "pdf" in ct.lower() or response.url.lower().endswith(".pdf"):
                pdf_url_capturada = response.url
                print(f"  PDF detectado: {response.url}")

        page.on("response", on_response)

        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(5)

        page.screenshot(path=str(SCREENSHOT), full_page=True)

        page.mouse.wheel(0, 2000)
        time.sleep(3)
        page.mouse.wheel(0, 2000)
        time.sleep(3)

        if pdf_url_capturada:
            cookies_sesion = context.cookies()

        # Extracción de texto desde frames (sin duplicados)
        seen_fingerprints = set()
        try:
            body_text = page.locator("body").inner_text(timeout=10000)
            texto_total += "\n\n--- BODY ---\n\n" + body_text
            seen_fingerprints.add(body_text[:300])
        except Exception as e:
            print("No pude leer body:", e)

        for i, frame in enumerate(page.frames):
            try:
                t = frame.locator("body").inner_text(timeout=5000)
                fp = t[:300]
                if fp in seen_fingerprints:
                    continue
                seen_fingerprints.add(fp)
                texto_total += f"\n\n--- FRAME {i} ---\n\n{t}"
            except Exception:
                pass

        browser.close()

    # Si se capturó un PDF, parsearlo con pdfplumber (texto mucho más limpio)
    if pdf_url_capturada and HAS_PDFPLUMBER:
        try:
            cookies_dict = {c["name"]: c["value"] for c in cookies_sesion}
            resp = _requests.get(pdf_url_capturada, cookies=cookies_dict, timeout=30)
            resp.raise_for_status()
            texto_pdf = ""
            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                for pg in pdf.pages:
                    texto_pdf += (pg.extract_text() or "") + "\n"
            if "Resultados" in texto_pdf or "Licitaciones" in texto_pdf:
                print("PDF extraído con pdfplumber — texto limpio disponible")
                texto_total = texto_pdf
            else:
                print("PDF descargado pero no contiene sección esperada; usando texto de frames")
        except Exception as e:
            print(f"No pude descargar/parsear PDF ({e}); usando texto de frames")

    TXT_OUTPUT.write_text(texto_total, encoding="utf-8")
    print(f"\nTexto extraído guardado en: {TXT_OUTPUT}")

    return texto_total


# =========================================================
# HELPERS
# =========================================================

def limpiar_texto_celda(x):
    return re.sub(r"\s+", " ", str(x)).strip()


def _año_para_mes(mes_num: int) -> int:
    hoy = datetime.date.today()
    año = hoy.year
    # Si el mes parseado es enero y hoy es diciembre, la liquidación cae en el año siguiente
    if mes_num == 1 and hoy.month == 12:
        año += 1
    return año


def fecha_stonex_a_ddmmyyyy(txt):
    m = re.search(r"(\d{1,2})\s+([a-z]{3})", str(txt).lower())
    if not m:
        return ""

    dia = m.group(1).zfill(2)
    mes = MESES.get(m.group(2))

    if not mes:
        return ""

    return f"{dia}/{mes}/{_año_para_mes(int(mes))}"


def fecha_licitacion_a_fecha(txt):
    m = re.search(r"(\d{1,2})\s+([a-z]{3})", str(txt).lower())
    if not m:
        return pd.NaT

    dia = int(m.group(1))
    mes_num = int(MESES.get(m.group(2), 0))
    if not mes_num:
        return pd.NaT

    return pd.Timestamp(year=_año_para_mes(mes_num), month=mes_num, day=dia)

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

    if "A LICITAR" in c or "A INFORMAR" in c or "+MG" in c:
        return "", ""

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


def cumple_monto(moneda, vn):
    if vn is None:
        return False

    if moneda in ["USD Mep", "USD Cable", "USD Linked", "USD Int"]:
        return vn > 10

    if moneda == "ARS":
        return vn >= 10000

    return False


def extraer_resultados(texto):
    parte = texto.split("Resultados", 1)[1] if "Resultados" in texto else texto

    if "Licita hoy" in parte:
        parte = parte.split("Licita hoy", 1)[0]

    if "Operaciones en difusión" in parte:
        parte = parte.split("Operaciones en difusión", 1)[0]

    return parte


def normalizar_emisor(emisor):
    s = limpiar_texto_celda(emisor)

    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"\s*-\s*", " – ", s)
    s = s.replace("[Ley NY]", "(Ley NY)")

    s = re.sub(
        r"\s*\(Integra en efectivo y/o en especie\)",
        "",
        s,
        flags=re.I
    )

    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*–\s*–\s*", " – ", s)

    # Si termina en clase romana y NO tiene guion, agregarlo.
    # Evita romper casos como "Tarjeta Naranja I LXVII".
    m = re.search(r"^(.*)\s+([IVXLCDM]+)$", s)
    if m and " – " not in s:
        base = m.group(1).strip()
        clase = m.group(2).strip()
        prev = base.split()[-1] if base.split() else ""
        if prev not in {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}:
            s = f"{base} – {clase}"

    return s


def nombre_desde_prefix(prefix):
    p = limpiar_texto_celda(prefix)

    # BONAR
    m_bonar = re.search(r"(BONAR\s+\d{4}).*?(AO\d+)", p)
    if m_bonar:
        return f"{m_bonar.group(1)} ({m_bonar.group(2)})"

    # Limpieza inicial
    p = re.sub(r"^\[OFERTA DE CANJE\]\s*", "", p, flags=re.I)
    p = re.sub(r"^ON\s+", "", p, flags=re.I)

    # Normalizar Ley NY
    p = p.replace("[Ley NY]", "(Ley NY)")

    # Sacar aclaraciones largas
    p = re.sub(
        r"\s*\(Integra en efectivo y/o en especie\)",
        "",
        p,
        flags=re.I
    )

    # Sacar aclaraciones largas que no queremos en el nombre
    p = re.sub(r"\s*\(Pyme\)", "", p, flags=re.I)

    # Normalizar guiones
    p = p.replace("—", "-").replace("–", "-")
    p = re.sub(r"\s*-\s*", " – ", p)

    # Limpieza final
    p = re.sub(r"\s+", " ", p).strip()

    return p


def fila_excluida(row_text):
    t = row_text.lower()

    if "ff " in t or "fideicomiso" in t:
        return True
    if "letra del tesoro" in t or "bono del tesoro" in t:
        return True
    if "a informar" in t:
        return True
    if "a licitar" in t:
        return True

    return False


# =========================================================
# PARSER GENERAL
# =========================================================

def parsear_resultados_generico(resultados):
    filas = []

    texto = limpiar_texto_celda(resultados)

    patron_fila = re.compile(
        rf"(?P<lic>{DIA})\s+"
        rf"(?P<body>(?:ON|BONAR|\[OFERTA DE CANJE\]\s+ON).*?)\s+"
        rf"(?P<tipo>Tasa|Margen|Precio|Book building|Por Adhesión)\s+"
        rf"(?P<liq>{DIA})",
        re.DOTALL
    )

    patron_detalle = re.compile(
        r"(?P<prefix>(?:ON|BONAR).*?)\s+"
        r"-?(?P<moneda>USD\s+Mep|USD\s+Cable|USD\s+Linked|USD\s+linked|ARS)\s+"
        r"(?P<vn>(?:USD|\$)\s*[\d\.]+)"
        r"(?:\s+\([^)]*\))?\s+"
        r"(?P<cupon>TAMAR\+\d+(?:,\d+)?%|T\+\d+(?:,\d+)?|\d{1,2},\d{2,3}%|0,00%)\s+"
        r"(?P<duration>[\d,]+)\s+"
        r"(?P<maturity>\d+)\s+"
        r"(?P<ultima>\d{2}/\d{2}/\d{4})\s+"
        r"(?P<rating>.*)$"
    )

    for fila in patron_fila.finditer(texto):
        row_text = limpiar_texto_celda(fila.group(0))
        body = limpiar_texto_celda(fila.group("body"))

        matches = list(patron_detalle.finditer(body))

        if not matches:
            continue

        for detalle in matches:

            prefix = detalle.group("prefix")

            if " ON " in prefix:
                prefix = "ON " + prefix.split(" ON ")[-1]

            if " BONAR " in prefix:
                prefix = "BONAR " + prefix.split(" BONAR ")[-1]

            emisor = nombre_desde_prefix(prefix)

            moneda = normalizar_moneda(
                detalle.group("moneda"),
                emisor
            )

            vn = limpiar_vn(
                detalle.group("vn")
            )

            if not cumple_monto(moneda, vn):
                continue

            tasa, margen = tasa_y_margen(
                detalle.group("cupon")
            )

            if not tasa or margen == "":
                continue

            rating = limpiar_texto_celda(
                detalle.group("rating")
            )

            rating = re.sub(
                r"\s+(Tasa|Margen|Precio|Book building|Por Adhesión)$",
                "",
                rating
            ).strip()

            filas.append({
                "FECHA": fecha_stonex_a_ddmmyyyy(fila.group("liq")),
                "EMISOR": emisor,
                "MONEDA": moneda,
                "TASA": tasa,
                "TASA/MARGEN": margen,
                "PLAZO (en meses)": plazo_meses(
                    detalle.group("maturity")
                ),
                "VN": vn,
                "CALIFICACIÓN": rating,
            })

    return filas


# =========================================================
# CSV
# =========================================================

def normalizar_y_deduplicar(df):
    df = df.copy()

    df = df[COLUMNAS].copy()

    df["FECHA"] = pd.to_datetime(
        df["FECHA"],
        dayfirst=True,
        errors="coerce"
    ).dt.strftime("%d/%m/%Y")

    for c in ["EMISOR", "MONEDA", "TASA", "TASA/MARGEN", "CALIFICACIÓN"]:
        df[c] = (
            df[c]
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

    df["EMISOR"] = df["EMISOR"].apply(normalizar_emisor)

    # Borra filas mal parseadas de pruebas anteriores
    df = df[
    ~df["EMISOR"].str.contains("Tasa mié|Tasa mar|Tasa lun", regex=True, na=False)
]
    df = df[
    ~df["EMISOR"].str.startswith("–", na=False)
]
    df["PLAZO (en meses)"] = (
        pd.to_numeric(df["PLAZO (en meses)"], errors="coerce")
        .round(0)
    )

    df["VN"] = (
        pd.to_numeric(df["VN"], errors="coerce")
        .round(1)
    )

    key_cols = [
        "FECHA",
        "EMISOR",
        "MONEDA",
        "TASA",
        "TASA/MARGEN",
        "PLAZO (en meses)",
        "VN",
    ]

    antes = len(df)
    df = df.drop_duplicates(subset=key_cols, keep="first")
    despues = len(df)

    if antes != despues:
        print(f"\nDuplicados eliminados: {antes - despues}")

    return df


def crear_key(df):
    return (
        df["FECHA"].astype(str) + "|" +
        df["EMISOR"].astype(str) + "|" +
        df["MONEDA"].astype(str) + "|" +
        df["TASA/MARGEN"].astype(str) + "|" +
        df["PLAZO (en meses)"].astype(str) + "|" +
        df["VN"].astype(str)
    )


def actualizar_csv(texto):
    resultados = extraer_resultados(texto)

    filas = parsear_resultados_generico(resultados)
    df_nuevo = pd.DataFrame(filas, columns=COLUMNAS)

    if CSV_OUTPUT.exists():
        df_existente = pd.read_csv(CSV_OUTPUT, sep=";")
    else:
        df_existente = pd.DataFrame(columns=COLUMNAS)

    df_existente = normalizar_y_deduplicar(df_existente)

    if df_nuevo.empty:
        print("\nNo se detectaron operaciones nuevas en Resultados.")
        df_existente.to_csv(CSV_OUTPUT, index=False, encoding="utf-8-sig", sep=";")
        return

    df_nuevo = normalizar_y_deduplicar(df_nuevo)

    df_existente["KEY"] = crear_key(df_existente)
    df_nuevo["KEY"] = crear_key(df_nuevo)

    df_agregar = df_nuevo[
        ~df_nuevo["KEY"].isin(set(df_existente["KEY"]))
    ]

    final = pd.concat([
        df_existente.drop(columns=["KEY"], errors="ignore"),
        df_agregar.drop(columns=["KEY"], errors="ignore")
    ], ignore_index=True)

    final = normalizar_y_deduplicar(final)

    final["FECHA_ORD"] = pd.to_datetime(
        final["FECHA"],
        format="%d/%m/%Y",
        errors="coerce"
    )

    final = final.sort_values(
    ["FECHA_ORD", "EMISOR"],
    ascending=[False, True]
    ).drop(columns=["FECHA_ORD"])

    # ==========================================
    # BACKUP CSV
    # ==========================================

    final.to_csv(
        CSV_OUTPUT,
        index=False,
        encoding="utf-8-sig",
        sep=";"
    )


    # ==========================================
    # CSV PARA WEB
    # ==========================================

    final_web = final.copy()

    final_web["FECHA"] = final_web["FECHA"].apply(
        fecha_para_web
    )

    final_web["VN"] = final_web["VN"].apply(
        numero_para_web
    )

    final_web["PLAZO (en meses)"] = final_web["PLAZO (en meses)"].apply(
        lambda x: str(int(float(x))) if pd.notna(x) else ""
    )

    final_web.to_csv(
        CSV_WEB,
        index=False,
        encoding="utf-8-sig"
    )
    
    print("\n====================================")
    print("CSV actualizado")
    print("Backup:", CSV_OUTPUT)
    print("Web:", CSV_WEB)
    print("====================================")

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

def actualizar_difusion(texto):

    print("\n======================")
    print("ACTUALIZANDO DIFUSION")
    print("======================")

    if "Operaciones en difusión" not in texto:
        print("No encontré sección difusión")

        if CSV_DIFUSION.exists():

            final = pd.read_csv(
                CSV_DIFUSION,
                sep=";",
                dtype=str
            ).fillna("")

            hoy = pd.Timestamp.today().normalize()

            fechas_lic = final[
                "FECHA LICITACIÓN"
            ].apply(
                fecha_licitacion_a_fecha
            )

            final = final[
                fechas_lic.isna()
                |
                (fechas_lic >= hoy)
            ]

            final.to_csv(
                CSV_DIFUSION,
                index=False,
                encoding="utf-8-sig",
                sep=";"
            )

            print(
                f"Difusión depurada. Total filas: {len(final)}"
            )

        return

    bloque = texto.split(
        "Operaciones en difusión",
        1
    )[1]

    patron = re.compile(
        rf"(?P<fecha_lic>{DIA})\s+"
        rf"(?P<reg>(?:ON |Títulos de Deuda).*?)\s+"
        rf"(?P<tipo>Tasa|Margen|Book building)\s+"
        rf"(?P<fecha_liq>{DIA}|A informar)",
        re.DOTALL
    )

    filas = []

    for m in patron.finditer(bloque):

        reg = m.group("reg")
        reg_limpio = limpiar_texto_celda(reg)

        fecha_lic = m.group("fecha_lic")
        fecha_liq = m.group("fecha_liq")

        # -------------------------
        # MONEDA
        # -------------------------

        moneda = ""

        if "USD Mep" in reg:
            moneda = "USD Mep"

        elif "USD Cable" in reg:
            moneda = "USD Cable"

        elif "USD Linked" in reg:
            moneda = "USD Linked"

        elif "ARS" in reg or "-ARS" in reg:
            moneda = "ARS"

        if "Ley NY" in reg:
            moneda = "USD Int"

        # -------------------------
        # EMISOR
        # -------------------------

        lineas = [
            x.strip()
            for x in reg.splitlines()
            if x.strip()
        ]

        partes = []

        for l in lineas:

            if l in [
                "USD Mep",
                "USD Cable",
                "USD Linked",
                "ARS",
                "-ARS"
            ]:
                break

            if re.fullmatch(r"[IVXLCDM]+", l):
                continue

            if re.fullmatch(r"\d+", l):
                continue

            if re.fullmatch(r"\d{2}/\d{2}/\d{4}", l):
                break

            m_usd = re.split(
                r"(?:-USD|\$)",
                l,
                maxsplit=1
            )

            if len(m_usd) > 1:

                texto_limpio = m_usd[0].strip()

                if texto_limpio:
                    partes.append(texto_limpio)

                break

            if re.search(r"^(USD|\$)\s*[\d\.]+", l):
                break

            if l in ["TAMAR+Mg", "A licitar"]:
                break

            partes.append(l)

        emisor = " ".join(partes)

        emisor = re.sub(r"^ON\s+", "", emisor, flags=re.I)
        emisor = re.sub(r"^Títulos de Deuda del\s+", "", emisor, flags=re.I)
        emisor = re.sub(r"\(Integra.*", "", emisor, flags=re.I)
        emisor = re.sub(r"\(Pyme\)", "", emisor, flags=re.I)
        emisor = re.sub(r"\[Ley NY\]", "", emisor)
        emisor = re.sub(r"\[Bono SVS\]", "", emisor)
        emisor = re.sub(r"Garantizadas?\s+", "", emisor, flags=re.I)
        emisor = re.sub(r"-(?:[IVXLCDM]+)$", "", emisor)

        emisor = limpiar_texto_celda(emisor)


        # -------------------------
        # PLAZO
        # -------------------------

        plazo = ""

        m_plazo = re.search(
            r"\s(\d{3,4})\s+\d{2}/\d{2}/\d{4}",
            reg_limpio
        )

        if m_plazo:
            plazo = plazo_meses(
                m_plazo.group(1)
            )

        if "Venc. entre los 8 y 10 años" in reg:
            plazo = 108

        # -------------------------
        # TASA
        # -------------------------

        tasa = (
            "TAMAR+Mg"
            if moneda == "ARS"
            else "Fija"
        )

        # -------------------------
        # RATING
        # -------------------------

        rating = ""

        m_rating = re.search(
            r"(AAA.*?\)|AA.*?\)|A1\+.*?\)|A-1.*?\)|A1.*?\)|SC|A informar)",
            reg_limpio
        )

        if m_rating:
            rating = m_rating.group(1)

        filas.append({
            "FECHA LICITACIÓN": fecha_lic,
            "FECHA LIQUIDACIÓN": fecha_liq,
            "EMISOR": emisor,
            "MONEDA": moneda,
            "TASA": tasa,
            "TASA/MARGEN": "A licitar",
            "PLAZO (en meses)": plazo,
            "CALIFICACIÓN": rating
        })

    df_nuevo = pd.DataFrame(
        filas,
        columns=COLUMNAS_DIFUSION
    )

    if CSV_DIFUSION.exists():
        df_existente = pd.read_csv(
            CSV_DIFUSION,
            sep=";"
        )
    else:
        df_existente = pd.DataFrame(
            columns=COLUMNAS_DIFUSION
        )

    df_existente = df_existente.fillna("")
    df_nuevo = df_nuevo.fillna("")

    df_existente["KEY"] = (
        df_existente["FECHA LICITACIÓN"].astype(str)
        + "|"
        + df_existente["EMISOR"].astype(str)
        + "|"
        + df_existente["MONEDA"].astype(str)
        + "|"
        + df_existente["PLAZO (en meses)"].astype(str)
    )

    df_nuevo["KEY"] = (
        df_nuevo["FECHA LICITACIÓN"].astype(str)
        + "|"
        + df_nuevo["EMISOR"].astype(str)
        + "|"
        + df_nuevo["MONEDA"].astype(str)
        + "|"
        + df_nuevo["PLAZO (en meses)"].astype(str)
    )

    df_agregar = df_nuevo[
        ~df_nuevo["KEY"].isin(
            set(df_existente["KEY"])
        )
    ]

    final = pd.concat([
        df_existente.drop(columns=["KEY"], errors="ignore"),
        df_agregar.drop(columns=["KEY"], errors="ignore")
    ])

    final["KEY"] = (
    final["FECHA LICITACIÓN"].fillna("").astype(str)
    + "|"
    + final["EMISOR"].fillna("").astype(str)
    + "|"
    + final["MONEDA"].fillna("").astype(str)
    + "|"
    + final["PLAZO (en meses)"].fillna("").astype(str)
    )

    final = final.drop_duplicates(
        subset=["KEY"],
        keep="first"
    ).drop(columns=["KEY"])

    # ==========================================
    # ELIMINAR LICITACIONES YA PASADAS
    # ==========================================

    hoy = pd.Timestamp.today().normalize()

    fechas_lic = final[
        "FECHA LICITACIÓN"
    ].apply(
        fecha_licitacion_a_fecha
    )

    print("\nHOY:", hoy)

    print("\nFECHAS LIC:")
    print(
        pd.DataFrame({
            "texto": final["FECHA LICITACIÓN"],
            "fecha": fechas_lic
        })
    )

    final = final[
        fechas_lic.isna()
        |
        (fechas_lic >= hoy)
    ]

    final.to_csv(
        CSV_DIFUSION,
        index=False,
        encoding="utf-8-sig",
        sep=";"
    )

    print(
        f"Difusión actualizada. Total filas: {len(final)}"
    )

# =========================================================
# MAIN
# =========================================================

def main():
    CARPETA.mkdir(parents=True, exist_ok=True)

    mail = buscar_mail_stonex()

    if not mail:
        print("\nNo encontré mail de StoneX.")
        return

    links = extraer_links(mail["html"], mail["body"])
    link_stonex = elegir_link_stonex(links)

    if not link_stonex:
        print("\nNo encontré link de Licitaciones Primarias.")
        return

    texto = abrir_y_extraer_texto(link_stonex)

    actualizar_csv(texto)
    actualizar_difusion(texto)

    # ==========================================
    # GIT PUSH
    # ==========================================

    import subprocess

    print("\nSubiendo cambios a GitHub...")
    print(f"Repo: {REPO_GIT}")

    # Agregar archivos que queremos subir
    rc_add = git([
        "add",
        str(CSV_WEB),
        str(CSV_OUTPUT),
        str(CSV_DIFUSION)
    ])

    if rc_add != 0:
        print("Error en git add")
        return

    # Verificar si hay algo para commitear
    status = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(REPO_GIT),
        capture_output=True,
        text=True,
    )

    if not status.stdout.strip():
        print("Sin cambios para commitear.")
        return

    # Commit
    rc_commit = git(["commit", "-m", "update deals automatico"])
    if rc_commit != 0:
        print("Error en git commit")
        return
    
    # Limpiar archivos temporales para que no bloqueen el pull
    git(["restore", str(SCREENSHOT)])
    git(["restore", str(TXT_OUTPUT)])

    # Push
    rc_push = git(["push", "origin", "main"])
    if rc_push != 0:
        print("Error en git push")
    else:
        print("Push exitoso.")

if __name__ == "__main__":
    main()