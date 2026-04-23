# Dashboard — Perfil de Vencimientos de Deuda (IRSA & Cresud)

## Descripción del proyecto
Dashboard web estático (single HTML file) que visualiza el perfil de vencimientos de deuda de **IRSA** y **Cresud**, e inversiones en SGR (Sociedades de Garantía Recíproca). Período de referencia: IIQ FY2026.

## Estructura del proyecto
```
index.html               # Toda la aplicación: HTML + CSS + JS en un único archivo
irsa_deuda.csv           # Vencimientos de capital de IRSA (fuente principal de KPIs IRSA)
irsa_deuda_total.csv     # Schedule completo IRSA: capital + intereses por período
cresud_deuda.csv         # Vencimientos de capital de Cresud (fuente principal de KPIs Cresud)
cresud_completo.csv      # Schedule completo Cresud: capital + intereses por período
garantia_sgr.csv         # Stock de garantías históricas por SGR (Garantías, FDR, Apalancamiento)
mora_antiguedad.csv      # Distribución de mora por antigüedad por SGR
garantias_sector_sgr.csv # Exposición por sector por SGR
mora_sobre_garantias.csv # Mora/Garantías mensual por SGR (jun-25 → feb-26): POTENCIAR, GARANTIZAR, INTEGRA, BIND, Promedio
mora_mercado.csv         # Mora mensual del mercado SGR (feb-25 → feb-26)
plazo_mora_mercado.csv   # Mora por plazo de garantía del mercado
Total_sgr.csv            # Ranking de 42 SGRs con mora (feb-26)
foto_sgr.csv             # Histórico mensual de posición IRSA en cada SGR (Periodo, SGR, Aporte, Posicion, Weight, P&L, Mora, TIR) — se agrega una fila por SGR por mes; el frontend toma el período más reciente
cartera_monedas.csv      # Composición por moneda por SGR (guardado, no usado aún)
composicion_carteras.csv # Composición por tipo de activo por SGR (guardado, no usado aún)
CLAUDE.md                # Este archivo
```

## Arquitectura del archivo `index.html`
El archivo está organizado en tres bloques principales dentro de un único `.html`:

1. **`<style>`** — CSS completo embebido (Inter font, grid layouts, tablas, charts, timeline, responsive)
2. **`<body>`** — HTML con tres secciones (`#page-irsa`, `#page-cresud`, `#page-sgr`) más la navegación
3. **`<script>`** — Lógica JS: tab switching, Chart.js charts, renderizado de timelines

### Dependencias externas (CDN)
- **Chart.js 4.4.3** — `https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js`
- **Google Fonts** — Inter (400, 500, 600, 700)

## Secciones del dashboard

### IRSA (color: `#1D4B6E` azul marino)
- KPI box con deuda total
- Tabla de emisiones (ON — Obligaciones Negociables)
- Info tables: condiciones de cada bono
- Maturity wall chart (Chart.js bar chart) con toggle Año Fiscal / Año Calendario
- **KPI boxes** (entre el chart y la timeline) — calculados dinámicamente desde `irsa_deuda.csv`:
  - Tasa Promedio Ponderada (USD): calculado al día de hoy sobre deuda USD vigente. Excluye Cohen (ARS, vencido 30/01/2026).
  - Vida Promedio Ponderada (USD): ídem.
  - Se recalculan al agregar/eliminar descubiertos (`_rebuildIrsa`).
  - IDs HTML: `#irsa-kpi-tasa`, `#irsa-kpi-vida`, `#irsa-kpi-note`.
- Tabla detalle de vencimientos por instrumento
- Pie chart de composición por moneda — N buckets dinámicos agrupados por `_tipoLabel(MONEDA)`, calculados desde `irsa_deuda.csv`; se recalcula con descubiertos; leyenda regenerada dinámicamente
- Timeline de cashflows con toggle **Solo Capital / + Intereses** (`setIrsaTlView`)
  - `#irsa-tl-cap`: timeline solo capital — generado dinámicamente desde `irsa_deuda.csv`
  - `#irsa-tl-full`: timeline capital + intereses — generado dinámicamente desde `irsa_deuda_total.csv`

### Cresud (color: `#1A3D2A` verde oscuro)
- Maturity wall chart con toggle Año Fiscal / Año Calendario (`setCresudMatView`)
- **KPI boxes** (entre el chart y la timeline) — calculados dinámicamente desde `cresud_deuda.csv`:
  - Tasa Promedio Ponderada (USD): calculado al día de hoy sobre deuda USD vigente. Excluye XXXVIII (vencida 03/03/2026) e ICBC (ARS, vencido 01/02/2026).
  - Vida Promedio Ponderada (USD): ídem.
  - Se recalculan al agregar/eliminar descubiertos (`_rebuildCresud`).
  - IDs HTML: `#cresud-kpi-tasa`, `#cresud-kpi-vida`, `#cresud-kpi-note`.
- Timeline de cashflows con toggle **Solo Capital / + Intereses** (`setCresudTlView`)
  - `#cresud-tl-cap`: timeline solo capital — generado dinámicamente desde `cresud_deuda.csv`
  - `#cresud-tl-full`: timeline capital + intereses — generado dinámicamente desde `cresud_completo.csv` (ONs) + `cresud_deuda.csv` (banking)
- Callout boxes con notas destacadas (borde dashed naranja `#E8960C`)
- Pie chart de composición por moneda

## Datos fuente (CSV)

