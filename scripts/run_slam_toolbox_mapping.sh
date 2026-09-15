#!/usr/bin/env bash
# Run slam_toolbox online SLAM with synthesized GPS/compass odometry while the
# robot patrols the room boundary. Intended to be launched by
# scripts/start_slam_mapping.ps1 (persistent hidden WSL process).
set -e
source /opt/ros/humble/setup.bash
source "$HOME/ros2_ws/install/setup.bash"
cd /mnt/d/DS_workspace/Liqingbiao/assignment

MAP_NAME="/mnt/d/DS_workspace/Liqingbiao/assignment/maps/slam_toolbox_map"
rm -f /tmp/odom_from_gps.log /tmp/slam_toolbox.log /tmp/patrol_slam.log

# 1) Synthesize /agent0/odom from GPS + compass.
python3 scripts/odom_from_gps.py --ros-args -p use_sim_time:=True   > /tmp/odom_from_gps.log 2>&1 &
ODOM_PID=$!

# 2) Start slam_toolbox online async.
ros2 launch slam_toolbox online_async_launch.py use_sim_time:=True   > /tmp/slam_toolbox.log 2>&1 &
SLAM_PID=$!

# 3) Wait for the /map topic.
for i in $(seq 1 40); do
  if ros2 topic list 2>/dev/null | grep -q "^/map$"; then
    echo "slam_toolbox /map is ready"
    break
  fi
  sleep 1
done

# 4) Patrol boundary for mapping.
python3 scripts/patrol_room.py --duration 280 > /tmp/patrol_slam.log 2>&1

# 5) Save the map.
sleep 3
ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap   "{name: {data: '${MAP_NAME}'}}" > /tmp/save_map.log 2>&1 || true
sleep 3

kill $ODOM_PID 2>/dev/null || true
kill $SLAM_PID 2>/dev/null || true
sleep 2
# Fallback: kill leftover nodes by name.
pkill -f "odom_from_gps.py" 2>/dev/null || true
pkill -f "async_slam_toolbox_node" 2>/dev/null || true
pkill -f "slam_toolbox online_async_launch" 2>/dev/null || true

echo "slam_toolbox mapping finished"
