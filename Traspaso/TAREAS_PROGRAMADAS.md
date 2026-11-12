# Tareas programadas en la PC de Ramiro (rellero) — Traspaso

Relevamiento al **2026-11-12**. Todas las tareas están en el **Programador de tareas de Windows** (Task Scheduler), corren en la PC `rellero` con la sesión de ese usuario iniciada (`LogonType = Interactive`). **No hay ningún servidor dedicado**: si la PC está apagada o sin sesión a la hora de la tarea, no corre.

Hay 7 tareas propias del proyecto. El resto de las tareas de la PC (Adobe, OneDrive, HP, SoftLanding) son del sistema y no tienen que ver con esto.

Los XML exportados están en [tareas_xml/](tareas_xml/) y sirven para recrear las tareas en otra PC (ver "Cómo migrarlas").

> Este documento **no contiene credenciales**. Los secretos viven en Vercel (env vars) y en `Padron\padron_auth.local.ps1` (archivo local, gitignoreado, **no está en el repo**).

---

## Resumen

| # | Tarea | Cuándo | Qué hace | Estado hoy |
|---|---|---|---|---|
| 1 | Descarga Padron IRSA | Lunes 11:00 | Baja el padrón de IRSA y lo guarda en la red `T:\` | ⚠️ **Falla si `T:\` no está montada** |
| 2 | Descarga Padron Cresud | Lunes 11:00 | Ídem para Cresud | ⚠️ Ídem |
| 3 | Descarga Padron Mensual IRSA | Todos los días 11:00 | Cierre de mes: actúa solo 3 días hábiles después del último hábil del mes | ✅ |
| 4 | Descarga Padron Mensual Cresud | Todos los días 11:00 | Ídem para Cresud | ✅ |
| 5 | Pull Diario Dashboard | Todos los días 11:00 | `git pull` del repo en la PC | ❓ **No verificado**: nunca escribió su log |
| 6 | Sincronizar Curvas ONs SharePoint | Todos los días 11:00 | Copia los CSV de curvas desde git a una carpeta que OneDrive sube a SharePoint | ✅ |
| 7 | Scraper Curvas ONs PPI | Todos los días 09:00 | **Obsoleta y rota** (ver abajo) | ❌ Falla todos los días |

Todas corren como `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<ruta>"` (la 7, como `cmd.exe /c`).

---

## Problemas detectados hoy (revisar primero)

