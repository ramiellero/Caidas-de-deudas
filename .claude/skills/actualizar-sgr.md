# Skill: Actualizar datos mensuales de SGR

Guía interactiva para cargar el corte mensual nuevo de las 7 entidades SGR
(Potenciar - 25, Potenciar - 26, Garantizar - 25, Garantizar - 26, Integra - 25,
Bind Garantías - 25, Acindar - 26) + datos de Mercado. El asistente pregunta los
datos al usuario, los agrega a los CSVs de `SGR/`, y al final hace commit + push
(con confirmación).

## Vintages "-25" / "-26" (desde jun-26)

Los aportes a SGR se hacen con plazo mínimo de 2 años, por eso Potenciar y
Garantizar están separados en dos series por año de entrada. Integra, Bind y
Acindar tienen un solo vintage cada uno (no se dividen). Tabla de mapeo
(`SGR_META` en `index.html`):

| Entidad (pill) | `csvLabel` (garantia_sgr / mora_antiguedad / garantias_sector) | `fotoLabel` (foto_sgr, mayúsculas) | Columna en mora_sobre_garantias / cartera_monedas / composicion_carteras |
|---|---|---|---|
| Potenciar - 25 | `Potenciar` | `POTENCIAR` | `POTENCIAR` / `Potenciar` |
| Potenciar - 26 | `Potenciar 26` | `POTENCIAR 26` | `POTENCIAR 26` / `Potenciar 26` |
| Garantizar - 25 | `Garantizar` | `GARANTIZAR` | `GARANTIZAR` / `Garantizar` |
| Garantizar - 26 | `Garantizar 26` | `GARANTIZAR 26` | `GARANTIZAR 26` / `Garantizar 26` |
| Integra - 25 | `Integra` | `INTEGRA` | `INTEGRA` / `Integra` |
| Bind Garantías - 25 | `Bind Garantias` | `BIND` | `BIND` / `BIND` |
| Acindar - 26 | `Acindar Pymes` | `ACINDAR` | (no tiene columna — se deriva de `Total_sgr.csv`) / `ACINDAR` |

`Total_sgr.csv` y `fondo_de_riesgo.csv` son a **nivel compañía** (no por vintage) —
Potenciar-25 y Potenciar-26 comparten el mismo `totalLabel` (`POTENCIAR S.G.R.`), ídem Garantizar.

## Cuándo usar

- El usuario dice "actualizar SGR", "cargar el mes de SGR", "nuevos datos de garantías"
- Hay un mes nuevo de reporting de las SGR para cargar

---

## Flujo general

1. Preguntar el **período** (fecha de corte, e.g. `30/6/2026`, y su forma corta `2026-06` / `jun-26`).
2. Recorrer cada archivo **por categoría** (un archivo/categoría a la vez, no por vehículo) — el usuario
   prefiere pasar los datos tal como aparecen en la página fuente: por categoría, con la lista de
   SGR + valor. No agrupar preguntas por vehículo (Potenciar primero con todos sus campos, luego
   Garantizar, etc.) — eso no matchea cómo el usuario tiene la información a mano.
3. Ir agregando las filas nuevas a cada CSV con `Edit` (append al final, respetando el formato exacto de cada columna — ver tabla).
4. Al terminar todos los archivos, mostrar un resumen corto de qué se agregó a cada CSV y pedir confirmación.
5. `git add` de los CSVs tocados, commit, y **preguntar antes de hacer `git push`** (push es una acción visible/compartida — no asumir autorización).

No tocar `index.html` — todo en SGR es dinámico desde CSV (ver CLAUDE.md, tabla "Qué es dinámico vs hardcodeado").

---

## Archivos y qué preguntar

Las 7 entidades con datos manuales mes a mes: **Potenciar, Potenciar 26, Garantizar, Garantizar 26,
Integra, Bind Garantias, Acindar Pymes** (nombres exactos de `SGR_META.csvLabel` — usar tal cual en
la columna `SGR` de `garantia_sgr.csv` / `mora_antiguedad.csv` / `garantias_sector_sgr.csv`; ver
tabla de vintages arriba para las demás columnas/labels).

