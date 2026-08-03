# Descarga semanal del padron de tenedores (IRSA + Cresud) via api/padron.js (proxy BYMA)
# y lo guarda como CSV crudo en una carpeta de red.
#
# Pensado para correr desde Task Scheduler todos los lunes a las 11:00.
# balanceDate = hoy - 3 dias => si corre un lunes, pide el viernes anterior (ultimo dia habil).
#
# Uso manual (los dos emisores, secuencial): powershell -File descargar_padron_semanal.ps1
# Uso por emisor (recomendado para Task Scheduler, corren en paralelo e independiente uno de otro):
#   powershell -File descargar_padron_semanal.ps1 -IssuerCode IRSA
#   powershell -File descargar_padron_semanal.ps1 -IssuerCode CRES
# Uso con fecha forzada (pruebas): agregar -BalanceDateOverride "2026-07-24"
#
# Modo mensual (-Mensual): pensado para un trigger diario (dias 1-10 de cada mes).
# El script chequea internamente si "hoy" es el 3er dia habil despues del ultimo dia habil
# del mes anterior; si no lo es, no hace nada (no llama a la API). Si lo es, descarga el
# balanceDate = ultimo dia habil del mes anterior (el cierre de mes real).

param(
    [ValidateSet('IRSA', 'CRES')]
    [string]$IssuerCode,
    [string]$BalanceDateOverride,
    [switch]$Mensual
)

# --- Configuracion ------------------------------------------------------------

$BaseUrl = 'https://caidas-de-deudas.vercel.app'

$DestinoBase = 'T:\Finanzas\TODOS\Mercado de Capitales\04 - Reportes MC\Tenedores ONs\BASE CAJA\Padron'

# Mapeo issuerCode (API) -> subcarpeta dentro de $DestinoBase
$SubcarpetaPorIssuer = @{
    'IRSA' = 'IRSA'
    'CRES' = 'Cresud'
}

# Si se pasa -IssuerCode corre solo ese emisor (proceso independiente); si no, corre los dos en secuencia
$Issuers = if ($IssuerCode) { @($IssuerCode) } else { @('IRSA', 'CRES') }

# BYMA documenta rate limit 1 req/seg, 5/min, 10/hora. Con el padron actual (~85.000 tenedores,
# ~55MB para Cresud) el reporte puede tardar varios minutos en estar listo; pollear cada 3s pega
# 20 veces/min contra ese limite y termina colgando el polling. 15s entre polls = 4/min.
$MaxIntentos = 24      # ~24 x 15s = 360s (6 min) de espera maxima por emisor
$EsperaSegundos = 15

# Log separado por emisor/modo para que procesos en paralelo no escriban al mismo archivo a la vez
$LogSuffix = if ($IssuerCode) { "_$IssuerCode" } else { '' }
$LogSuffix += if ($Mensual) { '_Mensual' } else { '' }
$LogFile = Join-Path $PSScriptRoot "descargar_padron_semanal$LogSuffix.log"

# --- Helpers -------------------------------------------------------------------

function Write-Log {
    param([string]$Mensaje)
    $linea = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Mensaje
    Write-Host $linea
    Add-Content -Path $LogFile -Value $linea -Encoding UTF8
}

function Add-BusinessDays {
    param(
        [datetime]$Fecha,
        [int]$Dias
    )
    $resultado = $Fecha
    $contados = 0
    while ($contados -lt $Dias) {
        $resultado = $resultado.AddDays(1)
        if ($resultado.DayOfWeek -ne [System.DayOfWeek]::Saturday -and $resultado.DayOfWeek -ne [System.DayOfWeek]::Sunday) {
            $contados++
        }
    }
    return $resultado
}

function Get-LastBusinessDayOfMonth {
    param(
        [int]$Anio,
        [int]$Mes
    )
    $ultimoDiaCalendario = [datetime]::new($Anio, $Mes, [datetime]::DaysInMonth($Anio, $Mes))
    while ($ultimoDiaCalendario.DayOfWeek -eq [System.DayOfWeek]::Saturday -or $ultimoDiaCalendario.DayOfWeek -eq [System.DayOfWeek]::Sunday) {
        $ultimoDiaCalendario = $ultimoDiaCalendario.AddDays(-1)
    }
    return $ultimoDiaCalendario
}

