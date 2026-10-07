---
name: pricing-vs-curva
description: Evalúa si una emisión de ON salió "tight" o "wide" comparando su tasa de corte contra la curva secundaria (curvas_on.csv). Usar cuando preguntan si una emisión salió cara/barata/en línea con el mercado.
---

# Evaluar si una emisión "pricing tight/wide" vs. la curva secundaria

## Datos
- `Deals/emisiones_obligaciones_negociables.csv` — tasa/margen y plazo de la emisión a evaluar.
- `Deals/curvas_on.csv` — curva secundaria vigente (YTM por duración, Ley, sector) para construir el comparable.

## Procedimiento
1. Ubicar la emisión en `emisiones_obligaciones_negociables.csv`: `EMISOR`, `TASA/MARGEN`, `PLAZO (en meses)`, `MONEDA`.
2. En `curvas_on.csv`, filtrar bonos de **la misma `Ley`** (Arg vs NY — no mezclar) e idealmente del mismo `Industria`/sector que el emisor.
3. Buscar el/los bono(s) con `DM` (duración modificada) más cercano al plazo de la emisión nueva (convertir `PLAZO (en meses)` a años ≈ referencia de duración, sabiendo que no es exactamente lo mismo que DM — aclarar esa diferencia si la precisión importa).
4. Comparar la tasa de salida de la emisión contra el `YTM` de esos comparables:
   - Tasa de salida **menor** al YTM de mercado comparable → priceó "tight" (más caro para el inversor, mejor para el emisor).
   - Tasa de salida **mayor** → priceó "wide" (concesión de tasa para colocar).
5. Chequear liquidez de los comparables con `ADTV_USD` de `curvas_on.csv` (US$ de volumen diario promedio): si el comparable más cercano en DM tiene ADTV muy bajo (orden de < US$ 25 mil), su YTM es poco representativo — preferir otro comparable más líquido y decirlo.
6. Si no hay comparables razonables (sector muy distinto, sin bonos de esa Ley con duración similar), decirlo explícitamente en vez de forzar una comparación floja.

## Output esperado
Conclusión corta (tight/wide/en línea) + los bonos comparables usados y su YTM, para que sea auditable. Nunca dar la conclusión sin mostrar contra qué se comparó.