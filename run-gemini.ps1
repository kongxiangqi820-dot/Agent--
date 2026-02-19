$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

function Import-DotEnvFile([string]$Path) {
  if (-not (Test-Path $Path)) {
    return
  }

  Get-Content -Path $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) {
      return
    }

    $idx = $line.IndexOf("=")
    if ($idx -le 0) {
      return
    }

    $name = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1)
    if (-not $name) {
      return
    }

    $existing = (Get-Item -Path ("Env:" + $name) -ErrorAction SilentlyContinue)
    if (-not $existing -or [string]::IsNullOrWhiteSpace($existing.Value)) {
      Set-Item -Path ("Env:" + $name) -Value $value
    }
  }
}

Import-DotEnvFile (Join-Path $PSScriptRoot ".env")

if (-not $env:OPENAI_API_KEY -and $env:GEMINI_API_KEY) {
  $env:OPENAI_API_KEY = $env:GEMINI_API_KEY
}

if (-not $env:OPENAI_API_KEY) {
  Write-Host "Missing key. Set OPENAI_API_KEY or GEMINI_API_KEY first."
  exit 1
}

$env:OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

& (Join-Path $PSScriptRoot "run.ps1") -Config "agent.gemini.json"
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