### `irsa_deuda.csv`
Vencimientos de capital de IRSA. Columnas: `AÑO, FY, MONEDA, Periodo, Compañía, Sociedad, Concepto, Concepto 2, Fecha Inicio, Fecha Fin, Tasa, Moneda, Monto Webcast, Monto USD, Outstanding`.
- Fuente del **maturity wall IRSA** y de la **timeline capital-only** (`#irsa-tl-cap`)
- ONs cubiertas: XIV, XVIII, XX, XXII, XXIII, XXIV
- Incluye un descubierto en ARS (Cohen, vencido 30/01/2026) — se filtra automáticamente
- `MONEDA`: tipo explícito de liquidación del instrumento — valores: `"Cable"` (HD puro), `"MEP"` (HD MEP), `"MEP S/MULC"` (HD sin MULC), `"CABLE S/MULC"`, `"DL"` (dólar linked), `"ARS"`. Reemplaza la columna `Detalle` y la lógica anterior de `TC < 0.99`
- `Monto Webcast`: monto nominal en moneda original (antes llamado `Monto MO`)
- `Monto USD`: equivalente USD ajustado por brecha para instrumentos S/MULC
- `Outstanding`: capital remanente del instrumento en moneda original (usado para calcular la columna Outstanding en la tabla de detalle)
- `Tasa`: formato punto decimal ("8.75%") — igual que Cresud; reemplaza el formato anterior con coma ("8,75%")
- Columna clave para nombre del ON en la timeline: `Concepto` (e.g. "XIV", "XXIV")

### `irsa_deuda_total.csv`
Schedule completo de IRSA con todos los flujos. Columnas: `AÑO, FY, Detalle, Compañía, Sociedad, ON, Concepto, Fecha Inicio, Fecha Fin, Tasa, Moneda, Monto Emitido, Outstanding, Intereses, Amortización, Capital`.
- Fuente de la **timeline capital + intereses** (`#irsa-tl-full`)
- `Concepto` puede ser: `Intereses` (pago solo de cupón) o `Intereses + Capital` (cuota con amortización)
- Para `Intereses`: el monto se toma de la columna `Intereses` (formato "19.218.167,92" con puntos como miles y coma decimal)
- Para `Intereses + Capital`: el monto mostrado es el de la columna `Capital`
- Columna clave para nombre del ON: `ON` (e.g. "XIV", "XXIV") — distinto de `irsa_deuda.csv` donde es `Concepto`
- `Moneda` distingue el tipo de liquidación: `USD Int` (Hard Dollar), `USD MEP - ARGENTINA S/MULC` (HD sin MULC), `USD MEP - ARGENTINA` (HD)
- Período cubierto: 2025–2035 (ON XXIV con última cuota mar-2035)
- ONs: XIV (8,75% USD), XVIII (7,00% USD MEP), XX (6,00% USD MEP), XXII (5,75% USD MEP), XXIII (7,25% USD MEP), XXIV (8,00% USD Int)

### `cresud_deuda.csv`
Vencimientos de capital de Cresud. Columnas: `AÑO, FY, MONEDA, Periodo, Compañía, Sociedad, Concepto, Concepto 2, Fecha Inicio, Fecha Fin, Tasa, Moneda, Monto Webcast, Monto USD`.
- Usado para calcular KPIs de tasa y vida promedio ponderada
- Incluye ONs, Prefinanciaciones bancarias (BBVA, Ciudad) y descubiertos (ICBC en ARS)

### `cresud_completo.csv`
Schedule completo de Cresud con todos los flujos. Columnas: `AÑO, FY, Compañía, Sociedad, Clase, Concepto 2, Fecha Inicio, Fecha Fin, Tasa, Moneda, Monto Emitido, Outstanding, Intereses, Amortización, Capital`.
- `Concepto 2` puede ser: `Capital`, `Intereses`, `Intereses + Capital`
- Usado para construir la timeline `#cresud-tl-full`
- Período cubierto: hasta marzo 2029 (ON L)

## Convenciones de código

### CSS
- **`.mat-table thead th:nth-child(n)`**: anchos explícitos por columna (1=13%, 2=12%, 3=7%, 4=13%, 5=14%, 6=14%, 7=16%, 8=8%) para evitar que el layout de 8 columnas colapse en widths inconsistentes
- **Call popover `max-width`**: `min(320px, calc(100vw - 20px))` — evita desborde en pantallas estrechas
- Variables de color inline (`style="color:#1D4B6E"`) para colores de marca específicos por empresa
- Clases utilitarias: `.grid-2`, `.grid-40-60`, `.grid-35-65` para layouts de dos columnas
- Colores de texto base: `#0F172A` (títulos), `#334155` (body), `#64748B` (muted), `#94A3B8` (placeholder)
- Fondo general: `#ffffff` (blanco)
- **KPI boxes** (`.kpi-box`): `border-radius: 6px`, `box-shadow: 0 1px 4px rgba(0,0,0,0.07)`, `padding: 14px 20px`
  - IRSA: fondo `#EBF2F8`, borde `1px solid #C5D8EA`, acento izquierdo `4px solid #1D4B6E`
  - Cresud: fondo `#EBF4EE`, borde `1px solid #C0D9C8`, acento izquierdo `4px solid #1A3D2A`

### JS
- Tab switching: `switchTab(co)` — alterna `.page.active` y `.nav-tab.active`
- **Maturity wall charts**: cargados dinámicamente desde CSV via `fetch()` al iniciar la página
  - `initIrsaMatChart()` — lee `irsa_deuda.csv`, construye datos, renderiza el chart IRSA, y llama `_updateIrsaKpis` + `_updateIrsaPie`
  - `initCresudMatChart()` — lee `cresud_deuda.csv`, construye datos y renderiza el chart Cresud (no llama KPI/pie porque `_cresudOnMoneda` aún no está listo)
  - Helpers compartidos: `_parseCsvLine()`, `_parseIrsaCsv()`, `_parseDMY()`, `_fyLabel()`
  - `_buildIrsaMatData(rows)` — filtra USD y no vencidos, agrupa por FY y AÑO, separa Bancaria vs ONs vs ON XXIV; retorna `{ labels, banking, otras, xxiv, totals, detail }`
  - `_buildCresudMatData(rows)` — ídem, separa Bancaria vs ONs; nombra bancaria como `Prefi (Concepto)`
