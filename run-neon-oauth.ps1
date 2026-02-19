param()

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "run-supabase-gemini.ps1")
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
