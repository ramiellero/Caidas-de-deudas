# Sincroniza los CSV de Curvas ONs (tablero BYMA Educa) desde el repo de git
# hacia una carpeta local dentro de este mismo proyecto (Deals\CurvasSync\).
#
# Como esta carpeta del proyecto ya vive dentro de OneDrive - IRSACORP, todo lo que
# se guarde en Deals\CurvasSync\ se sincroniza solo a SharePoint sin pasos adicionales.
#
# Por que "leer desde git" y no correr scraper_curvas.py acá: scraper_curvas.py ya corre
# solo todos los dias habiles a las 10am ART via GitHub Actions y comitea curvas_on.csv /
# curvas_propias_historico.csv al repo. Este script simplemente toma esos archivos ya
# generados desde el commit mas reciente de origin/main - no duplica la logica de scraping
# de BYMA ni requiere Python/dependencias instaladas en esta PC.
#
# Por que git fetch + git show y no raw.githubusercontent.com: el repo es PRIVADO, asi que
# una descarga HTTP anonima a raw.githubusercontent.com devuelve 404 (necesitaria un token
# hardcodeado en el script). Usando "git show origin/main:<path>" se reutilizan las mismas
# credenciales de git ya configuradas en esta PC (las que usa Claude Code / el usuario para
# hacer push a este repo) sin guardar ningun secreto nuevo en el script.
#
# Requisito: correr DESDE dentro de este repo clonado (usa $PSScriptRoot para ubicar el
# .git). Si se mueve este script a otra carpeta, hay que ajustar $RepoRoot.
#
# Pensado para correr desde Task Scheduler todos los dias a las 11:00 (una hora despues
# del Action de GitHub, para darle margen a que el commit ya este pusheado).
#
# Uso manual: powershell -File sincronizar_curvas_sharepoint.ps1

param(
    [string]$FechaOverride   # yyyy-MM-dd, solo para pruebas / backfill puntual
)

# --- Configuracion ------------------------------------------------------------

$RepoRoot = Split-Path -Parent $PSScriptRoot   # Deals\.. -> raiz del repo
$Rama = 'origin/main'

$DestinoBase = Join-Path $PSScriptRoot 'CurvasSync'

# Archivos a sincronizar: ruta dentro del repo -> si se guarda con fecha en el nombre o se pisa
$Archivos = @(
    @{ RutaRepo = 'Deals/curvas_on.csv';                ConFecha = $true  },  # snapshot del dia -> se guarda uno por fecha
    @{ RutaRepo = 'Deals/curvas_propias_historico.csv'; ConFecha = $false }   # historico acumulado -> siempre se pisa con la ultima version
)

$LogFile = Join-Path $PSScriptRoot 'sincronizar_curvas_sharepoint.log'

# --- Helpers -------------------------------------------------------------------

function Write-Log {
    param([string]$Mensaje)
    $linea = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Mensaje
    Write-Host $linea
    Add-Content -Path $LogFile -Value $linea -Encoding UTF8
}

# --- Main ------------------------------------------------------------------------

if (-not (Test-Path $DestinoBase)) {
    New-Item -ItemType Directory -Path $DestinoBase | Out-Null
}

$Fecha = if ($FechaOverride) { $FechaOverride } else { (Get-Date).ToString('yyyy-MM-dd') }
Write-Log "=== Inicio sincronizacion curvas ONs - fecha=$Fecha ==="

Push-Location $RepoRoot
try {
    git fetch origin main --quiet 2>&1 | ForEach-Object { Write-Log "git fetch: $_" }
    if ($LASTEXITCODE -ne 0) {
        throw "git fetch fallo (exit $LASTEXITCODE) - revisar conexion / credenciales de git"
    }

    foreach ($archivo in $Archivos) {
        $rutaRepo = $archivo.RutaRepo
        $nombreArchivo = Split-Path -Leaf $rutaRepo

        $nombreDestino = if ($archivo.ConFecha) {
            $base = [System.IO.Path]::GetFileNameWithoutExtension($nombreArchivo)
            "${base}_${Fecha}.csv"
        } else {
            $nombreArchivo
        }
        $rutaDestino = Join-Path $DestinoBase $nombreDestino

        try {
            $contenido = git show "${Rama}:${rutaRepo}" 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "git show fallo: $contenido"
            }
            Set-Content -Path $rutaDestino -Value $contenido -Encoding UTF8
            Write-Log "OK: $rutaRepo -> $rutaDestino"
        }
        catch {
            Write-Log "ERROR sincronizando ${rutaRepo}: $($_.Exception.Message)"
        }
    }
}
finally {
    Pop-Location
}

Write-Log "=== Fin sincronizacion curvas ONs ==="
