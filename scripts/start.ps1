$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$backendPath=Join-Path $projectRoot 'backend'
$frontendPath=Join-Path $projectRoot 'frontend'
$pythonPath=Join-Path $projectRoot '.venv\Scripts\python.exe'
$vitePath=Join-Path $frontendPath 'node_modules\vite\bin\vite.js'
if (!(Test-Path -LiteralPath $pythonPath) -or !(Test-Path -LiteralPath $vitePath)) { throw 'Install dependencies first using README.md.' }
$logPath=Join-Path $projectRoot '.logs'
New-Item -ItemType Directory -Force -Path $logPath | Out-Null
function Is-Ready([string]$Url) {
    try { return (Invoke-WebRequest -Uri $Url -TimeoutSec 2 -UseBasicParsing).StatusCode -eq 200 } catch { return $false }
}
if (!(Is-Ready 'http://127.0.0.1:8011/api/health')) {
    Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8011') -WorkingDirectory $backendPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logPath 'backend.log') -RedirectStandardError (Join-Path $logPath 'backend-error.log') | Out-Null
}
if (!(Is-Ready 'http://127.0.0.1:5173')) {
    $nodePath=(Get-Command node -ErrorAction Stop).Source
    Start-Process -FilePath $nodePath -ArgumentList @(('"'+$vitePath+'"'),'--host','127.0.0.1','--strictPort') -WorkingDirectory $frontendPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logPath 'frontend.log') -RedirectStandardError (Join-Path $logPath 'frontend-error.log') | Out-Null
}
function Wait-Ready([string]$Url, [string]$Service) {
    $deadline=(Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        if (Is-Ready $Url) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "$Service did not become ready. Check startup logs in $logPath."
}
Wait-Ready 'http://127.0.0.1:8011/api/health' 'Backend'
Wait-Ready 'http://127.0.0.1:5173/api/health' 'Frontend API proxy'
Write-Host 'StockPilot is ready: http://127.0.0.1:5173'
Write-Host 'Demo: demo@stockpilot.local / StockPilot-demo-2026!'
Write-Host ('Startup logs: '+$logPath)