- `setIrsaMatView(mode, btn)` — toggle Año Fiscal / Año Calendario en maturity wall IRSA; delega en `_applyIrsaMatData(d)`
- `setCresudMatView(mode, btn)` — ídem para Cresud; delega en `_applyCresudMatData(d)`
- **Timelines IRSA y Cresud**: generadas dinámicamente desde CSV via `fetch()` al iniciar la página
  - `initIrsaTimeline()` — carga `irsa_deuda.csv` y `irsa_deuda_total.csv` en paralelo
  - `_renderIrsaCapTimeline(rows)` — filtra USD + no vencidos; si `Concepto 2 === 'Bancaria'` → badge "Desc." (color HD `#1D4B6E`); si no → badge via `_tipoLabel(r['MONEDA'])`
  - `_renderIrsaFullTimeline(rows)` — agrupa intereses con misma `Fecha Fin`; badge via `_tipoLabel(r['Moneda'])`
  - `initCresudTimeline()` — carga `cresud_deuda.csv` y `cresud_completo.csv` en paralelo; construye lookup `Clase → Moneda` para badge del timeline capital; al terminar llama `_updateCresudKpis` + `_updateCresudPie` (único punto donde `_cresudOnMoneda` está garantizado)
  - `_renderCresudCapTimeline(capRows, onMoneda)` — fuente: `cresud_deuda.csv`; badge: "Prefi" si `Concepto 2='Bancaria'`, "DL" si `MONEDA='DL'`, "HD s/MULC" si el ON tiene `S/MULC` en el lookup, "HD" el resto
  - `_renderCresudFullTimeline(capRows, fullRows)` — ONs desde `cresud_completo.csv` + banking desde `cresud_deuda.csv`; badge según `Moneda` del CSV completo; `Concepto 2` puede ser `Capital`, `Intereses`, `Intereses + Capital`
  - Helpers compartidos: `MESES` (meses ES abreviados), `_fmtM(n)` (formato "19,2M"), `_parseNum(s)` (parsea "19.218.167,92" europeo), `_tlEvHtml(..., badgeTextColor?)` (HTML de un evento; param 11 opcional para texto oscuro en badge DL verde)
- **`_tipoLabel(tipo)`** — normaliza el valor de la columna `MONEDA` / `Moneda` a una etiqueta corta de display. Usado en badges de timeline y leyendas de pie charts:
  - `'USD Int'` / `'USD Cable NY'` → `'Cable'`
  - `'USD Cable NY - S/MULC'` → `'Cable s/MULC'`
  - `'USD MEP - ARGENTINA'` → `'MEP'`
  - `'USD MEP - ARGENTINA S/MULC'` → `'MEP S/MULC'`
  - `'Dólar Linked'` → `'DL'`
  - Valores ya cortos del CSV de capital (`irsa_deuda.csv`, `cresud_deuda.csv`) — e.g. `'Cable'`, `'MEP S/MULC'` — se devuelven sin cambio (passthrough)
- **`IRSA_PIE_COLORS`** — lookup `label → color` para el pie chart IRSA: `{ 'Cable': '#1D4B6E', 'MEP': '#3A6E9B', 'MEP S/MULC': '#5B8DB8', 'Cable s/MULC': '#7AAFC8' }`
- **`CRESUD_PIE_COLORS`** — lookup análogo para Cresud: `{ 'Cable': '#1A3D2A', 'HD': '#1A3D2A', 'MEP': '#2D6B4A', 'MEP S/MULC': '#4A8C60', 'Cable s/MULC': '#5EA375', 'DL': '#6BBF8A' }`
- **`_pieColor(label, colorMap)`** — helper que retorna el color del mapa o `'#94A3B8'` como fallback
- `setIrsaTlView(mode, btn)` — toggle Solo Capital / + Intereses en timeline IRSA; controla `#irsa-tl-cap`, `#irsa-tl-full`, `#irsa-tl-int-legend`
- `setCresudTlView(mode, btn)` — ídem para Cresud; controla `#cresud-tl-cap`, `#cresud-tl-full`, `#cresud-tl-int-legend`
- Fecha dinámica en el header: IIFE al final del `<script>` popula todos los `.header-today` con la fecha actual en formato `dd/mm/yyyy` usando `new Date()`
- No hay frameworks JS — vanilla JS puro

### Columna Outstanding (tabla de detalle)

Nueva columna **Outstanding (USD M)** añadida entre **Capital (USD M)** y **Año Fiscal** en ambas tablas (`#irsa-mat-table`, `#cresud-mat-table`).

**Lógica**:
- Para ONs con amortización parcial (e.g. ON XIV con 3 cuotas): muestra el outstanding reverse-cumulativo — suma del capital de la tranche actual más todas las futuras del mismo instrumento
- Para filas bancarias: muestra el capital íntegro (outstanding = monto de la tranche)
- Para ONs bullet (una sola tranche): outstanding = capital de esa tranche

**Funciones**:
- `_computeOutstandingMap(rows)` — agrupa filas USD vigentes por `Concepto`, las ordena por fecha y computa el acumulado reverso; retorna un mapa `"Concepto|YYYY-MM-DD" → outstanding`
- `_applyOutstandingCol(tableId, map)` — recorre `tbody tr:not(.extra-row)` y rellena la celda `.outstanding-td` con el valor del mapa (o "—" si no hay match)
- Se llama en `initIrsaMatChart()`, `initCresudMatChart()` y en cada `_rebuildIrsa()` / `_rebuildCresud()`

**CSS**: `.outstanding-td` — clase en cada `<td>` de la columna

**Extra-rows (descubiertos)**: incluyen una `<td></td>` vacía extra para mantener alineación de columnas

### Columna Tipo (tabla de detalle)

La segunda columna de ambas tablas ahora muestra el tipo de instrumento específico basado en la columna `MONEDA` del CSV, en lugar del texto genérico anterior ("Bono HD", "Bono DL"):
- ONs IRSA: `"Cable"`, `"MEP"`, `"MEP S/MULC"`, `"CABLE S/MULC"`
- ONs Cresud: `"MEP"`, `"MEP S/MULC"`, `"DL"`, `"CABLE S/MULC"`
- Bancarias: `"Bancaria"` (sin cambio)

### Columna Call Option (tabla de detalle)

Columna interactiva añadida en ambas tablas (`#irsa-mat-table`, `#cresud-mat-table`) entre **Vencimiento** y **Capital (USD M)**. Muestra si el bono es actualmente ejercible y permite ver el detalle al hacer click.

