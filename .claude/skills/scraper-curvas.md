# Skill: Actualizar Curvas ONs (scraper BYMA Educa)

Descarga el tablero de BYMA Educa (`https://tablero.bymaeduca.com.ar/`), extrae las ONs
hard-dollar y actualiza `Deals/curvas_on.csv` (snapshot) y `Deals/curvas_propias_historico.csv`
(histórico de ONs IRSA/Cresud). Reemplazó al scraper del informe IAMC (PDF) el 2026-10-06.

## Cuándo usar

- Verificar si el Action automático corrió y tiene datos frescos
- Correr manualmente (el Action corre lun-vie 10:00 ART en GitHub; no depende de la PC)
- Completar ruedas faltantes de las ONs propias (`--backfill`)
- Diagnosticar por qué falló o por qué faltan bonos

---

## Correr manualmente

```powershell
cd "c:\Users\rellero\OneDrive - IRSACORP\Downloads\Dashboard Caídas de Deudas"
python Deals\scraper_curvas.py             # última rueda publicada
python Deals\scraper_curvas.py --backfill  # además completa ruedas faltantes de IRC*/CS* (hasta ~21 ruedas)
python Deals\scraper_curvas.py --commit    # git commit + push al terminar
python Deals\scraper_curvas.py --from-file tablero.html   # pruebas con un HTML ya guardado
```

Requiere solo `pip install requests`. En la red IRSACORP (inspección SSL) el helper `_get()`
reintenta con `verify=False` automáticamente.

## Cómo funciona

El tablero es un HTML de ~2,4 MB con todo embebido en `<script id="payload" type="application/json">`
(no hay API). Del payload se usa `on`:

| Campo | Uso |
|---|---|
| `on.fecha` / `on.fecha_liq` | fecha de la rueda / liquidación T+1 |
| `on.rows[]` | una fila por ticker, ~52 campos (`px`, `ai`, `vr`, `vt`, `ytm`, `cy`, `dm`, `adtv`, `adtvu`, `pxd`, `dytm`, `fxi`…) |
| `on.histi` | ~21 ruedas de TIR / CY / precio sucio por ticker (para el backfill) |

- Solo segmento `hd` (hard dollar). `dlf` / `dlz` / `ars` se descartan.
- **Precio_Clean = (px − ai) / vr × 100**: `px` es precio sucio por 100 de VN original; `ai` y `vr`
  vienen en las mismas unidades (`vt = vr + ai`). Importa para amortizantes (IRCFO: px 49,9 → clean 102,5).
- `Fecha` del CSV = fecha de la rueda de BYMA (no la de ejecución). Si se corre dos veces la misma
  rueda no se duplican filas en el histórico de propias.
- `Moneda`: `MEP` → `USD Mep`; `CCL` + Ley NY → `USD Int`; `CCL` + Ley Arg → `USD Cable`.
- Industria: `_SECTOR_RULES` (prefijo de ticker) con fallback al sector de BYMA. Tickers que caen en
  `Otros` se listan en el log: `[!] N tickers sin industria` → agregar su prefijo a `_SECTOR_RULES`.

## Verificar que el automático corrió

```powershell
Get-Content "Deals\scraper_curvas.log" -Tail 30
git log -5 --format="%h %ad %s" --date=short -- Deals/curvas_on.csv
```

Una corrida OK termina con `[OK] Listo.` y el commit dice `update curvas ONs — BYMA DD/MM/YYYY`.
Si no hay rueda nueva, el Action dice "Sin cambios".

## Errores típicos

| Log | Causa / acción |
|---|---|
| `[ERROR] No se pudo obtener el tablero BYMA` | Red o BYMA caído. Reintentar; los CSV quedan intactos |
| `No se encontró <script id="payload">` | BYMA cambió el formato del tablero. Revisar el HTML y ajustar `_PAYLOAD_RE` / `build_rows` |
| `Sin filas` | Cambió el campo `seg` o la estructura de `on.rows` |

## Filtros que aplica el frontend (no el scraper)

`initCurvasSection()` en `index.html` descarta: filas sin `Precio_Clean`, emisor "San Miguel",
YTM < 0% y YTM > 20%. No hace falta tocar el scraper para cambiarlos.

## Archivos relevantes

| Archivo | Descripción |
|---|---|
| `Deals/scraper_curvas.py` | Scraper principal |
| `.github/workflows/scraper-curvas.yml` | Action diario (lun-vie 10:00 ART) |
| `Deals/run_scraper_curvas.bat` | Wrapper para correrlo local con `--commit` |
| `Deals/curvas_on.csv` | Snapshot de la última rueda (se sobreescribe) |
| `Deals/curvas_propias_historico.csv` | Histórico IRC*/CS* (se appendea) |
| `Deals/scraper_curvas.log` | Log de ejecuciones |
| `Deals/curvas_moneda_lookup.csv`, `curvas_last_id.txt`, `enrich_curvas_moneda.py` | Legado (IAMC/PPI), ya no se usan |
