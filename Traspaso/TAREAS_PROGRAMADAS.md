# Tareas programadas del dashboard — PC de Juan (jgrandi)

Adaptado el **2026-11-12** a partir del relevamiento de la PC de Ramiro (`rellero`). Las tareas viven en el **Programador de tareas de Windows** (Task Scheduler) de la PC de `IRSACORP\jgrandi` y corren con la sesión de ese usuario iniciada (`LogonType = Interactive`). **No hay ningún servidor dedicado**: si la PC está apagada a la hora de la tarea, corre apenas se prende (`StartWhenAvailable`), pero la tarea igual necesita la sesión iniciada.

- **Repo**: `C:\Users\Jgrandi\Caidas-de-deudas-repo` (fuera de OneDrive).
- **Usuario**: `IRSACORP\jgrandi`.
- **Cómo se registran**: con [registrar_tareas.ps1](registrar_tareas.ps1), que arma las tareas con las rutas de este clon y el usuario que lo corre. Ya no hace falta editar ni importar XML.
- Los XML de [tareas_xml/](tareas_xml/) quedan **solo como referencia** de cómo estaban en la PC de Ramiro (tienen su ruta y su SID). No importarlos.

> Este documento **no contiene credenciales**. Los secretos viven en Cloudflare Pages y Vercel (env vars) y en `Padron\padron_auth.local.ps1` (archivo local, gitignoreado, **no está en el repo**).

---

## Sobre "los scrapers"

- **Scraper de curvas ONs** (`Deals\scraper_curvas.py`): **no corre en la PC**. Lo corre **GitHub Actions** lun-vie 10:00 ART y commitea los CSV; el push redeploya Cloudflare Pages. Lo único que hace la PC es *bajar* esos CSV (tareas 5 y 6). La tarea vieja "Scraper Curvas ONs PPI" está obsoleta y **no se registra**.
- **Carga de emisiones** (`StoneX\actualizar_deals.py`): la corre a mano un compañero desde su PC. No es una tarea programada.
- **Padrón** (tareas 1–4): es lo único que *tiene* que correr en una PC de la red, porque guarda en `T:\`.

---

## Resumen

| # | Tarea | Cuándo | Qué hace |
|---|---|---|---|
| 1 | Descarga Padron IRSA | Lunes 11:00 | Baja el padrón de IRSA y lo guarda en `T:\` |
| 2 | Descarga Padron Cresud | Lunes 11:00 | Ídem para Cresud |
| 3 | Descarga Padron Mensual IRSA | Todos los días 11:00 | Cierre de mes: actúa solo 3 días hábiles después del último hábil del mes |
| 4 | Descarga Padron Mensual Cresud | Todos los días 11:00 | Ídem para Cresud |
| 5 | Pull Diario Dashboard | Todos los días 11:00 | `git pull` del repo en la PC |
| 6 | Sincronizar Curvas ONs SharePoint | Todos los días 11:00 | Copia los CSV de curvas desde git a `C:\Users\Jgrandi\OneDrive - IRSACORP\Curvas ONs\` (OneDrive lo sube solo) |

Todas corren como `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<ruta>"`, con `WorkingDirectory` = raíz del repo y un límite de 2 horas por corrida.

---

## Puesta en marcha (una sola vez)

