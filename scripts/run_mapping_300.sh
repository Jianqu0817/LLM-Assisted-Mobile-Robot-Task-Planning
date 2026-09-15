#!/usr/bin/env bash
# Run 300 s mapping with boundary patrol. Intended to be launched by
# scripts/start_mapping_300.ps1 (persistent hidden WSL process).
set -e
source /opt/ros/humble/setup.bash
source "$HOME/ros2_ws/install/setup.bash"
cd /mnt/d/DS_workspace/Liqingbiao/assignment

rm -f /tmp/build_map_full.log /tmp/patrol_room.log
python3 scripts/build_map.py --output maps/break_room_map_full --duration 300   > /tmp/build_map_full.log 2>&1 &
MAP_PID=$!

sleep 3
python3 scripts/patrol_room.py --duration 285 > /tmp/patrol_room.log 2>&1 &
PATROL_PID=$!

wait $PATROL_PID
wait $MAP_PID
echo "mapping and patrol finished"
