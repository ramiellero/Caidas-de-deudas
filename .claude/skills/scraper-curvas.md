# Skill: Actualizar Curvas ONs (Scraper PPI)

Descarga el informe de cierre diario de Portfolio Personal Inversiones (PPI),
extrae la tabla de Bonos Corporativos USD (páginas 12-13) y actualiza
`curvas_on.csv` en el repo.

## Cuándo usar

- Verificar si el scraper automático corrió y tiene datos frescos
- Correr manualmente porque la PC estaba apagada a las 9am
- Forzar un ID específico para recuperar un informe pasado
- Diagnosticar por qué no se extrajeron bonos

---

## Correr manualmente

```powershell
cd "c:\Users\rellero\OneDrive - IRSACORP\Downloads\Dashboard Caídas de Deudas"
python scraper_curvas.py --commit
```

El flag `--commit` hace el `git push` automáticamente al terminar.
Sin `--commit`, solo actualiza los archivos localmente.

### Forzar un ID específico

```powershell
python scraper_curvas.py --id 24525 --commit
```

### Ver qué está haciendo (debug)

```powershell
python scraper_curvas.py --id 24525 --debug
```

Imprime el texto raw de las páginas 12-13. Útil para diagnosticar filas no parseadas.

---

## Verificar que el automático corrió

### Ver el log

```powershell
Get-Content "scraper_curvas.log" -Tail 30
```

Cada ejecución empieza con `[YYYY-MM-DD] === Iniciando scraper ===`.
Una ejecución exitosa termina con `[OK] Listo. Próximo ID a probar: XXXXX`.

### Ver cuándo corrió la tarea programada

```powershell
Get-ScheduledTaskInfo -TaskName "Scraper Curvas ONs PPI" | Select-Object LastRunTime, LastTaskResult, NextRunTime
```

`LastTaskResult = 0` → OK. Cualquier otro valor → revisar el log.

### Ver el ID descargado

```powershell
Get-Content curvas_last_id.txt
```

---

## Cómo funciona la búsqueda de informes

PPI publica dos tipos de informe con IDs secuenciales:
- **Informe de cierre** — contiene tabla de bonos en páginas 12-13 → se procesa
- **Informe diario de mercados** — no tiene esa tabla → se saltea y continúa

El scraper itera desde `last_id + 1` sin límite fijo de intentos:

1. Si el ID no existe (HTTP 404) → incrementa contador de 404s consecutivas
2. Si el PDF es el informe diario → lo saltea y pasa al siguiente ID
3. Si el PDF es el informe de cierre → lo parsea, guarda y termina

**Condición de salida sin éxito**: 3 IDs consecutivos sin respuesta
(`MAX_CONSECUTIVE_404 = 3`). Eso indica que el informe no fue publicado aún.

```
[--] 3 IDs consecutivos sin respuesta (ID 24526–24528). Informe no publicado aún.
```
Esto es normal en fines de semana y feriados.

**Ejemplo típico de un día normal**:
```
[BUSCA] desde ID 24526  (last_id=24525)
  [OK] https://...24526.pdf  (842 KB)
  [SKIP] ID 24526 → informe diario (sin tabla de Bonos Corporativos en p.12-13)
  [OK] https://...24527.pdf  (1.2 MB)

[PARSE] ID 24527
  -> 47 bonos extraidos
  [ID] Guardado last_id = 24527
  [GIT] commit y push OK (ID 24527)
[OK] Listo. Próximo ID a probar: 24528
```

---

## Filtros que aplica el frontend (no el scraper)

Una vez que `curvas_on.csv` se actualiza, el dashboard aplica estos filtros
al cargar la sección Curvas ONs:

| Criterio | Motivo |
|---|---|
| Sin `Precio_Clean_MEP` | Sin precio de mercado, no graficable |
| Emisor contiene "san miguel" | Reestructurado (SNSBO) |
| MEP con TIR > 10% | Candidato a reestructuración |
| CCL con TIR > 13% o < -5% | Outlier de precio |

Estos filtros están en `initCurvasSection()` en `index.html` y no requieren
tocar el scraper.

---

## Recuperar un informe pasado

Los IDs son secuenciales. Si se sabe que el informe del lunes fue el 24520:

```powershell
python scraper_curvas.py --id 24520
```

Esto sobreescribe `curvas_on.csv` y actualiza `curvas_last_id.txt`.
Luego `--commit` para pushear, o hacerlo a mano con `git add` + `git commit`.

Para encontrar el ID correcto cuando no se sabe cuál es:
1. Revisar `scraper_curvas.log` — los IDs probados quedan registrados
2. Probar con `--debug` a partir del último ID conocido (`curvas_last_id.txt`)

---

## Tarea programada (Windows Task Scheduler)

| Parámetro | Valor |
|---|---|
| Nombre | `Scraper Curvas ONs PPI` |
| Horario | Diariamente a las 09:00 |
| Comando | `cmd.exe /c run_scraper_curvas.bat` |
| StartWhenAvailable | Sí — corre si la PC estaba apagada |
| RunOnlyIfNetworkAvailable | Sí |

### Ver / editar desde GUI

`Win + R` → `taskschd.msc` → Biblioteca del Programador de tareas → `Scraper Curvas ONs PPI`

### Forzar ejecución ahora desde PowerShell

```powershell
Start-ScheduledTask -TaskName "Scraper Curvas ONs PPI"
Start-Sleep 5
Get-ScheduledTaskInfo -TaskName "Scraper Curvas ONs PPI" | Select LastRunTime, LastTaskResult
```

### Deshabilitar temporalmente

```powershell
Disable-ScheduledTask -TaskName "Scraper Curvas ONs PPI"
# Para rehabilitar:
Enable-ScheduledTask  -TaskName "Scraper Curvas ONs PPI"
```

---

## Archivos relevantes

| Archivo | Descripción |
|---|---|
| `scraper_curvas.py` | Scraper principal |
| `run_scraper_curvas.bat` | Wrapper para la tarea programada |
| `curvas_on.csv` | Datos más recientes (sobreescrito en cada ejecución exitosa) |
| `curvas_last_id.txt` | Último ID procesado exitosamente |
| `scraper_curvas.log` | Log de todas las ejecuciones (append) |
