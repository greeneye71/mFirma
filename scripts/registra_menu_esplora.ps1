$ErrorActionPreference = 'Stop'

$verbPath = 'HKCU:\Software\Classes\SystemFileAssociations\.pdf\shell\mFirma'
$commandPath = Join-Path $verbPath 'command'
$launcher = (Resolve-Path (Join-Path $PSScriptRoot '..\avvia_mFirma.cmd')).Path
$command = '"{0}" /d /s /c ""{1}" "%1""' -f $env:ComSpec, $launcher

New-Item -Path $verbPath -Force | Out-Null
Set-Item -Path $verbPath -Value 'Firma PDF con mFirma'
New-ItemProperty -Path $verbPath -Name 'MultiSelectModel' -Value 'Player' -PropertyType String -Force | Out-Null
New-Item -Path $commandPath -Force | Out-Null
Set-Item -Path $commandPath -Value $command