**UI por fila**:
- 🟢 Botón verde `"Callable"` — hoy ≥ call date
- 🔴 Botón rojo `"Not Callable now"` — existe call option pero todavía no ejercible
- Filas con `Tipo = "Bancaria"` → celda vacía (sin botón)
- ONs sin call option (e.g. ON XLII) → celda vacía

**Lógica**:
- `callData` — objeto con los datos de call de cada instrumento; dos tipos:
  - `type: "schedule"` (ON XIV, ON XXIV): callable si `today >= start`; el popover muestra tabla escalonada de precios por tramo
  - Sin type (resto): callable si `today >= callDate`; el popover muestra Call Date + Price
  - `null` (ON XLII): sin call option
- `_callIsCallable(key)` — retorna `true/false/null`; `null` = no tiene call
- `_callCurrentPrice(key)` — recorre los steps del schedule para encontrar el precio vigente
- `_callPopoverHtml(key, outstanding)` — genera el HTML del popover; muestra "Outstanding: X USD M" en la cabecera del popover; lee el outstanding desde `td[6]` de la fila del botón
- `_callCellHtml(instrText)` — genera el HTML del botón para una fila
- `initCallColumns()` — inyecta la `<td>` en cada `tr` de `tbody` (excepto `.extra-row`); se posiciona antes del índice 4 (Capital); excluye filas con `Tipo = "Bancaria"`; se llama una sola vez al cargar la página
- `toggleCallPopover(btn, key)` — muestra/oculta el popover fijo; lo mide off-screen antes de posicionarlo para evitar desborde de viewport; click fuera lo cierra
- `_callPopoverBtn` — referencia al botón activo (para toggle)

**CSS**: `.call-btn`, `.call-btn.callable` (`#16a34a`), `.call-btn.not-callable` (`#dc2626`), `.call-popover` (fijo, fondo `#111`), `.call-sched-table`

**Integración con extra-rows**: `_updateIrsaTable` y `_updateCresudTable` incluyen un `<td></td>` vacío en la posición de Call Option al generar filas de descubiertos, para mantener la alineación de columnas.

### Agregar Descubierto (modal en sesión)
Permite añadir descubiertos bancarios de corto plazo (1–14 días) en memoria durante la sesión, sin editar CSVs manualmente. Los datos **no persisten** al refrescar; el flujo previsto es: agregar → descargar CSV actualizado → reemplazar el archivo y hacer commit.

**UI**: botón "**+ Agregar Descubierto**" encima de la tabla de detalle en cada sección (IRSA y Cresud). El modal se pre-selecciona con la empresa correspondiente.

**Campos del formulario**: Empresa · Nombre/Banco · Moneda (USD / ARS) · Fecha Inicio · Fecha Vencimiento (máx. 14 días) · Monto · Tasa %.

**Comportamiento por moneda**:
- **USD**: el descubierto se refleja en el maturity wall (barra "Deuda Bancaria" `#4A7A9B`), en la timeline de capital (badge "Desc."), en el pie chart (bucket HD) y en la tabla de detalle.
- **ARS**: solo aparece en la tabla de detalle (columna Tipo = "Desc. ARS", monto en naranja). No afecta charts ni pie, igual que Cohen/ICBC en los CSVs originales.

**Globals de estado**:
- `_irsaCapRows` / `_cresudCapRows` — filas del CSV de capital cargadas al init
- `_irsaFullRows` / `_cresudFullRows` — filas del CSV completo (intereses)
- `_cresudOnMoneda` — lookup `Clase → Moneda` de `cresud_completo.csv`
- `_irsaExtraRows` / `_cresudExtraRows` — filas añadidas en sesión
- `_irsaCapCsvText` / `_cresudCapCsvText` — texto original del CSV (base para descarga)
- `_irsaPieChart` / `_cresudPieChart` — referencias a los Chart.js de pie
- `_irsaPieTotal` / `_cresudPieTotal` — totales dinámicos usados en el callback de tooltip del pie

**Funciones principales**:
- `_buildIrsaExtraRow(nombre, fi, ff, monto, tasa, moneda)` — construye objeto compatible con `irsa_deuda.csv`; usa `MONEDA: isUsd ? 'HD' : 'ARS'`, `Monto USD='0'` para ARS (reemplazó el campo `TC`)
- `_buildCresudExtraRow(...)` — ídem para `cresud_deuda.csv`
- `_rebuildIrsa()` / `_rebuildCresud()` — recalcula todo: maturity wall, timeline cap, pie chart, tabla, KPI boxes
- `_applyIrsaMatData(d)` / `_applyCresudMatData(d)` — aplican datos pre-calculados al chart Chart.js; usados tanto por los toggles de vista como por el rebuild
- `_updateIrsaPie(allCapRows)` / `_updateCresudPie(allCapRows)` — llaman a `_computePieDataFromRows`, actualizan `labels`, `data` y `backgroundColor` del chart dinámicamente, y regeneran el HTML de la leyenda (`.currency-legend`) completo
- `_updateIrsaTable(allCapRows)` / `_updateCresudTable(allCapRows)` — insertan filas `.extra-row` antes del `<tfoot>` y recalculan el total (solo USD)
- `_computePieDataFromRows(rows)` — función unificada que agrupa filas USD vigentes por `_tipoLabel(r['MONEDA'])`, ordena por valor descendente; retorna `{ labels, values, total }`. Reemplaza las funciones individuales `_computeIrsaPieData` y `_computeCresudPieData` que fueron eliminadas
- `_computeKpis(rows, parseTasa)` — calcula tasa y vida promedio ponderadas (Σ monto×tasa / Σ monto y Σ monto×años / Σ monto) sobre filas USD vigentes; `parseTasa` es función para parsear el formato de tasa del CSV
- `_updateIrsaKpis(allCapRows)` — actualiza `#irsa-kpi-tasa`, `#irsa-kpi-vida`, `#irsa-kpi-note`; usa parsing con punto decimal ("8.75%") — mismo formato que Cresud desde el cambio de schema de `irsa_deuda.csv`
- `_updateCresudKpis(allCapRows)` — ídem para Cresud; usa parsing con punto decimal ("6.00%")
- `openDescModal(empresa?)` — abre modal; si se pasa `empresa` ('irsa'/'cresud') lo pre-selecciona, si no detecta el tab activo
- `submitDescubierto()` — valida fechas y monto, construye fila, llama rebuild
- `removeDescubierto(empresa, idx)` — splice del array y rebuild
- `downloadDescCsv()` — serializa extra rows al formato CSV de cada empresa y descarga el archivo actualizado

