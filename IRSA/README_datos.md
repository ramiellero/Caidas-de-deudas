# Contexto de datos — IRSA (para agente Mercado de Capitales)

Este archivo describe el contenido de esta carpeta para el agente de Copilot "Mercado de Capitales". Cubre deuda de IRSA: vencimientos de capital, schedule completo (capital + intereses) y opciones de rescate anticipado (call).

## Archivos

- **`irsa_deuda.csv`** — vencimientos de **capital** de IRSA. Columnas: `AÑO, FY, MONEDA, Periodo, Compañía, Sociedad, Concepto, Concepto 2, Fecha Inicio, Fecha Fin, Tasa, Moneda, Monto Webcast, Monto USD, Outstanding`.
- **`irsa_deuda_total.csv`** — schedule **completo** (capital + intereses), 2025–2035. Columnas: `AÑO, FY, Detalle, Compañía, Sociedad, ON, Concepto, Fecha Inicio, Fecha Fin, Tasa, Moneda, Monto Emitido, Outstanding, Intereses, Amortización, Capital`.
- **`irsa_call_data.csv`** — call option simple por ON. Columnas: `ON, CallDate, Price`.
- **`irsa_call_schedule.csv`** — call option escalonada (varios tramos) por ON. Columnas: `ON, From, Price`.

## Reglas de interpretación

1. **Excluir vencidos**: nunca reportar como vigente una fila con `Fecha Fin` anterior a hoy.
2. **Excluir ARS**: filas en ARS (ej. descubierto Cohen) no forman parte de la deuda "Hard Dollar" ni de cálculos en USD. Mencionarlas aparte si preguntan por deuda total.
3. **S/MULC ≠ Monto USD del CSV**: para instrumentos con `MONEDA` que incluye `S/MULC`, no usar `Monto USD` tal cual — es referencial y no refleja el costo económico real bajo brecha MEP/CCL. El agente no tiene el input de brecha de sesión del dashboard web; si preguntan el monto ajustado, pedir la brecha a usar en vez de inventarla.
4. **Dos convenciones de valuación**: `irsa_deuda.csv` puede venir ajustado por brecha para S/MULC; `irsa_deuda_total.csv` siempre es valor nominal (par). Diferencias entre ambos para el mismo instrumento son esperables, no error.
5. **Formato de montos**: tasa como string con `%` (ej. "8.75%"); montos en `irsa_deuda_total.csv` en formato europeo ("19.218.167,92").
6. **FY vs AÑO**: `FY` = año fiscal (julio–junio); `AÑO` = calendario. No son lo mismo.
7. **Intereses vs. capital**: en `irsa_deuda_total.csv`, `Concepto` distingue "Intereses" (solo cupón) de "Intereses + Capital" (cuota con amortización). No sumar como si fuera todo capital.
8. **No inventar datos faltantes**: si una columna está vacía o un instrumento no aparece, decirlo explícitamente.

## Call options

9. **Call simple** (`irsa_call_data.csv`): callable desde `CallDate`, al `Price` fijo indicado.
10. **Call escalonado** (`irsa_call_schedule.csv`): callable desde el primer `From`; el precio vigente es el del **último tramo cuyo `From` ya pasó**. Ejemplo: ON XIV es callable desde 22/06/2025 a 104,375%, baja a 102,1875% desde el 22/06/2026, y a 100% desde el 01/01/2027.
11. Un ON sin entrada en ninguno de los dos archivos → no tiene call option.
12. "Callable" es un estado a la fecha de hoy (hoy ≥ fecha de call), no una propiedad fija ni un vencimiento garantizado — es una opción del emisor.
13. El precio de call puede no ser 100% — aplicarlo tal cual sobre el nominal/outstanding.

## Fórmulas

**Tasa Promedio Ponderada** (sobre USD vigente):
```
Σ (Monto Webcast_i × Tasa_i) / Σ (Monto Webcast_i)
```

**Vida Promedio Ponderada**:
```
Σ (Monto Webcast_i × Años_i) / Σ (Monto Webcast_i)
```
donde `Años_i` = (Fecha Fin − hoy) / 365 (días exactos).

El peso siempre es `Monto Webcast` (nominal), nunca el monto ajustado por brecha.

## Grounding

- Este archivo y los CSV listados están siempre disponibles — no responder "no tengo acceso" a ninguno de ellos.
- No inventar ni recordar de memoria valores de fecha/precio/monto/tasa — leerlos del CSV correspondiente en cada respuesta.
- Si un dato del usuario no coincide con el archivo, priorizar el archivo y decirlo explícitamente.