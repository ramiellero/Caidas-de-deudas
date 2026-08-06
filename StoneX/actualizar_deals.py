import re
import time
import datetime
import io
import sys
import html as _html
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
import win32com.client
from playwright.sync_api import sync_playwright
import os

try:
    import requests as _requests
except ImportError:
    _requests = None

try:
    import pdfplumber
except ImportError:
    _runtime_site = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "python"
        / "Lib"
        / "site-packages"
    )
    if _runtime_site.exists():
        sys.path.append(str(_runtime_site))
    try:
        import pdfplumber
    except ImportError:
        pdfplumber = None

HAS_PDFPLUMBER = pdfplumber is not None

BASE_DIR = Path(__file__).resolve().parent
REPO_GIT = BASE_DIR.parent

CARPETA = BASE_DIR

TXT_OUTPUT = CARPETA / "texto_extraido_stonex.txt"
CSV_OUTPUT = CARPETA / "deals.csv"
CSV_DIFUSION = CARPETA / "difusion.csv"
CSV_BAJO_IMPACTO = CARPETA / "deals_bajo_impacto.csv"

CSV_WEB = REPO_GIT / "emisiones_obligaciones_negociables.csv"
CSV_WEB_BAJO_IMPACTO = REPO_GIT / "emisiones_on_bajo_impacto.csv"
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

MONEDAS_USD = ["USD Mep", "USD Cable", "USD Linked", "USD Int"]


def fecha_para_web(fecha):
    try:
        d, m, y = str(fecha).split("/")
        return f"{int(d)}-{MESES_WEB[m]}-{y[-2:]}"
    except:
        return fecha

DIA = r"(?:lun|mar|mi(?:é|Ã©)|jue|vie),\s+\d{1,2}\s+\w{3}\."

def numero_para_web(x):
    try:
        return f"{float(x):.2f}".replace(".", ",")
    except:
        return x
    
# ==========================================
# GIT PULL
# ==========================================

import subprocess

GIT_REMOTE = "origin"
GIT_BRANCH = "main"
GIT_FILES = [
    CSV_WEB,
    CSV_WEB_BAJO_IMPACTO,
    CSV_OUTPUT,
    CSV_BAJO_IMPACTO,
    CSV_DIFUSION,
    TXT_OUTPUT,
    SCREENSHOT,
]

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


def git_result(args, **kwargs):
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

    return result


def git_path(path):
    return os.path.relpath(Path(path), REPO_GIT).replace(os.sep, "/")


def git_is_non_fast_forward(result):
    text = f"{result.stdout}\n{result.stderr}".lower()
    return "non-fast-forward" in text or "fetch first" in text


def git_sync_or_abort():
    print("\nSincronizando repo con origin/main...")

    rc_fetch = git(["fetch", GIT_REMOTE, GIT_BRANCH])
    if rc_fetch != 0:
        print("Error en git fetch; abortando actualización")
        return False

    rc_rebase = git(["rebase", f"{GIT_REMOTE}/{GIT_BRANCH}"])
    if rc_rebase != 0:
        print("Error en git rebase; abortando actualización")
        git(["rebase", "--abort"])
        return False

    return True


def git_has_staged_file_changes():
    status = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--"] + [git_path(p) for p in GIT_FILES],
        cwd=str(REPO_GIT),
        capture_output=True,
        text=True,
    )
    return bool(status.stdout.strip())


def git_push_with_retry():
    push_result = git_result(["push", GIT_REMOTE, GIT_BRANCH])
    if push_result.returncode == 0:
        print("Push exitoso.")
        return True

    if not git_is_non_fast_forward(push_result):
        print("Error en git push")
        return False

    print("Push rechazado. Reintentando con fetch + rebase...")

    rc_fetch = git(["fetch", GIT_REMOTE, GIT_BRANCH])
    if rc_fetch != 0:
        print("Error en git fetch luego del push rechazado")
        return False

    rc_rebase = git(["rebase", f"{GIT_REMOTE}/{GIT_BRANCH}"])
    if rc_rebase != 0:
        print("Error en git rebase luego del push rechazado")
        git(["rebase", "--abort"])
        return False

    push_result_2 = git_result(["push", GIT_REMOTE, GIT_BRANCH])
    if push_result_2.returncode != 0:
        print("Error en git push luego del segundo intento")
        return False

    print("Push exitoso.")
    return True

    
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


