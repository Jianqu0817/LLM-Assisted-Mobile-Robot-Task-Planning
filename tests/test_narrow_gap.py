#!/usr/bin/env python3
"""Synthetic narrow-gap checks for the local safety layer.

This test uses the real ``RobotSkills`` methods ``_free_gap_width_around``,
``_is_gap_too_narrow`` and ``_is_direction_blocked`` with a fake LaserScan.
It does not need Webots or a running robot.

Run in a ROS 2 environment:
    python3 tests/test_narrow_gap.py
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ros2_ws", "src", "robot_skills"))

from robot_skills.skills import RobotSkills


class FakeScan:
    pass


def make_scan(free_half_deg: float, free_range: float = 1.5, blocked_range: float = 0.2) -> FakeScan:
    """Create a 360-degree scan with a free sector around 0 rad."""
    n = 180
    inc = 2.0 * math.pi / n
    scan = FakeScan()
    scan.angle_min = -math.pi
    scan.angle_increment = inc
    scan.range_min = 0.05
    scan.range_max = 10.0
    half = math.radians(free_half_deg)
    ranges = []
    for i in range(n):
        angle = -math.pi + i * inc
        if angle > math.pi:
            angle -= 2.0 * math.pi
        ranges.append(free_range if abs(angle) <= half else blocked_range)
    scan.ranges = ranges
    return scan


def make_skills(scan: FakeScan) -> RobotSkills:
    skills = object.__new__(RobotSkills)
    skills.scan = scan
    skills._last_scan_time = time.monotonic()
    skills.scan_timeout_s = 1.0
    skills.obstacle_cone_rad = 0.35
    skills.obstacle_stop_distance = 0.15
    skills.min_gap_width_m = 0.45
    skills.gap_check_distance_m = 1.5
    skills.gap_free_range_m = 0.8
    skills.side_clearance_cone_rad = 0.35
    return skills


def main() -> int:
    results = []
    for half_deg in (3.0, 20.0, 30.0):
        skills = make_skills(make_scan(half_deg))
        gap = skills._free_gap_width_around(0.0)
        results.append(
            {
                "free_sector_half_deg": half_deg,
                "estimated_gap_m": None if gap is None else round(float(gap), 3),
                "too_narrow": bool(skills._is_gap_too_narrow(0.0)),
                "direction_blocked": bool(skills._is_direction_blocked(0.0)),
            }
        )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
