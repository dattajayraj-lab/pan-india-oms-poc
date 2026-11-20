<#
.SYNOPSIS
  Stops the Grid-India OMS POC servers started by start-oms.ps1 (API on 8000, frontend on 5173).
#>
param([int]$ApiPort = 8000, [int]$WebPort = 5173)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $Root '.oms-pids'

foreach ($port in $ApiPort, $WebPort) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped process $($c.OwningProcess) on port $port"
    }
}
if (Test-Path $PidFile) {
    foreach ($id in Get-Content $PidFile) {
        if ($id -match '^\d+$') { Stop-Process -Id ([int]$id) -Force -ErrorAction SilentlyContinue }
    }
    Remove-Item $PidFile -Force
}
Write-Host 'OMS stopped.' -ForegroundColor Green
