#!/usr/bin/env python3
"""Patrol the break-room boundary with no-map direct PID navigation.

This script is intended to be run while scripts/build_map.py is recording.
It repeatedly sends the robot to waypoints around the room boundary, so the
laser scanner observes a much larger area than the default named locations.
Individual waypoints may fail (obstacle / timeout); the patrol continues.
"""
from __future__ import annotations

import argparse
import time

import rclpy
from robot_skills.skills import RobotSkills

# Room boundary loop, with margins from the known wall positions.
BOUNDARY_WAYPOINTS = [
    (0.0, -1.2, 0.0),
    (3.0, -1.2, 0.0),
    (5.2, -1.2, 0.0),
    (5.6, 0.5, 0.0),
    (5.6, 2.0, 0.0),
    (4.5, 3.5, 0.0),
    (2.0, 4.0, 0.0),
    (0.0, 4.2, 0.0),
    (-2.0, 4.0, 0.0),
    (-4.0, 3.2, 0.0),
    (-5.5, 1.5, 0.0),
    (-5.5, -0.5, 0.0),
    (-4.0, -2.0, 0.0),
    (-2.0, -2.2, 0.0),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Patrol room boundary for mapping.")
    parser.add_argument("--duration", type=float, default=300.0)
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args()

    rclpy.init()
    skills = RobotSkills()
    skills.use_map = False
    skills.load_map()

    start = time.monotonic()
    loop = 0
    try:
        while rclpy.ok() and time.monotonic() - start < args.duration:
            for index, (x, y, theta) in enumerate(BOUNDARY_WAYPOINTS):
                if time.monotonic() - start >= args.duration:
                    break
                print(
                    f"[patrol {loop}:{index}] -> ({x:.1f}, {y:.1f}, {theta:.1f})",
                    flush=True,
                )
                result = skills.navigate_to(x, y, theta, timeout_s=args.timeout)
                print(
                    f"[patrol {loop}:{index}] result: success={result.success}, "
                    f"reason={result.reason}, error={result.position_error_m}",
                    flush=True,
                )
                if result.reason == "obstacle_blocked":
                    skills.recover_from_obstacle()
            loop += 1
    except KeyboardInterrupt:
        pass
    finally:
        try:
            skills.stop()
        except Exception:
            pass
        skills.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