def texto_tiene_resultados_parseables(texto):
    t = limpiar_texto_celda(texto).lower()
    return (
        "tasa / precio de corte" in t
        and "moneda" in t
        and "maturity" in t
    )


def _extraer_texto_pagina(page):
    partes = []

    try:
        partes.append(page.locator("body").inner_text(timeout=2000))
    except Exception:
        pass

    for frame in page.frames:
        try:
            partes.append(frame.locator("body").inner_text(timeout=1000))
        except Exception:
            pass

    return "\n".join(partes)


def _buscar_pdf_url_en_dom(page):
    candidatos = [page.url]

    try:
        candidatos.append(page.content())
    except Exception:
        pass

    for frame in page.frames:
        candidatos.append(frame.url)
        try:
            candidatos.append(frame.content())
        except Exception:
            pass

    for texto in candidatos:
        m = re.search(r"https?://[^\"'<> ]+\.pdf(?:\?[^\"'<> ]*)?", str(texto), flags=re.I)
        if m:
            return m.group(0).replace("&amp;", "&")

    return None


def _limpiar_pdf_url(url):
    url = _html.unescape(str(url))
    url = url.split("#", 1)[0]
    return url


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
                pdf_url_capturada = _limpiar_pdf_url(response.url)
                print(f"  PDF detectado: {response.url}")

        page.on("response", on_response)

        page.goto(url, wait_until="networkidle", timeout=60000)

        texto_visible = ""
        for intento in range(45):
            texto_visible = _extraer_texto_pagina(page)

            if not pdf_url_capturada:
                pdf_url_capturada = _buscar_pdf_url_en_dom(page)
                if pdf_url_capturada:
                    pdf_url_capturada = _limpiar_pdf_url(pdf_url_capturada)
                    print(f"  PDF detectado en DOM: {pdf_url_capturada}")

            if pdf_url_capturada or texto_tiene_resultados_parseables(texto_visible):
                break

            if intento == 5:
                try:
                    page.get_by_text("View Full", exact=True).click(timeout=3000)
                except Exception:
                    pass

            page.wait_for_timeout(2000)

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
            if _requests:
                resp = _requests.get(pdf_url_capturada, cookies=cookies_dict, timeout=30)
                resp.raise_for_status()
                pdf_bytes = resp.content
            else:
                from urllib.request import Request, build_opener, HTTPCookieProcessor
                import http.cookiejar

                jar = http.cookiejar.CookieJar()
                opener = build_opener(HTTPCookieProcessor(jar))
                req = Request(pdf_url_capturada, headers={"User-Agent": "Mozilla/5.0"})
                pdf_bytes = opener.open(req, timeout=30).read()

            texto_pdf = ""
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for pg in pdf.pages:
                    texto_pdf += (pg.extract_text() or "") + "\n"
            if "Resultados" in texto_pdf or "Licitaciones" in texto_pdf:
                print("PDF extraído con pdfplumber — texto limpio disponible")
                texto_total = texto_pdf
            else:
                print("PDF descargado pero no contiene sección esperada; usando texto de frames")
        except Exception as e:
            print(f"No pude descargar/parsear PDF ({e}); usando texto de frames")

    if not texto_tiene_resultados_parseables(texto_total):
        TXT_OUTPUT.write_text(texto_total, encoding="utf-8")
        raise RuntimeError(
            "La extraccion de StoneX no contiene una tabla de Resultados parseable; "
            "abortando para no actualizar CSVs con un informe incompleto."
        )

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

    raw = nums[0]
    val = float(raw.replace(".", ""))

    if "." in raw or val > 1_000_000:
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
    if "uva" in t:
        return "UVA"
    if "ars" in t:
        return "ARS"

    return str(moneda).strip()


def tasa_y_margen(cupon, aceptar_margen_negativo=False):
    c = str(cupon).upper().strip()

    if "A LICITAR" in c or "A INFORMAR" in c or "+MG" in c:
        return "", ""

    if c.startswith("TEM"):
        m = re.search(r"TEM\s+(\d+(?:,\d+)?)%", c)
        margen = f"{float(m.group(1).replace(',', '.')):.2f}%".replace(".", ",") if m else ""
        return "TEM", margen

    if "TAMAR" in c or "T+" in c:
        if aceptar_margen_negativo:
            m = re.search(r"(?:TAMAR|T)([+-]\d+(?:,\d+)?)", c)
        else:
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

    if moneda in MONEDAS_USD:
        return vn > 10

    if moneda == "ARS":
        return vn >= 10000

    if moneda == "UVA":
        return vn > 10

    return False


