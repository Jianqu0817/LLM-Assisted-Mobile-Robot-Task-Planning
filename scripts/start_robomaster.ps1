# Start the simulation in a persistent hidden WSL process.
# This allows the GUI/ROS launch to keep running after the caller exits.
$script = "/mnt/d/DS_workspace/Liqingbiao/assignment/scripts/run_robomaster_foreground.sh"
Start-Process -FilePath "wsl.exe" -ArgumentList @(
    "-d", "Ubuntu-22.04",
    "-u", "ubuntu",
    "-e", "bash", $script
) -WindowStyle Hidden
Write-Output "Simulation launch requested."
