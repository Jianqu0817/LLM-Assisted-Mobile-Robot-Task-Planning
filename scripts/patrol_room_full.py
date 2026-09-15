#!/usr/bin/env python3
"""Full-room zigzag patrol for map building.

Runs the robot back and forth across the room in horizontal stripes so the
laser scanner observes the whole floor. Waypoint failures (obstacle/timeout)
are skipped so the patrol never gets stuck for long.
"""
from __future__ import annotations

import argparse
import time

import rclpy
from robot_skills.skills import RobotSkills


def make_waypoints() -> list:
    y_rows = [-2.2, -0.8, 0.6, 2.0, 3.4, 4.2]
    x_cols = [-5.5, -4.0, -2.5, -1.0, 0.5, 2.0, 3.5, 5.0, 6.0]
    waypoints = []
    reverse = False
    for y in y_rows:
        xs = list(reversed(x_cols)) if reverse else x_cols
        for x in xs:
            waypoints.append((x, y, 0.0))
        reverse = not reverse
    return waypoints


def main() -> int:
    parser = argparse.ArgumentParser(description="Full-room zigzag patrol for mapping.")
    parser.add_argument("--duration", type=float, default=600.0,
                        help="Patrol duration in seconds; 0 means until Ctrl+C.")
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args()

    rclpy.init()
    skills = RobotSkills()
    skills.use_map = False
    skills.load_map()

    waypoints = make_waypoints()
    start = time.monotonic()
    loop = 0
    try:
        while rclpy.ok():
            for index, (x, y, theta) in enumerate(waypoints):
                if args.duration > 0 and time.monotonic() - start >= args.duration:
                    break
                print(f"[zigzag {loop}:{index}] -> ({x:.1f}, {y:.1f})", flush=True)
                result = skills.navigate_to(x, y, theta, timeout_s=args.timeout)
                print(
                    f"[zigzag {loop}:{index}] success={result.success}, "
                    f"reason={result.reason}, error={result.position_error_m}",
                    flush=True,
                )
                if result.reason == "obstacle_blocked":
                    skills.recover_from_obstacle()
            if args.duration > 0 and time.monotonic() - start >= args.duration:
                break
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
