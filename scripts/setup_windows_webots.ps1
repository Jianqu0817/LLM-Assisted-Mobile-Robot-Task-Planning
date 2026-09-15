# Download and silently install Webots R2025a for Windows to D:/Webots.
# Run this in PowerShell (internet required; optional proxy).
param(
    [string]$Proxy = "",
    [string]$Installer = "D:/DS_workspace/Liqingbiao/webots-R2025a_setup.exe",
    [string]$Target = "D:/Webots"
)

$url = "https://github.com/cyberbotics/webots/releases/download/R2025a/webots-R2025a_setup.exe"
$curlArgs = @("-L", "--retry", "3", "--retry-delay", "5", "-o", $Installer, $url)
if ($Proxy -ne "") {
    $curlArgs = @("--proxy", $Proxy) + $curlArgs
}
Write-Host "Downloading Webots R2025a..."
Start-Process -FilePath "curl.exe" -ArgumentList $curlArgs -Wait -NoNewWindow
Write-Host "Installing silently to $Target ..."
$p = Start-Process -FilePath $Installer -ArgumentList "/S", "/D=$Target" -Verb RunAs -Wait -PassThru
Write-Host "Installer exit code: $($p.ExitCode)"
Write-Host "Expected executable: $Target/msys64/mingw64/bin/webots.exe"
