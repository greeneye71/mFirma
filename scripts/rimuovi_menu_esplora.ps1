$ErrorActionPreference = 'Stop'

$verbPath = 'HKCU:\Software\Classes\SystemFileAssociations\.pdf\shell\mFirma'
if (Test-Path -LiteralPath $verbPath) {
    Remove-Item -LiteralPath $verbPath -Recurse -Force
}
