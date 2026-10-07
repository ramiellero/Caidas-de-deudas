---
name: seguimiento-on-propias
description: Trackea la evolución de precio y YTM en el mercado secundario de las ONs propias de IRSA y Cresud usando el histórico diario, y marca movimientos relevantes. Usar cuando preguntan cómo viene el pricing de un bono propio o si hubo un movimiento anormal.
---

# Seguimiento de pricing secundario de ONs propias (IRSA/Cresud)

## Datos
- `Deals/curvas_propias_historico.csv` — única fuente con serie temporal para tickers `IRC*` (IRSA) y `CS<dígito>*` (Cresud).

## Procedimiento
1. Filtrar por el `Ticker` pedido (o listar los disponibles si el usuario no especifica cuál).
2. Ordenar por `Fecha` ascendente.
3. Calcular la variación entre la primera y última observación del rango pedido (o últimos 30 días si no se especifica): `ΔYTM` en puntos básicos, `ΔPrecio_Clean` en % del par.
4. Marcar como movimiento **relevante** si `|ΔYTM| ≥ 50bps` en la ventana evaluada — es un umbral orientativo, aclarar que es una heurística propia del agente, no un dato del CSV.
5. Si el usuario pregunta por liquidez, flujo o canje: `ADTV_USD` (volumen diario promedio en US$), `Var_Px_Pct`/`Var_YTM_bps` (variación diaria) y `Canje_Pct` están en el mismo CSV pero **solo desde 2026-10-06** (antes vacíos) — no inventar valores previos ni promediar celdas vacías como cero. Las ruedas 01, 02 y 05/10 fueron completadas retroactivamente y no tienen `DM` ni estas columnas.
6. No confundir esta serie con `curvas_on.csv` (snapshot de un solo día) — si el usuario pide "hoy", puede responderse con la última fecha disponible en `curvas_propias_historico.csv`, aclarando qué fecha es.

## Fuera de alcance de este agente
Este agente **no tiene acceso** a `IRSA/irsa_call_data.csv` ni `Cresud/cresud_call_data.csv` (eso es del agente "Mercado de Capitales"). Si el usuario pregunta si el movimiento de precio se explica por una call próxima, aclarar que no tenés esa información acá y sugerir consultar al otro agente.

## Output esperado
Serie resumida (no necesariamente todos los puntos): fecha inicial vs. final, ΔYTM, ΔPrecio, y si superó el umbral de relevancia.