### 1. `SGR/garantia_sgr.csv` — Stock de Garantías
Columnas: `Fecha,SGR,Garantias,FDR,Apalancamiento`
- Preguntar por vehículo: **Garantías** (miles), **FDR** (miles), **Apalancamiento** (con `%`, e.g. `229%`)
- Una fila por SGR: `30/6/2026,Potenciar,180.500,76.200,237%`

### 2. `SGR/mora_antiguedad.csv` — Mora por Antigüedad
Columnas: `Fecha,SGR,Plazo,Mora_por_Antiguedad`
- Tramos fijos: `< 31 d`, `32 - 90 d`, `91- 180 d`, `181 - 360 d`, `> 360 d`
- Preguntar los 5 valores (fracción decimal, e.g. `0.14` = 14%) por vehículo
- 5 filas por SGR

### 3. `SGR/garantias_sector_sgr.csv` — Garantías por Sector
Columnas: `SGR,Sectores,Weight`
- **Sin columna Fecha** — este archivo se sobreescribe/actualiza por SGR, no se appendea histórico. Antes de tocar: `Grep` las filas existentes de ese SGR y reemplazarlas si el usuario da un breakdown nuevo, o dejarlas si no hay cambios este mes.
- Preguntar: lista de sectores + weight (fracción, deben sumar ~1) por vehículo — solo si el usuario tiene el dato nuevo (no es obligatorio todos los meses)

### 4. `SGR/mora_sobre_garantias.csv` — Mora/Garantías mensual
Columnas: `Fecha,POTENCIAR,POTENCIAR 26,GARANTIZAR,GARANTIZAR 26,INTEGRA,BIND,Promedio`
- **Importante**: acá las 6 entidades van en columnas (no filas), y los valores son **string con `%`** (e.g. `"0.9%"`), no fracción. Acindar Pymes NO tiene columna acá — su mora se deriva en runtime desde `Total_sgr.csv` (ver nota en CLAUDE.md), no preguntar por Acindar en este archivo. Potenciar 26 / Garantizar 26 pueden quedar vacíos hasta que tengan histórico propio.
- Preguntar los valores disponibles + calcular o pedir el Promedio (el Promedio histórico es el promedio simple de Potenciar, Garantizar, Integra, Bind — sin los "26" nuevos ni Acindar, salvo que el usuario indique lo contrario)
- Una sola fila nueva: `30/6/2026,0.9%,,6.5%,,9.1%,4.5%,5.3%`

### 5. `SGR/foto_sgr.csv` — KPIs individuales (fila por SGR)
Columnas: `Periodo,SGR,Aporte,Posicion,Weight,P&L,Mora,TIR,Rendimiento Cartera,Rend. Neto c/benef,TIR c/benef`
- `SGR` en mayúsculas: `POTENCIAR, POTENCIAR 26, GARANTIZAR, GARANTIZAR 26, INTEGRA, BIND, ACINDAR`
- Preguntar por entidad: **Aporte, Posición, P&L** (ARS MM), **Weight, TIR, Rendimiento Cartera** (fracción decimal), **Rend. Neto c/benef** (ARS MM), **TIR c/benef** (fracción decimal)
- **Mora**: NO preguntar — se completa solo con el valor de esa misma entidad ya cargado en `mora_sobre_garantias.csv` para el mismo mes (columna `POTENCIAR`/`POTENCIAR 26`/etc., como fracción — `6.7%` → `0.067`). Para Acindar, dejar vacío (su mora se deriva de `Total_sgr.csv`, no de este archivo).
- Las últimas 3 columnas (Rendimiento Cartera, Rend. Neto c/benef, TIR c/benef) son opcionales — si el usuario no tiene el dato todavía, dejar vacío
- Si el usuario indica que se omita un TIR/TIR c/benef negativo puntual, respetarlo (no es la regla general, es a pedido)
- 7 filas nuevas (una por entidad), `Periodo` = `YYYY-MM`

