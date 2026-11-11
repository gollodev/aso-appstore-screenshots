<#
.SYNOPSIS
  Installer for the aso-appstore-screenshots agent skill (Windows PowerShell 5.1+ / PowerShell 7+).

.DESCRIPTION
  Installs the skill into Claude Code and/or GitHub Copilot skill folders, creates a shared
  Python virtual environment with Pillow, runs a self-test and (optionally) configures the
  Gemini MCP server used for AI enhancement.

.EXAMPLE
  .\install.ps1                                  # Claude Code + Copilot, user scope
.EXAMPLE
  .\install.ps1 -Copilot -Project C:\code\my-app # .github\skills in a repository
.EXAMPLE
  $env:GEMINI_API_KEY = "..."; .\install.ps1 -All -SetupMcp
.EXAMPLE
  .\install.ps1 -All -Uninstall
#>
[CmdletBinding()]
param(
  [switch]$Claude,
  [switch]$Copilot,
  [switch]$Agents,
  [switch]$All,
  [string]$Project = "",
  [switch]$Link,
  [switch]$SetupMcp,
  [switch]$NoVenv,
  [switch]$SkipTest,
  [switch]$Force,
  [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$SkillName = "aso-appstore-screenshots"
$SrcDir = $PSScriptRoot
$OnWindows = ($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows
$HomeDir = if ($OnWindows) { $env:USERPROFILE } else { $env:HOME }
$DataDir = if ($env:ASO_VENV) { Split-Path $env:ASO_VENV -Parent }
           elseif ($OnWindows) { Join-Path $env:LOCALAPPDATA $SkillName }
           else { Join-Path ($(if ($env:XDG_DATA_HOME) { $env:XDG_DATA_HOME } else { Join-Path $HomeDir ".local/share" })) $SkillName }
$VenvDir = if ($env:ASO_VENV) { $env:ASO_VENV } else { Join-Path $DataDir "venv" }
$VenvPy = if ($OnWindows) { Join-Path $VenvDir "Scripts\python.exe" } else { Join-Path $VenvDir "bin/python" }
$env:PYTHONDONTWRITEBYTECODE = "1"

function Ok($m)   { Write-Host "✓ $m" -ForegroundColor Green }
function Warn($m) { Write-Host "⚠ $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "✗ $m" -ForegroundColor Red }

$Targets = @()
if ($All) { $Targets = @("claude", "copilot", "agents") }
else {
  if ($Claude) { $Targets += "claude" }
  if ($Copilot) { $Targets += "copilot" }
  if ($Agents) { $Targets += "agents" }
}
if ($Targets.Count -eq 0) { $Targets = @("claude", "copilot") }

if ($Project) { $Project = (Resolve-Path $Project).Path }

function Get-Dest([string]$t) {
  if ($Project) {
    switch ($t) {
      "claude"  { return (Join-Path $Project ".claude/skills/$SkillName") }
      "copilot" { return (Join-Path $Project ".github/skills/$SkillName") }
      "agents"  { return (Join-Path $Project ".agents/skills/$SkillName") }
    }
  }
  switch ($t) {
    "claude"  { return (Join-Path $HomeDir ".claude/skills/$SkillName") }
    "copilot" { return (Join-Path $HomeDir ".copilot/skills/$SkillName") }
    "agents"  { return (Join-Path $HomeDir ".agents/skills/$SkillName") }
  }
}

function Test-OurSkill([string]$d) {
  $f = Join-Path $d "SKILL.md"
  return (Test-Path $f) -and (Select-String -Path $f -Pattern "^name: $SkillName" -Quiet)
}

function Test-IsLink([string]$d) {
  $i = Get-Item $d -Force -ErrorAction SilentlyContinue
  return $i -and ($i.Attributes -band [IO.FileAttributes]::ReparsePoint)
}

function Remove-Dest([string]$d) {
  if (Test-IsLink $d) { (Get-Item $d -Force).Delete(); return }
  Remove-Item $d -Recurse -Force
}

# ── Uninstall ────────────────────────────────────────────────────────
if ($Uninstall) {
  foreach ($t in $Targets) {
    $d = Get-Dest $t
    if (Test-Path $d) {
      if ((Test-IsLink $d) -or (Test-OurSkill $d) -or $Force) { Remove-Dest $d; Ok "removed $d" }
      else { Fail "$d doesn't look like $SkillName — use -Force" }
    } else { Write-Host "- nothing at $d" -ForegroundColor DarkGray }
  }
  if (-not $Project -and (Test-Path $VenvDir)) {
    $left = @(".claude", ".copilot", ".agents") | Where-Object { Test-Path (Join-Path $HomeDir "$_/skills/$SkillName") }
    if (-not $left) { Remove-Item $DataDir -Recurse -Force; Ok "removed Python env $DataDir" }
    else { Write-Host "- kept shared Python env $VenvDir (other installs still use it)" -ForegroundColor DarkGray }
  }
  exit 0
}

# ── Python ───────────────────────────────────────────────────────────
$PyCmd = $null
$candidates = if ($OnWindows) { @(@("py", "-3"), @("python"), @("python3")) } else { @(@("python3"), @("python")) }
foreach ($c in $candidates) {
  $exe = $c[0]; $pre = @($c | Select-Object -Skip 1)
  if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
  try {
    & $exe @pre -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { $PyCmd = $c; break }
  } catch { }
}
if (-not $PyCmd) {
  Fail "Python 3.9+ is required. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') or 'winget install Python.Python.3.12', then re-run."
  exit 1
}
$PyExe = $PyCmd[0]; $PyPre = @($PyCmd | Select-Object -Skip 1)
Ok "Python: $((& $PyExe @PyPre --version) 2>&1)"

function Initialize-PythonEnv {
  if (-not $NoVenv) {
    if (-not (Test-Path $VenvPy)) {
      New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
      & $PyExe @PyPre -m venv $VenvDir 2>$null
      if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPy)) {
        Warn "could not create a virtualenv — using the system Python"
        $script:NoVenv = $true
      }
    }
    if (-not $script:NoVenv) {
      & $VenvPy -m pip install --quiet --disable-pip-version-check --upgrade pip 2>$null | Out-Null
      & $VenvPy -m pip install --quiet --disable-pip-version-check -r (Join-Path $SrcDir "requirements.txt")
      if ($LASTEXITCODE -ne 0) { Fail "pip install failed"; exit 1 }
      return $VenvPy
    }
  }
  & $PyExe @PyPre -c "import PIL" 2>$null
  if ($LASTEXITCODE -ne 0) {
    & $PyExe @PyPre -m pip install --user --quiet -r (Join-Path $SrcDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) { Fail "Pillow is missing. Run: $PyExe -m pip install Pillow"; exit 1 }
  }
  return (& $PyExe @PyPre -c "import sys; print(sys.executable)").Trim()
}

function Copy-Skill([string]$d) {
  $parent = Split-Path $d -Parent
  New-Item -ItemType Directory -Force -Path $parent | Out-Null
  if (Test-Path $d) {
    if ((Test-IsLink $d) -or (Test-OurSkill $d) -or $Force) { Remove-Dest $d }
    else { Fail "$d exists and isn't $SkillName — re-run with -Force"; exit 1 }
  }
  if ($Link) {
    if ($OnWindows) { New-Item -ItemType Junction -Path $d -Target $SrcDir | Out-Null }
    else { New-Item -ItemType SymbolicLink -Path $d -Target $SrcDir | Out-Null }
    return
  }
  New-Item -ItemType Directory -Force -Path $d | Out-Null
  foreach ($it in @("SKILL.md", "README.md", "LICENSE", "requirements.txt", "scripts", "assets", "examples")) {
    $p = Join-Path $SrcDir $it
    if (Test-Path $p) { Copy-Item $p -Destination $d -Recurse -Force }
  }
  Get-ChildItem $d -Recurse -Force -Include "__pycache__", ".DS_Store" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

function Invoke-SelfTest([string]$d, [string]$py) {
  $tmp = Join-Path ([IO.Path]::GetTempPath()) ("aso-test-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $tmp | Out-Null
  try {
    & $py (Join-Path $d "scripts/compose.py") --device iphone-6.9 --bg "#2563EB" --verb TEST --desc "INSTALL OK" `
      --screenshot (Join-Path $d "examples/sample-phone-portrait.png") --output (Join-Path $tmp "iphone.png") | Out-Null
    $a = $LASTEXITCODE
    & $py (Join-Path $d "scripts/compose.py") --device android-tablet-10 --orientation landscape --skin none --bg "#111827" `
      --verb TEST --desc TABLET --screenshot (Join-Path $d "examples/sample-android-tablet-landscape.png") --output (Join-Path $tmp "tab.png") 2>$null | Out-Null
    $b = $LASTEXITCODE
    & $py (Join-Path $d "scripts/validate.py") (Join-Path $tmp "iphone.png") (Join-Path $tmp "tab.png") | Out-Null
    if ($a -eq 0 -and $b -eq 0 -and $LASTEXITCODE -eq 0) { Ok "self-test passed (rendered + validated iPhone and Android tablet scaffolds)" }
    else { Fail "self-test failed — run: $py $d/scripts/compose.py --help" }
    $font = (& $py (Join-Path $d "scripts/fonts.py") | Select-Object -First 1) -replace ".*→ ", ""
    Write-Host "  headline font: $font" -ForegroundColor DarkGray
  } finally { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}

# ── Install ──────────────────────────────────────────────────────────
$Installed = @()
foreach ($t in $Targets) {
  $d = Get-Dest $t
  Copy-Skill $d
  if ($Link) { Ok "$t → $d (link → $SrcDir)" } else { Ok "$t → $d" }
  $Installed += , @($t, $d)
}
$Py = Initialize-PythonEnv
Ok "Python env: $Py (Pillow $((& $Py -c 'import PIL; print(PIL.__version__)')))"
if (-not $SkipTest) { Invoke-SelfTest $Installed[0][1] $Py }

# ── Gemini MCP (optional) ────────────────────────────────────────────
function Read-JsonFile([string]$path) {
  if (Test-Path $path) {
    $raw = Get-Content $path -Raw
    if ($raw.Trim()) { return ($raw | ConvertFrom-Json) }
  }
  return [pscustomobject]@{}
}
function Set-Prop($obj, [string]$name, $value) {
  if ($obj.PSObject.Properties[$name]) { $obj.$name = $value } else { $obj | Add-Member -NotePropertyName $name -NotePropertyValue $value }
}
function Write-JsonFile([string]$path, $obj) {
  New-Item -ItemType Directory -Force -Path (Split-Path $path -Parent) | Out-Null
  $json = $obj | ConvertTo-Json -Depth 20
  [IO.File]::WriteAllText($path, $json + "`n", (New-Object Text.UTF8Encoding($false)))
}
function Add-VsCodeMcp([string]$path) {
  $cfg = Read-JsonFile $path
  if (-not $cfg.PSObject.Properties["inputs"]) { Set-Prop $cfg "inputs" @() }
  $inputs = @($cfg.inputs | Where-Object { $_.id -ne "gemini-api-key" })
  $inputs += [pscustomobject]@{ type = "promptString"; id = "gemini-api-key"; description = "Google AI Studio API key for Gemini / Nano Banana Pro"; password = $true }
  Set-Prop $cfg "inputs" $inputs
  if (-not $cfg.PSObject.Properties["servers"]) { Set-Prop $cfg "servers" ([pscustomobject]@{}) }
  Set-Prop $cfg.servers "gemini" ([pscustomobject]@{ type = "stdio"; command = "npx"; args = @("-y", "@houtini/gemini-mcp"); env = [pscustomobject]@{ GEMINI_API_KEY = '${input:gemini-api-key}' } })
  Write-JsonFile $path $cfg
  Ok "VS Code: gemini MCP added to $path (VS Code asks for the key on first start)"
}

if ($SetupMcp) {
  Write-Host ""
  if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
    Warn "npx (Node.js 18+) not found — install Node.js LTS from https://nodejs.org (or 'winget install OpenJS.NodeJS.LTS') and re-run with -SetupMcp"
  } else {
    $Key = $env:GEMINI_API_KEY
    if (-not $Key -and ($Targets -contains "claude" -or $Targets -contains "copilot")) {
      $sec = Read-Host "Gemini API key (https://aistudio.google.com/apikey) — leave empty to skip" -AsSecureString
      $Key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    }
    foreach ($t in $Targets) {
      if ($t -eq "claude") {
        if ((Get-Command claude -ErrorAction SilentlyContinue) -and $Key) {
          $scope = if ($Project) { "local" } else { "user" }
          Push-Location $(if ($Project) { $Project } else { $HomeDir })
          try {
            & claude mcp remove gemini -s $scope 2>$null | Out-Null
            & claude mcp add -e "GEMINI_API_KEY=$Key" -s $scope gemini -- npx -y "@houtini/gemini-mcp" | Out-Null
            if ($LASTEXITCODE -eq 0) { Ok "Claude Code: gemini MCP added ($scope scope) — check with: claude mcp get gemini" }
            else { Warn "Claude Code: 'claude mcp add' failed — see README → Gemini MCP setup" }
          } finally { Pop-Location }
        } else { Warn "Claude Code: 'claude' CLI or API key not available — see README → Gemini MCP setup" }
      }
      elseif ($t -eq "copilot") {
        if ($Key) {
          $path = Join-Path $HomeDir ".copilot/mcp-config.json"
          $cfg = Read-JsonFile $path
          if (-not $cfg.PSObject.Properties["mcpServers"]) { Set-Prop $cfg "mcpServers" ([pscustomobject]@{}) }
          Set-Prop $cfg.mcpServers "gemini" ([pscustomobject]@{ type = "local"; command = "npx"; args = @("-y", "@houtini/gemini-mcp"); env = [pscustomobject]@{ GEMINI_API_KEY = $Key }; tools = @("*") })
          Write-JsonFile $path $cfg
          Ok "Copilot CLI: gemini MCP added to $path — check with /mcp"
        } else { Warn "Copilot CLI: no API key given — skipped ~/.copilot/mcp-config.json" }
        if ($Project) { Add-VsCodeMcp (Join-Path $Project ".vscode/mcp.json") }
        else {
          $vsUser = if ($OnWindows) { Join-Path $env:APPDATA "Code\User" }
                    elseif ($IsMacOS) { Join-Path $HomeDir "Library/Application Support/Code/User" }
                    else { Join-Path $HomeDir ".config/Code/User" }
          if (Test-Path $vsUser) { Add-VsCodeMcp (Join-Path $vsUser "mcp.json") }
          else { Write-Host "  VS Code user folder not found — skipped VS Code mcp.json" -ForegroundColor DarkGray }
        }
      }
    }
  }
}

# ── Next steps ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "Next steps"
foreach ($e in $Installed) {
  switch ($e[0]) {
    "claude"  { Write-Host "  • Claude Code: start 'claude' in your app's folder and run /$SkillName" }
    "copilot" { Write-Host "  • Copilot CLI: run '/skills reload' then '/skills info $SkillName'; use /$SkillName"
                Write-Host "  • VS Code (Copilot agent mode): type /$SkillName in Chat, or Chat: Open Customizations → Skills" }
    "agents"  { Write-Host "  • Other Agent Skills agents: the skill is in $($e[1])" }
  }
}
if (-not $SetupMcp) { Write-Host "  • Optional AI polish: re-run with -SetupMcp (needs Node.js + a Gemini API key), or see README" }
