Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Repo       = "D:\CAFirm\cafirm"
$Backend    = Join-Path $Repo "backend"
$Frontend   = Join-Path $Repo "frontend"
$Venv       = Join-Path $Backend ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$NodeExe    = Join-Path $env:ProgramFiles "nodejs\node.exe"
$NpmCmd     = Join-Path $env:ProgramFiles "nodejs\npm.cmd"

$LogRoot  = Join-Path $Repo "validation_logs"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile   = Join-Path $LogRoot "ewp_000_1a_validation_$Timestamp.log"

function Write-Step {
    param([Parameter(Mandatory = $true)][string]$Message)

    Write-Host ""
    Write-Host "=====================================================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "=====================================================================" -ForegroundColor Cyan
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    Write-Host ""
    Write-Host "[RUN] $Name" -ForegroundColor Yellow

    $global:LASTEXITCODE = 0
    & $Command
    $ExitCode = $LASTEXITCODE

    if ($null -eq $ExitCode) {
        $ExitCode = 0
    }

    if ($ExitCode -ne 0) {
        throw "$Name failed with exit code $ExitCode"
    }

    Write-Host "[PASS] $Name" -ForegroundColor Green
}

if (-not (Test-Path -LiteralPath $LogRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
}

Set-Location -LiteralPath $Repo
Start-Transcript -LiteralPath $LogFile -Force | Out-Null

try {
    Write-Step "STEP 1 — PRE-FLIGHT"

    $RequiredFiles = @(
        "README.md",
        ".gitignore",
        ".pre-commit-config.yaml",
        "backend\manage.py",
        "backend\pyproject.toml",
        "backend\requirements\development.txt",
        "frontend\package.json",
        "scripts\verify_structure.py"
    )

    foreach ($RelativePath in $RequiredFiles) {
        $FullPath = Join-Path $Repo $RelativePath

        if (-not (Test-Path -LiteralPath $FullPath -PathType Leaf)) {
            throw "Required repository file missing: $FullPath"
        }
    }

    if (-not (Test-Path -LiteralPath $NodeExe -PathType Leaf)) {
        throw "Node.js executable not found: $NodeExe"
    }

    if (-not (Test-Path -LiteralPath $NpmCmd -PathType Leaf)) {
        throw "npm.cmd not found: $NpmCmd"
    }

    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw "Python launcher 'py' was not found."
    }

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git was not found."
    }

    $PythonVersion = (
        & py -3.12 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
    ).Trim()

    if ([string]::IsNullOrWhiteSpace($PythonVersion) -or $LASTEXITCODE -ne 0 -or -not $PythonVersion.StartsWith("3.12.")) {
        throw "Python 3.12 is required. Detected result: $PythonVersion"
    }

    $NodeVersion = ((& $NodeExe --version) | Out-String).Trim()
    if ([string]::IsNullOrWhiteSpace($NodeVersion)) {
        throw "Node.js returned no version output. Executable: $NodeExe"
    }

    if ([string]::IsNullOrWhiteSpace($NodeVersion)) {
        throw "Node.js returned no version output. Executable: $NodeExe"
    }

    $NodeMajor = [int](($NodeVersion -replace "^v", "").Split(".")[0])

    if ($NodeMajor -lt 20) {
        throw "Node.js 20 or later is required. Detected: $NodeVersion"
    }

    $NpmVersion = ((& $NpmCmd --version) | Out-String).Trim()
    $GitVersion = ((& git --version) | Out-String).Trim()

    Write-Host "Repository: $Repo" -ForegroundColor Green
    Write-Host "Python    : $PythonVersion" -ForegroundColor Green
    Write-Host "Node.js   : $NodeVersion" -ForegroundColor Green
    Write-Host "npm       : $NpmVersion" -ForegroundColor Green
    Write-Host "Git       : $GitVersion" -ForegroundColor Green
    Write-Host "Log       : $LogFile" -ForegroundColor Green

    Write-Step "STEP 2 — STRUCTURE VALIDATION"

    Invoke-Checked "Initial repository structure check" {
        & py -3.12 .\scripts\verify_structure.py
    }

    Write-Step "STEP 3 — GIT INITIALISATION"

    if (-not (Test-Path -LiteralPath (Join-Path $Repo ".git") -PathType Container)) {
        Invoke-Checked "Initialise Git repository" {
            & git init
        }
    }
    else {
        Write-Host "Git repository already initialised." -ForegroundColor Yellow
    }

    Invoke-Checked "Verify Git work tree" {
        & git rev-parse --is-inside-work-tree
    }

    Write-Step "STEP 4 — PYTHON VIRTUAL ENVIRONMENT"

    if (-not (Test-Path -LiteralPath $Venv -PathType Container)) {
        Invoke-Checked "Create Python 3.12 virtual environment" {
            & py -3.12 -m venv $Venv
        }
    }
    else {
        Write-Host "Existing virtual environment found: $Venv" -ForegroundColor Yellow
    }

    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        throw "Virtual-environment Python not found: $VenvPython"
    }

    $VenvVersion = (
        & $VenvPython -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
    ).Trim()

    if ([string]::IsNullOrWhiteSpace($VenvVersion) -or -not $VenvVersion.StartsWith("3.12.")) {
        throw "Virtual environment uses Python $VenvVersion; Python 3.12 is required."
    }

    Write-Host "Virtual environment Python: $VenvVersion" -ForegroundColor Green

    Write-Step "STEP 5 — BACKEND DEPENDENCIES"

    Set-Location -LiteralPath $Backend

    Invoke-Checked "Upgrade pip" {
        & $VenvPython -m pip install --upgrade pip
    }

    Invoke-Checked "Install backend development dependencies" {
        & $VenvPython -m pip install -r .\requirements\development.txt
    }

    Invoke-Checked "Validate Python dependency compatibility" {
        & $VenvPython -m pip check
    }

    Write-Step "STEP 6 — BACKEND VALIDATION"

    Invoke-Checked "Backend format check" {
        & $VenvPython -m ruff format --check .
    }

    Invoke-Checked "Backend lint check" {
        & $VenvPython -m ruff check .
    }

    Invoke-Checked "Backend strict type check" {
        & $VenvPython -m mypy .
    }

    Invoke-Checked "Django system check" {
        $env:DJANGO_SETTINGS_MODULE = "config.settings.test"
        & $VenvPython .\manage.py check
    }

    Invoke-Checked "Backend pytest suite" {
        $env:DJANGO_SETTINGS_MODULE = "config.settings.test"
        & $VenvPython -m pytest
    }

    Remove-Item Env:DJANGO_SETTINGS_MODULE -ErrorAction SilentlyContinue

    Write-Step "STEP 7 — FRONTEND DEPENDENCIES"

    Set-Location -LiteralPath $Frontend

    if (Test-Path -LiteralPath ".\package-lock.json" -PathType Leaf) {
        Invoke-Checked "Install frontend dependencies from lock file" {
            & $NpmCmd ci
        }
    }
    else {
        Invoke-Checked "Install frontend dependencies and create lock file" {
            & $NpmCmd install
        }
    }

    Write-Step "STEP 8 — FRONTEND VALIDATION"

    Invoke-Checked "Frontend formatting check" {
        & $NpmCmd run format:check
    }

    Invoke-Checked "Frontend ESLint check" {
        & $NpmCmd run lint
    }

    Invoke-Checked "Frontend TypeScript check" {
        & $NpmCmd run typecheck
    }

    Invoke-Checked "Frontend test suite" {
        & $NpmCmd run test:run
    }

    Invoke-Checked "Frontend production build" {
        & $NpmCmd run build
    }

    Invoke-Checked "Frontend production dependency audit" {
        & $NpmCmd audit --omit=dev --audit-level=high
    }

    Write-Step "STEP 9 — PRE-COMMIT VALIDATION"

    Set-Location -LiteralPath $Repo

    Invoke-Checked "Install pre-commit hook" {
        & $VenvPython -m pre_commit install
    }

    Invoke-Checked "Run pre-commit against all repository files" {
        & $VenvPython -m pre_commit run --all-files
    }

    Write-Step "STEP 10 — FINAL STRUCTURE AND STATUS"

    Invoke-Checked "Final repository structure check" {
        & $VenvPython .\scripts\verify_structure.py
    }

    Write-Host ""
    Write-Host "Git status:" -ForegroundColor Cyan
    & git status --short

    Write-Host ""
    Write-Host "=====================================================================" -ForegroundColor Green
    Write-Host "EWP-000.1A DEPENDENCY, QUALITY AND BUILD VALIDATION PASSED" -ForegroundColor Green
    Write-Host "Repository: $Repo" -ForegroundColor Green
    Write-Host "Evidence  : $LogFile" -ForegroundColor Green
    Write-Host "No Git commit was created." -ForegroundColor Green
    Write-Host "=====================================================================" -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "=====================================================================" -ForegroundColor Red
    Write-Host "EWP-000.1A VALIDATION STOPPED" -ForegroundColor Red
    Write-Host ("Error message : " + $_.Exception.Message) -ForegroundColor Red
    Write-Host ("Script line   : " + $_.InvocationInfo.ScriptLineNumber) -ForegroundColor Red
    Write-Host ("Position      : " + $_.InvocationInfo.PositionMessage) -ForegroundColor Red
    Write-Host ("Stack trace   : " + $_.ScriptStackTrace) -ForegroundColor DarkYellow
    Write-Host "Evidence log: $LogFile" -ForegroundColor Yellow
    Write-Host "No further engineering package should be started." -ForegroundColor Red
    Write-Host "=====================================================================" -ForegroundColor Red

    exit 1
}
finally {
    Remove-Item Env:DJANGO_SETTINGS_MODULE -ErrorAction SilentlyContinue
    Set-Location -LiteralPath $Repo -ErrorAction SilentlyContinue
    Stop-Transcript -ErrorAction SilentlyContinue | Out-Null
}


