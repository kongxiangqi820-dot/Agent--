param(
  [string]$ListenHost = "0.0.0.0",
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "run-api.ps1") -Config "agent.supabase.json" -ListenHost $ListenHost -Port $Port
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
