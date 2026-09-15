#!/usr/bin/env bash
# Start the Webots + ROS 2 simulation.
# Default: Windows-native Webots GUI + WSL ROS 2 driver.
set -e

source /opt/ros/humble/setup.bash
source "$HOME/ros2_ws/install/setup.bash"

export WEBOTS_HOME="${WEBOTS_HOME:-/usr/local/webots}"
unset TMPDIR

pkill -9 -x webots-bin 2>/dev/null || true
pkill -9 -x webots 2>/dev/null || true
pkill -f "robot_launch.py" 2>/dev/null || true
powershell.exe -NoProfile -Command "Get-Process webots -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null || true
sleep 2

nohup ros2 launch webots_ros2_robomaster robot_launch.py > /tmp/robomaster_launch.log 2>&1 &
echo "STARTED pid=$!"