**Maturity wall IRSA — dataset 3**: se agregó un tercer dataset "Deuda Bancaria" (color `#4A7A9B`, índice 0) delante de "ONs" (otras, índice 1) y "ONs" (xxiv, índice 2). El plugin de anotación `irsaMatPlugin` usa `m0/m1/m2` y elige la barra más alta para el label de total.

**Formato CSV de descarga**:
- IRSA: `AÑO,FY,MONEDA,Periodo,Compañía,Sociedad,Concepto,Concepto 2,Fecha Inicio,Fecha Fin,Tasa,Moneda,Monto Webcast,Monto USD,Outstanding` — tasa con punto decimal; sin `TC`; columna `Outstanding` al final
- Cresud: `AÑO,FY,MONEDA,Periodo,Compañía,Sociedad,Concepto,Concepto 2,Fecha Inicio,Fecha Fin,Tasa,Moneda,Monto Webcast,Monto USD` — sin `TC`, tasa con punto decimal

### Lógica de filtrado CSV (maturity walls)
- Se excluyen automáticamente filas donde `Moneda != 'USD'` (e.g. Cohen ARS, ICBC ARS)
- Se excluyen automáticamente filas donde `Fecha Fin <= hoy` (vencimientos pasados desaparecen solos)
- Agrupación FY: usa columna `FY` del CSV (e.g. "FY2026", "FY2027") — un instrumento puede tener `AÑO` distinto al año fiscal de su `FY`
- Agrupación Calendario: usa columna `AÑO`
- Label FY actual (año en curso): `"IVQ YY"` — años futuros: `"FY YY"` (calculado dinámicamente)
- **Cresud FY view**: el FY en curso se divide en barras por quarter fiscal (IIIQ, IVQ, etc.) según la fecha de vencimiento; los FYs futuros se agrupan en una sola barra anual. IRSA no requiere este split (todos sus vencimientos FY en curso caen en IVQ).

