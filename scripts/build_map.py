#!/usr/bin/env python3
"""Build a 2D occupancy grid map from Webots GPS + compass + /scan.

The robot pose is taken from /agent0/gps and /agent0/compass/bearing
(ground-truth pose in simulation), and /scan provides the laser ranges.
This produces a map aligned with the current Webots world.
"""
from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import numpy as np
import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from webots_ros2_msgs.msg import FloatStamped


def normalize_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


class MapBuilder(Node):
    def __init__(
        self,
        resolution: float,
        width: int,
        height: int,
        origin_x: float,
        origin_y: float,
    ) -> None:
        super().__init__("map_builder")
        self.resolution = float(resolution)
        self.width = int(width)
        self.height = int(height)
        self.origin_x = float(origin_x)
        self.origin_y = float(origin_y)

        self.free = np.zeros((self.height, self.width), dtype=np.int32)
        self.occ = np.zeros((self.height, self.width), dtype=np.int32)

        self.x = None
        self.y = None
        self.yaw = None
        self.last_scan = None

        self.create_subscription(PointStamped, "/agent0/gps", self._gps_cb, 10)
        self.create_subscription(
            FloatStamped, "/agent0/compass/bearing", self._bearing_cb, 10
        )
        self.create_subscription(LaserScan, "/scan", self._scan_cb, 10)
        self.create_timer(0.1, self._integrate)
        self.get_logger().info("MapBuilder started")

    def _gps_cb(self, msg: PointStamped) -> None:
        self.x = float(msg.point.x)
        self.y = float(msg.point.y)

    def _bearing_cb(self, msg: FloatStamped) -> None:
        self.yaw = normalize_angle(-math.radians(float(msg.data)))

    def _scan_cb(self, msg: LaserScan) -> None:
        self.last_scan = msg

    def _world_to_grid(self, x: float, y: float):
        col = int(round((x - self.origin_x) / self.resolution))
        row = self.height - 1 - int(round((y - self.origin_y) / self.resolution))
        return col, row

    @staticmethod
    def _bresenham(c0: int, r0: int, c1: int, r1: int):
        cells = []
        dc = abs(c1 - c0)
        dr = abs(r1 - r0)
        sc = 1 if c0 < c1 else -1
        sr = 1 if r0 < r1 else -1
        err = dc - dr
        c, r = c0, r0
        while True:
            cells.append((c, r))
            if c == c1 and r == r1:
                break
            e2 = 2 * err
            if e2 > -dr:
                err -= dr
                c += sc
            if e2 < dc:
                err += dc
                r += sr
        return cells

    def _integrate(self) -> None:
        if (
            self.x is None
            or self.y is None
            or self.yaw is None
            or self.last_scan is None
        ):
            return
        scan = self.last_scan
        c0, r0 = self._world_to_grid(self.x, self.y)
        if not (0 <= c0 < self.width and 0 <= r0 < self.height):
            return

        self.free[r0, c0] += 5
        angle = scan.angle_min
        for distance in scan.ranges:
            if math.isfinite(distance) and scan.range_min < distance < scan.range_max:
                wx = self.x + distance * math.cos(self.yaw + angle)
                wy = self.y + distance * math.sin(self.yaw + angle)
                c1, r1 = self._world_to_grid(wx, wy)
                if 0 <= c1 < self.width and 0 <= r1 < self.height:
                    cells = self._bresenham(c0, r0, c1, r1)
                    for c, r in cells[:-1]:
                        self.free[r, c] += 1
                    self.occ[r1, c1] += 3
            angle += scan.angle_increment

    def save(self, output_prefix: str) -> None:
        # Endpoint hits are strong evidence of an obstacle; free-ray
        # evidence must not overwrite them.
        occupied = self.occ >= 2
        free = (self.free >= 3) & (~occupied)
        # Inflate occupied cells by one cell for safer A* paths.
        inflated = occupied.copy()
        inflated[1:, :] |= occupied[:-1, :]
        inflated[:-1, :] |= occupied[1:, :]
        inflated[:, 1:] |= occupied[:, :-1]
        inflated[:, :-1] |= occupied[:, 1:]
        img = np.full((self.height, self.width), 205, dtype=np.uint8)
        img[free & (~inflated)] = 254
        img[inflated] = 0

        prefix = Path(output_prefix)
        prefix.parent.mkdir(parents=True, exist_ok=True)
        pgm = prefix.with_suffix(".pgm")
        yaml = prefix.with_suffix(".yaml")
        with pgm.open("wb") as handle:
            header = f"P5\n{self.width} {self.height}\n255\n".encode("ascii")
            handle.write(header)
            handle.write(img.tobytes())
        yaml.write_text(
            f"image: {pgm.name}\n"
            f"resolution: {self.resolution}\n"
            f"origin: [{self.origin_x}, {self.origin_y}, 0.0]\n"
            "negate: 0\n"
            "occupied_thresh: 0.65\n"
            "free_thresh: 0.25\n",
            encoding="utf-8",
        )
        self.get_logger().info(f"saved map: {pgm}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a 2D map from Webots scan data.")
    parser.add_argument("--output", required=True, help="Output prefix, e.g. maps/break_room_map")
    parser.add_argument("--duration", type=float, default=120.0, help="Mapping duration in seconds; 0 means run until Ctrl+C")
    parser.add_argument("--resolution", type=float, default=0.02)
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=640)
    parser.add_argument("--origin-x", type=float, default=-8.0)
    parser.add_argument("--origin-y", type=float, default=-4.0)
    args = parser.parse_args()

    rclpy.init()
    node = MapBuilder(
        resolution=args.resolution,
        width=args.width,
        height=args.height,
        origin_x=args.origin_x,
        origin_y=args.origin_y,
    )
    start = time.monotonic()
    last_save = start
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.1)
            if args.duration > 0 and time.monotonic() - start >= args.duration:
                break
            now = time.monotonic()
            if now - last_save >= 10.0:
                node.save(args.output)
                last_save = now
    except KeyboardInterrupt:
        pass
    finally:
        node.save(args.output)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