1. **Tareas 1 y 2 — la unidad `T:\` no estaba montada el lunes 2026-11-09.** El padrón se descargó bien de BYMA pero no se pudo guardar: `No se encuentra la carpeta destino: T:\Finanzas\...\Padron\IRSA (no esta montada la red T:\?)`. Pasó también el 2026-08-17. Task Scheduler igual marca "Última ejecución: 0 (éxito)", así que **no avisa**: hay que mirar los `.log`. El padrón del 2026-11-06 (viernes) quedó sin guardar; se puede recuperar corriendo a mano con `-BalanceDateOverride "2026-11-06"` con `T:\` montada.
2. **Tarea 7 (Scraper Curvas ONs PPI) está obsoleta y falla (resultado 1) todos los días.** Apunta a `...\Dashboard Caídas de Deudas\run_scraper_curvas.bat`, pero ese archivo ahora está en `Deals\`. Además es redundante: el scraping de curvas ya lo hace **GitHub Actions** (ver más abajo). Recomendación: **deshabilitarla o borrarla**; no hace falta migrarla.
3. **Tarea 5 (Pull Diario) — no hay evidencia de que funcione.** Task Scheduler marca éxito (0), pero `pull_diario.log` no existe en ningún lado, cuando el script escribe una línea en cada corrida. Causa probable: `pull_diario.ps1` está guardado sin BOM UTF-8 y Windows PowerShell 5 lee mal la "í" de `Caídas` en `$repoPath`, entonces `Set-Location` y el log fallan en silencio. No lo probé. Para verificarlo: correrlo a mano (`powershell -File pull_diario.ps1`) y ver si aparece el log. Arreglo probable: guardar el `.ps1` como "UTF-8 con BOM". En la práctica no es crítico, porque el repo se puede actualizar a mano con `git pull`.
4. **Tareas 1 y 2 — fallos esporádicos por demora de BYMA.** Hubo corridas sin éxito por "se agotaron los 24 intentos" (2026-11-02) y "fetch failed" (2026-10-26): son del lado de BYMA (el reporte tarda). Si pasa, se corre a mano.

---

## Detalle de cada tarea

### 1 y 2. Descarga Padron IRSA / Descarga Padron Cresud (semanal)
- **Script**: `Padron\descargar_padron_semanal.ps1 -IssuerCode IRSA` (o `CRES`)
- **Disparador**: semanal, lunes 11:00.
- **Qué hace**: hace login contra `/api/login` del dashboard en Vercel, llama a `/api/padron` (que a su vez consulta la API de Custodia de BYMA), espera hasta que el reporte esté listo (polling cada 15 s, hasta 24 intentos) y guarda el CSV crudo.
- **Fecha de balance**: hoy − 3 días (si corre un lunes, pide el viernes previo).
- **Salida**: `T:\Finanzas\TODOS\Mercado de Capitales\04 - Reportes MC\Tenedores ONs\BASE CAJA\Padron\{IRSA|Cresud}\Padron_{IRSA|Cresud}_{fecha}.csv`
- **Log**: `Padron\descargar_padron_semanal_IRSA.log` / `_CRES.log`
- **Necesita**: red corporativa con `T:\` montada, credenciales en `Padron\padron_auth.local.ps1` (variables `$PadronAuthUser` / `$PadronAuthPassword`) o env vars `PADRON_AUTH_USER` / `PADRON_AUTH_PASSWORD`, y que el sitio en Vercel esté activo.

### 3 y 4. Descarga Padron Mensual IRSA / Cresud (cierre de mes)
- **Script**: igual que arriba, con `-Mensual`.
- **Disparador**: **todos los días** 11:00. Es a propósito: `schtasks` no permite listar días específicos del mes, así que el script decide solo. Casi todos los días loguea "no es el dia de corrida" y termina sin hacer nada.
- **Lógica**: calcula el último día hábil (lun-vie, **sin feriados**) del mes anterior, le suma 3 días hábiles, y solo ese día descarga el padrón del cierre de mes.
- **Salida**: `Padron_{IRSA|Cresud}_{fecha}_CierreMes.csv` en las mismas carpetas de `T:\`.
- **Log**: `descargar_padron_semanal_IRSA_Mensual.log` / `_CRES_Mensual.log`.
- Última corrida real: 2026-11-04 (cierre del 2026-10-30), OK para ambos. La próxima corresponde a principios de diciembre (cierre de noviembre). Si un feriado desplaza el cálculo, correr a mano con `-BalanceDateOverride`.

### 5. Pull Diario Dashboard
- **Script**: `pull_diario.ps1` (en la raíz del repo).
- **Disparador**: diario 11:00.
- **Qué hace**: `git pull` del repo en la PC para tener el código y CSV actualizados (el scraper de GitHub Actions y los compañeros pushean). Si hay cambios locales sin commitear, **no hace pull** para no pisarlos.
- **Log**: `pull_diario.log` (en la raíz; no se versiona).
- **Necesita**: credenciales de git funcionando en esa PC.

### 6. Sincronizar Curvas ONs SharePoint
- **Script**: `Deals\sincronizar_curvas_sharepoint.ps1`
- **Disparador**: diario 11:00 (una hora después de GitHub Actions, para que el commit ya esté pusheado).
- **Qué hace**: `git fetch` y copia desde `origin/main` dos archivos a `Deals\CurvasSync\`: `curvas_on.csv` (uno por fecha, `curvas_on_YYYY-MM-DD.csv`) y `curvas_propias_historico.csv` (se pisa). Como esa carpeta está dentro de OneDrive - IRSACORP, **se sube sola a SharePoint**.
- **Log**: `Deals\sincronizar_curvas_sharepoint.log`.

### 7. Scraper Curvas ONs PPI — OBSOLETA
- Ver "Problemas detectados". Ejecuta `run_scraper_curvas.bat` (en `Deals\`), que corre `python Deals\scraper_curvas.py --commit` con `C:\Users\rellero\AppData\Local\Programs\Python\Python312\python.exe`. Quedó reemplazada por GitHub Actions. **No migrar.**

---

## Lo que NO corre en esta PC pero también es parte de la operación

- **GitHub Actions** — `.github/workflows/scraper-curvas.yml`: scraper de curvas de ONs (BYMA Educa), lun-vie 10:00 ART. Commitea `Deals/curvas_on.csv` y `Deals/curvas_propias_historico.csv`; ese push dispara el redeploy en Vercel. Se puede lanzar a mano desde la pestaña Actions ("Run workflow"). Sigue funcionando al transferir el repo.
- **Vercel**: hosting del dashboard, `/api/login`, `/api/padron`. Env vars necesarias (no están en el repo): `AUTH_USER`, `AUTH_PASSWORD_HASH`, `SESSION_SECRET`, `BYMA_OKTA_TOKEN_URL`, `BYMA_SCOPE`, `BYMA_API_BASE`, `BYMA_CLIENT_ID`, `BYMA_CLIENT_SECRET` (y opcionalmente las variantes `_IRSA` / `_CRES`).
- **Carga semanal de emisiones** (`Deals\emisiones_*.csv`): la hace **un compañero** a mano con `StoneX\actualizar_deals.py` desde su propia PC (ver `StoneX\CLAUDE.md`). Si el repo cambia de dueño, esa persona tiene que actualizar el `remote` de su clon.

---

## Cómo migrarlas a otra PC (la de Lucila)

Requisitos en la PC nueva: Windows con la unidad **`T:\` montada** y acceso a la carpeta `...\Tenedores ONs\BASE CAJA\Padron\`, `git` con credenciales a este repo, el repo clonado, y el archivo `Padron\padron_auth.local.ps1` creado (copiar `$PadronAuthUser` / `$PadronAuthPassword` desde un canal seguro; **no por mail ni por el repo**).

1. Clonar el repo y ajustar las rutas: los scripts y los XML tienen la ruta de Ramiro (`C:\Users\rellero\OneDrive - IRSACORP\Downloads\Dashboard Caídas de Deudas`) y el usuario `Rellero`. Editar los XML (`<Command>`, `<Arguments>`, `<UserId>`) antes de importar. Nota: `pull_diario.ps1` tiene la ruta fija en la variable `$repoPath`.
2. Importar cada tarea (PowerShell): `Register-ScheduledTask -Xml (Get-Content "<archivo>.xml" -Raw) -TaskName "<nombre>"`, o desde la UI: Programador de tareas → Acción → Importar tarea.
3. **No importar** `Scraper Curvas ONs PPI.xml` (obsoleta).
4. Probar a mano cada script una vez, por ejemplo: `powershell -File Padron\descargar_padron_semanal.ps1 -IssuerCode CRES`, y revisar su `.log`.
5. **Desactivar las tareas en la PC de Ramiro** al terminar el traspaso, para no tener dos PCs bajando y pisando el mismo padrón. La PC vieja deja de ser útil cuando Ramiro se vaya.
6. Pasar el control de Vercel (proyecto, env vars) y el `gh auth logout` en la PC de Ramiro.

## Cómo saber si algo falló
Task Scheduler muestra resultado 0 aunque el script haya fallado (por ejemplo `T:\` sin montar). **La fuente de verdad son los `.log`**: buscar `ERROR` en `Padron\*.log` y en `Deals\sincronizar_curvas_sharepoint.log`. Para tener un recordatorio, revisarlos los lunes después de las 11:30.
