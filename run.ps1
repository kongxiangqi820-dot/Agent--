param(
  [string]$Config = "agent.json"
)

$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = (Join-Path $PSScriptRoot "src")

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

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
  Write-Host "Python not found. Install Python 3.10+ and ensure it is in PATH."
  exit 1
}

if ($py.Source -like "*WindowsApps*python.exe") {
  Write-Host "Detected Windows Store python stub: $($py.Source)"
  Write-Host "Install real Python 3.10+ (python.org), reopen terminal, then run again."
  exit 1
}

$configPath = Join-Path $PSScriptRoot $Config
python -m agentfw.cli --config $configPath
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
