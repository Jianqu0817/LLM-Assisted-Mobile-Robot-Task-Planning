#!/usr/bin/env bash
# Run the simulation in the foreground. Intended to be launched by a
# persistent Windows wsl.exe process.
set -e
source /opt/ros/humble/setup.bash
source "$HOME/ros2_ws/install/setup.bash"
export WEBOTS_HOME="${WEBOTS_HOME:-/usr/local/webots}"
export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/mnt/wslg/runtime-dir}"
unset TMPDIR
exec > /tmp/robomaster_launch.log 2>&1
exec ros2 launch webots_ros2_robomaster robot_launch.py
