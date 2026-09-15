#!/usr/bin/env bash
set -e
export WEBOTS_HOME=/usr/local/webots
export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/mnt/wslg/runtime-dir}"
pkill -f "[p]ort=1240" 2>/dev/null || true
nohup /usr/local/webots/webots --batch --mode=fast --port=1240 /home/ubuntu/ros2_ws/src/webots_ros2_robomaster/worlds/break_room_map_export.wbt > /tmp/webots_export.log 2>&1 &
sleep 12
/opt/ros/humble/share/webots_ros2_driver/scripts/webots-controller --robot-name=MapExporter --protocol=ipc --port=1240 /mnt/d/DS_workspace/Liqingbiao/assignment/scripts/supervisor_export_objects.py
pkill -f "[p]ort=1240" 2>/dev/null || true
