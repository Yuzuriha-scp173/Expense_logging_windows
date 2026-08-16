$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$LaunchVbs = Join-Path $Root "scripts\launch-daybook.vbs"
$Shortcut = Join-Path $Desktop "Daybook.lnk"
$Icon = Join-Path $Root "build\icon.png"
if (Test-Path (Join-Path $Root "build\icon.ico")) {
  $Icon = Join-Path $Root "build\icon.ico"
}

Set-Content -Path (Join-Path $Root "scripts\project-path.txt") -Value $Root -Encoding ASCII

$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($Shortcut)
$Sc.TargetPath = "$env:SystemRoot\System32\wscript.exe"
$Sc.Arguments = "`"$LaunchVbs`""
$Sc.WorkingDirectory = $Root
$Sc.WindowStyle = 7
$Sc.Description = "Daybook (Windows version)"
if (Test-Path $Icon) {
  $Sc.IconLocation = $Icon
}
$Sc.Save()

Write-Host "Daybook shortcut is on your Desktop and will launch from:"
Write-Host "  $Root"
Write-Host "Double-click Daybook to start."
