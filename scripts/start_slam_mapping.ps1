# Start slam_toolbox mapping + boundary patrol in a persistent hidden WSL process.
$script = "/mnt/d/DS_workspace/Liqingbiao/assignment/scripts/run_slam_toolbox_mapping.sh"
Start-Process -FilePath "wsl.exe" -ArgumentList @(
    "-d", "Ubuntu-22.04",
    "-u", "ubuntu",
    "-e", "bash", $script
) -WindowStyle Hidden
Write-Output "slam_toolbox mapping requested."
