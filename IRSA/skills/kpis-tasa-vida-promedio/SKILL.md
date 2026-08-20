---
name: irsa-kpis-tasa-vida-promedio
description: Fórmulas de Tasa Promedio Ponderada y Vida Promedio Ponderada para la deuda USD vigente de IRSA. Usar siempre que pidan tasa promedio, vida promedio, duración o "perfil" de la deuda en tasa/plazo.
---

# Tasa y Vida Promedio Ponderada — IRSA

## Universo de filas
Sobre `irsa_deuda.csv`, filas que cumplan **todas**:
- `Moneda == 'USD'` (excluye ARS).
- `Fecha Fin` posterior a hoy (excluye vencidas).

## Tasa Promedio Ponderada
```
Σ (Monto Webcast_i × Tasa_i) / Σ (Monto Webcast_i)
```
- `Tasa_i` parseada como decimal (`"8.75%"` → `0.0875`).

## Vida Promedio Ponderada
```
Σ (Monto Webcast_i × Años_i) / Σ (Monto Webcast_i)
```
- `Años_i = (Fecha Fin − hoy) / 365` (365 días exactos, no 365,25).

## Regla del peso
El peso de ambas fórmulas es siempre **`Monto Webcast`** (nominal), nunca
`Monto USD` — esto vale incluso para instrumentos S/MULC, cuyo `Monto USD`
es referencial y no ajustado a la brecha real (ver `README_datos.md`).

## Output esperado
Solo el resultado final (ej. "Tasa Promedio Ponderada: 6,8%"), sin mostrar el
desarrollo del cálculo salvo que se pida explícitamente.
