# Pull automatico diario del repo del dashboard.
# Corre via Task Scheduler ("Pull Diario Dashboard"), todos los dias a las 11:00.
#
# La ruta del repo sale de $PSScriptRoot (la carpeta donde vive este script, la raiz del repo),
# asi funciona en cualquier PC/usuario sin editar nada. El archivo es solo ASCII a proposito:
# Windows PowerShell 5 lee mal los acentos de un .ps1 sin BOM (era la causa de que la version
# anterior, con la ruta "Caidas" acentuada hardcodeada, nunca escribiera su log).

$repoPath = $PSScriptRoot
$logFile  = Join-Path $repoPath "pull_diario.log"

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logFile -Value "[$ts] $msg"
}

try {
    Set-Location $repoPath -ErrorAction Stop

    $status = git status --porcelain
    if ($status) {
        Write-Log "Hay cambios locales sin commitear - se aborta el pull para no pisarlos:`n$status"
        exit 0
    }

    $output = git pull 2>&1
    Write-Log "git pull (exit $LASTEXITCODE): $output"
}
catch {
    Write-Log "ERROR: $($_.Exception.Message)"
}
