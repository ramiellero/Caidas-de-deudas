# Contexto de datos — StoneX (para agente Deals — Mercado de ONs)

Esta carpeta contiene el scraper que carga semanalmente `emisiones_obligaciones_negociables.csv` (`Deals/`) a partir del informe "Agenda de Emisiones" de StoneX. La mayoría de los archivos son scripts/debugging del scraper, **no datos para responder preguntas** — el agente debe ignorarlos.

## Archivos relevantes para el agente

- **`difusion.csv`** — licitaciones **anunciadas pero aún sin resultado** (pipeline, "operaciones en difusión"), no confundir con emisiones ya cerradas. Columnas: `FECHA LICITACIÓN, FECHA LIQUIDACIÓN, EMISOR, MONEDA, TASA, TASA/MARGEN, PLAZO (en meses), CALIFICACIÓN`. `TASA/MARGEN` siempre vale `"A licitar"` (todavía no hay precio de corte). Las licitaciones con `FECHA LICITACIÓN` ya pasada se eliminan automáticamente en cada corrida del scraper — lo que queda en el archivo es agenda futura vigente.
- **`deals.csv`** — backup local de las emisiones ya cerradas, mismo contenido que `emisiones_obligaciones_negociables.csv` (`Deals/`) pero en otro formato: separador `;`, `FECHA` en `DD/MM/YYYY`, `VN` como número decimal plano (ej. `157.0` = USD 157M, no `"157.000,00"`). **No es fuente adicional** — es la misma información en otro layout. Si `emisiones_obligaciones_negociables.csv` está disponible, usar ese como fuente primaria por consistencia de formato; usar `deals.csv` solo si el otro no está accesible.

## Archivos a ignorar (no son datos)

`actualizar_deals.py`, `prueba_stonex.py`, `parser_completo.py`, `excel_a_csv_base.py`, `texto_extraido_stonex.txt`, `screenshot_stonex.png`, `CLAUDE.md` — son código y artefactos de debugging del scraper (uso interno de desarrollo), no información de mercado para responder consultas.

## Reglas de interpretación

1. **Difusión vs. cerrado**: `difusion.csv` = licitación anunciada, sin tasa de corte todavía (`"A licitar"`). `emisiones_obligaciones_negociables.csv` = licitación ya resuelta, con `TASA/MARGEN` real. No mezclar ambos como si fueran el mismo tipo de dato — si preguntan "¿qué se licita esta semana?" es `difusion.csv`; si preguntan "¿qué se emitió?" es el CSV de emisiones cerradas.
2. **Normalización de `MONEDA`**: igual que en `emisiones_obligaciones_negociables.csv` — `USD Mep`, `USD Cable`, `USD Linked`, `ARS`; bonos con `[Ley NY]` se reclasifican como `USD Int`.
3. **No proyectar `difusion.csv` como emisión confirmada**: es agenda anunciada, no un hecho cerrado — la tasa/margen final puede diferir o la licitación puede no concretarse.

## Grounding

- `difusion.csv` está siempre disponible si esta carpeta fue otorgada — no responder "no tengo acceso".
- No inventar tasas de corte para deals en difusión — todavía no existen (`TASA/MARGEN = "A licitar"`).
- Si un dato del usuario no coincide con el archivo, priorizar el archivo y decirlo explícitamente.