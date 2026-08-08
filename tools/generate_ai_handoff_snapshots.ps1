param(
    [Parameter(Mandatory = $false)]
    [string]$Repo = "D:\CAFirm\cafirm"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------
# CA Firm Platform — Repository and Architecture Snapshot Generator
#
# READ-ONLY source inspection.
# The script writes reports only under:
#   research_outputs\ai_handoff_snapshot_<timestamp>
#
# It excludes secrets, databases, media, caches, dependencies and Git data.
# ---------------------------------------------------------------------

function Write-Section {
    param(
        [Parameter(Mandatory = $true)]
        [System.Text.StringBuilder]$Builder,

        [Parameter(Mandatory = $true)]
        [string]$Title,

        [int]$Level = 2
    )

    [void]$Builder.AppendLine("")
    [void]$Builder.AppendLine(("#" * $Level) + " " + $Title)
    [void]$Builder.AppendLine("")
}

function Add-CodeBlock {
    param(
        [Parameter(Mandatory = $true)]
        [System.Text.StringBuilder]$Builder,

        [AllowEmptyString()]
        [string]$Text,

        [string]$Language = "text"
    )

    [void]$Builder.AppendLine('```' + $Language)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        [void]$Builder.AppendLine("(none)")
    }
    else {
        [void]$Builder.AppendLine($Text.TrimEnd())
    }

    [void]$Builder.AppendLine('```')
    [void]$Builder.AppendLine("")
}

function Invoke-GitText {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [switch]$AllowFailure
    )

    $PreviousNativePreference = $null
    $HasNativePreference = Test-Path variable:PSNativeCommandUseErrorActionPreference

    if ($HasNativePreference) {
        $PreviousNativePreference = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }

    try {
        $Output = & git @Arguments 2>&1
        $ExitCode = $LASTEXITCODE

        if (($ExitCode -ne 0) -and (-not $AllowFailure)) {
            throw "Git command failed: git $($Arguments -join ' ')`n$($Output -join [Environment]::NewLine)"
        }

        return ($Output -join [Environment]::NewLine)
    }
    finally {
        if ($HasNativePreference) {
            $PSNativeCommandUseErrorActionPreference = $PreviousNativePreference
        }
    }
}

function Get-RelativePathSafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,

        [Parameter(Mandatory = $true)]
        [string]$FullPath
    )

    $Base = [System.IO.Path]::GetFullPath($BasePath).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )

    $Full = [System.IO.Path]::GetFullPath($FullPath)

    if ($Full.StartsWith($Base, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $Full.Substring($Base.Length).TrimStart(
            [System.IO.Path]::DirectorySeparatorChar,
            [System.IO.Path]::AltDirectorySeparatorChar
        ).Replace("\", "/")
    }

    return $Full.Replace("\", "/")
}

function Test-IsExcludedPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )

    $Normalized = "/" + $RelativePath.Replace("\", "/").TrimStart("/") + "/"

    $ExcludedSegments = @(
        "/.git/",
        "/node_modules/",
        "/.venv/",
        "/venv/",
        "/env/",
        "/__pycache__/",
        "/.pytest_cache/",
        "/.mypy_cache/",
        "/.ruff_cache/",
        "/coverage/",
        "/dist/",
        "/build/",
        "/media/",
        "/staticfiles/",
        "/.idea/",
        "/.vscode/",
        "/research_outputs/"
    )

    foreach ($Segment in $ExcludedSegments) {
        if ($Normalized.IndexOf($Segment, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            return $true
        }
    }

    $Name = [System.IO.Path]::GetFileName($RelativePath)

    if ($Name -match '(?i)\.(sqlite|sqlite3|db|pyc|pyo|log|zip|7z|tar|gz)$') {
        return $true
    }

    if ($Name -match '(?i)^\.env($|\.)') {
        return $true
    }

    return $false
}

function Get-SafeText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return ""
    }

    $Lines = Get-Content -LiteralPath $Path -ErrorAction Stop

    $SensitivePattern = '(?i)(SECRET|PASSWORD|PASSWD|TOKEN|API[_-]?KEY|PRIVATE[_-]?KEY|CLIENT[_-]?SECRET|ACCESS[_-]?KEY|DATABASE[_-]?URL|CONNECTION[_-]?STRING)'

    $Sanitized = foreach ($Line in $Lines) {
        if ($Line -match $SensitivePattern) {
            if ($Line -match '^\s*([^:=]+)\s*[:=]') {
                "$($Matches[1].Trim()) = [REDACTED]"
            }
            else {
                "[REDACTED SENSITIVE CONFIGURATION LINE]"
            }
        }
        else {
            $Line
        }
    }

    return ($Sanitized -join [Environment]::NewLine)
}

function Get-SourceFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $AllowedExtensions = @(
        ".py",
        ".tsx",
        ".ts",
        ".jsx",
        ".js",
        ".css",
        ".scss",
        ".html",
        ".json",
        ".toml",
        ".ini",
        ".cfg",
        ".yaml",
        ".yml",
        ".md",
        ".txt",
        ".ps1"
    )

    return @(
        Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object {
                $Relative = Get-RelativePathSafe -BasePath $Root -FullPath $_.FullName

                (-not (Test-IsExcludedPath -RelativePath $Relative)) -and
                ($AllowedExtensions -contains $_.Extension.ToLowerInvariant())
            } |
            Sort-Object FullName
    )
}