### Lógica de las timelines IRSA (dinámica)
- **Auto-expiry**: filas con `Fecha Fin <= hoy` se excluyen automáticamente; la timeline se actualiza sola con el paso del tiempo
- **Posicionamiento**: eventos distribuidos uniformemente de izq a der, `left = 5 + i × (90 / (n–1)) %`; alternancia arriba/abajo por índice par/impar
- **Badges IRSA** en `#irsa-tl-cap`: texto via `_tipoLabel(r['MONEDA'])` (e.g. "Cable", "MEP S/MULC"); color: S/MULC → `#5B8DB8`, resto → `#1D4B6E`; reemplazó el texto hardcodeado "HD" / "HD s/MULC" y la lógica `TC < 0.99`
- **Badges IRSA** en `#irsa-tl-full`: texto via `_tipoLabel(r['Moneda'])` desde `irsa_deuda_total.csv`; misma lógica de color
- **Eventos de interés agrupados**: filas consecutivas de tipo `Intereses` con la misma `Fecha Fin` se muestran como un solo evento (e.g. XXII+XXIII en Jul 2026); se suman los montos y se concatenan las tasas ("5,75/7,25%")
- **Eventos de capital**: filas `Intereses + Capital` siempre generan un evento individual (nunca se agrupan)
- **Formato de montos**: `_fmtM(n)` → divide por 1e6, fija a 1 decimal, cambia punto decimal por coma (e.g. 19218167 → "19,2M")
- **Parsing de montos CSV**: `_parseNum(s)` elimina puntos de miles y reemplaza coma decimal por punto (formato europeo "19.218.167,92") — solo para `irsa_deuda_total.csv`. Los montos en `cresud_completo.csv` son floats planos ("12609341.91") y se parsean con `parseFloat()` directamente
- **Tasa en CSVs de Cresud**: formato punto decimal ("6.00%") — igual que IRSA ahora (ambos usan punto desde el cambio de schema)
- **Badges Cresud** (`_cresudCapBadge`, `_cresudFullBadge`): texto via `_tipoLabel()` para todos los tipos excepto "Prefi" (banking) y "DL"; colores: Prefi → `#1A3D2A`, DL → `#6BBF8A` (texto oscuro `#0F172A`), S/MULC → `#4A8C60`, resto → `#1A3D2A`
- **Badge DL**: requiere `badgeTextColor = '#0F172A'` en `_tlEvHtml` porque el verde claro (#6BBF8A) no contrasta con texto blanco
- **Full timeline Cresud**: fuente dual — `cresud_completo.csv` para ONs con schedule de intereses, `cresud_deuda.csv` para prefinanciaciones bancarias (BBVA, Ciudad) que no tienen cupones en el CSV completo; se mergean y reordenan por fecha
- **Columna ON en Cresud**: en `cresud_completo.csv` es `Clase` (e.g. "XLIV"); en `cresud_deuda.csv` es `Concepto`

### Colores de la timeline de intereses
- IRSA intereses: `#7AAFC8` (azul claro)
- Cresud intereses: `#7AAFC8` (mismo azul, consistencia visual)
- Clase `.tl-int` aplica estilos reducidos (fuente y stem más chicos) para eventos de interés

## Flujo de trabajo
- **Ver cambios**: el dashboard se sirve vía HTTP (GitHub Pages u otro host) — refrescar el browser tras cada commit
- **Actualizar datos de maturity walls**: editar el CSV correspondiente y hacer commit; el chart se recalcula automáticamente al cargar la página
- **Actualizar timeline IRSA**: editar `irsa_deuda.csv` (capital) o `irsa_deuda_total.csv` (capital+intereses) y hacer commit; la timeline se regenera automáticamente
- **Actualizar timeline Cresud**: editar `cresud_deuda.csv` (capital, banking) o `cresud_completo.csv` (capital+intereses de ONs) y hacer commit
- **No hay build step** — editar archivos y hacer commit directamente

### SGR (color por vehículo: Potenciar `#166534`, Garantizar `#1D4B6E`, Integra `#6D28D9`, Bind `#B45309`)
Sección nueva accesible desde la pestaña **SGR** en la nav. El nav muestra un separador visual (`<span class="nav-sep">`) entre las pestañas de Debt Profile (IRSA/Cresud) y SGR.

**Selector de vehículo** (pills): Potenciar · Garantizar · Integra · Bind Garantías · Mercado. Cada opción cambia el header (color de fondo) y el contenido de forma dinámica.

**Vista individual** (Potenciar / Garantizar / Integra / Bind):
- **KPI fila primaria** (`.sgr-foto-kpi-row`, `.sgr-kpi-primary`): Aporte, Posición, Weight, P&L, Mora — fuente: `foto_sgr.csv`; el frontend muestra siempre el registro más reciente por SGR (la tarjeta TIR sin benef. fue eliminada)
  - Aporte / Posición / P&L: número entero con separador de miles (`es-AR`); subtítulo "ARS MM" debajo del label
  - Weight: porcentaje a 1 decimal (e.g. `87.0%`)
  - P&L: con signo explícito `+` / `−`
  - Mora: porcentaje a 1 decimal
  - CSS: `.sgr-kpi-primary` — label 12px, valor 20px
  - Label de período `#sgr-foto-periodo-label`: muestra automáticamente "Datos al: mmm-aa" (e.g. "Datos al: mar-26") según el `Periodo` del registro elegido
- **KPI fila secundaria** (`.sgr-foto-kpi-row2`, `.sgr-kpi-secondary`): métricas de rendimiento — 4 boxes en una segunda fila debajo de la primaria
  - **Rend. Cartera** (`#sgr-foto-rend-cartera`): `Rendimiento Cartera` del CSV; porcentaje a 1 decimal; subtítulo "sin netear mora y fee"
  - **Benchmark** (`#sgr-foto-benchmark`): TTRFPD — valor **hardcodeado** en HTML (`46,3%`); no viene del CSV
  - **P&L neto c/benef** (`#sgr-foto-rend-neto`): `Rend. Neto c/benef` del CSV; en ARS MM, con signo (`fmtSign`)
  - **TIR c/benef impos.** (`#sgr-foto-tir-benef`): `TIR c/benef` del CSV; porcentaje a 1 decimal
  - CSS: `.sgr-kpi-secondary` — padding 8px 14px, border-left 2px, label 10.5px `#64748B`, valor 13px peso 600
  - Si una columna no tiene dato para ese período (e.g. filas feb-26), el JS muestra `—`
- **Mora/Garantías**: línea de evolución mensual de la SGR seleccionada (en su color) + línea dashed naranja del Promedio Mercado; fuente: `mora_sobre_garantias.csv`
- **Stock de Garantías**: barras Garantías + FDR por mes, línea Apalancamiento en eje derecho; fuente: `garantia_sgr.csv`
- **Mora por Antigüedad**: donut con distribución por tramos; fuente: `mora_antiguedad.csv`
- **Garantías por Sector**: donut con exposición sectorial; fuente: `garantias_sector_sgr.csv` (filtra sectores con `Weight = 0`)

**Vista Mercado**:
- Tendencia de mora: las 4 SGRs como líneas en sus colores + Promedio Mercado (naranja, 3px, dashed) — fuente: `mora_sobre_garantias.csv`
- Mora por plazo de garantía (barras horizontales); fuente: `plazo_mora_mercado.csv`
- Ranking de 42 SGRs por mora (barras horizontales, 20px/barra, scrolleable); vehículos IRSA resaltados en `#166534`; fuente: `Total_sgr.csv`; label de fecha en el título hardcodeado en HTML ("feb-26")

**Colores dinámicos**: el header de la sección cambia de gradiente al seleccionar cada vehículo. Los KPI boxes (`.sgr-kpi`) actualizan `background`, `borderColor` y `borderLeftColor` vía JS al cambiar de SGR.

**Paletas de color** (`_SGR_PALETTES`): array de 7 tonos (oscuro → claro) mapeado por color base de cada SGR; se usa para donut charts (antigüedad y sector).

**Globals de estado**:
- `_sgrGarantiasData`  — `{ csvLabel: [{fecha, garantias, fdr, apalancamiento, apalNum}] }` — ordenado por fecha
- `_sgrAntiguedadData` — `{ csvLabel: [{plazo, mora}] }`
- `_sgrSectorData`     — `{ csvLabel: [{sector, weight}] }` (sin sectores con weight=0)
- `_sgrMoraMercado`    — `[{fecha, mora}]`
- `_sgrMoraEvolucion`  — `[{fecha, potenciar, garantizar, integra, bind, promedio}]` — valores en % (e.g. 0.7 = 0.7%)
- `_sgrPlazoMercado`   — `[{plazo, mora}]`
- `_sgrTotalSgr`       — `[{sgr, mora}]`
- `_sgrFotoData`       — `{ 'POTENCIAR': {periodo, aporte, posicion, weight, pnl, mora, tir, rendCartera, rendNeto, tirConBenef}, ... }` — keyed por `fotoLabel`; solo el registro más reciente por SGR (seleccionado durante el parse de `foto_sgr.csv`)
- `_sgrActiveSgr`      — key activa ('potenciar' | 'garantizar' | 'integra' | 'bind' | 'mercado')

**Instancias de Chart.js**:
- `_sgrMoraChartInst`, `_sgrGarantiasChartInst`, `_sgrAntiguedadChartInst`, `_sgrSectorChartInst`
- `_sgrMktMoraChartInst`, `_sgrMktPlazoChartInst`, `_sgrMktRankChartInst`
- Todas se destruyen y recrean al cambiar de vehículo via `_sgrDestroy(inst)`

**Funciones principales**:
- `initSgrSection()` — carga 7 CSVs en paralelo (incluye `foto_sgr.csv`), parsea, llama `selectSgr(_sgrActiveSgr)` al terminar; se llama en init junto con los demás `initXxx()`
- `selectSgr(sgr)` — actualiza pills, header, muestra/oculta `#sgr-individual` o `#sgr-mercado`; llama al render correspondiente
- `_sgrRenderIndividual(sgr)` — actualiza KPIs y llama a los 4 renders de chart
- `_sgrRenderMercado()` — llama a los 3 renders de charts de mercado
- `_sgrParseCsv(text)` — parser CSV genérico (split por coma, sin soporte de comillas)
- `_sgrParseDMY(s)` — parsea "31/7/2025" → Date
- `_sgrMonthLabel(d)` — formatea Date → "jul-25"
- `_sgrPalette(color, n)` — retorna n colores de la paleta del SGR

**Mapeo de nombres por fuente** (definido en `SGR_META`):
- `csvLabel`: clave usada en `garantia_sgr.csv`, `mora_antiguedad.csv`, `garantias_sector_sgr.csv` (e.g. "Bind Garantias")
- `totalLabel`: clave usada en `Total_sgr.csv` (e.g. "GARANTIAS BIND S.G.R.")
- `fotoLabel`: clave usada en `foto_sgr.csv` — mayúsculas sin sufijo (e.g. "BIND")

### `foto_sgr.csv` — esquema histórico y lógica de carga

**Estructura del CSV** (columnas en orden):
```
Periodo,SGR,Aporte,Posicion,Weight,P&L,Mora,TIR,Rendimiento Cartera,Rend. Neto c/benef,TIR c/benef
```
- `Periodo`: formato `YYYY-MM` (e.g. `2026-03`) — clave de ordenamiento; ordena correctamente como string
- `SGR`: nombre en mayúsculas, sin sufijo — debe coincidir con `fotoLabel` en `SGR_META` (e.g. `POTENCIAR`, `GARANTIZAR`, `INTEGRA`, `BIND`)
- `Aporte` / `Posicion` / `P&L`: valores enteros o decimales en ARS MM
- `Weight`: fracción decimal (e.g. `0.87398` para 87.4%)
- `Mora` / `TIR`: fracción decimal (e.g. `0.007` para 0.7%, `0.444` para 44.4%)
- `Rendimiento Cartera`: fracción decimal (e.g. `0.506` para 50.6%); puede dejarse vacío (``) en períodos sin dato
- `Rend. Neto c/benef`: número entero en ARS MM (e.g. `7744`); puede dejarse vacío (``) en períodos sin dato
- `TIR c/benef`: fracción decimal (e.g. `1.112` para 111.2%); puede dejarse vacío (``) en períodos sin dato
- No incluir fila `Total` — el JS la ignora pero es mejor no agregarla
- El orden de las filas no importa — la lógica selecciona el `Periodo` más reciente por SGR

**Lógica de selección en el parse** (`initSgrSection`):
- Por cada fila se compara `r['Periodo']` con el período ya almacenado para ese SGR
- Si el nuevo período es mayor (string), reemplaza; si es igual o menor, se ignora
- En caso de filas con mismo `SGR` y mismo `Periodo`, gana la **última** en el CSV

**Cómo agregar un nuevo mes** — simplemente agregar 4 filas al final del CSV. Las tres últimas columnas son opcionales (dejar vacías si aún no están disponibles):
```csv
2026-04,POTENCIAR,11500,15200,0.875,4100,0.006,0.451,0.510,8000,1.120
2026-04,GARANTIZAR,1500,1530,0.088,185,0.041,0.152,0.330,700,0.940
2026-04,INTEGRA,392,365,0.021,-20,0.072,-0.098,0.250,110,0.430
2026-04,BIND,275,265,0.015,48,0.025,0.210,0.370,140,0.590
```
Si las columnas de rendimiento no están disponibles aún: `2026-04,POTENCIAR,11500,15200,0.875,4100,0.006,0.451,,,`

No es necesario tocar el JS — el frontend toma el período más alto automáticamente.

**Label de período en la UI**: el elemento `#sgr-foto-periodo-label` muestra "Datos al: mmm-aa" (e.g. "Datos al: mar-26"); se actualiza solo al cambiar de SGR vía `_sgrRenderIndividual`.

**CSS**:
- `.sgr-selector`, `.sgr-pill`, `.sgr-pill.active`, `.sgr-pill-sep` — selector de vehículo
- `.sgr-chart-grid` — grid 2×2 para los 4 charts individuales
- `.sgr-chart-card` — card blanca con borde `#E2E8F0`
- `.sgr-chart-title` — label de cada chart (11.5px, uppercase)
- `.sgr-kpi` — variante del `.kpi-box` base; colores se actualizan vía JS
- `.kpi-box-sm` — modificador para la fila foto: label 11px, valor 15px, padding 10px 14px; permite caber 6 tarjetas en una fila
- `.sgr-foto-kpi-row` — contenedor de la fila primaria de KPIs (Aporte, Posición, etc.); en mobile colapsa a grid 2 columnas
- `.sgr-kpi-primary` — variante de `.sgr-kpi` para fila primaria: label 12px, valor 20px
- `.sgr-foto-kpi-row2` — contenedor de la fila secundaria (Rend. Cartera, Benchmark, etc.); en mobile colapsa a grid 2 columnas
- `.sgr-kpi-secondary` — variante de `.sgr-kpi` para fila secundaria: padding 8px 14px, border-left 2px, label 10.5px `#64748B`, valor 13px
- `.sgr-legend`, `.sgr-legend-item`, `.sgr-legend-dot` — leyenda custom de donuts
- `.sgr-mkt-grid` — grid 2 columnas para la vista Mercado
- `.sgr-rank-wrap` — contenedor scrolleable del ranking
- `nav-sep` — separador visual entre Debt Profile y SGR en la nav

**Datos no usados aún** (guardados en repo para uso futuro):
- `cartera_monedas.csv` — split USD/ARS por SGR
- `composicion_carteras.csv` — composición por tipo de activo por SGR

## Qué es dinámico vs hardcodeado

| Componente | Fuente |
|---|---|
| Maturity wall IRSA (barras + tooltips) | `irsa_deuda.csv` — dinámico |
| Maturity wall Cresud (barras + tooltips) | `cresud_deuda.csv` — dinámico |
| KPI boxes (tasa y vida prom. ponderada) | Dinámico desde CSV; se recalcula con descubiertos |
| Pie charts de moneda | Dinámico desde CSV; se recalcula con descubiertos |
| Timeline IRSA (capital) | `irsa_deuda.csv` — dinámico |
| Timeline IRSA (capital + intereses) | `irsa_deuda_total.csv` — dinámico |
| Timeline Cresud (capital) | `cresud_deuda.csv` — dinámico |
| Timeline Cresud (capital + intereses) | `cresud_completo.csv` + `cresud_deuda.csv` (banking) — dinámico |
| Tabla detalle de vencimientos | Base hardcodeada en HTML; filas de descubiertos se insertan dinámicamente en sesión |
| SGR — Stock de Garantías chart | `garantia_sgr.csv` — dinámico |
| SGR — Mora/Garantías chart (individual) | `mora_sobre_garantias.csv` — dinámico |
| SGR — Mora por Antigüedad donut | `mora_antiguedad.csv` — dinámico |
| SGR — Garantías por Sector donut | `garantias_sector_sgr.csv` — dinámico |
| SGR — Mercado: tendencia mora (4 SGRs + Promedio) | `mora_sobre_garantias.csv` — dinámico |
| SGR — Mercado: mora por plazo | `plazo_mora_mercado.csv` — dinámico |
| SGR — Mercado: ranking SGRs | `Total_sgr.csv` — dinámico |
| SGR — KPI foto (Aporte, Posición, Weight, P&L, Mora) | `foto_sgr.csv` — dinámico; histórico multi-período; siempre muestra el mes más reciente por SGR |

## Diseño responsive (mobile + desktop)

El dashboard **debe verse bien tanto en desktop como en mobile** (celulares y tablets). Los jefes del equipo lo consultan desde el celular.

### Breakpoints
- **≤ 900px (tablet)**: grids colapsan a 1 columna; tablas con scroll horizontal; padding reducido
- **≤ 600px (phone)**: layout completamente simplificado — nav condensado, fuentes y padding reducidos, charts más bajos, KPI boxes apilados verticalmente, pie chart apilado, modal en columna

### Reglas CSS clave
- `.mat-table`: `display: block; overflow-x: auto; -webkit-overflow-scrolling: touch` — permite scroll horizontal en tablas largas sin cambiar el HTML
- `.kpi-row`: clase en el contenedor `div` de los KPI boxes (IRSA y Cresud) — aplica `flex-direction: column` en mobile. **Importante**: el div tiene `style="display:flex"` inline, por lo que la clase es necesaria para poder sobrescribir `flex-direction` via media query (no se puede hacer solo con clase si el inline style lo pisa)
- `.chart-wrap`: forzado a `height: 200px !important` en mobile para no ocupar demasiado espacio vertical
- `.currency-row`: pasa de horizontal a `flex-direction: column` en mobile, apilando el pie chart arriba y la leyenda abajo
- `.grid-2`, `.grid-40-60`, `.grid-35-65`: colapsan a `1fr` en tablet via `grid-template-columns: 1fr !important`

### Elementos ocultos en mobile
- `.header-title` (≤ 900px): texto largo del header
- `.nav-logo` (≤ 600px): logo en la barra de navegación
- `.header-ir` (≤ 600px): texto "Investor Relations" del header
- Columnas **Outstanding** (col 7) y **Año Fiscal** (col 8) de `.mat-table` (≤ 600px): ocultadas con `display: none` via `nth-child(7/8)` en `thead th`, `tbody td` y `tfoot td`

### Lo que NO debe cambiar en mobile
- Las timelines de cashflows se mantienen horizontales con scroll (no se rediseñan para mobile)
- Los Chart.js bars siguen siendo responsivos (Chart.js lo maneja solo con `maintainAspectRatio: false`)
- Los popovers de Call Option se posicionan con `position: fixed` — funcionan en mobile pero pueden no ser ideales en pantallas muy chicas

## Notas importantes
- El dashboard se sirve vía HTTP (GitHub Pages), por lo que `fetch()` funciona para leer los CSVs
- Los CSV de los maturity walls son la fuente de verdad — editarlos es suficiente para actualizar esos charts
- **Criterio de valuación de montos**: los CSVs de vencimientos (`irsa_deuda.csv`, `cresud_deuda.csv`) muestran el valor económico ajustado por brecha de tipo de cambio para instrumentos HD s/MULC (MEP/cable) — `Monto USD` puede diferir del nominal para estos instrumentos. Los CSVs completos (`irsa_deuda_total.csv`, `cresud_completo.csv`) muestran el valor nominal (par value) sin ajuste de brecha. Por eso los montos de capital en el timeline "Solo Capital" (fuente: CSV de vencimientos) pueden diferir de los del timeline "+ Intereses" (fuente: CSV completo) exactamente cuando el instrumento es HD s/MULC. Esto es intencional: cada timeline refleja la perspectiva de su CSV fuente.
- **Clasificación S/MULC en IRSA**: desde el cambio de schema de `irsa_deuda.csv`, la columna `MONEDA` reemplazó a `TC` como fuente de verdad para identificar instrumentos HD s/MULC. La clasificación se hace con `MONEDA.includes('S/MULC')` en lugar de `TC < 0.99`. La columna `TC` fue eliminada del CSV.
- Los demás datos financieros siguen embebidos en el HTML/JS hasta que se migren
- Montos expresados en millones de USD (MM USD) salvo aclaración
- Año fiscal de IRSA/Cresud: julio–junio (FY termina en junio)
- El archivo original se llamaba `dashboard (1).html` y fue renombrado a `index.html`
- Encoding de los CSV: UTF-8 (los archivos originales tenían corrupción de encoding que fue corregida al guardarlos)
