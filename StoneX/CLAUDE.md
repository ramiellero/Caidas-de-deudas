# StoneX — Scraper de Agenda de Emisiones de ONs

## Propósito
Automatiza la carga semanal de emisiones de Obligaciones Negociables al dashboard. Cada semana StoneX envía por mail la "Agenda de Emisiones" con los resultados de licitaciones primarias; este script la parsea y actualiza `emisiones_obligaciones_negociables.csv` en el repo.

## Archivos

```
actualizar_deals.py         # Script principal — correr este cada semana
prueba_stonex.py            # Prueba original (headless=False, útil para debugging visual)
parser_completo.py          # Parser anterior con patrones hardcodeados por emisor (obsoleto)
excel_a_csv_base.py         # One-shot: convirtió el Excel histórico inicial a CSV base
deals.csv                   # Backup local del CSV de emisiones (separador ";")
difusion.csv                # Operaciones en difusión (próximas licitaciones anunciadas)
texto_extraido_stonex.txt   # Último texto extraído del sitio StoneX (para debugging)
screenshot_stonex.png       # Screenshot del sitio al momento de la extracción
```

**Archivo destino en el repo:**
```
../emisiones_obligaciones_negociables.csv   # Lo que consume el dashboard
```

## Flujo de `actualizar_deals.py`

```
Outlook → buscar mail StoneX
    ↓
Extraer link "Licitaciones Primarias" del HTML del mail
    ↓
Playwright abre el link (headless)
  ├─ Intercepta respuestas HTTP para capturar URL del PDF embebido
  └─ Extrae texto de frames como fallback (deduplicado)
    ↓
Si se capturó PDF → pdfplumber (texto limpio)
Si no             → texto de frames colapsado por limpiar_texto_celda()
    ↓
extraer_resultados() → aísla sección "Resultados" (corta en "Licita hoy")
    ↓
parsear_resultados_generico() → regex sobre texto colapsado
    ↓
actualizar_csv()     → dedup + merge con deals.csv + escribe CSV web
actualizar_difusion() → parsea sección "Operaciones en difusión"
    ↓
git add emisiones_obligaciones_negociables.csv → commit → push
```

## Cómo correr

```bash
cd StoneX
python actualizar_deals.py
```

Requiere: Outlook abierto en Windows, Python con `playwright`, `beautifulsoup4`, `pywin32`, `pandas`. Opcional pero recomendado: `pdfplumber`, `requests` (para extracción limpia del PDF).

```bash
pip install playwright beautifulsoup4 pywin32 pandas pdfplumber requests
playwright install chromium
```

## Lógica de parseo (`parsear_resultados_generico`)

El texto del informe, tras colapsar whitespace, tiene este formato por fila:

```
<DIA_LIC>  ON <Emisor> - <MONEDA> <VN> <Cupón> <Duration> <Maturity(días)> <UltimaFecha> <Rating>  <TipoLic>  <DIA_LIQ>
```

- **`patron_fila`**: ancla por `DIA` (e.g. `"mié, 10 jun."`) antes y después de cada bloque. El cuerpo debe empezar con `ON`, `BONAR` o `[OFERTA DE CANJE] ON`.
- **`patron_detalle`**: extrae moneda (`USD Mep`, `USD Cable`, `USD Linked`, `ARS`), VN, cupón, maturity y rating del cuerpo.
- **Ley NY**: bonos con `[Ley NY]` usan moneda `USD Cable` en el informe; `normalizar_moneda()` los reclasifica a `"USD Int"` al detectar `"ley ny"` en el texto combinado emisor+moneda.
- **Exclusiones automáticas**: filas con monto < USD 10M (USD) o < ARS 10.000M (ARS), fideicomiso (`FF`), letras/bonos del Tesoro, "a licitar", "a informar".
- **Tasa**: `tasa_y_margen()` devuelve `("Fija", "9,45%")` o `("TAMAR", "100bps")`. Si la tasa no se puede parsear, la fila se descarta.

## Convenciones de datos

### Formato CSV local (`deals.csv`)
- Separador: `;`
- Encoding: `utf-8-sig`
- `FECHA`: `DD/MM/YYYY`
- `VN`: número decimal (e.g. `157.0` = USD 157M)
- `TASA/MARGEN`: porcentaje con coma decimal (e.g. `"9,45%"`)
- `PLAZO (en meses)`: entero

### Formato CSV web (`emisiones_obligaciones_negociables.csv`)
- Separador: `,`
- Encoding: `utf-8-sig`
- `FECHA`: `DD-mesES-AA` (e.g. `"29-abr-26"`) — formato que consume el dashboard JS
- `VN`: `"157.000,00"` — formato argentino con puntos de miles y coma decimal
- El resto igual que el CSV local

### Normalización de `MONEDA`
| Texto en informe StoneX | → CSV web |
|---|---|
| `USD Mep` | `USD Mep` |
| `USD Cable` | `USD Cable` |
| `USD Linked` / `USD linked` | `USD Linked` |
| `USD Cable` + `[Ley NY]` en emisor | `USD Int` |
| `ARS` | `ARS` |

## Sección "Operaciones en difusión" (`actualizar_difusion`)

Parsea el bloque posterior a "Operaciones en difusión" para capturar licitaciones ya anunciadas (sin precio de corte). Se guarda en `difusion.csv`. Las licitaciones con fecha de licitación pasada se eliminan automáticamente al procesar cada semana.

Columnas de `difusion.csv`: `FECHA LICITACIÓN`, `FECHA LIQUIDACIÓN`, `EMISOR`, `MONEDA`, `TASA`, `TASA/MARGEN` (siempre `"A licitar"`), `PLAZO (en meses)`, `CALIFICACIÓN`.

## Notas importantes

- **Mail buscado**: asunto contiene `"AGENDA DE EMISIONES"`, remitente contiene `"stonex"` — case-insensitive.
- **Link elegido**: primer link con texto `"licitaciones primarias"`, o primer link con `"intel.stonex.com/article-landing"` en la URL.
- **Deduplicación**: la key para detectar duplicados es `FECHA + EMISOR + MONEDA + TASA/MARGEN + PLAZO + VN`. El mismo deal no se agrega dos veces aunque el script corra múltiples veces.
- **Año en fechas**: calculado dinámicamente desde `datetime.date.today().year`, con ajuste automático si el mes parseado es enero y hoy es diciembre (edge case fin de año).
- **Git push**: solo sube `emisiones_obligaciones_negociables.csv` al repo; los archivos locales de debugging (`deals.csv`, `texto_extraido_stonex.txt`, `screenshot_stonex.png`) no se commiten.
- **Bonos soberanos**: BONAR y bonos del Tesoro pueden aparecer en el informe; el filtro `fila_excluida()` los descarta (pendiente: integrar llamada en el loop genérico — Bug 1 conocido).
- **`pdfplumber`**: si está instalado, se usa para extraer el PDF embebido en la página con texto limpio y estructurado. Si no, se cae al método de extracción de texto por frames de Playwright (funciona pero el texto es más fragmentado).

## Archivos obsoletos / de apoyo

- **`prueba_stonex.py`**: versión de exploración con `headless=False` para ver el browser. Útil cuando el sitio cambia de estructura para hacer debugging.
- **`parser_completo.py`**: parser anterior con patrones específicos para Mercado Pago y Pampa Energía. Reemplazado por el parser genérico. No correr.
- **`excel_a_csv_base.py`**: convirtió el Excel histórico de deals a `deals.csv`. Ya fue usado; no volver a correr.
