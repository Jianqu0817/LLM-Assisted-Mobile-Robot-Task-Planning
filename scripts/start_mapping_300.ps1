# Start 300 s mapping + boundary patrol in a persistent hidden WSL process.
$script = "/mnt/d/DS_workspace/Liqingbiao/assignment/scripts/run_mapping_300.sh"
Start-Process -FilePath "wsl.exe" -ArgumentList @(
    "-d", "Ubuntu-22.04",
    "-u", "ubuntu",
    "-e", "bash", $script
) -WindowStyle Hidden
Write-Output "Mapping 300s requested."
