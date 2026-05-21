import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
import win32com.client
from playwright.sync_api import sync_playwright

CARPETA_SALIDA = Path(r"C:\Users\lgullo\OneDrive - IRSACORP\Downloads\Prueba_StoneX")
CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

ASUNTO_BUSCADO = "AGENDA DE EMISIONES"
REMITENTE_BUSCADO = "stonex"


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
    print("\nABRIENDO LINK:")
    print(url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        page = browser.new_page(
            accept_downloads=True,
            viewport={"width": 1600, "height": 900}
        )

        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(10)

        screenshot_path = CARPETA_SALIDA / "screenshot_stonex.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        print("\nSCREENSHOT:")
        print(screenshot_path)

        # Baja hasta el PDF embebido para que cargue más texto
        page.mouse.wheel(0, 2000)
        time.sleep(3)
        page.mouse.wheel(0, 2000)
        time.sleep(3)

        texto_total = ""

        # Texto de página principal
        try:
            texto_total += "\n\n--- BODY ---\n\n"
            texto_total += page.locator("body").inner_text(timeout=10000)
        except Exception as e:
            print("No pude leer body:", e)

        # Texto de frames/iframes
        for i, frame in enumerate(page.frames):
            try:
                t = frame.locator("body").inner_text(timeout=5000)
                texto_total += f"\n\n--- FRAME {i} ---\n\n"
                texto_total += t
            except Exception:
                pass

        salida_txt = CARPETA_SALIDA / "texto_extraido_stonex.txt"
        salida_txt.write_text(texto_total, encoding="utf-8")

        print("\nTEXTO EXTRAÍDO:")
        print(salida_txt)

        browser.close()


def main():
    mail = buscar_mail_stonex()

    if not mail:
        print("\nNo encontré mail StoneX.")
        return

    links = extraer_links(mail["html"], mail["body"])

    print("\nLINKS EN EL MAIL:\n")
    for l in links:
        print("-", l["texto"], "|", l["href"])

    link_stonex = elegir_link_stonex(links)

    if not link_stonex:
        print("\nNo encontré link StoneX.")
        return

    print("\nLINK ELEGIDO:")
    print(link_stonex)

    abrir_y_extraer_texto(link_stonex)


if __name__ == "__main__":
    main()