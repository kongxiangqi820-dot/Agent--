param(
  [string]$Root = "."
)

$ErrorActionPreference = "Stop"

$patterns = @(
  @{ Name = "OpenAI key"; Regex = "sk-[A-Za-z0-9]{20,}" },
  @{ Name = "GitHub PAT"; Regex = "github_pat_[A-Za-z0-9_]{20,}" },
  @{ Name = "Google API key"; Regex = "AIza[0-9A-Za-z\-_]{20,}" },
  @{ Name = "Private key header"; Regex = "-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----" }
)

$excludeDirs = @("\.git\", "\.venv\", "\.agent\", "node_modules\", "__pycache__\")
$files = Get-ChildItem -Path $Root -Recurse -File

$hits = @()
foreach ($f in $files) {
  $full = $f.FullName
  $skip = $false
  foreach ($d in $excludeDirs) {
    if ($full -like "*$d*") {
      $skip = $true
      break
    }
  }
  if ($skip) { continue }

  $content = Get-Content -Path $full -Raw -ErrorAction SilentlyContinue
  if (-not $content) { continue }

  foreach ($p in $patterns) {
    if ($content -match $p.Regex) {
      $hits += [PSCustomObject]@{
        file = $full
        pattern = $p.Name
      }
    }
  }
}

if ($hits.Count -eq 0) {
  Write-Host "No obvious secrets found."
  exit 0
}

Write-Host "Potential secrets found:"
$hits | Sort-Object file, pattern | Format-Table -AutoSize
exit 1
