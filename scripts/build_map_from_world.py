#!/usr/bin/env python3
"""Build a 2D occupancy grid directly from the Webots world file geometry.

This is a simulation-level map generator: instead of moving the robot and
recording laser scans, it parses break_room.wbt, draws the room rectangle as
free, and draws walls / furniture as occupied. The result is aligned with the
current world and covers the full room immediately.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np

WBT = Path("/home/ubuntu/ros2_ws/src/webots_ros2_robomaster/worlds/break_room.wbt")

# Map parameters: cover the full room with 0.02 m/pixel.
RES = 0.02
ORIGIN_X = -8.0
ORIGIN_Y = -4.0
WIDTH = 800
HEIGHT = 640


def world_to_grid(x, y):
    col = int(round((x - ORIGIN_X) / RES))
    row = HEIGHT - 1 - int(round((y - ORIGIN_Y) / RES))
    return col, row


def draw_rect(img, cx, cy, sx, sy, rotation, value=0):
    """Draw a rectangle in world coordinates into the grid."""
    corners = []
    for dx, dy in [(-sx / 2, -sy / 2), (sx / 2, -sy / 2), (sx / 2, sy / 2), (-sx / 2, sy / 2)]:
        cos, sin = math.cos(rotation), math.sin(rotation)
        x = cx + dx * cos - dy * sin
        y = cy + dx * sin + dy * cos
        corners.append(world_to_grid(x, y))
    cols = sorted(c[0] for c in corners)
    rows = sorted(c[1] for c in corners)
    c0, c1 = max(0, cols[0]), min(WIDTH - 1, cols[-1])
    r0, r1 = max(0, rows[0]), min(HEIGHT - 1, rows[-1])
    img[r0:r1 + 1, c0:c1 + 1] = value


def draw_disk(img, cx, cy, radius):
    c, r = world_to_grid(cx, cy)
    rad = int(round(radius / RES))
    rr, cc = np.ogrid[:HEIGHT, :WIDTH]
    mask = (rr - r) ** 2 + (cc - c) ** 2 <= rad * rad
    img[mask] = 0


def parse_vec3(line):
    nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", line)
    if len(nums) >= 3:
        return float(nums[0]), float(nums[1]), float(nums[2])
    return None


def main() -> int:
    text = WBT.read_text()
    img = np.full((HEIGHT, WIDTH), 205, dtype=np.uint8)

    # Free area: only the actual room interior inside the outer walls.
    # Outer walls are at x=-6.17 / x=6.68 and y=-2.9 / y=4.8.
    draw_rect(img, 0.25, 0.95, 12.79, 7.64, 0.0, value=254)
    # Draw outer walls:
    draw_rect(img, -6.17, 0.92, 0.10, 7.7, 0.0)   # west
    draw_rect(img, 6.68, 0.92, 0.10, 7.7, 0.0)    # east
    draw_rect(img, 0.26, -2.9, 13.0, 0.10, 0.0)   # south
    draw_rect(img, -3.35, 4.8, 5.7, 0.10, math.pi/2)  # north-left
    draw_rect(img, 3.6, 4.8, 6.2, 0.10, math.pi/2)    # north-right
    # North door gap is left free (x in [-0.5, 0.5]).

    # Inner partition walls.
    inner_walls = [
        (-2.65, 0.0, 0.05, 5.0, 0.0),
        (2.65, -0.77, 0.05, 3.55, 0.0),
        (0.0, -2.52, 5.35, 0.05, 0.0),
        (-1.65, 2.524, 2.05, 0.05, 0.0),
        (-0.65, 3.05, 1.0, 0.05, 0.0),
        (0.4, 3.05, 1.0, 0.05, 0.0),
        (1.876, 2.524, 3.0, 0.05, 0.0),
        (3.026, 0.979, 0.7, 0.05, 0.0),
    ]
    for x, y, sx, sy, _ in inner_walls:
        draw_rect(img, x, y, sx, sy, 0.0)

    # Furniture.
    furniture = [
        ("Sofa", 0.9, 2.0),
        ("Cabinet", 0.7, 0.7),
        ("Sink", 0.7, 0.7),
        ("SolidBox", 0.5, 0.5),
    ]
    for obj in ["Sofa", "Cabinet", "Sink", "SolidBox"]:
        for m in re.finditer(rf"{obj} \{{(.*?)\n\}}", text, re.S):
            body = m.group(1)
            t = re.search(r"translation\s+([-+0-9.eE ]+)", body)
            if not t:
                continue
            x, y, _ = parse_vec3(t.group(1))
            if obj == "Sofa":
                draw_rect(img, x, y, 0.9, 2.0, 0.0)
            elif obj == "Cabinet":
                draw_rect(img, x, y, 0.7, 0.7, 0.0)
            elif obj == "Sink":
                draw_rect(img, x, y, 0.7, 0.7, 0.0)
            elif obj == "SolidBox":
                s = re.search(r"size\s+([-+0-9.eE ]+)", body)
                if s:
                    sx, sy, _ = parse_vec3(s.group(1))
                    draw_rect(img, x, y, sx, sy, 0.0)

    # Potted trees.
    for m in re.finditer(r"PottedTree \{\s*translation\s+([-+0-9.eE ]+)\s*\}", text):
        x, y, _ = parse_vec3(m.group(1))
        draw_disk(img, x, y, 0.45)

    # Office chairs (small floor obstacles).
    for m in re.finditer(r"OfficeChair \{(.*?)\}", text, re.S):

        body = m.group(1)
        t = re.search(r"translation\s+([-+0-9.eE ]+)", body)
        if t:
            x, y, _ = parse_vec3(t.group(1))
            draw_disk(img, x, y, 0.35)

    # Tables (parse size when present, otherwise default 1.0 x 1.0).
    for m in re.finditer(r"Table \{(.*?)\n\}", text, re.S):
        body = m.group(1)
        t = re.search(r"translation\s+([-+0-9.eE ]+)", body)
        if not t:
            continue
        x, y, _ = parse_vec3(t.group(1))
        s = re.search(r"size\s+([-+0-9.eE ]+)", body)
        sx = sy = 1.0
        if s:
            vals = parse_vec3(s.group(1))
            sx, sy = vals[0], vals[1]
        rot = 0.0
        r = re.search(r"rotation\s+([-+0-9.eE ]+)", body)
        if r:
            _, _, rot = parse_vec3(r.group(1))
        draw_rect(img, x, y, sx, sy, rot)

    # Inflate occupied cells by 5 pixels (0.10 m) for safer A* clearance.
    occ = img == 0
    for _ in range(5):
        occ[1:, :] |= occ[:-1, :]
        occ[:-1, :] |= occ[1:, :]
        occ[:, 1:] |= occ[:, :-1]
        occ[:, :-1] |= occ[:, 1:]
    img[occ] = 0

    # Save PGM/YAML.
    prefix = Path("maps/break_room_world_map")
    with prefix.with_suffix(".pgm").open("wb") as f:
        f.write(f"P5\n{WIDTH} {HEIGHT}\n255\n".encode())
        f.write(img.tobytes())
    prefix.with_suffix(".yaml").write_text(
        f"image: {prefix.with_suffix('.pgm').name}\n"
        f"resolution: {RES}\n"
        f"origin: [{ORIGIN_X}, {ORIGIN_Y}, 0.0]\n"
        "negate: 0\n"
        "occupied_thresh: 0.65\n"
        "free_thresh: 0.25\n",
        encoding="utf-8",
    )
    print("saved maps/break_room_world_map.pgm and .yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
