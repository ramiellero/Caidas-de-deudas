# Dashboard — Perfil de Vencimientos de Deuda (IRSA & Cresud)

## Descripción del proyecto
Dashboard web estático (single HTML file) que visualiza el perfil de vencimientos de deuda de **IRSA** y **Cresud**. Período de referencia: IIQ FY2026.

## Estructura del proyecto
```
index.html            # Toda la aplicación: HTML + CSS + JS en un único archivo
irsa_deuda.csv        # Vencimientos de capital de IRSA (fuente principal de KPIs IRSA)
irsa_deuda_total.csv  # Schedule completo IRSA: capital + intereses por período
cresud_deuda.csv      # Vencimientos de capital de Cresud (fuente principal de KPIs Cresud)
cresud_completo.csv   # Schedule completo Cresud: capital + intereses por período
CLAUDE.md             # Este archivo
```

## Arquitectura del archivo `index.html`
El archivo está organizado en tres bloques principales dentro de un único `.html`:

1. **`<style>`** — CSS completo embebido (Inter font, grid layouts, tablas, charts, timeline, responsive)
2. **`<body>`** — HTML con dos secciones (`#page-irsa` y `#page-cresud`) más la navegación
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
- **KPI boxes** (entre el chart y la timeline):
  - Tasa Promedio Ponderada (USD): **7,86%**
  - Vida Promedio Ponderada (USD): **6,4 años**
  - Base: `irsa_deuda.csv`, calculado al 17/03/2026 sobre deuda USD vigente (~651,6 MM USD). Excluye Cohen (ARS, vencido 30/01/2026).
- Tabla detalle de vencimientos por instrumento
- Pie chart de composición por moneda
- Timeline de cashflows con toggle **Solo Capital / + Intereses** (`setIrsaTlView`)
  - `#irsa-tl-cap`: timeline solo capital (min-width 1020px, 9 eventos)
  - `#irsa-tl-full`: timeline capital + intereses (min-width 3500px, 36 eventos)

### Cresud (color: `#1A3D2A` verde oscuro)
- Maturity wall chart con toggle Año Fiscal / Año Calendario (`setCresudMatView`)
- **KPI boxes** (entre el chart y la timeline):
  - Tasa Promedio Ponderada (USD): **5,76%**
  - Vida Promedio Ponderada (USD): **1,7 años**
  - Base: `cresud_deuda.csv`, calculado al 17/03/2026 sobre deuda USD vigente (391,3 MM USD). Excluye XXXVIII (vencida 03/03/2026) e ICBC (ARS, vencido 01/02/2026).
- Timeline de cashflows con toggle **Solo Capital / + Intereses** (`setCresudTlView`)
  - `#cresud-tl-cap`: timeline solo capital (min-width 1200px, 13 eventos)
  - `#cresud-tl-full`: timeline capital + intereses (min-width 4200px, 42 eventos). Fuente: `cresud_completo.csv`
- Callout boxes con notas destacadas (borde dashed naranja `#E8960C`)
- Pie chart de composición por moneda

## Datos fuente (CSV)

### `irsa_deuda.csv`
Vencimientos de capital de IRSA. Columnas: `AÑO, FY, Detalle, Período, Compañía, Sociedad, Concepto, Concepto 2, Fecha Inicio, Fecha Fin, Tasa, Moneda, Monto MO, Monto USD, TC`.
- Usado para calcular KPIs de tasa y vida promedio ponderada de IRSA
- ONs cubiertas: XIV, XVIII, XX, XXII, XXIII, XXIV
- Incluye un descubierto en ARS (Cohen, vencido 30/01/2026)
- `Monto MO`: monto en moneda original; `Monto USD`: equivalente USD; `TC`: tipo de cambio usado

### `irsa_deuda_total.csv`
Schedule completo de IRSA con todos los flujos. Columnas: `AÑO, FY, Detalle, Compañía, Sociedad, ON, Concepto, Fecha Inicio, Fecha Fin, Tasa, Moneda, Monto Emitido, Outstanding, Intereses, Amortización, Capital`.
- `Concepto` puede ser: `Intereses`, `Intereses + Capital`
- Usado para construir la timeline `#irsa-tl-full`
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
- Variables de color inline (`style="color:#1D4B6E"`) para colores de marca específicos por empresa
- Clases utilitarias: `.grid-2`, `.grid-40-60`, `.grid-35-65` para layouts de dos columnas
- Colores de texto base: `#0F172A` (títulos), `#334155` (body), `#64748B` (muted), `#94A3B8` (placeholder)
- Fondo general: `#EAECEF`

### JS
- Tab switching: `switchTab(co)` — alterna `.page.active` y `.nav-tab.active`
- Charts: instancias de `Chart` inicializadas al cargar la página
- `setIrsaMatView(mode, btn)` — toggle Año Fiscal / Año Calendario en maturity wall IRSA
- `setCresudMatView(mode, btn)` — ídem para Cresud
- `setIrsaTlView(mode, btn)` — toggle Solo Capital / + Intereses en timeline IRSA; controla `#irsa-tl-cap`, `#irsa-tl-full`, `#irsa-tl-int-legend`
- `setCresudTlView(mode, btn)` — ídem para Cresud; controla `#cresud-tl-cap`, `#cresud-tl-full`, `#cresud-tl-int-legend`
- Fecha dinámica en el header: IIFE al final del `<script>` popula todos los `.header-today` con la fecha actual en formato `dd/mm/yyyy` usando `new Date()`
- No hay frameworks JS — vanilla JS puro

### Colores de la timeline de intereses
- IRSA intereses: `#7AAFC8` (azul claro)
- Cresud intereses: `#7AAFC8` (mismo azul, consistencia visual)
- Clase `.tl-int` aplica estilos reducidos (fuente y stem más chicos) para eventos de interés

## Flujo de trabajo
- **Ver cambios**: abrir `index.html` directamente en el browser y refrescar (F5) tras cada edición
- **No hay build step** — editar y refrescar directamente
- **Datos hardcodeados** en el HTML/JS — no hay API ni backend

## Notas importantes
- Todos los datos financieros están embebidos directamente en el HTML/JS (no se leen los CSV en runtime)
- Los CSV son fuente de verdad para recalcular métricas y reconstruir timelines manualmente
- Montos expresados en millones de USD (MM USD) salvo aclaración
- Año fiscal de IRSA/Cresud: julio–junio (FY termina en junio)
- El archivo original se llamaba `dashboard (1).html` y fue renombrado a `index.html`
- Encoding de los CSV: UTF-8 (los archivos originales tenían corrupción de encoding que fue corregida al guardarlos)
