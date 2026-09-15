#!/usr/bin/env bash
# Stop the Webots + ROS 2 simulation (Linux and Windows Webots).
pkill -f "robot_launch.py" 2>/dev/null || true
sleep 1
pkill -9 -x webots-bin 2>/dev/null || true
pkill -9 -x webots 2>/dev/null || true
powershell.exe -NoProfile -Command "Get-Process webots -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null || true
echo "STOPPED"
