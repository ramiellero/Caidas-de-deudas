# Registra en el Programador de tareas de Windows las tareas programadas del dashboard,
# para el usuario que corre este script y apuntando a ESTE clon del repo.
#
# Reemplaza a importar los XML de Traspaso\tareas_xml\ (que tienen la ruta y el usuario de
# la PC original): las rutas salen de $PSScriptRoot, asi que no hay que editar nada.
#
# Uso (PowerShell normal, no hace falta admin):
#   powershell -ExecutionPolicy Bypass -File Traspaso\registrar_tareas.ps1
#   powershell -ExecutionPolicy Bypass -File Traspaso\registrar_tareas.ps1 -Desregistrar   # las borra
#
# No registra "Scraper Curvas ONs PPI": esta obsoleta, el scraper corre en GitHub Actions.
# Solo ASCII a proposito (Windows PowerShell 5 lee mal los acentos de un .ps1 sin BOM).

param(
    # Carpeta de OneDrive a la que se copian los CSV de curvas (se sube sola a SharePoint).
    [string]$DestinoCurvas = $(if ($env:OneDriveCommercial) { Join-Path $env:OneDriveCommercial 'Curvas ONs' } else { '' }),
    [switch]$Desregistrar
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Usuario  = "$env:USERDOMAIN\$env:USERNAME"

$scriptPadron = Join-Path $RepoRoot 'Padron\descargar_padron_semanal.ps1'
$scriptPull   = Join-Path $RepoRoot 'pull_diario.ps1'
$scriptCurvas = Join-Path $RepoRoot 'Deals\sincronizar_curvas_sharepoint.ps1'

$argsCurvas = "-File `"$scriptCurvas`""
if ($DestinoCurvas) { $argsCurvas += " -Destino `"$DestinoCurvas`"" }

# Lunes 11:00 (semanal) / todos los dias 11:00 (diario). El 2026-11-16 es lunes.
$inicio = [datetime]'2026-11-16T11:00:00'

$Tareas = @(
    @{ Nombre = 'Descarga Padron IRSA';              Args = "-File `"$scriptPadron`" -IssuerCode IRSA";          Semanal = $true  }
    @{ Nombre = 'Descarga Padron Cresud';            Args = "-File `"$scriptPadron`" -IssuerCode CRES";          Semanal = $true  }
    @{ Nombre = 'Descarga Padron Mensual IRSA';      Args = "-File `"$scriptPadron`" -IssuerCode IRSA -Mensual"; Semanal = $false }
    @{ Nombre = 'Descarga Padron Mensual Cresud';    Args = "-File `"$scriptPadron`" -IssuerCode CRES -Mensual"; Semanal = $false }
    @{ Nombre = 'Pull Diario Dashboard';             Args = "-File `"$scriptPull`"";                             Semanal = $false }
    @{ Nombre = 'Sincronizar Curvas ONs SharePoint'; Args = $argsCurvas;                                         Semanal = $false }
)

if ($Desregistrar) {
    foreach ($t in $Tareas) {
        if (Get-ScheduledTask -TaskName $t.Nombre -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $t.Nombre -Confirm:$false
            Write-Host "Borrada: $($t.Nombre)"
        }
    }
    return
}

foreach ($s in @($scriptPadron, $scriptPull, $scriptCurvas)) {
    if (-not (Test-Path $s)) { throw "No existe $s" }
}
if (-not (Test-Path (Join-Path $RepoRoot 'Padron\padron_auth.local.ps1')) -and -not $env:PADRON_AUTH_USER) {
    Write-Warning "Falta Padron\padron_auth.local.ps1 (o las env vars PADRON_AUTH_USER/PADRON_AUTH_PASSWORD): las tareas de padron van a fallar al loguearse."
}
if (-not (Test-Path 'T:\')) {
    Write-Warning "La unidad T:\ no esta montada ahora: las tareas de padron fallan si no lo esta a las 11:00."
}

$principal = New-ScheduledTaskPrincipal -UserId $Usuario -LogonType Interactive
# StartWhenAvailable: si la PC estaba apagada a las 11:00, la tarea corre apenas se prende.
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)

foreach ($t in $Tareas) {
    $trigger = if ($t.Semanal) {
        New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $inicio
    } else {
        New-ScheduledTaskTrigger -Daily -At $inicio
    }
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' `
                -Argument "-NoProfile -ExecutionPolicy Bypass $($t.Args)" -WorkingDirectory $RepoRoot

    Register-ScheduledTask -TaskName $t.Nombre -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Force | Out-Null
    Write-Host "Registrada: $($t.Nombre)"
}

Write-Host ""
Write-Host "Listo. Usuario: $Usuario  |  Repo: $RepoRoot"
if ($DestinoCurvas) { Write-Host "Curvas ONs se copian a: $DestinoCurvas" }
