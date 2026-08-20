---
name: resumen-semanal
description: Arma el resumen semanal del mercado de ONs argentinas combinando emisiones cerradas, emisiones de bajo impacto, agenda de licitaciones en difusión (StoneX) y contexto de curva secundaria. Usar cuando piden "resumen de la semana", "qué pasó en el mercado" o "novedades de emisiones".
---

# Resumen semanal de mercado de ONs

## Datos que combina
- `Deals/emisiones_obligaciones_negociables.csv` — emisiones cerradas (principal).
- `Deals/emisiones_on_bajo_impacto.csv` — emisiones cerradas de bajo impacto (ver skill `bajo-impacto` sobre cuándo sumarlas).
- `StoneX/difusion.csv` — licitaciones anunciadas para próxima semana (pipeline, sin resultado aún).
- `Deals/curvas_on.csv` — contexto de mercado secundario del día más reciente (nivel de YTM por Ley/sector).

## Procedimiento
1. Definir la ventana: si no se especifica, usar los últimos 7 días corridos desde hoy, sobre la columna `FECHA`.
2. Filtrar `emisiones_obligaciones_negociables.csv` a esa ventana. Agrupar por `MONEDA` (normalizada) y sumar `VN`. Contar cantidad de emisiones.
3. Mencionar `emisiones_on_bajo_impacto.csv` de la misma ventana **por separado**, aclarando que son montos chicos — no sumarlas al total principal sin decirlo.
4. Listar próximas licitaciones de `difusion.csv` con `FECHA LICITACIÓN` futura (agenda de la semana entrante).
5. Cerrar con una línea de contexto de curva secundaria: YTM promedio actual por Ley (Arg/NY) desde `curvas_on.csv`, fecha del informe incluida.

## Output esperado
Formato breve tipo "parte semanal": cantidad de emisiones + VN total por moneda, agenda próxima, contexto de curva. No es necesario listar cada emisión fila por fila salvo que el usuario pida el detalle.