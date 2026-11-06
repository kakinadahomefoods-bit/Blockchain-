param([ValidateSet('Ethereum','Local')][string]$Mode='Ethereum')
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
Write-Host '======================================================' -ForegroundColor Cyan
Write-Host " BlockAttend : $Mode Mode - Setup + Start" -ForegroundColor Cyan
Write-Host '======================================================' -ForegroundColor Cyan
Write-Host 'First launch needs internet for open-source dependencies.' -ForegroundColor Yellow

function Find-Python {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($version in @('3.12','3.13','3.11')) {
      try {
        & py "-$version" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] in [(3,11),(3,12),(3,13)] else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { return @{Cmd='py';Args=@("-$version")} }
      } catch { }
    }
  }
  foreach ($candidate in @('python','python3',"$env:LOCALAPPDATA\Programs\Python\Python312\python.exe","$env:LOCALAPPDATA\Programs\Python\Python313\python.exe")) {
    if (!(Get-Command $candidate -ErrorAction SilentlyContinue) -and !(Test-Path $candidate)) { continue }
    try {
      & $candidate -c 'import sys; raise SystemExit(0 if sys.version_info[:2] in [(3,11),(3,12),(3,13)] else 1)' 2>$null
      if ($LASTEXITCODE -eq 0) { return @{Cmd=$candidate;Args=@()} }
    } catch { }
  }
  return $null
}

function Find-Node {
  foreach ($path in @('node',"$env:ProgramFiles\nodejs\node.exe","$env:APPDATA\npm\node.exe")) {
    try { & $path --version *> $null; if ($LASTEXITCODE -eq 0) { return $path } } catch { }
  }
  return $null
}
function Find-Npm {
  foreach ($path in @('npm.cmd',"$env:ProgramFiles\nodejs\npm.cmd")) {
    try { & $path --version *> $null; if ($LASTEXITCODE -eq 0) { return $path } } catch { }
  }
  return $null
}
function Refresh-Path {
  $env:PATH=[Environment]::GetEnvironmentVariable('PATH','Machine')+';'+[Environment]::GetEnvironmentVariable('PATH','User')
}
function Install-Winget([string]$id) {
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { return $false }
  Write-Host "Requesting installation of $id via winget..." -ForegroundColor Yellow
  & winget install --id $id --exact --scope user --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) { Write-Warning "winget installation of $id failed."; return $false }
  Refresh-Path
  return $true
}
try {
  $python=Find-Python
  if (-not $python) {
    [void](Install-Winget 'Python.Python.3.12')
    $python=Find-Python
  }
  if (-not $python) { throw 'Python 3.11-3.13 not found. Install Python 3.12 from python.org (check Add Python to PATH), then run again.' }
  if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Write-Host 'Creating the isolated Python environment...'
    $pyArgs=$python.Args
    & $python.Cmd @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
  }
  $venv=Join-Path $root '.venv\Scripts\python.exe'
  if ($Mode -eq 'Ethereum') {
    & $venv -m pip install --disable-pip-version-check -r requirements-ethereum.txt
  } else {
    & $venv -m pip install --disable-pip-version-check -r requirements.txt
  }
  if ($LASTEXITCODE -ne 0) { throw 'Python package installation failed; check your internet connection.' }
  & $venv scripts\init_project.py
  if ($LASTEXITCODE -ne 0) { throw 'Unable to create faculty login and local database.' }
  if ($Mode -eq 'Ethereum') {
    $node=Find-Node
    $npm=Find-Npm
    if (-not $node -or -not $npm) {
      [void](Install-Winget 'OpenJS.NodeJS.LTS')
      $node=Find-Node
      $npm=Find-Npm
    }
    if (-not $node -or -not $npm) { throw 'Node.js is missing. Install Node.js LTS from nodejs.org and run again.' }
    if (-not (Test-Path 'node_modules\ganache\dist\node\cli.js') -or -not (Test-Path 'node_modules\.bin\solcjs.cmd')) {
      Write-Host 'Installing Ganache and the Solidity compiler (first launch only)...'
      & $npm install --no-audit --no-fund --prefer-offline
      if ($LASTEXITCODE -ne 0) { throw 'npm installation failed; check your internet connection.' }
    }
    $env:BLOCKATTEND_NODE_EXE=$node
    & $venv scripts\start_evm.py
  } else {
    & $venv scripts\start_local.py
  }
  if ($LASTEXITCODE -ne 0) { throw 'The application stopped with an error; check the message above.' }
} catch {
  Write-Host "`nFAILED: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host 'Do not delete your data folder: it contains your existing records.' -ForegroundColor Yellow
  exit 1
}