### 6. `SGR/cartera_monedas.csv` — Composición por Moneda
Columnas: `Fecha,Moneda,Potenciar,Potenciar 26,Garantizar,Garantizar 26,Integra,BIND,ACINDAR`
- Dos filas nuevas por mes: una `USD` y una `ARS`, con el weight fracción (0-1) de cada entidad; USD+ARS deben sumar ~1 por columna
- Preguntar el % USD por entidad (el ARS sale de 1 − USD)

### 7. `SGR/composicion_carteras.csv` — Composición por tipo de activo (no usado aún en frontend, pero se mantiene)
Columnas: `Fecha,Categoria,Potenciar,Potenciar 26,Garantizar,Garantizar 26,Integra,BIND,ACINDAR`
- Preguntar solo si el usuario tiene el dato a mano; si no, **omitir este archivo** (no bloquea el resto del flujo)

### Datos de Mercado (no por vehículo)

### 8. `SGR/mora_mercado.csv` — Mora mensual de mercado
Columnas: `Fecha,Mora` — `Fecha` en formato corto `mmm-aa` (e.g. `jun-26`), `Mora` fracción decimal
- Preguntar un solo valor

### 9. `SGR/plazo_mora_mercado.csv` — Mora por plazo de garantía (mercado)
Columnas: `Fecha,Plazo,Mora`
- Tramos: `< 31 dias`, `< 90 dias`, `< 180 dias`, `< 365 dias`, `> 365 dias`
- Preguntar los 5 valores (fracción decimal)

### 10. `SGR/Total_sgr.csv` — Ranking ~42 SGRs por mora
Columnas: `Fecha,SGR,Mora`
- Este es un ranking de mercado completo (42 SGRs), normalmente viene de una tabla/reporte externo.
- **No preguntar campo por campo** — pedir al usuario que pegue la tabla completa (texto o Excel) y parsearla. Si no la tiene todavía, se puede omitir este paso y volver después (recordar que `Total_sgr.csv` también alimenta la mora de Acindar Pymes, así que sin esto Acindar queda sin mora ese mes).

### 11. `SGR/fondo_de_riesgo.csv` — Ranking por Fondo de Riesgo
Columnas: `SGR,Valor_Mercado`
- **Snapshot único, se sobreescribe completo** (no se appendea) — confirmar con el usuario si tiene el ranking actualizado; si no lo tiene, dejar el archivo como está.
- Igual que Total_sgr, pedir que pegue la tabla si la tiene.

---

## Formato de preguntas sugerido (por categoría, no por vehículo)

Preguntar **una categoría/archivo a la vez**, pidiendo el valor de los 5 SGR para esa categoría —
así es como el usuario tiene los datos disponibles en su página fuente. Ejemplo:

> Pasame **Garantías / FDR / Apalancamiento** para cada SGR (Potenciar, Garantizar, Integra, Bind, Acindar).

Recién cuando esa categoría está completa (los 5 SGR, o los que apliquen), pasar a la siguiente
categoría (Mora por Antigüedad, Mora/Garantías, Foto KPIs, % USD, etc.). No mezclar campos de
distintas categorías en la misma pregunta, y no pedir "todos los campos de un vehículo" de una vez.

Si el usuario prefiere pegar todo junto en una tabla/Excel, parsear directamente en vez de seguir
preguntando campo por campo.

---

## Al terminar

1. Mostrar resumen: qué archivos se modificaron y cuántas filas se agregaron a cada uno.
2. `git status` / `git diff --stat` de los CSVs de `SGR/` para que el usuario confirme visualmente.
3. `git add SGR/<archivos tocados>` + commit con mensaje descriptivo (e.g. `SGR: carga datos jun-26`).
4. **Preguntar explícitamente antes de `git push`** — no pushear automáticamente sin confirmación, aunque el resto del flujo haya sido aprobado.
5. Recordar al usuario que Vercel redespliega solo tras el push (no hace falta ningún otro paso).
