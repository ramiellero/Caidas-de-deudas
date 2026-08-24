# Pull automático diario del repo del dashboard.
# Corre vía Task Scheduler ("Pull Diario Dashboard"), todos los días a las 11:00.

$repoPath = "C:\Users\rellero\OneDrive - IRSACORP\Downloads\Dashboard Caídas de Deudas"
$logFile  = Join-Path $repoPath "pull_diario.log"

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logFile -Value "[$ts] $msg"
}

Set-Location $repoPath

try {
    $status = git status --porcelain
    if ($status) {
        Write-Log "Hay cambios locales sin commitear - se aborta el pull para no pisarlos:`n$status"
        exit 0
    }

    $output = git pull 2>&1
    Write-Log "git pull output: $output"
}
catch {
    Write-Log "ERROR: $($_.Exception.Message)"
}
