Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$pluginRoot = Split-Path -Parent $PSScriptRoot

Write-Host "[1/3] compileall" -ForegroundColor Cyan
py -3 -m compileall $pluginRoot

Write-Host "[2/3] validate_plugin" -ForegroundColor Cyan
Push-Location $pluginRoot
try {
    py -3 ..\packaging\validate_plugin.py .

    Write-Host "[3/3] headless_integrity" -ForegroundColor Cyan
    py -3 tests\headless_integrity.py
}
finally {
    Pop-Location
}

Write-Host "Headless CI PASS" -ForegroundColor Green

