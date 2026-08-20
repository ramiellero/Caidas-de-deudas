---
name: concentracion-emisiones
description: Detecta concentración de oferta de emisiones de ONs por moneda o emisor en una ventana temporal, marcando cuando una categoría domina el volumen. Usar cuando preguntan por tendencias o concentración de emisiones ("qué moneda domina", "hay mucha oferta en X").
---

# Detectar concentración de oferta por moneda/emisor

## Datos
- `Deals/emisiones_obligaciones_negociables.csv` (emisiones principales; sumar `emisiones_on_bajo_impacto.csv` solo si el usuario pide el panorama completo — ver skill `bajo-impacto`).

## Procedimiento
1. Definir la ventana temporal (pedirla si no está clara — "últimas" sin período es ambiguo: proponer 30 o 90 días como default razonable y aclarar cuál se usó).
2. Normalizar `MONEDA` (ver reglas del `README_datos.md`) antes de agrupar.
3. Agrupar por `MONEDA` normalizada: contar emisiones y sumar `VN`.
4. Calcular el % que representa cada moneda sobre el `VN` total de la ventana.
5. Marcar concentración **alta** si una sola moneda supera 60% del VN total de la ventana — umbral orientativo del agente, aclararlo como tal.
6. Si se pide por sector/emisor en vez de moneda, mismo procedimiento pero agrupando por `EMISOR` (no hay columna de sector en este CSV — si se necesita sector, cruzar por nombre de emisor contra `Industria` de `curvas_on.csv`, y aclarar que es un cruce aproximado por nombre, no una clave garantizada).

## Output esperado
Tabla o lista corta: moneda → cantidad de emisiones → VN → % del total. Mencionar explícitamente si se detectó concentración alta.