# Skill: Agregar Nueva ON (Obligación Negociable)

Cuando el usuario pega el texto del prospecto/licitación de una ON nueva de IRSA o Cresud,
extraer los datos, calcular los cupones y agregar las filas a los CSVs correspondientes.

## Cuándo usar

- El usuario pega texto de un resultado de licitación o prospecto de ON
- Menciona "nueva ON", "Clase XXX", "emisión de ON"
- Pide agregar un bono nuevo al dashboard

---

## Datos a extraer del prospecto

| Campo | Dónde aparece en el prospecto |
|---|---|
| Empresa | IRSA o Cresud (contexto / encabezado) |
| Clase | "Obligaciones Negociables Clase XXX" |
| VN a emitirse | "Valor Nominal a Emitirse: USD X" |
| Fecha de Emisión | "Fecha de Emisión y Liquidación" |
| Fecha de Vencimiento | "Fecha de Vencimiento" |
| Tasa de Interés | "Tasa de Interés: X,XX%" |
| Amortización | "Amortización" — bullet (1 cuota) o amortización parcial |
| Fechas de pago de intereses | "Fechas de Pago de Intereses" |
| Lugar de pago / liquidación | "Forma y Lugar de Pago" |

---

## Determinar MONEDA (campo crítico — preguntar siempre si no es inequívoco)

| Liquidación | `MONEDA` en CSV capital | `Moneda` en CSV completo |
|---|---|---|
| Cable / USD Int (ley NY, exterior) | `Cable` | `USD Int` |
| MEP en Argentina, sin restricción MULC | `MEP` | `USD MEP - ARGENTINA` |
| MEP en Argentina, **S/MULC** | `MEP S/MULC` | `USD MEP - ARGENTINA S/MULC` |
| Dólar Linked | `DL` | `Dólar Linked` |

**Regla práctica**: si el prospecto dice "en la Argentina a través de Caja de Valores" → MEP.
Confirmar siempre si es con o sin acceso al MULC antes de escribir los CSVs.

---

## Calcular cupones (convención Actual/365)

Para cada período de intereses:

```
días = (fecha_fin - fecha_inicio).days
intereses = VN × tasa_anual × días / 365
```

Formato en CSV: separador de miles = punto, decimal = coma → `"940.068,49"`

### Ejemplo ON XXV (3.75%, bullet, semestral)
- Cupón 1: 8-jun-26 → 8-dic-26 = 183 días → 50.000.000 × 3,75% × 183/365 = **940.068,49**
- Cupón 2 + Capital: 8-dic-26 → 8-jun-27 = 182 días → 50.000.000 × 3,75% × 182/365 = **934.931,51**

---

## Archivos a editar

### IRSA
- `irsa_deuda.csv` — 1 fila por tranche de amortización
- `irsa_deuda_total.csv` — 1 fila por pago (cupones intermedios + último con capital)

### Cresud
- `cresud_deuda.csv` — 1 fila por tranche de amortización
- `cresud_completo.csv` — 1 fila por pago

---

## Formato `irsa_deuda.csv` / `cresud_deuda.csv` (CSV capital)

Columnas: `AÑO,FY,MONEDA,Periodo,Compañía,Sociedad,Concepto,Concepto 2,Fecha Inicio,Fecha Fin,Tasa,Moneda,Monto Webcast,Monto USD,Outstanding`

**Reglas por campo**:
- `AÑO`: año calendario de `Fecha Fin`
- `FY`: año fiscal (jul–jun). Si `Fecha Fin` es jul–dic → `FY{año+1}`; si es ene–jun → `FY{año}`
- `MONEDA`: ver tabla arriba (`Cable`, `MEP`, `MEP S/MULC`, `DL`)
- `Periodo`: si es el FY en curso y hay vencimientos por quarter → `"IVQ YY"` o similar; si es FY futuro → solo el año (`"2027"`)
- `Compañía` / `Sociedad`: `"3000 - IRSA Inversiones y Repr"` para IRSA; `"1000 - Cresud S.A.C.I.F.A."` para Cresud
- `Concepto`: número romano de la clase (e.g. `XXV`)
- `Concepto 2`: `"Mdo de capitales"` para ONs
- `Fecha Inicio`: fecha de emisión (dd/mm/aaaa)
- `Fecha Fin`: fecha de vencimiento de esa tranche (dd/mm/aaaa)
- `Tasa`: formato punto decimal, con % → `"3.75%"`
- `Moneda`: `"USD"` (siempre, para ONs en dólares)
- `Monto Webcast` / `Monto USD`: VN en USD (igual para instrumentos sin ajuste de brecha; diferente para S/MULC si aplica ajuste)
- `Outstanding`: capital remanente (= suma de esta tranche + todas las futuras del mismo instrumento)