Estado verificado el 2026-11-12 en esta PC: `T:\` montada y con las carpetas `Padron\IRSA` y `Padron\Cresud` accesibles ✅ · `git` con credenciales (`credential.helper = manager`) ✅ · OneDrive - IRSACORP en `C:\Users\Jgrandi\OneDrive - IRSACORP` ✅ · **`Padron\padron_auth.local.ps1` no existe todavía** ❌.

1. **Crear `Padron\padron_auth.local.ps1`** (pedirle los valores a Ramiro por un canal seguro, **no por mail ni por el repo**):
   ```powershell
   $PadronAuthUser     = '<usuario del dashboard>'
   $PadronAuthPassword = '<contraseña del dashboard>'
   ```
2. **Registrar las tareas** (PowerShell normal, no hace falta admin):
   ```powershell
   powershell -ExecutionPolicy Bypass -File Traspaso\registrar_tareas.ps1
   ```
   Para elegir otra carpeta de OneDrive para las curvas: `-DestinoCurvas "<carpeta>"`. Para borrarlas: `-Desregistrar`. Se puede volver a correr cuando quieras; pisa las tareas existentes.
3. **Probar cada una a mano** una vez y revisar su `.log`:
   ```powershell
   powershell -File Padron\descargar_padron_semanal.ps1 -IssuerCode CRES
   powershell -File Padron\descargar_padron_semanal.ps1 -IssuerCode IRSA
   powershell -File pull_diario.ps1
   powershell -File Deals\sincronizar_curvas_sharepoint.ps1 -Destino "$env:OneDriveCommercial\Curvas ONs"
   ```
   O desde la UI: Programador de tareas → clic derecho en la tarea → Ejecutar.
4. **Que Ramiro desactive sus tareas** en su PC (las 7) cuando las tuyas estén andando, para no tener dos PCs bajando y pisando el mismo padrón.
5. **Si el repo cambia de dueño** (transferencia de GitHub o repo nuevo): actualizar el remote de este clon (`git remote set-url origin <url nueva>`). Hoy apunta a `github.com/ramiellero/Caidas-de-deudas`. El compañero de StoneX tiene que hacer lo mismo en su clon.
6. Pasar el control de Cloudflare y Vercel (proyecto, env vars) y que Ramiro haga `gh auth logout` en su PC.

---

## Cambios respecto de la PC de Ramiro

- **Las rutas no están hardcodeadas.** `pull_diario.ps1` ahora usa `$PSScriptRoot` y es solo ASCII. Era la causa probable de que en la PC de Ramiro nunca escribiera su log (la ruta con "í" en un `.ps1` sin BOM). Probado acá el 2026-11-12: escribe el log bien.
- **Curvas a SharePoint**: en la PC de Ramiro el repo estaba dentro de OneDrive, así que `Deals\CurvasSync\` se subía sola. Este clon está **fuera** de OneDrive, así que el script ahora acepta `-Destino` y la tarea copia a `OneDrive - IRSACORP\Curvas ONs\`. ⚠️ Es una carpeta **nueva en tu OneDrive**: si alguien consumía los archivos desde el OneDrive/SharePoint de Ramiro, hay que pasarle el link nuevo (o compartirle la carpeta).
- **`StartWhenAvailable`**: si la PC estaba apagada a las 11:00, la tarea corre al prenderla. El job mensual solo actúa si "hoy" es el día de corrida, así que si la PC se prende recién al día siguiente, ese mes hay que correrlo a mano con `-BalanceDateOverride`.
- **No se registra** "Scraper Curvas ONs PPI" (obsoleta, ver arriba).
- `pull_diario.log` se agregó a `.gitignore`.

---

## Detalle de cada tarea

### 1 y 2. Descarga Padron IRSA / Descarga Padron Cresud (semanal)
- **Script**: `Padron\descargar_padron_semanal.ps1 -IssuerCode IRSA` (o `CRES`).
- **Disparador**: semanal, lunes 11:00.
- **Qué hace**: hace login contra `/api/login` del dashboard en Cloudflare Pages, llama a `/api/padron` (que consulta la API de Custodia de BYMA), espera hasta que el reporte esté listo (polling cada 15 s, hasta 24 intentos) y guarda el CSV crudo.
- **Fecha de balance**: hoy − 3 días (si corre un lunes, pide el viernes previo).
- **Salida**: `T:\Finanzas\TODOS\Mercado de Capitales\04 - Reportes MC\Tenedores ONs\BASE CAJA\Padron\{IRSA|Cresud}\Padron_{IRSA|Cresud}_{fecha}.csv`
- **Log**: `Padron\descargar_padron_semanal_IRSA.log` / `_CRES.log`.
- **Necesita**: red corporativa con `T:\` montada, `Padron\padron_auth.local.ps1` (o env vars `PADRON_AUTH_USER` / `PADRON_AUTH_PASSWORD`) y el sitio de Cloudflare Pages activo (y el backend del padrón en Vercel).
- **Fallos conocidos**: si `T:\` no está montada, el padrón se baja pero no se guarda (pasó en la PC de Ramiro el 2026-08-17 y el 2026-11-09). También hay fallos esporádicos del lado de BYMA ("se agotaron los 24 intentos", "fetch failed"). En ambos casos, correr a mano.
- **Pendiente heredado**: el padrón del 2026-11-06 (viernes) quedó sin guardar en la PC de Ramiro. Se recupera con `powershell -File Padron\descargar_padron_semanal.ps1 -BalanceDateOverride "2026-11-06"` (corre ambos emisores).

### 3 y 4. Descarga Padron Mensual IRSA / Cresud (cierre de mes)
- **Script**: igual que arriba, con `-Mensual`.
- **Disparador**: **todos los días** 11:00, a propósito: el script decide solo y casi todos los días loguea "no es el dia de corrida".
- **Lógica**: calcula el último día hábil (lun-vie, **sin feriados**) del mes anterior, le suma 3 días hábiles, y solo ese día descarga el padrón del cierre de mes.
- **Salida**: `Padron_{IRSA|Cresud}_{fecha}_CierreMes.csv` en las mismas carpetas de `T:\`.
- **Log**: `descargar_padron_semanal_IRSA_Mensual.log` / `_CRES_Mensual.log`.
- Última corrida real (PC de Ramiro): 2026-11-04 (cierre del 2026-10-30), OK. La próxima es el **jueves 2026-12-03** (cierre del lunes 2026-11-30). Si un feriado desplaza el cálculo, correr a mano con `-BalanceDateOverride`.

### 5. Pull Diario Dashboard
- **Script**: `pull_diario.ps1` (raíz del repo).
- **Disparador**: diario 11:00.
- **Qué hace**: `git pull` para tener el código y los CSV al día (GitHub Actions y los compañeros pushean). Si hay cambios locales sin commitear, **no hace pull** para no pisarlos y lo deja anotado en el log.
- **Log**: `pull_diario.log` (raíz; gitignoreado).

### 6. Sincronizar Curvas ONs SharePoint
- **Script**: `Deals\sincronizar_curvas_sharepoint.ps1 -Destino "C:\Users\Jgrandi\OneDrive - IRSACORP\Curvas ONs"`.
- **Disparador**: diario 11:00 (una hora después de GitHub Actions, para que el commit ya esté pusheado).
- **Qué hace**: `git fetch` y copia desde `origin/main` `curvas_on.csv` (uno por fecha, `curvas_on_YYYY-MM-DD.csv`) y `curvas_propias_historico.csv` (se pisa) a la carpeta destino, que OneDrive sube sola.
- **Log**: `Deals\sincronizar_curvas_sharepoint.log`.
- Probado el 2026-11-12 contra una carpeta temporal: copia bien los dos archivos.

---

## Lo que NO corre en esta PC pero también es parte de la operación

- **GitHub Actions** — `.github/workflows/scraper-curvas.yml`: scraper de curvas (BYMA Educa), lun-vie 10:00 ART. Se puede lanzar a mano desde la pestaña Actions ("Run workflow"). Sigue funcionando si se transfiere el repo.
- **Cloudflare Pages**: hosting del dashboard y `/api/login`; `/api/padron` es un proxy a Vercel. Env vars en Cloudflare: `AUTH_USER`, `AUTH_PASSWORD_HASH` (PBKDF2 10.000 iteraciones + pepper), `AUTH_PEPPER`, `SESSION_SECRET` (igual que en Vercel), `PADRON_UPSTREAM`.
- **Vercel**: solo backend del padrón (`api/padron.js`, que consulta BYMA). Env vars: `SESSION_SECRET` y `AUTH_USER` (iguales a los de Cloudflare), `BYMA_OKTA_TOKEN_URL`, `BYMA_SCOPE`, `BYMA_API_BASE`, `BYMA_CLIENT_ID`, `BYMA_CLIENT_SECRET` (y opcionalmente las variantes `_IRSA` / `_CRES`).
- **Carga semanal de emisiones** (`Deals\emisiones_*.csv`): un compañero, a mano, con `StoneX\actualizar_deals.py` desde su PC (ver `StoneX\CLAUDE.md`).

---

## Cómo saber si algo falló

Task Scheduler muestra resultado 0 aunque el script haya fallado (por ejemplo, `T:\` sin montar). **La fuente de verdad son los `.log`**: buscar `ERROR` en `Padron\*.log`, `Deals\sincronizar_curvas_sharepoint.log` y `pull_diario.log`. Conviene revisarlos los lunes después de las 11:30:

```powershell
Select-String -Path Padron\*.log, Deals\sincronizar_curvas_sharepoint.log, pull_diario.log -Pattern ERROR | Select-Object -Last 20
```