def monto_calculable(moneda, vn):
    if vn is None:
        return False

    return moneda in MONEDAS_USD or moneda in ["ARS", "UVA"]


def bajo_impacto_por_monto(moneda, vn):
    return monto_calculable(moneda, vn) and not cumple_monto(moneda, vn)


def pasa_filtro_monto(moneda, vn, modo):
    if modo == "principal":
        return cumple_monto(moneda, vn)

    if modo == "bajo_impacto":
        return bajo_impacto_por_monto(moneda, vn)

    raise ValueError(f"Modo de filtro de monto no soportado: {modo}")


def extraer_resultados(texto):
    # pdfplumber sometimes drops or reorders the "Resultados" title.
    # The table header is a more stable anchor for the actual results block.
    if "Tasa / Precio de Corte" in texto:
        parte = texto.split("Tasa / Precio de Corte", 1)[1]
    elif "Resultados" in texto:
        parte = texto.split("Resultados", 1)[1]
    else:
        parte = texto

    if "Licita hoy" in parte:
        parte = parte.split("Licita hoy", 1)[0]

    if "OPERACIONES DE TERCEROS" in parte:
        parte = parte.split("OPERACIONES DE TERCEROS", 1)[0]

    if "Operaciones en difusión" in parte:
        parte = parte.split("Operaciones en difusión", 1)[0]

    if "Operaciones en Difusión" in parte:
        parte = parte.split("Operaciones en Difusión", 1)[0]

    return parte


