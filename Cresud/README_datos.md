# Contexto de datos — Cresud (para agente Mercado de Capitales)

Este archivo describe el contenido de esta carpeta para el agente de Copilot "Mercado de Capitales". Cubre deuda de Cresud: vencimientos de capital, schedule completo (capital + intereses), opciones de rescate anticipado (call) e historial de calls ya ejercidos.

## Archivos

- **`cresud_deuda.csv`** — vencimientos de **capital** de Cresud (ONs + prefinanciaciones bancarias + descubiertos). Columnas: `AÑO, FY, MONEDA, Periodo, Compañía, Sociedad, Concepto, Concepto 2, Fecha Inicio, Fecha Fin, Tasa, Moneda, Monto Webcast, Monto USD`.
- **`cresud_completo.csv`** — schedule **completo**, hasta abril 2030. Columnas: `AÑO, FY, Compañía, Sociedad, Clase, Concepto 2, Fecha Inicio, Fecha Fin, Tasa, Moneda, Monto Emitido, Outstanding, Intereses, Amortización, Capital`.
- **`cresud_call_data.csv`** — call option simple por ON. Columnas: `ON, CallDate, Price`.
- **`cresud_call_schedule.csv`** — call option escalonada por ON. Columnas: `ON, From, Price` (vacío actualmente — ninguna ON de Cresud tiene call en tramos).
- **`historial_calls.csv`** — calls ya ejercidos. Columnas: `ON, Fecha Call Ejercido, Fecha Maturity Original, Precio Call, Motivo, Monto Nominal USD, Tasa`.

## Reglas de interpretación

1. **Excluir vencidos**: nunca reportar como vigente una fila con `Fecha Fin` anterior a hoy.
2. **Excluir ARS**: filas en ARS (ej. descubierto ICBC) no forman parte de la deuda "Hard Dollar" ni de cálculos en USD. Mencionarlas aparte si preguntan por deuda total.
3. **S/MULC ≠ Monto USD del CSV**: para instrumentos con `MONEDA` que incluye `S/MULC`, no usar `Monto USD` tal cual — es referencial y no refleja el costo económico real bajo brecha MEP/CCL. El agente no tiene el input de brecha de sesión del dashboard web; si preguntan el monto ajustado, pedir la brecha a usar en vez de inventarla.
4. **Dos convenciones de valuación**: `cresud_deuda.csv` puede venir ajustado por brecha para S/MULC; `cresud_completo.csv` siempre es valor nominal (par). Diferencias entre ambos para el mismo instrumento son esperables, no error.
5. **Formato de montos**: tasa como string con `%` (ej. "6.00%"), formato punto decimal en ambos CSV.
6. **FY vs AÑO**: `FY` = año fiscal (julio–junio); `AÑO` = calendario. No son lo mismo.
7. **Intereses vs. capital**: en `cresud_completo.csv`, `Concepto 2` puede ser `Capital`, `Intereses` o `Intereses + Capital`. No sumar como si fuera todo capital.
8. **Columna de instrumento distinta según archivo**: en `cresud_completo.csv` es `Clase`; en `cresud_deuda.csv` es `Concepto`. No asumir que se llaman igual al cruzar ambos.
9. **No inventar datos faltantes**: si una columna está vacía o un instrumento no aparece, decirlo explícitamente.

## Call options

10. **Call simple** (`cresud_call_data.csv`): callable desde `CallDate`, al `Price` fijo indicado.
11. **Call escalonado** (`cresud_call_schedule.csv`): actualmente vacío — ninguna ON de Cresud tiene call en tramos; no inventar tramos si el archivo no tiene filas.
12. Un ON sin entrada en ningún archivo de call → no tiene call option.
13. "Callable" es un estado a la fecha de hoy (hoy ≥ `CallDate`), no una propiedad fija ni un vencimiento garantizado — es una opción del emisor.
14. El precio de call puede no ser 100% — aplicarlo tal cual sobre el nominal/outstanding.
15. **Calls ya ejercidos** (`historial_calls.csv`): si una ON aparece acá, ya fue cancelada anticipadamente en `Fecha Call Ejercido` — no proyectarla en su `Fecha Maturity Original`. Ejemplo: ON XLIV fue llamada el 17/07/2026 a 101% (vencimiento original 17/01/2027, USD 39.765.830 nominales, tasa 6,00%).

## Fórmulas

Ver skill `skills/kpis-tasa-vida-promedio/SKILL.md` — Tasa y Vida Promedio Ponderada sobre USD vigente, peso siempre `Monto Webcast`.

## Grounding

- Este archivo y los CSV listados están siempre disponibles — no responder "no tengo acceso" a ninguno de ellos.
- No inventar ni recordar de memoria valores de fecha/precio/monto/tasa — leerlos del CSV correspondiente en cada respuesta.
- Si un dato del usuario no coincide con el archivo, priorizar el archivo y decirlo explícitamente.