function Get-RegexMatches {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Pattern
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return @()
    }

    $Matches = Select-String `
        -LiteralPath $Path `
        -Pattern $Pattern `
        -AllMatches `
        -ErrorAction SilentlyContinue

    # Prevent PowerShell from unrolling a zero-item or one-item result.
    # Callers can therefore safely use both foreach and .Count.
    $Result = @($Matches)
    return ,$Result
}

function Add-FileExcerpt {
    param(
        [Parameter(Mandatory = $true)]
        [System.Text.StringBuilder]$Builder,

        [Parameter(Mandatory = $true)]
        [string]$Root,

        [Parameter(Mandatory = $true)]
        [string]$Path,

        [int]$MaximumLines = 500
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }

    $Relative = Get-RelativePathSafe -BasePath $Root -FullPath $Path

    Write-Section -Builder $Builder -Title $Relative -Level 3

    $Text = Get-SafeText -Path $Path
    $Lines = @($Text -split "`r?`n")

    if ($Lines.Count -gt $MaximumLines) {
        $Text = (
            $Lines |
                Select-Object -First $MaximumLines
        ) -join [Environment]::NewLine

        $Text += [Environment]::NewLine +
            "... [TRUNCATED AFTER $MaximumLines LINES]"
    }

    $Language = "text"

    switch ([System.IO.Path]::GetExtension($Path).ToLowerInvariant()) {
        ".py"   { $Language = "python" }
        ".ts"   { $Language = "typescript" }
        ".tsx"  { $Language = "tsx" }
        ".js"   { $Language = "javascript" }
        ".jsx"  { $Language = "jsx" }
        ".json" { $Language = "json" }
        ".css"  { $Language = "css" }
        ".ps1"  { $Language = "powershell" }
        ".md"   { $Language = "markdown" }
        ".toml" { $Language = "toml" }
        ".yaml" { $Language = "yaml" }
        ".yml"  { $Language = "yaml" }
    }

    Add-CodeBlock -Builder $Builder -Text $Text -Language $Language
}

function Get-DirectoryTreeFromFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$RelativeFiles
    )

    if ($RelativeFiles.Count -eq 0) {
        return "(none)"
    }

    return ($RelativeFiles | Sort-Object) -join [Environment]::NewLine
}

function Add-InventoryTable {
    param(
        [Parameter(Mandatory = $true)]
        [System.Text.StringBuilder]$Builder,

        [Parameter(Mandatory = $true)]
        [object[]]$Rows,

        [Parameter(Mandatory = $true)]
        [string[]]$Columns
    )

    if ($Rows.Count -eq 0) {
        [void]$Builder.AppendLine("_No matching records were found._")
        [void]$Builder.AppendLine("")
        return
    }

    [void]$Builder.AppendLine(
        "| " + ($Columns -join " | ") + " |"
    )

    [void]$Builder.AppendLine(
        "| " + (($Columns | ForEach-Object { "---" }) -join " | ") + " |"
    )

    foreach ($Row in $Rows) {
        $Values = foreach ($Column in $Columns) {
            $Value = $Row.$Column

            if ($null -eq $Value) {
                ""
            }
            else {
                ([string]$Value).Replace("|", "\|").Replace(
                    "`r",
                    " "
                ).Replace(
                    "`n",
                    " "
                )
            }
        }

        [void]$Builder.AppendLine(
            "| " + ($Values -join " | ") + " |"
        )
    }

    [void]$Builder.AppendLine("")
}

# ---------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------

if (-not (Test-Path -LiteralPath $Repo -PathType Container)) {
    throw "Repository path not found: $Repo"
}

$Repo = (Resolve-Path -LiteralPath $Repo).Path
Set-Location -LiteralPath $Repo

$InsideWorkTree = Invoke-GitText -Arguments @(
    "rev-parse",
    "--is-inside-work-tree"
)