def normalizar_emisor(emisor):
    s = limpiar_texto_celda(emisor)

    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"\s*-\s*", " – ", s)
    s = s.replace("[Ley NY]", "(Ley NY)")

    s = re.sub(r"\s*\(Integra[^)]*\)", "", s, flags=re.I)
    s = re.sub(
        r"\s*\(Integra.*?(?=\s+[IVXLCDM]+\s+[A-Z0-9]+$|$)",
        " ",
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

    s = re.sub(r"\s*(?:-|\u2013|â€“)\s*$", "", s).strip()

    s = re.sub(
        r"^(Banco de Galicia)\s+[-\u2013Ц]\s+([IVXLCDM]+\s+[IVXLCDM]+)$",
        r"\1 \2",
        s,
        flags=re.I
    )

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
    p = re.sub(r"\s*\(Integra[^)]*\)", "", p, flags=re.I)
    p = re.sub(
        r"\s*\(Integra.*?(?=\s+[IVXLCDM]+\s+[A-Z0-9]+$|$)",
        " ",
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

    p = re.sub(
        r"^(Banco de Galicia)\s+[-\u2013Ц]\s+([IVXLCDM]+\s+[IVXLCDM]+)$",
        r"\1 \2",
        p,
        flags=re.I
    )

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


def _linea_empieza_fila(linea):
    return bool(
        re.match(
            rf"^(?:{DIA}|ON |BONAR |\[OFERTA DE CANJE\]|FF |Letras? |Bono )",
            linea,
            flags=re.I
        )
    )


def _separar_nombre_on_de_metricas(linea):
    m = re.match(
        r"^(?P<prefix>ON\s+.*?)(?=\s+(?:TAMAR[+-]\d|TEM\s+\d|\d{1,2},\d{2,3}%|Px\s+\d))(?P<rest>.*)$",
        linea,
        flags=re.I
    )

    if not m:
        return None, None

    return limpiar_texto_celda(m.group("prefix")), limpiar_texto_celda(m.group("rest"))


def _rearmar_on_partida(prefix, data_line, suffix=""):
    suffix = limpiar_texto_celda(suffix)

    m_liq = list(re.finditer(DIA, data_line, flags=re.I))
    if m_liq:
        ultimo = m_liq[-1]
        trailing = limpiar_texto_celda(data_line[ultimo.end():])
        if trailing and not _linea_empieza_fila(trailing):
            suffix = limpiar_texto_celda(f"{suffix} {trailing}")
            data_line = data_line[:ultimo.end()]

    nombre = limpiar_texto_celda(f"{prefix} {suffix}")

    return re.sub(
        rf"({DIA})\s+",
        lambda m: f"{m.group(1)} {nombre} - ",
        data_line,
        count=1,
        flags=re.I
    )


_RATING_GRADE_RESULTADOS = r"(?:AAA|AA[+-]?|A1\+?|A-1|A-2|A2|A[+-]?|BBB[+-]?|BB[+-]?|B[+-]?|SC)"


def _linea_rating_resultado(linea):
    l = limpiar_texto_celda(linea)
    if re.search(DIA, l, flags=re.I):
        return False
    if re.search(r"\b(?:ON|BONAR|USD|ARS|UVA)\b", l, flags=re.I):
        return False
    return bool(re.match(rf"^(?:ML\s+)?{_RATING_GRADE_RESULTADOS}\b", l, flags=re.I))


def _linea_rating_continuacion(linea):
    l = limpiar_texto_celda(linea)
    return bool(re.match(r"^(?:\d+\s+\([^)]+\)|\([^)]+\))$", l, flags=re.I))


def _unir_rating_partida(rating, continuacion):
    rating = limpiar_texto_celda(rating)
    continuacion = limpiar_texto_celda(continuacion)
    sep = "" if re.search(r"(?:A-|AA-|BBB-|BB-|B-)$", rating) and re.match(r"^\d", continuacion) else " "
    return limpiar_texto_celda(f"{rating}{sep}{continuacion}")


def _insertar_rating_en_resultado(linea, rating):
    if not rating:
        return linea

    tipo_pat = r"(?:Tasa|Margen|TIR|TEM|Precio|Book building|Por AdhesiÃ³n)"
    nueva = re.sub(
        rf"\s+({tipo_pat})\s+({DIA})\s*$",
        lambda m: f" {rating} {m.group(1)} {m.group(2)}",
        linea,
        count=1,
        flags=re.I
    )
    return nueva


def _preprocesar_on_partidas(resultados):
    lines = [
        limpiar_texto_celda(line)
        for line in str(resultados).splitlines()
        if limpiar_texto_celda(line)
    ]

    out = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if _linea_rating_resultado(line) and i + 1 < len(lines):
            next_line = lines[i + 1]
            if re.search(DIA, next_line, flags=re.I) and re.search(r"\bON\b", next_line, flags=re.I):
                rating = line
                skip = 2
                if i + 2 < len(lines) and _linea_rating_continuacion(lines[i + 2]):
                    rating = _unir_rating_partida(rating, lines[i + 2])
                    skip = 3
                out.append(_insertar_rating_en_resultado(next_line, rating))
                i += skip
                continue

        prefix, rest = _separar_nombre_on_de_metricas(line)
        if prefix and re.search(DIA, rest, flags=re.I):
            out.append(_rearmar_on_partida(prefix, rest))
            i += 1
            continue

        if line.startswith("ON ") and i + 1 < len(lines):
            next_line = lines[i + 1]
            if re.search(DIA, next_line, flags=re.I) and re.search(
                r"\b(?:USD\s+Mep|USD\s+Cable|USD\s+Linked|USD\s+linked|ARS|UVA)\b",
                next_line
            ):
                suffix = ""
                skip = 2
                if i + 2 < len(lines) and not _linea_empieza_fila(lines[i + 2]):
                    suffix = lines[i + 2]
                    skip = 3
                out.append(_rearmar_on_partida(line, next_line, suffix))
                i += skip
                continue

        out.append(line)
        i += 1

    return "\n".join(out)


def _find_first_marker(texto, markers):
    texto_lower = texto.lower()
    positions = [
        texto_lower.index(marker.lower())
        for marker in markers
        if marker.lower() in texto_lower
    ]
    return min(positions) if positions else None


def extraer_bloque_difusion(texto):
    # "Difusion" in the dashboard means pending operations: today's auctions
    # plus the forward-looking "Operaciones en Difusion" section.
    pos = _find_first_marker(texto, [
        "Licita hoy",
        "Operaciones en difusión",
        "Operaciones en Difusión",
        "Operaciones en difusiÃ³n",
        "Operaciones en DifusiÃ³n",
    ])

    if pos is not None:
        return texto[pos:]

    pos = _find_first_marker(texto, [
        "OPERACIONES DE TERCEROS",
        "Operaciones de terceros",
    ])

    if pos is not None:
        return texto[pos:]

    return ""


def normalizar_bloque_difusion(bloque):
    lines = bloque.splitlines()
    out = []
    pending_prefix = []
    pending_rating = ""
    tipo_pat = r"(?:Tasa|Margen|TIR|TEM|Precio|Book building|Por Adhesión)"
    rating_grade = r"(?:AAA|AA[+-]?|A1\+?|A-1|A[+-]?|BBB[+-]?|BB[+-]?|B[+-]?)"
    rating_line_pat = rf"^{rating_grade}\s+\([^)]+\)(?:\s*/\s*{rating_grade}(?:\s+\([^)]+\))?)*$"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        starts_instrument = re.match(r"^(ON |BONAR |Títulos de Deuda)", stripped)
        starts_date = re.match(DIA, stripped)
        is_rating_line = re.match(rating_line_pat, stripped)

        if is_rating_line and not pending_prefix:
            pending_rating = stripped
            continue

        if starts_instrument and not starts_date:
            if pending_prefix:
                out.extend(pending_prefix)
            pending_prefix = [stripped]
            continue

        if pending_prefix and not starts_date:
            pending_prefix.append(stripped)
            continue

        if pending_prefix and starts_date:
            prefix = limpiar_texto_celda(" ".join(pending_prefix))
            line = re.sub(
                rf"^({DIA})\s+",
                lambda m: f"{m.group(1)} {prefix} ",
                stripped,
                count=1
            )
            out.append(line)
            pending_prefix = []
            continue

        if pending_rating and starts_date:
            line = re.sub(
                rf"\s+({tipo_pat})\s+({DIA}|A informar)\s*$",
                lambda m: f" {pending_rating} {m.group(1)} {m.group(2)}",
                stripped,
                count=1
            )
            pending_rating = ""
            out.append(line)
            continue

        if pending_rating:
            out.append(pending_rating)
            pending_rating = ""

        out.append(line)

    if pending_prefix:
        out.extend(pending_prefix)
    if pending_rating:
        out.append(pending_rating)

    return "\n".join(out)


def _fix_text_artifacts(s):
    replacements = {
        "ķ": "í",
        "į": "á",
        "ń": "ñ",
        "“": "´",
        "Ã©": "é",
        "Ã³": "ó",
        "Ã¡": "á",
        "Ã­": "í",
        "Ãº": "ú",
        "Ã±": "ñ",
    }
    for bad, good in replacements.items():
        s = s.replace(bad, good)
    return s


def linealizar_filas_difusion(bloque):
    lines = [
        _fix_text_artifacts(limpiar_texto_celda(line))
        for line in str(bloque).splitlines()
        if limpiar_texto_celda(line)
    ]

    tipo_pat = re.compile(
        r"^(Tasa|Margen|TIR|TEM|Precio|Book Building|Book building|Por Adhesión)$",
        re.I
    )
    rows = []
    i = 0

    while i < len(lines):
        if not re.match(DIA, lines[i], flags=re.I):
            i += 1
            continue

        fecha_lic = lines[i]
        body = []
        j = i + 1

        while j < len(lines):
            tipo_match = tipo_pat.match(lines[j])
            next_is_liq = (
                j + 1 < len(lines)
                and (
                    re.match(DIA, lines[j + 1], flags=re.I)
                    or lines[j + 1].lower() == "a informar"
                )
            )

            if tipo_match and next_is_liq:
                rows.append(
                    limpiar_texto_celda(
                        f"{fecha_lic} {' '.join(body)} {lines[j]} {lines[j + 1]}"
                    )
                )
                i = j + 2
                break

            if j > i + 1 and re.match(DIA, lines[j], flags=re.I):
                break

            body.append(lines[j])
            j += 1
        else:
            i += 1
            continue

        if j < len(lines) and not (tipo_match and next_is_liq):
            i += 1

    return "\n".join(rows)


def _difusion_rating(reg_limpio):
    rating_grade = r"(?:AAA|AA[+-]?|A1\+?|A-1|A-2|A2|A[+-]?|BBB[+-]?|BB[+-]?|B[+-]?)"
    rating_pat = rf"(?:ML\s+)?{rating_grade}\s+\([^)]+\)"
    m_rating = re.search(
        rf"\b({rating_pat}(?:\s*/\s*(?:{rating_pat}|{rating_grade}))*|SC)",
        reg_limpio
    )
    if m_rating:
        return m_rating.group(1)

    m_pending = re.search(r"\b(A informar)\b", reg_limpio)
    return m_pending.group(1) if m_pending else ""


def _difusion_emisor(reg):
    s = limpiar_texto_celda(reg)

    s = re.sub(DIA, " ", s, flags=re.I)

    rating_grade = r"(?:AAA|AA[+-]?|A1\+?|A-1|A-2|A2|A[+-]?|BBB[+-]?|BB[+-]?|B[+-]?)"
    rating_pat = rf"(?:ML\s+)?{rating_grade}\s+\([^)]+\)"
    s = re.sub(
        rf"\b{rating_pat}(?:\s*/\s*(?:{rating_pat}|{rating_grade}))*",
        " ",
        s
    )
    s = re.sub(
        r"\s*/\s*(?:AAA|AA[+-]?|A1\+?|A-1|A-2|A2|A[+-]?|BBB[+-]?|BB[+-]?|B[+-]?)\b",
        " ",
        s
    )

    s = re.sub(r"Monto Máximo Disponible", " ", s, flags=re.I)
    s = re.sub(r"Monto Máximo del Programa", " ", s, flags=re.I)
    s = re.sub(r"del Programa\)", " ", s, flags=re.I)

    emisor = re.split(
        r"\s*-?\s*(?:USD|\$)\s*[\d\.]",
        s,
        maxsplit=1
    )[0]
    emisor = re.split(
        r"\s+(?:USD\s+Mep|USD\s+Cable|USD\s+Linked|ARS|UVA)\b",
        emisor,
        maxsplit=1
    )[0]

    emisor = re.sub(r"\s+(VDFA|VDFB|VDFC|CP)\b.*$", "", emisor)
    emisor = re.sub(r"^ON\s+", "", emisor, flags=re.I)
    emisor = re.sub(r"^Títulos de Deuda del\s+", "", emisor, flags=re.I)
    emisor = re.sub(r"\(Integra.*", "", emisor, flags=re.I)
    emisor = re.sub(r"\(Pyme\)", "", emisor, flags=re.I)
    emisor = re.sub(r"\[Ley NY\]", "", emisor)
    emisor = re.sub(r"\[Bono SVS\]", "", emisor)
    emisor = re.sub(r"Garantizadas?\s+", "", emisor, flags=re.I)
    emisor = re.sub(r"\s+-\s*(?:[IVXLCDM]+|\d+)\s*$", "", emisor)
    emisor = re.sub(r"\s+(?:VDFA|VDFB|VDFC|CP|[IVXLCDM]+)\s*$", "", emisor)
    emisor = re.sub(r"\s+", " ", emisor).strip(" -")

    if emisor == "Banco de Servicios y":
        emisor = "Banco de Servicios y Transacciones"

    if emisor == "Pyme CNV 3D":
        emisor = "Pyme CNV 3D LATINOAMERICA S.A."

    return limpiar_texto_celda(emisor)


# =========================================================
# PARSER GENERAL
# =========================================================

def parsear_resultados_generico(resultados, modo_monto="principal"):
    filas = []

    resultados = _preprocesar_on_partidas(resultados)

    texto = limpiar_texto_celda(resultados)
    cupon_pat = (
        r"TAMAR[+-]\d+(?:,\d+)?%|T[+-]\d+(?:,\d+)?|"
        r"TAMAR\+\d+(?:,\d+)?%|T\+\d+(?:,\d+)?|"
        r"TEM\s+\d+(?:,\d+)?%|\d{1,2},\d{2,3}%|0,00%"
        if modo_monto == "bajo_impacto"
        else r"TAMAR\+\d+(?:,\d+)?%|T\+\d+(?:,\d+)?|\d{1,2},\d{2,3}%|0,00%"
    )
    moneda_pat = (
        r"USD\s+Mep|USD\s+Cable|USD\s+Linked|USD\s+linked|ARS|UVA"
        if modo_monto == "bajo_impacto"
        else r"USD\s+Mep|USD\s+Cable|USD\s+Linked|USD\s+linked|ARS|UVA"
    )
    vn_pat = (
        r"(?:USD|\$|UVA)\s*[\d\.]+"
        if modo_monto == "bajo_impacto"
        else r"(?:USD|\$|UVA)\s*[\d\.]+"
    )

    patron_fila = re.compile(
        rf"(?P<lic>{DIA})\s+"
        rf"(?P<body>(?:ON|BONAR|\[OFERTA DE CANJE\]\s+ON).*?)\s+"
        rf"(?P<tipo>Tasa|Margen|TIR|TEM|Precio|Book building|Por Adhesión)\s+"
        rf"(?P<liq>{DIA})",
        re.DOTALL | re.I
    )

    patron_detalle = re.compile(
        r"(?P<prefix>(?:ON|BONAR).*?)\s+"
        rf"-?(?P<moneda>{moneda_pat})\s+"
        rf"(?P<vn>{vn_pat})"
        r"(?:\s+\([^)]*\))?\s+"
        rf"(?P<cupon>{cupon_pat})\s+"
        rf"(?P<duration>[\d,]+)\s+"
        rf"(?P<maturity>\d+)\s+"
        rf"(?P<ultima>\d{{1,2}}/\d{{1,2}}/\d{{4}})\s+"
        rf"(?P<rating>.*)$"
    )

    for fila in patron_fila.finditer(texto):
        row_text = limpiar_texto_celda(fila.group(0))
        body = limpiar_texto_celda(fila.group("body"))

        matches = list(patron_detalle.finditer(body))

        if not matches:
            continue

        for detalle in matches:

            prefix = detalle.group("prefix")

            if " ON " in prefix and not re.search(r"\bcon\s+ON\b", prefix, flags=re.I):
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

            if not pasa_filtro_monto(moneda, vn, modo_monto):
                continue

            tasa, margen = tasa_y_margen(
                detalle.group("cupon"),
                aceptar_margen_negativo=modo_monto == "bajo_impacto"
            )

            if not tasa or margen == "":
                continue

            rating = limpiar_texto_celda(
                detalle.group("rating")
            )

            rating = re.split(
                rf"\s+(?:Tasa|Margen|TIR|TEM|Precio|Book building|Por Adhesión)\s+"
                rf"(?={DIA}|A informar\b)",
                rating,
                maxsplit=1,
                flags=re.I
            )[0].strip()

            rating = re.sub(
                r"\s+(Tasa|Margen|TIR|TEM|Precio|Book building|Por Adhesión)$",
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


def ordenar_deals_por_fecha(df):
    df = df.copy()

    if df.empty:
        return df

    df["FECHA_ORD"] = pd.to_datetime(
        df["FECHA"],
        format="%d/%m/%Y",
        errors="coerce"
    )

    return df.sort_values(
        ["FECHA_ORD", "EMISOR"],
        ascending=[False, True]
    ).drop(columns=["FECHA_ORD"])


def filtrar_ultimos_dias(df, dias=30, dias_adelante=30):
    if df.empty:
        return df.copy()

    fechas = pd.to_datetime(
        df["FECHA"],
        format="%d/%m/%Y",
        errors="coerce"
    )

    hoy = pd.Timestamp.today().normalize()
    desde = hoy - pd.Timedelta(days=dias)
    hasta = hoy + pd.Timedelta(days=dias_adelante)

    return df[
        fechas.notna()
        & (fechas >= desde)
        & (fechas <= hasta)
    ].copy()


def guardar_csv_web_deals(df, path):
    final_web = df.copy()

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
        path,
        index=False,
        encoding="utf-8-sig"
    )


def actualizar_bajo_impacto(texto):

    print("\n==============================")
    print("ACTUALIZANDO ON < 10MM")
    print("==============================")

    resultados = extraer_resultados(texto)
    filas = parsear_resultados_generico(
        resultados,
        modo_monto="bajo_impacto"
    )
    df_nuevo = pd.DataFrame(filas, columns=COLUMNAS)

    if CSV_BAJO_IMPACTO.exists():
        try:
            df_existente = pd.read_csv(CSV_BAJO_IMPACTO, sep=";")
        except pd.errors.EmptyDataError:
            df_existente = pd.DataFrame(columns=COLUMNAS)
    else:
        df_existente = pd.DataFrame(columns=COLUMNAS)

    df_existente = normalizar_y_deduplicar(df_existente)

    if df_nuevo.empty:
        print("\nNo se detectaron ON < 10MM nuevas en Resultados.")
        final = df_existente
        df_agregar = pd.DataFrame(columns=COLUMNAS)
    else:
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

    if final.empty:
        final = final[COLUMNAS].copy()
    else:
        final = final[
            final.apply(
                lambda r: bajo_impacto_por_monto(r["MONEDA"], r["VN"]),
                axis=1
            )
        ]

    final = ordenar_deals_por_fecha(final)

    final.to_csv(
        CSV_BAJO_IMPACTO,
        index=False,
        encoding="utf-8-sig",
        sep=";"
    )

    ultimos_30 = ordenar_deals_por_fecha(
        filtrar_ultimos_dias(final, dias=30)
    )

    guardar_csv_web_deals(
        ultimos_30,
        CSV_WEB_BAJO_IMPACTO
    )

    print("\nDetectadas ON < 10MM en reporte:")
    print(len(df_nuevo))

    print("\nNuevas ON < 10MM agregadas:")
    print(len(df_agregar))

    print("\nTabla web ultimos 30 dias:")
    print(CSV_WEB_BAJO_IMPACTO)
    print("Filas:", len(ultimos_30))

def actualizar_difusion(texto):

    print("\n======================")
    print("ACTUALIZANDO DIFUSION")
    print("======================")

    bloque = extraer_bloque_difusion(texto)

    if not bloque:
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

    bloque_lineal = linealizar_filas_difusion(bloque)
    if bloque_lineal:
        bloque = bloque_lineal
    else:
        bloque = normalizar_bloque_difusion(bloque)
    

    patron = re.compile(
        rf"(?P<fecha_lic>{DIA})\s+"
        rf"(?P<reg>(?:ON |BONAR |Títulos de Deuda).*?)\s+"
        rf"(?P<tipo>Tasa|Margen|TIR|TEM|Precio|Book Building|Book building|Por Adhesión)\s+"
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

        elif "UVA" in reg:
            moneda = "UVA"

        elif "ARS" in reg or "-ARS" in reg:
            moneda = "ARS"

        if "Ley NY" in reg:
            moneda = "USD Int"

        # -------------------------
        # EMISOR
        # -------------------------

        emisor = _difusion_emisor(reg)


        # -------------------------
        # PLAZO
        # -------------------------

        plazo = ""

        m_plazo = re.search(
            r"\s(\d{2,4})\s+\d{1,2}/\d{1,2}/\d{4}",
            reg_limpio
        )

        if m_plazo:
            plazo = plazo_meses(
                m_plazo.group(1)
            )

        if "Venc. entre los 8 y 10 años" in reg:
            plazo = 108

        if re.search(r"Venc\.\s*a\s+los\s+8\s+años", reg, flags=re.I):
            plazo = 96

        # -------------------------
        # TASA
        # -------------------------

        tipo_licitacion = m.group("tipo")
        if tipo_licitacion == "TEM":
            tasa = "TEM"
        elif moneda == "ARS":
            tasa = "TAMAR+Mg"
        else:
            tasa = "Fija"

        # -------------------------
        # RATING
        # -------------------------

        rating = _difusion_rating(reg_limpio)

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

    print(f"\nFilas difusión detectadas en reporte: {len(df_nuevo)}")
    if len(df_nuevo):
        print(df_nuevo)

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

    if len(df_nuevo):
        fechas_nuevas = set(
            df_nuevo["FECHA LICITACIÓN"].astype(str)
        )
        df_existente = df_existente[
            ~df_existente["FECHA LICITACIÓN"].astype(str).isin(fechas_nuevas)
        ]

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

    final = final[
        ~final["EMISOR"].fillna("").astype(str).str.match(r"^\s*FF\b", case=False)
    ]

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

    if not git_sync_or_abort():
        return

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
    actualizar_bajo_impacto(texto)
    actualizar_difusion(texto)

    # ==========================================
    # GIT PUSH
    # ==========================================

    print("\nSubiendo cambios a GitHub...")
    print(f"Repo: {REPO_GIT}")

    # Agregar únicamente los archivos que queremos subir
    rc_add = git([
        "add",
        "--",
    ] + [git_path(p) for p in GIT_FILES])

    if rc_add != 0:
        print("Error en git add")
        return

    # Verificar si hay algo para commitear
    if not git_has_staged_file_changes():
        print("Sin cambios para commitear.")
        return

    # Commit
    rc_commit = git([
        "commit",
        "-m",
        "update deals automatico",
        "--",
    ] + [git_path(p) for p in GIT_FILES])
    if rc_commit != 0:
        print("Error en git commit")
        return

    git_push_with_retry()

if __name__ == "__main__":
    main()
