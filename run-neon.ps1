param()

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "run.ps1") -Config "agent.supabase.gemini.json"
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
