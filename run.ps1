# News Trust Platform - launcher (Windows PowerShell).
# Usage (from project root):
#   .\run.ps1                 # start dashboard (port 8000 or $env:NTP_PORT)
#   .\run.ps1 streamlit       # start Streamlit product UI (recommended MVP)
#   .\run.ps1 -Port 8765      # listen on 8765
#   .\run.ps1 stop            # kill whatever is listening on that port
#   .\run.ps1 restart         # stop then serve (same port)
#   .\run.ps1 setup           # first-time venv + pip install -e ".[dev]"
#   .\run.ps1 migrate         # apply Django migrations
#   .\run.ps1 score-feeds     # seed RSS feeds (if empty), ingest, and score

param(
    [Parameter(Position = 0)]
    [ValidateSet("serve", "streamlit", "worker", "setup", "migrate", "score-feeds", "train", "train-quick", "test", "doctor", "stop", "restart")]
    [string]$Command = "serve",
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"

function Get-PythonForVenv {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return "py"
    }
    return "python"
}

function Get-ListeningPort {
    if ($Port -gt 0) { return $Port }
    $e = $env:NTP_PORT
    if ($e) {
        $parsed = 0
        if ([int]::TryParse($e, [ref]$parsed)) { return $parsed }
    }
    return 8000
}

function Write-ServeBanner([int]$p) {
    $base = "http://127.0.0.1:$p"
    Write-Host ""
    Write-Host "  News Trust Platform" -ForegroundColor Cyan
    Write-Host "  -------------------"
    Write-Host "  Dashboard:  $base/#dashboard"
    Write-Host "  Quick demo: $base/?demo=1#dashboard"
    Write-Host "  Queue API:  $base/api/v1/jobs/submit"
    Write-Host "  (OpenAPI not served: configure clients from code or REST tools.)" -ForegroundColor DarkGray
    Write-Host "  Health:     $base/api/health"
    Write-Host ""
}

function Stop-ListenerOnPort([int]$ListenPort) {
    try {
        $conns = @(Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction Stop |
                Select-Object -ExpandProperty OwningProcess -Unique)
        foreach ($procId in $conns) {
            if ($procId -and $procId -ne 0) {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                Write-Host "Stopped process $procId (was listening on port $ListenPort)"
            }
        }
        if (-not $conns -or $conns.Count -eq 0) {
            Write-Host "Nothing was listening on port $ListenPort"
        }
    }
    catch {
        Write-Host "Could not inspect port $ListenPort (try Task Manager or a different -Port). $_" -ForegroundColor Yellow
    }
}

switch ($Command) {
    "setup" {
        $py = Get-PythonForVenv
        if (-not (Test-Path $venvPython)) {
            if ($py -eq "py") {
                & py -3.11 -m venv .venv
            }
            else {
                & python -m venv .venv
            }
        }
        & $venvPython -m pip install -U pip
        & $venvPython -m pip install -e ".[dev]"
        Write-Host "Setup done. Start Streamlit UI: .\run.ps1 streamlit   (optional: .\run.ps1 train)"
        break
    }
    "stop" {
        Stop-ListenerOnPort (Get-ListeningPort)
        break
    }
    "restart" {
        if (-not (Test-Path $venvPython)) {
            Write-Host "No .venv found. Run first: .\run.ps1 setup"
            exit 1
        }
        $p = Get-ListeningPort
        Stop-ListenerOnPort $p
        Start-Sleep -Seconds 1
        Write-ServeBanner $p
        $env:NTP_PORT = "$p"
        & $venvPython (Join-Path $Root "manage.py") runserver "127.0.0.1:$p"
        break
    }
    default {
        if (-not (Test-Path $venvPython)) {
            Write-Host "No .venv found. Run first: .\run.ps1 setup"
            exit 1
        }
        switch ($Command) {
            "train" {
                & $venvPython -m src.pipeline.run_train
            }
            "train-quick" {
                & $venvPython -m src.pipeline.run_train --quick --skip-build
            }
            "serve" {
                $p = Get-ListeningPort
                Write-ServeBanner $p
                $env:NTP_PORT = "$p"
                & $venvPython (Join-Path $Root "manage.py") runserver "127.0.0.1:$p"
            }
            "streamlit" {
                Write-Host ""
                Write-Host "  News Trust Platform - Streamlit Product UI" -ForegroundColor Cyan
                Write-Host "  ----------------------------------------"
                Write-Host "  App:       http://localhost:8501"
                Write-Host "  Auto demo: http://localhost:8501/?demo=1"
                Write-Host ""
                & $venvPython -m streamlit run (Join-Path $Root "streamlit_app.py") --server.port 8501 --browser.gatherUsageStats false
            }
            "migrate" {
                & $venvPython (Join-Path $Root "manage.py") migrate
            }
            "score-feeds" {
                & $venvPython (Join-Path $Root "manage.py") score_feeds --seed
            }
            "worker" {
                & $venvPython (Join-Path $Root "manage.py") process_jobs --poll-interval 2 --worker-name win-worker
            }
            "test" {
                & $venvPython -m pytest -q
            }
            "doctor" {
                & $venvPython -m src.pipeline.doctor
            }
        }
    }
}
