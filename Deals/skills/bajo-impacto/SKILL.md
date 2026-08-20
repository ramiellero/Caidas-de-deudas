---
name: bajo-impacto
description: Regla transversal sobre cuándo incluir emisiones_on_bajo_impacto.csv en totales agregados de emisiones para no distorsionar promedios. Usar en cualquier análisis agregado (totales, promedios, conteos) de emisiones cerradas.
---

# Cuándo incluir emisiones de bajo impacto

## Regla
- **Por defecto, NO sumar** `emisiones_on_bajo_impacto.csv` a los totales de `emisiones_obligaciones_negociables.csv` — son emisiones de montos chicos que distorsionan promedios de tasa/plazo si se mezclan con el mercado principal.
- Mostrarlas **aparte**, como dato complementario, cuando el usuario pida panorama completo o pregunte explícitamente por emisiones chicas/bajo impacto.
- Si el usuario pide "todas las emisiones" sin calificar, preguntar si quiere incluir bajo impacto o mantener el corte estándar del mercado principal.
- Mismo esquema de columnas que el CSV principal — misma lógica de normalización de `MONEDA` y mismo formato de `FECHA`/`VN` aplica a ambos.

## Output esperado
Cuando se mencionan ambos, dejarlo explícito: "X emisiones principales (VN total) + Y de bajo impacto (VN total, mostradas aparte)".