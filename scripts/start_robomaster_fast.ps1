# Start the simulation in a persistent hidden WSL process using Webots fast mode.
$script = "/mnt/d/DS_workspace/Liqingbiao/assignment/scripts/run_robomaster_foreground_fast.sh"
Start-Process -FilePath "wsl.exe" -ArgumentList @(
    "-d", "Ubuntu-22.04",
    "-u", "ubuntu",
    "-e", "bash", $script
) -WindowStyle Hidden
Write-Output "Simulation launch requested (fast mode)."
