# Contexto de datos — Deals (para agente Deals — Mercado de ONs)

Este archivo describe el contenido de esta carpeta para el agente de Copilot "Deals — Mercado de ONs". Cubre el mercado secundario de ONs argentinas (curvas de rendimiento) y el registro de emisiones primarias.

## Archivos en esta carpeta

- **`curvas_on.csv`** — snapshot del informe diario IAMC "Deuda Corporativa". **Se sobreescribe** cada corrida — NO es histórico, refleja un solo día. Columnas clave: `Fecha, Ticker, Emisor, Industria, Ley, Cupon, Vencimiento, Precio_Clean, YTM, CY, DM, Monto_Emitido, ADTV_ARS`.
  - `Ley`: `Arg` (ley argentina) o `NY` (ley Nueva York) — no comparables directamente entre sí.
  - `YTM`/`CY`: decimal sin `%` (ej. `6.5` = 6,5%). `DM`: duración modificada.
  - Ticker IRSA: prefijo `IRC`. Ticker Cresud: `CS` + dígito (ej. `CS1`, `CS34`).
- **`curvas_propias_historico.csv`** — histórico diario (**se appendea**, no se sobreescribe) SOLO de tickers `IRC*` y `CS<dígito>*`. Columnas: `Fecha, Ticker, Emisor, Vencimiento, Precio_Clean, YTM, CY, DM`. Es la única fuente con serie temporal en esta carpeta — para "evolución" o "tendencia" de precio/YTM usar este archivo, nunca `curvas_on.csv`.
- **`curvas_moneda_lookup.csv`** — lookup interno Ticker → Moneda usado por el scraper; no suele necesitarse para responder preguntas de usuario.
- **`emisiones_obligaciones_negociables.csv`** — registro semanal de emisiones **primarias** del mercado argentino. Columnas: `FECHA, EMISOR, MONEDA, TASA, TASA/MARGEN, PLAZO (en meses), VN, CALIFICACIÓN`.
  - `FECHA`: formato `29-abr-26` (día-mesES-año2d). `VN`: formato argentino ("157.000,00" = 157.000).
  - `MONEDA` viene heterogénea — normalizar antes de agrupar: "USD" → "USD Mep", "USD - Int" → "USD Int", "USD - CCL" → "USD Cable", "USD - Linked" → "USD Linked". Filas con `MONEDA = "resultado pendiente"` descartar siempre.
- **`emisiones_on_bajo_impacto.csv`** — mismo formato que `emisiones_obligaciones_negociables.csv`, pero para emisiones de bajo impacto (montos chicos, por debajo del umbral que se incluye en el registro principal).

## Reglas de interpretación

1. **`curvas_on.csv` es un snapshot, no serie histórica**. Para evolución de precio/YTM usar `curvas_propias_historico.csv` (solo cubre IRSA/Cresud) — para otros emisores no hay histórico en estas carpetas.
2. **Separar por Ley** al comparar curvas de rendimiento (Arg vs. NY no son comparables directamente).
3. **Excluir outliers antes de calcular promedios/curvas**: filas sin `Precio_Clean`, con `YTM < 0%` o `YTM > 20%`, y el emisor San Miguel (reestructurado) quedan fuera salvo pedido explícito.
4. **Formato de montos**: `VN` en formato argentino (punto miles, coma decimal); `Monto_Emitido` en `curvas_on.csv` en millones USD directo.
5. **Normalizar `MONEDA`** de emisiones antes de agrupar o sumar.
6. **Primario vs. secundario**: `emisiones_obligaciones_negociables.csv` = tasa/condiciones de salida al emitir; `curvas_on.csv`/`curvas_propias_historico.csv` = pricing de mercado secundario. No mezclar tasa de emisión con YTM de mercado como si fueran lo mismo.

## Grounding

- Los archivos listados arriba (dentro de esta carpeta) están siempre disponibles — no responder "no tengo acceso" a ninguno de ellos.
- No inventar ni recordar de memoria valores de fecha/precio/YTM/monto — leerlos del CSV correspondiente en cada respuesta.
- Si un dato del usuario no coincide con el archivo, priorizar el archivo y decirlo explícitamente.
- Siempre citar la fecha del informe (columna `Fecha`) al reportar datos de `curvas_on.csv`, ya que cambia día a día.