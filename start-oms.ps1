<#
.SYNOPSIS
  Starts the Grid-India OMS POC: backend API (FastAPI, port 8000) and frontend (Vite, port 5173).

.DESCRIPTION
  First run sets everything up automatically: Python virtual environment + packages, npm packages,
  database schema and seed data. Each server opens in its own PowerShell window so you can watch its log.
  Stop everything with .\stop-oms.ps1 (or close the two windows).

.EXAMPLE
  .\start-oms.ps1                 # start (set up on first run)
  .\start-oms.ps1 -Reset          # wipe the database and reseed before starting
  .\start-oms.ps1 -Reset -Demo    # reseed and load demo activity (tickets, FTC cases, codes, ...)
  .\start-oms.ps1 -NoBrowser      # don't open the browser
#>
param(
    [switch]$Reset,
    [switch]$Demo,
    [switch]$NoBrowser,
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173
)

$ErrorActionPreference = 'Stop'
$Root     = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend  = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$VenvPy   = Join-Path $Backend '.venv\Scripts\python.exe'
$PidFile  = Join-Path $Root '.oms-pids'

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Test-Port($port) {
    foreach ($h in '127.0.0.1', '::1') {
        try { $c = New-Object Net.Sockets.TcpClient($h, $port); $c.Close(); return $true } catch {}
    }
    return $false
}
function Stop-PortOwner($port) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue }
}

Write-Host ''
Write-Host 'Grid-India OMS - Proof of Concept' -ForegroundColor Yellow
Write-Host ''

# ---------------------------------------------------------------- prerequisites
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js not found. Install Node.js 20+ and re-run.' }
if (-not (Test-Path $VenvPy)) {
    Write-Step 'Creating Python virtual environment (first run)'
    $venvDir = Join-Path $Backend '.venv'
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv $venvDir }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { & python -m venv $venvDir }
    else { throw 'Python 3.11+ not found. Install Python and re-run.' }
    if (-not (Test-Path $VenvPy)) { throw 'Could not create the Python virtual environment' }
    Write-Step 'Installing backend packages'
    & $VenvPy -m pip install --disable-pip-version-check -q -r (Join-Path $Backend 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }
}
if (-not (Test-Path (Join-Path $Frontend 'node_modules'))) {
    Write-Step 'Installing frontend packages (first run)'
    Push-Location $Frontend
    try { npm install --no-audit --no-fund; if ($LASTEXITCODE -ne 0) { throw 'npm install failed' } } finally { Pop-Location }
}

# ---------------------------------------------------------------- free the ports if a reset is requested
if ($Reset -and (Test-Port $ApiPort)) {
    Write-Step "Stopping the running API on port $ApiPort (database reset needs the file unlocked)"
    Stop-PortOwner $ApiPort
    Start-Sleep -Seconds 2
}

# ---------------------------------------------------------------- database
$Db = Join-Path $Backend 'oms_dev.db'
Push-Location $Backend
try {
    if ($Reset -or -not (Test-Path $Db)) {
        Write-Step 'Creating database and seed data'
        & $VenvPy -m app.db.seed --reset
        if ($LASTEXITCODE -ne 0) { throw 'Seeding failed' }
        if ($Demo) {
            Write-Step 'Loading demo activity'
            & $VenvPy -m scripts.demo_data
        }
    } elseif ($Demo) {
        Write-Host '    -Demo only applies together with -Reset (or on first run); skipping.' -ForegroundColor DarkYellow
    }
} finally { Pop-Location }

# ---------------------------------------------------------------- start servers
$pids = @()
if (Test-Port $ApiPort) {
    Write-Host "    API already running on port $ApiPort - reusing it." -ForegroundColor DarkYellow
} else {
    Write-Step "Starting backend API on http://127.0.0.1:$ApiPort"
    $api = Start-Process powershell -PassThru -WorkingDirectory $Backend -ArgumentList @(
        '-NoExit', '-NoProfile', '-Command',
        "`$Host.UI.RawUI.WindowTitle = 'OMS API :$ApiPort'; & '$VenvPy' -m uvicorn app.main:app --host 127.0.0.1 --port $ApiPort")
    $pids += $api.Id
}

if (Test-Port $WebPort) {
    Write-Host "    Frontend already running on port $WebPort - reusing it." -ForegroundColor DarkYellow
} else {
    Write-Step "Starting frontend on http://localhost:$WebPort"
    $web = Start-Process powershell -PassThru -WorkingDirectory $Frontend -ArgumentList @(
        '-NoExit', '-NoProfile', '-Command',
        "`$Host.UI.RawUI.WindowTitle = 'OMS Web :$WebPort'; npx vite --port $WebPort --strictPort")
    $pids += $web.Id
}
if ($pids.Count) { Add-Content -Path $PidFile -Value ($pids -join "`n") }

# ---------------------------------------------------------------- wait until healthy
Write-Step 'Waiting for the services to come up'
$deadline = (Get-Date).AddSeconds(90)
$apiOk = $false; $webOk = $false
while ((Get-Date) -lt $deadline -and -not ($apiOk -and $webOk)) {
    if (-not $apiOk) { try { $apiOk = (Invoke-WebRequest "http://127.0.0.1:$ApiPort/api/v1/health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch {} }
    if (-not $webOk) { $webOk = Test-Port $WebPort }
    if (-not ($apiOk -and $webOk)) { Start-Sleep -Seconds 1 }
}
if (-not $apiOk) { Write-Host "    API did not respond within 90 s - check the 'OMS API' window." -ForegroundColor Red }
if (-not $webOk) { Write-Host "    Frontend did not respond within 90 s - check the 'OMS Web' window." -ForegroundColor Red }

$url = "http://localhost:$WebPort"
Write-Host ''
Write-Host "OMS is running:  $url" -ForegroundColor Green
Write-Host "API docs:        http://127.0.0.1:$ApiPort/docs     GraphQL: http://127.0.0.1:$ApiPort/graphql"
Write-Host 'Demo logins:     superadmin, nr_coord, nr_shiftic, nr_operator, re_dev, pg_user ...  password Grid@2026 (OTP shown on screen)'
Write-Host 'Stop:            .\stop-oms.ps1'
Write-Host ''
if (-not $NoBrowser -and $apiOk -and $webOk) { Start-Process $url }