function Get-PadronData {
    param(
        [string]$IssuerCode,
        [string]$BalanceDate
    )

    $uuid = $null
    for ($intento = 1; $intento -le $MaxIntentos; $intento++) {
        $url = "$BaseUrl/api/padron?issuerCode=$IssuerCode&balanceDate=$BalanceDate"
        if ($uuid) { $url += "&uuid=$uuid" }

        try {
            $resp = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 150
        }
        catch {
            Write-Log "[$IssuerCode] Aviso: request fallo (intento $intento/$MaxIntentos): $($_.Exception.Message) - reintentando"
            Start-Sleep -Seconds $EsperaSegundos
            continue
        }

        switch ($resp.status) {
            'ready' {
                Write-Log "[$IssuerCode] Listo (intento $intento)"
                return $resp
            }
            'pending' {
                $uuid = $resp.uuid
                Write-Log "[$IssuerCode] Pendiente (intento $intento/$MaxIntentos), uuid=$uuid"
                Start-Sleep -Seconds $EsperaSegundos
            }
            'error' {
                throw "[$IssuerCode] Error de la API: $($resp.message)"
            }
            default {
                throw "[$IssuerCode] Respuesta inesperada: $($resp | ConvertTo-Json -Compress)"
            }
        }
    }

    throw "[$IssuerCode] Se agotaron los $MaxIntentos intentos sin recibir status=ready"
}

function Save-PadronCsv {
    param(
        [string]$IssuerCode,
        [string]$BalanceDate,
        [pscustomobject]$Data
    )

    $subcarpeta = $SubcarpetaPorIssuer[$IssuerCode]
    $destinoCarpeta = Join-Path $DestinoBase $subcarpeta

    if (-not (Test-Path $destinoCarpeta)) {
        throw "No se encuentra la carpeta destino: $destinoCarpeta (no esta montada la red T:\?)"
    }

    $sufijoArchivo = if ($Mensual) { '_CierreMes' } else { '' }
    $nombreArchivo = "Padron_${subcarpeta}_${BalanceDate}${sufijoArchivo}.csv"
    $rutaCompleta = Join-Path $destinoCarpeta $nombreArchivo

    # $Data.csv ya es el texto CSV crudo ';'-delimitado que devuelve BYMA, tal cual (api/padron.js
    # dejo de parsearlo a columns/rows para no inflar el payload JSON ~3.4x en la transferencia).
    Set-Content -Path $rutaCompleta -Value $Data.csv -Encoding UTF8 -NoNewline
    Write-Log "[$IssuerCode] Guardado: $rutaCompleta"
}

# --- Main ------------------------------------------------------------------------

if ($Mensual -and -not $BalanceDateOverride) {
    $hoy = (Get-Date).Date
    $primerDiaMesActual = [datetime]::new($hoy.Year, $hoy.Month, 1)
    $mesCierre = $primerDiaMesActual.AddDays(-1)   # ultimo dia calendario del mes anterior
    $ultimoHabilMesAnterior = Get-LastBusinessDayOfMonth -Anio $mesCierre.Year -Mes $mesCierre.Month
    $fechaObjetivoCorrida = (Add-BusinessDays -Fecha $ultimoHabilMesAnterior -Dias 3).Date

    if ($hoy -ne $fechaObjetivoCorrida) {
        Write-Log "Modo mensual: hoy ($($hoy.ToString('yyyy-MM-dd'))) no es el dia de corrida (corresponde el $($fechaObjetivoCorrida.ToString('yyyy-MM-dd'))). Sin accion."
        exit 0
    }

    $BalanceDateOverride = $ultimoHabilMesAnterior.ToString('yyyy-MM-dd')
    Write-Log "Modo mensual: hoy es el dia de corrida. Cierre de mes a descargar: $BalanceDateOverride"
}

$BalanceDate = if ($BalanceDateOverride) { $BalanceDateOverride } else { (Get-Date).AddDays(-3).ToString('yyyy-MM-dd') }
Write-Log "=== Inicio descarga padron - balanceDate=$BalanceDate ==="

foreach ($issuer in $Issuers) {
    try {
        $data = Get-PadronData -IssuerCode $issuer -BalanceDate $BalanceDate
        Save-PadronCsv -IssuerCode $issuer -BalanceDate $BalanceDate -Data $data
    }
    catch {
        Write-Log "ERROR procesando ${issuer}: $($_.Exception.Message)"
    }
}

Write-Log "=== Fin descarga padron ==="