**Fila ejemplo (ON XXV)**:
```
2027,FY2027,MEP S/MULC,2027,3000 - IRSA Inversiones y Repr,3000 - IRSA Inversiones y Repr,XXV,Mdo de capitales,08/06/2026,08/06/2027,3.75%,USD,50000000,50000000,50000000
```

---

## Formato `irsa_deuda_total.csv` (CSV completo con intereses)

Columnas: `AÑO,FY,Detalle,Compañía,Sociedad,ON,Concepto,Fecha Inicio,Fecha Fin,Tasa,Moneda,Monto Emitido,Outstanding,Intereses,Amortización,Capital`

**Reglas por campo**:
- `AÑO`: año calendario de `Fecha Fin`
- `FY`: año fiscal de `Fecha Fin`
- `Detalle`: siempre `"HD"`
- `ON`: número romano de la clase (e.g. `XXV`) — columna `ON`, no `Concepto`
- `Concepto`: `"Intereses"` para cupones intermedios; `"Intereses + Capital"` para el último pago
- `Tasa`: formato coma decimal, con % entre comillas → `"3,75%"`
- `Moneda`: valor largo según tabla MONEDA (e.g. `"USD MEP - ARGENTINA S/MULC"`)
- `Monto Emitido`: VN total emitido (solo en filas `Intereses + Capital`; vacío en `Intereses`)
- `Outstanding`: saldo vigente al inicio del período
- `Intereses`: monto en formato europeo entre comillas → `"940.068,49"`
- `Amortización`: porcentaje (e.g. `100%`) — solo en `Intereses + Capital`; vacío en `Intereses`
- `Capital`: monto nominal en formato europeo (e.g. `50.000.000`) — solo en `Intereses + Capital`

**Filas ejemplo (ON XXV)**:
```
2026,FY2027,HD,3000 - IRSA Inversiones y Repr,3000 - IRSA Inversiones y Repr,XXV,Intereses,08/06/2026,08/12/2026,"3,75%",USD MEP - ARGENTINA S/MULC,,50000000,"940.068,49",,
2027,FY2027,HD,3000 - IRSA Inversiones y Repr,3000 - IRSA Inversiones y Repr,XXV,Intereses + Capital,08/12/2026,08/06/2027,"3,75%",USD MEP - ARGENTINA S/MULC,50000000,50000000,"934.931,51",100%,50.000.000
```

---

## Formato `cresud_completo.csv` (diferencias respecto a IRSA)

Columnas: `AÑO,FY,Compañía,Sociedad,Clase,Concepto 2,Fecha Inicio,Fecha Fin,Tasa,Moneda,Monto Emitido,Outstanding,Intereses,Amortización,Capital`

Diferencias clave vs `irsa_deuda_total.csv`:
- No tiene columna `Detalle`
- La ON se llama `Clase` (no `ON`)
- El tipo de pago se llama `Concepto 2` (no `Concepto`) — valores: `Capital`, `Intereses`, `Intereses + Capital`
- Los montos en `cresud_completo.csv` son floats planos sin formato europeo (e.g. `12609341.91`), no `"12.609.341,91"`

---

## Call option

Si el prospecto menciona una opción de rescate anticipado:
- Agregar entrada en el objeto `callData` de `index.html`
- Ver sección "Call Option" en CLAUDE.md para el formato exacto

Si no hay call option → no tocar `index.html`.

---

## Checklist al procesar un prospecto

- [ ] Identificar empresa (IRSA / Cresud)
- [ ] Extraer: Clase, VN, Fecha Emisión, Fecha Vencimiento, Tasa, frecuencia de cupones, fechas de pago
- [ ] Confirmar MONEDA con el usuario (MEP / MEP S/MULC / Cable / DL)
- [ ] Calcular intereses de cada período (Actual/365)
- [ ] Agregar fila(s) al CSV de capital
- [ ] Agregar filas al CSV completo (una por fecha de pago)
- [ ] Verificar `Outstanding` en CSV capital (acumulado reverso si hay amortización parcial)
- [ ] Si hay call option → actualizar `callData` en `index.html`
- [ ] Hacer commit
