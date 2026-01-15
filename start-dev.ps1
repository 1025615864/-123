param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [string]$BackendHost = "127.0.0.1",
  [string]$FrontendHost = "127.0.0.1",
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

$venvDir = Join-Path $backendDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $backendDir)) { throw "backend directory not found: $backendDir" }
if (-not (Test-Path $frontendDir)) { throw "frontend directory not found: $frontendDir" }

Write-Host "Repo: $repoRoot"
Write-Host "Backend: http://${BackendHost}:${BackendPort}"
Write-Host "Frontend: http://${FrontendHost}:${FrontendPort}"

if (-not $SkipInstall) {
  if (-not (Test-Path $venvPython)) {
    Write-Host "Creating backend venv: $venvDir"
    & py -m venv $venvDir
  }

  Write-Host "Installing backend requirements..."
  & $venvPython -m pip install -U pip
  & $venvPython -m pip install -r (Join-Path $backendDir "requirements.txt")

  $nodeModules = Join-Path $frontendDir "node_modules"
  if (-not (Test-Path $nodeModules)) {
    Write-Host "Installing frontend dependencies..."
    & npm --prefix $frontendDir install
  }
}

$proxyTarget = "http://${BackendHost}:${BackendPort}"
$wsProxyTarget = $proxyTarget -replace '^http', 'ws'

$backendCmd = "& '${venvPython}' -m uvicorn app.main:app --reload --host ${BackendHost} --port ${BackendPort}"
$frontendCmd = "`$env:VITE_PROXY_TARGET='${proxyTarget}'; `$env:VITE_WS_PROXY_TARGET='${wsProxyTarget}'; npm --prefix '${frontendDir}' run dev -- --host ${FrontendHost} --port ${FrontendPort}"

Write-Host "Starting backend..."
Start-Process -FilePath "powershell" -ArgumentList @(
  "-NoExit",
  "-Command",
  $backendCmd
) -WorkingDirectory $backendDir

Write-Host "Starting frontend..."
Start-Process -FilePath "powershell" -ArgumentList @(
  "-NoExit",
  "-Command",
  $frontendCmd
) -WorkingDirectory $repoRoot

Write-Host "Done. Close the two spawned windows to stop services."