if ($InsideWorkTree.Trim() -ne "true") {
    throw "Not inside a Git work tree: $Repo"
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputRoot = Join-Path `
    $Repo `
    "research_outputs\ai_handoff_snapshot_$Timestamp"

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

$RepositoryReport = Join-Path `
    $OutputRoot `
    "Repository_Intelligence_Snapshot.md"

$ArchitectureReport = Join-Path `
    $OutputRoot `
    "Architecture_Intelligence_Snapshot.md"

$HashManifest = Join-Path `
    $OutputRoot `
    "Tracked_File_SHA256_Manifest.csv"

$SummaryFile = Join-Path `
    $OutputRoot `
    "SNAPSHOT_SUMMARY.txt"

# ---------------------------------------------------------------------
# Git evidence
# ---------------------------------------------------------------------

$Branch = (
    Invoke-GitText -Arguments @(
        "branch",
        "--show-current"
    )
).Trim()

$Commit = (
    Invoke-GitText -Arguments @(
        "rev-parse",
        "HEAD"
    )
).Trim()

$ShortCommit = (
    Invoke-GitText -Arguments @(
        "rev-parse",
        "--short=12",
        "HEAD"
    )
).Trim()

$Describe = (
    Invoke-GitText `
        -Arguments @(
            "describe",
            "--tags",
            "--always",
            "--dirty"
        ) `
        -AllowFailure
).Trim()

$Status = Invoke-GitText -Arguments @(
    "status",
    "--short",
    "--branch"
)

$RecentLog = Invoke-GitText -Arguments @(
    "log",
    "--oneline",
    "--decorate",
    "-15"
)

$Tags = Invoke-GitText -Arguments @(
    "tag",
    "--sort=-creatordate"
)

$TrackedText = Invoke-GitText -Arguments @(
    "ls-files"
)

$TrackedFiles = @(
    $TrackedText -split "`r?`n" |
        Where-Object {
            -not [string]::IsNullOrWhiteSpace($_)
        } |
        ForEach-Object {
            $_.Replace("\", "/")
        } |
        Where-Object {
            -not (Test-IsExcludedPath -RelativePath $_)
        } |
        Sort-Object -Unique
)

$SourceFiles = Get-SourceFiles -Root $Repo

# ---------------------------------------------------------------------
# File manifest
# ---------------------------------------------------------------------

$HashRows = New-Object System.Collections.Generic.List[object]

foreach ($RelativePath in $TrackedFiles) {
    $FullPath = Join-Path $Repo $RelativePath

    if (-not (Test-Path -LiteralPath $FullPath -PathType Leaf)) {
        continue
    }

    $File = Get-Item -LiteralPath $FullPath
    $Hash = Get-FileHash `
        -LiteralPath $FullPath `
        -Algorithm SHA256

    $HashRows.Add(
        [pscustomobject]@{
            RelativePath = $RelativePath
            SizeBytes    = $File.Length
            LastWriteUtc = $File.LastWriteTimeUtc.ToString("o")
            SHA256       = $Hash.Hash.ToLowerInvariant()
        }
    )
}

$HashRows |
    Export-Csv `
        -LiteralPath $HashManifest `
        -NoTypeInformation `
        -Encoding UTF8

# ---------------------------------------------------------------------
# Structured inventories
# ---------------------------------------------------------------------

$PythonFiles = @(
    $SourceFiles |
        Where-Object {
            $_.Extension -eq ".py"
        }
)

$FrontendFiles = @(
    $SourceFiles |
        Where-Object {
            $_.Extension -in @(
                ".ts",
                ".tsx",
                ".js",
                ".jsx",
                ".css"
            )
        }
)

$PythonDefinitions = New-Object System.Collections.Generic.List[object]
$FrontendDefinitions = New-Object System.Collections.Generic.List[object]
$ApiEvidence = New-Object System.Collections.Generic.List[object]
$PermissionEvidence = New-Object System.Collections.Generic.List[object]
$WorkflowEvidence = New-Object System.Collections.Generic.List[object]
$ModelEvidence = New-Object System.Collections.Generic.List[object]
$MigrationEvidence = New-Object System.Collections.Generic.List[object]
$TestEvidence = New-Object System.Collections.Generic.List[object]

foreach ($File in $PythonFiles) {
    $Relative = Get-RelativePathSafe -BasePath $Repo -FullPath $File.FullName

    $Definitions = Get-RegexMatches `
        -Path $File.FullName `
        -Pattern '^\s*(class|def|async\s+def)\s+([A-Za-z_][A-Za-z0-9_]*)'

    foreach ($Match in $Definitions) {
        $Kind = $Match.Matches[0].Groups[1].Value
        $Name = $Match.Matches[0].Groups[2].Value

        $PythonDefinitions.Add(
            [pscustomobject]@{
                File = $Relative
                Line = $Match.LineNumber
                Kind = $Kind
                Name = $Name
            }
        )

        if (
            ($Name -match '(Model|Item|Client|Employee|Firm|Branch|Team|Service|Domain|Vertical|Attachment|Request|Audit|Expertise)$') -or
            ($Match.Line -match 'models\.Model')
        ) {
            $ModelEvidence.Add(
                [pscustomobject]@{
                    File = $Relative
                    Line = $Match.LineNumber
                    Definition = $Match.Line.Trim()
                }
            )
        }
    }

    $ApiMatches = Get-RegexMatches `
        -Path $File.FullName `
        -Pattern '(router\.register|path\s*\(|re_path\s*\(|@action\s*\(|ViewSet|APIView|GenericAPIView)'

    foreach ($Match in $ApiMatches) {
        $ApiEvidence.Add(
            [pscustomobject]@{
                File = $Relative
                Line = $Match.LineNumber
                Evidence = $Match.Line.Trim()
            }
        )
    }

    $PermissionMatches = Get-RegexMatches `
        -Path $File.FullName `
        -Pattern '(permission|authorize|authorise|role|principal|can_[a-z_]+|is_staff|is_superuser)'

    foreach ($Match in $PermissionMatches) {
        $PermissionEvidence.Add(
            [pscustomobject]@{
                File = $Relative
                Line = $Match.LineNumber
                Evidence = $Match.Line.Trim()
            }
        )
    }

    $WorkflowMatches = Get-RegexMatches `
        -Path $File.FullName `
        -Pattern '(status|transition|submit|approve|reject|rework|complete|cancel|lock|unlock|assign|reviewer|owner)'

    foreach ($Match in $WorkflowMatches) {
        $WorkflowEvidence.Add(
            [pscustomobject]@{
                File = $Relative
                Line = $Match.LineNumber
                Evidence = $Match.Line.Trim()
            }
        )
    }

    if ($Relative -match '/migrations/\d+.*\.py$') {
        $MigrationEvidence.Add(
            [pscustomobject]@{
                File = $Relative
                SizeBytes = $File.Length
            }
        )
    }

    if (
        ($Relative -match '(^|/)tests?(/|_)') -or
        ($File.Name -match '^test_.*\.py$')
    ) {
        $TestCount = (
            Get-RegexMatches `
                -Path $File.FullName `
                -Pattern '^\s*(def|async\s+def)\s+test_[A-Za-z0-9_]+'
        ).Count

        $TestEvidence.Add(
            [pscustomobject]@{
                File = $Relative
                Type = "Backend"
                TestDefinitions = $TestCount
            }
        )
    }
}

foreach ($File in $FrontendFiles) {
    $Relative = Get-RelativePathSafe -BasePath $Repo -FullPath $File.FullName

    $Patterns = @(
        '^\s*export\s+default\s+function\s+([A-Za-z_][A-Za-z0-9_]*)',
        '^\s*export\s+function\s+([A-Za-z_][A-Za-z0-9_]*)',
        '^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)',
        '^\s*export\s+(?:const|let)\s+([A-Za-z_][A-Za-z0-9_]*)',
        '^\s*(?:const|let)\s+([A-Za-z_][A-Za-z0-9_]*)',
        '^\s*export\s+interface\s+([A-Za-z_][A-Za-z0-9_]*)',
        '^\s*interface\s+([A-Za-z_][A-Za-z0-9_]*)',
        '^\s*export\s+type\s+([A-Za-z_][A-Za-z0-9_]*)',
        '^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)'
    )

    foreach ($Pattern in $Patterns) {
        $Matches = Get-RegexMatches `
            -Path $File.FullName `
            -Pattern $Pattern

        foreach ($Match in $Matches) {
            $Name = $Match.Matches[0].Groups[1].Value

            if (-not [string]::IsNullOrWhiteSpace($Name)) {
                $FrontendDefinitions.Add(
                    [pscustomobject]@{
                        File = $Relative
                        Line = $Match.LineNumber
                        Name = $Name
                        Evidence = $Match.Line.Trim()
                    }
                )
            }
        }
    }

    $FrontendApiMatches = Get-RegexMatches `
        -Path $File.FullName `
        -Pattern '(fetch\s*\(|axios\.|api\.(get|post|put|patch|delete)|/api/)'

    foreach ($Match in $FrontendApiMatches) {
        $ApiEvidence.Add(
            [pscustomobject]@{
                File = $Relative
                Line = $Match.LineNumber
                Evidence = $Match.Line.Trim()
            }
        )
    }

    if (
        ($Relative -match '(^|/)tests?(/|_)') -or
        ($File.Name -match '\.(test|spec)\.(ts|tsx|js|jsx)$')
    ) {
        $TestCount = (
            Get-RegexMatches `
                -Path $File.FullName `
                -Pattern '\b(it|test)\s*\('
        ).Count

        $TestEvidence.Add(
            [pscustomobject]@{
                File = $Relative
                Type = "Frontend"
                TestDefinitions = $TestCount
            }
        )
    }
}

# Keep raw evidence readable and bounded.
$PermissionEvidence = @(
    $PermissionEvidence |
        Sort-Object File, Line |
        Select-Object -First 500
)

$WorkflowEvidence = @(
    $WorkflowEvidence |
        Sort-Object File, Line |
        Select-Object -First 700
)

$ApiEvidence = @(
    $ApiEvidence |
        Sort-Object File, Line |
        Select-Object -First 600
)

# ---------------------------------------------------------------------
# Important configuration files
# ---------------------------------------------------------------------

$ConfigCandidates = @(
    "backend\config\settings\base.py",
    "backend\config\settings\development.py",
    "backend\config\settings\test_sqlite.py",
    "backend\config\settings\media.py",
    "backend\config\urls.py",
    "backend\config\urls_internal.py",
    "backend\manage.py",
    "backend\pytest.ini",
    "backend\pyproject.toml",
    "backend\requirements.txt",
    "backend\requirements\base.txt",
    "backend\requirements\development.txt",
    "frontend\package.json",
    "frontend\vite.config.ts",
    "frontend\tsconfig.json",
    "frontend\src\apps\internal\App.tsx",
    ".gitignore"
)

$ExistingConfigFiles = @(
    foreach ($Candidate in $ConfigCandidates) {
        $FullPath = Join-Path $Repo $Candidate

        if (Test-Path -LiteralPath $FullPath -PathType Leaf) {
            $FullPath
        }
    }
)

# ---------------------------------------------------------------------
# Repository Intelligence Snapshot
# ---------------------------------------------------------------------

$RIS = New-Object System.Text.StringBuilder

[void]$RIS.AppendLine("# Repository Intelligence Snapshot")
[void]$RIS.AppendLine("")
[void]$RIS.AppendLine("**Repository:** ``$Repo``  ")
[void]$RIS.AppendLine("**Generated:** $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')  ")
[void]$RIS.AppendLine("**Branch:** ``$Branch``  ")
[void]$RIS.AppendLine("**Commit:** ``$Commit``  ")
[void]$RIS.AppendLine("**Description:** ``$Describe``  ")
[void]$RIS.AppendLine("")
[void]$RIS.AppendLine("> This document is generated from local repository evidence. Sensitive configuration values are redacted. It does not include dependency directories, databases, uploaded media, caches, environment files or Git internals.")

Write-Section -Builder $RIS -Title "1. Git Baseline"
[void]$RIS.AppendLine("### Current status")
Add-CodeBlock -Builder $RIS -Text $Status -Language "text"

[void]$RIS.AppendLine("### Recent history")
Add-CodeBlock -Builder $RIS -Text $RecentLog -Language "text"

[void]$RIS.AppendLine("### Tags")
Add-CodeBlock -Builder $RIS -Text $Tags -Language "text"

Write-Section -Builder $RIS -Title "2. Repository Statistics"

$BackendCount = @(
    $TrackedFiles |
        Where-Object {
            $_ -like "backend/*"
        }
).Count

$FrontendCount = @(
    $TrackedFiles |
        Where-Object {
            $_ -like "frontend/*"
        }
).Count

$MigrationCount = $MigrationEvidence.ToArray().Count
$BackendTestCount = @(
    $TestEvidence |
        Where-Object {
            $_.Type -eq "Backend"
        } |
        Measure-Object -Property TestDefinitions -Sum
).Sum

$FrontendTestCount = @(
    $TestEvidence |
        Where-Object {
            $_.Type -eq "Frontend"
        } |
        Measure-Object -Property TestDefinitions -Sum
).Sum

$Stats = @(
    [pscustomobject]@{
        Metric = "Tracked files included"
        Value  = $TrackedFiles.Count
    },
    [pscustomobject]@{
        Metric = "Backend tracked files"
        Value  = $BackendCount
    },
    [pscustomobject]@{
        Metric = "Frontend tracked files"
        Value  = $FrontendCount
    },
    [pscustomobject]@{
        Metric = "Source/config files inspected"
        Value  = $SourceFiles.Count
    },
    [pscustomobject]@{
        Metric = "Python definitions discovered"
        Value  = $PythonDefinitions.Count
    },
    [pscustomobject]@{
        Metric = "Frontend definitions discovered"
        Value  = $FrontendDefinitions.Count
    },
    [pscustomobject]@{
        Metric = "Migration files discovered"
        Value  = $MigrationCount
    },
    [pscustomobject]@{
        Metric = "Backend test definitions detected"
        Value  = $BackendTestCount
    },
    [pscustomobject]@{
        Metric = "Frontend test definitions detected"
        Value  = $FrontendTestCount
    }
)

Add-InventoryTable `
    -Builder $RIS `
    -Rows $Stats `
    -Columns @(
        "Metric",
        "Value"
    )

Write-Section -Builder $RIS -Title "3. Canonical Tracked File Inventory"
Add-CodeBlock `
    -Builder $RIS `
    -Text (Get-DirectoryTreeFromFiles -RelativeFiles $TrackedFiles) `
    -Language "text"

Write-Section -Builder $RIS -Title "4. Backend Python Definition Inventory"
Add-InventoryTable `
    -Builder $RIS `
    -Rows @($PythonDefinitions | Sort-Object File, Line) `
    -Columns @(
        "File",
        "Line",
        "Kind",
        "Name"
    )

Write-Section -Builder $RIS -Title "5. Frontend Definition Inventory"
Add-InventoryTable `
    -Builder $RIS `
    -Rows @($FrontendDefinitions | Sort-Object File, Line) `
    -Columns @(
        "File",
        "Line",
        "Name",
        "Evidence"
    )

Write-Section -Builder $RIS -Title "6. Model and Entity Evidence"
Add-InventoryTable `
    -Builder $RIS `
    -Rows @($ModelEvidence | Sort-Object File, Line) `
    -Columns @(
        "File",
        "Line",
        "Definition"
    )

Write-Section -Builder $RIS -Title "7. API and Routing Evidence"
Add-InventoryTable `
    -Builder $RIS `
    -Rows @($ApiEvidence) `
    -Columns @(
        "File",
        "Line",
        "Evidence"
    )

Write-Section -Builder $RIS -Title "8. Migration Inventory"
Add-InventoryTable `
    -Builder $RIS `
    -Rows @($MigrationEvidence | Sort-Object File) `
    -Columns @(
        "File",
        "SizeBytes"
    )

Write-Section -Builder $RIS -Title "9. Test Inventory"
Add-InventoryTable `
    -Builder $RIS `
    -Rows @($TestEvidence | Sort-Object Type, File) `
    -Columns @(
        "Type",
        "File",
        "TestDefinitions"
    )

Write-Section -Builder $RIS -Title "10. Configuration Evidence"
[void]$RIS.AppendLine("> Values matching secret, token, password, key or connection-string patterns are redacted.")
[void]$RIS.AppendLine("")

foreach ($ConfigPath in $ExistingConfigFiles) {
    Add-FileExcerpt `
        -Builder $RIS `
        -Root $Repo `
        -Path $ConfigPath `
        -MaximumLines 700
}

Write-Section -Builder $RIS -Title "11. File Integrity Manifest"
[void]$RIS.AppendLine("The complete tracked-file SHA-256 manifest is stored beside this report:")
[void]$RIS.AppendLine("")
[void]$RIS.AppendLine("- ``Tracked_File_SHA256_Manifest.csv``")
[void]$RIS.AppendLine("")
[void]$RIS.AppendLine("Files hashed: **$($HashRows.Count)**")
[void]$RIS.AppendLine("")

Write-Section -Builder $RIS -Title "12. Snapshot Limitations"
[void]$RIS.AppendLine("- Static inspection cannot prove runtime behavior.")
[void]$RIS.AppendLine("- Regex inventories identify implementation evidence but are not a substitute for complete semantic source review.")
[void]$RIS.AppendLine("- Runtime database contents are intentionally excluded.")
[void]$RIS.AppendLine("- Secrets and environment-specific values are intentionally excluded or redacted.")
[void]$RIS.AppendLine("- Test results are not inferred from test files; only test definitions are inventoried.")
[void]$RIS.AppendLine("")

[System.IO.File]::WriteAllText(
    $RepositoryReport,
    $RIS.ToString(),
    [System.Text.UTF8Encoding]::new($false)
)

# ---------------------------------------------------------------------
# Architecture Intelligence Snapshot
# ---------------------------------------------------------------------

$AIS = New-Object System.Text.StringBuilder

[void]$AIS.AppendLine("# Architecture Intelligence Snapshot")
[void]$AIS.AppendLine("")
[void]$AIS.AppendLine("**Repository:** ``$Repo``  ")
[void]$AIS.AppendLine("**Generated:** $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')  ")
[void]$AIS.AppendLine("**Authoritative branch:** ``$Branch``  ")
[void]$AIS.AppendLine("**Authoritative commit:** ``$Commit``  ")
[void]$AIS.AppendLine("")
[void]$AIS.AppendLine("> This is an evidence-oriented architecture snapshot. It reports discovered source structures and does not claim unverified runtime behavior.")

Write-Section -Builder $AIS -Title "1. Executive Baseline"

[void]$AIS.AppendLine("The repository contains a Django backend and a TypeScript/React frontend. The current snapshot is anchored to:")
[void]$AIS.AppendLine("")
[void]$AIS.AppendLine("- Branch: ``$Branch``")
[void]$AIS.AppendLine("- Commit: ``$Commit``")
[void]$AIS.AppendLine("- Git description: ``$Describe``")
[void]$AIS.AppendLine("- Tracked source/configuration files included: **$($TrackedFiles.Count)**")
[void]$AIS.AppendLine("")

Write-Section -Builder $AIS -Title "2. Top-Level Architecture"

$TopLevelGroups = @(
    $TrackedFiles |
        ForEach-Object {
            ($_ -split "/")[0]
        } |
        Group-Object |
        Sort-Object Name |
        ForEach-Object {
            [pscustomobject]@{
                Area = $_.Name
                TrackedFiles = $_.Count
            }
        }
)

Add-InventoryTable `
    -Builder $AIS `
    -Rows $TopLevelGroups `
    -Columns @(
        "Area",
        "TrackedFiles"
    )

Write-Section -Builder $AIS -Title "3. Backend Bounded Context Inventory"

$BackendContextsPath = Join-Path $Repo "backend\contexts"
$ContextRows = New-Object System.Collections.Generic.List[object]

if (Test-Path -LiteralPath $BackendContextsPath -PathType Container) {
    $ContextDirectories = Get-ChildItem `
        -LiteralPath $BackendContextsPath `
        -Directory |
        Sort-Object Name

    foreach ($Context in $ContextDirectories) {
        $RelativeContext = Get-RelativePathSafe `
            -BasePath $Repo `
            -FullPath $Context.FullName

        $ContextFiles = @(
            Get-ChildItem `
                -LiteralPath $Context.FullName `
                -Recurse `
                -File `
                -ErrorAction SilentlyContinue |
                Where-Object {
                    $Relative = Get-RelativePathSafe `
                        -BasePath $Repo `
                        -FullPath $_.FullName

                    -not (Test-IsExcludedPath -RelativePath $Relative)
                }
        )

        $ModelFiles = @(
            $ContextFiles |
                Where-Object {
                    $_.Name -eq "models.py"
                }
        ).Count

        $SerializerFiles = @(
            $ContextFiles |
                Where-Object {
                    $_.Name -eq "serializers.py"
                }
        ).Count

        $ViewFiles = @(
            $ContextFiles |
                Where-Object {
                    $_.Name -eq "views.py"
                }
        ).Count

        $Migrations = @(
            $ContextFiles |
                Where-Object {
                    $_.FullName -match '\\migrations\\\d+.*\.py$'
                }
        ).Count

        $Tests = @(
            $TestEvidence |
                Where-Object {
                    $_.File -like "$RelativeContext/*"
                }
        ).Count

        $ContextRows.Add(
            [pscustomobject]@{
                Context = $Context.Name
                Files = $ContextFiles.Count
                ModelsFiles = $ModelFiles
                SerializerFiles = $SerializerFiles
                ViewFiles = $ViewFiles
                Migrations = $Migrations
                LocalTests = $Tests
            }
        )
    }
}

Add-InventoryTable `
    -Builder $AIS `
    -Rows $ContextRows.ToArray() `
    -Columns @(
        "Context",
        "Files",
        "ModelsFiles",
        "SerializerFiles",
        "ViewFiles",
        "Migrations",
        "LocalTests"
    )

Write-Section -Builder $AIS -Title "4. Backend Model and Entity Definitions"
Add-InventoryTable `
    -Builder $AIS `
    -Rows @($ModelEvidence | Sort-Object File, Line) `
    -Columns @(
        "File",
        "Line",
        "Definition"
    )

Write-Section -Builder $AIS -Title "5. API Architecture Evidence"
Add-InventoryTable `
    -Builder $AIS `
    -Rows @($ApiEvidence) `
    -Columns @(
        "File",
        "Line",
        "Evidence"
    )

Write-Section -Builder $AIS -Title "6. Authorization and Permission Evidence"

[void]$AIS.AppendLine("> The rows below are source references containing authorization, role, principal or permission-related terms. They require semantic review before declaring a complete RBAC capability.")
[void]$AIS.AppendLine("")

Add-InventoryTable `
    -Builder $AIS `
    -Rows @($PermissionEvidence) `
    -Columns @(
        "File",
        "Line",
        "Evidence"
    )

Write-Section -Builder $AIS -Title "7. Workflow and State-Transition Evidence"

[void]$AIS.AppendLine("> The rows below identify source evidence associated with status, assignment, review, locking and workflow transitions.")
[void]$AIS.AppendLine("")

Add-InventoryTable `
    -Builder $AIS `
    -Rows @($WorkflowEvidence) `
    -Columns @(
        "File",
        "Line",
        "Evidence"
    )

Write-Section -Builder $AIS -Title "8. Frontend Application Architecture"

$FrontendAreaRows = @(
    $TrackedFiles |
        Where-Object {
            $_ -like "frontend/src/*"
        } |
        ForEach-Object {
            $Parts = $_ -split "/"

            if ($Parts.Count -ge 4) {
                $Parts[0..3] -join "/"
            }
            else {
                $_
            }
        } |
        Group-Object |
        Sort-Object Name |
        ForEach-Object {
            [pscustomobject]@{
                Area = $_.Name
                Files = $_.Count
            }
        }
)

Add-InventoryTable `
    -Builder $AIS `
    -Rows $FrontendAreaRows `
    -Columns @(
        "Area",
        "Files"
    )

Write-Section -Builder $AIS -Title "9. React, TypeScript and UI Definition Inventory"
Add-InventoryTable `
    -Builder $AIS `
    -Rows @($FrontendDefinitions | Sort-Object File, Line) `
    -Columns @(
        "File",
        "Line",
        "Name",
        "Evidence"
    )

Write-Section -Builder $AIS -Title "10. Database Evolution"

[void]$AIS.AppendLine("Discovered migration files: **$MigrationCount**")
[void]$AIS.AppendLine("")

Add-InventoryTable `
    -Builder $AIS `
    -Rows @($MigrationEvidence | Sort-Object File) `
    -Columns @(
        "File",
        "SizeBytes"
    )

Write-Section -Builder $AIS -Title "11. Test Architecture"

$TestSummary = @(
    $TestEvidence |
        Group-Object Type |
        Sort-Object Name |
        ForEach-Object {
            [pscustomobject]@{
                TestLayer = $_.Name
                Files = $_.Count
                DetectedDefinitions = (
                    $_.Group |
                        Measure-Object `
                            -Property TestDefinitions `
                            -Sum
                ).Sum
            }
        }
)

Add-InventoryTable `
    -Builder $AIS `
    -Rows $TestSummary `
    -Columns @(
        "TestLayer",
        "Files",
        "DetectedDefinitions"
    )

Add-InventoryTable `
    -Builder $AIS `
    -Rows @($TestEvidence | Sort-Object Type, File) `
    -Columns @(
        "Type",
        "File",
        "TestDefinitions"
    )

Write-Section -Builder $AIS -Title "12. Configuration Architecture"

[void]$AIS.AppendLine("The following configuration authorities were discovered and reproduced with sensitive values redacted:")
[void]$AIS.AppendLine("")

foreach ($ConfigPath in $ExistingConfigFiles) {
    $Relative = Get-RelativePathSafe `
        -BasePath $Repo `
        -FullPath $ConfigPath

    [void]$AIS.AppendLine("- ``$Relative``")
}

[void]$AIS.AppendLine("")

foreach ($ConfigPath in $ExistingConfigFiles) {
    Add-FileExcerpt `
        -Builder $AIS `
        -Root $Repo `
        -Path $ConfigPath `
        -MaximumLines 350
}

Write-Section -Builder $AIS -Title "13. Identified Extension Areas"

[void]$AIS.AppendLine("Based on file and definition evidence, likely extension areas include:")
[void]$AIS.AppendLine("")
[void]$AIS.AppendLine("- ``backend/contexts/identity`` for employee-related extensions such as expertise tagging.")
[void]$AIS.AppendLine("- ``backend/contexts/work`` for work aggregation, employee action centres and operational metrics.")
[void]$AIS.AppendLine("- ``backend/core/api`` for shared request-context and API conventions.")
[void]$AIS.AppendLine("- ``frontend/src/features/console`` for employee and executive operational dashboards.")
[void]$AIS.AppendLine("- ``frontend/src/features/master-data`` for manageable expertise catalogues and employee expertise administration.")
[void]$AIS.AppendLine("- A dedicated or existing audit context must be verified before implementing audit persistence.")
[void]$AIS.AppendLine("")
[void]$AIS.AppendLine("> These are evidence-guided candidate extension points, not implementation approval. The supplied source must be reviewed semantically before code is written.")

Write-Section -Builder $AIS -Title "14. Architectural Guardrails for the Next Handoff"

[void]$AIS.AppendLine("- Treat commit ``$Commit`` as the authoritative source baseline.")
[void]$AIS.AppendLine("- Do not assume access to the local environment beyond the supplied snapshot and source package.")
[void]$AIS.AppendLine("- Preserve existing API, workflow and permission contracts.")
[void]$AIS.AppendLine("- Use additive migrations; do not edit historical migrations.")
[void]$AIS.AppendLine("- Keep the backend as the business-rule and authorization authority.")
[void]$AIS.AppendLine("- Extend the existing internal React application; do not create a disconnected console.")
[void]$AIS.AppendLine("- Base dashboards on deterministic backend queries and real persisted data.")
[void]$AIS.AppendLine("- Do not infer completion from folder names or scaffolding.")
[void]$AIS.AppendLine("- Preserve regression tests and add tests for every new contract.")
[void]$AIS.AppendLine("")

Write-Section -Builder $AIS -Title "15. Verification Boundaries"

[void]$AIS.AppendLine("The following cannot be proven solely from this static snapshot:")
[void]$AIS.AppendLine("")
[void]$AIS.AppendLine("- Runtime database state.")
[void]$AIS.AppendLine("- Deployed environment configuration.")
[void]$AIS.AppendLine("- Actual authentication-provider behavior.")
[void]$AIS.AppendLine("- Runtime authorization outcomes across all actors.")
[void]$AIS.AppendLine("- Current test-pass state unless separate validation output is supplied.")
[void]$AIS.AppendLine("- Production performance and scalability.")
[void]$AIS.AppendLine("- External integrations not represented in tracked source.")
[void]$AIS.AppendLine("")

[System.IO.File]::WriteAllText(
    $ArchitectureReport,
    $AIS.ToString(),
    [System.Text.UTF8Encoding]::new($false)
)

# ---------------------------------------------------------------------
# Summary and archive
# ---------------------------------------------------------------------

$Summary = @"
CA FIRM AI HANDOFF SNAPSHOT
===========================

Generated:
$(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")

Repository:
$Repo

Branch:
$Branch

Commit:
$Commit

Git description:
$Describe

Repository Intelligence Snapshot:
$RepositoryReport

Architecture Intelligence Snapshot:
$ArchitectureReport

SHA-256 Manifest:
$HashManifest

Tracked files included:
$($TrackedFiles.Count)

Files hashed:
$($HashRows.Count)

Source/config files inspected:
$($SourceFiles.Count)

Security:
- Secret-like values were redacted from reproduced configuration.
- .env files were excluded.
- Databases were excluded.
- media and uploads were excluded.
- node_modules and virtual environments were excluded.
- Git internals were excluded.
"@

[System.IO.File]::WriteAllText(
    $SummaryFile,
    $Summary,
    [System.Text.UTF8Encoding]::new($false)
)

$ZipPath = "$OutputRoot.zip"

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

Compress-Archive `
    -LiteralPath $OutputRoot `
    -DestinationPath $ZipPath `
    -CompressionLevel Optimal

Write-Host ""
Write-Host "============================================================"
Write-Host "AI HANDOFF SNAPSHOT GENERATED SUCCESSFULLY"
Write-Host "============================================================"
Write-Host ""
Write-Host "Repository : $Repo"
Write-Host "Branch     : $Branch"
Write-Host "Commit     : $Commit"
Write-Host ""
Write-Host "RIS        : $RepositoryReport"
Write-Host "AIS        : $ArchitectureReport"
Write-Host "Manifest   : $HashManifest"
Write-Host "ZIP        : $ZipPath"
Write-Host ""
Write-Host "No application source files were modified."
Write-Host "============================================================"


