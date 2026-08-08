param(
    [Parameter(Mandatory = $true)]
    [string]$Repo,

    [Parameter(Mandatory = $true)]
    [string]$ScriptPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

try {
    & $ScriptPath -Repo $Repo
}
catch {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "DETAILED SNAPSHOT FAILURE"
    Write-Host "============================================================"
    Write-Host ""

    Write-Host "Exception type:"
    Write-Host $_.Exception.GetType().FullName
    Write-Host ""

    Write-Host "Message:"
    Write-Host $_.Exception.Message
    Write-Host ""

    Write-Host "Script stack trace:"
    Write-Host $_.ScriptStackTrace
    Write-Host ""

    Write-Host "Invocation position:"
    Write-Host $_.InvocationInfo.PositionMessage
    Write-Host ""

    Write-Host "Script name:"
    Write-Host $_.InvocationInfo.ScriptName
    Write-Host ""

    Write-Host "Script line number:"
    Write-Host $_.InvocationInfo.ScriptLineNumber
    Write-Host ""

    Write-Host "Offset in line:"
    Write-Host $_.InvocationInfo.OffsetInLine
    Write-Host ""

    Write-Host "Failing line:"
    Write-Host $_.InvocationInfo.Line
    Write-Host ""

    Write-Host "Full error record:"
    $_ | Format-List * -Force

    Write-Host ""
    Write-Host "Inner exception:"
    if ($null -ne $_.Exception.InnerException) {
        $_.Exception.InnerException | Format-List * -Force
    }
    else {
        Write-Host "(none)"
    }

    exit 1
}
