#!/usr/bin/env python3
"""Build a 2D occupancy grid from Webots Supervisor-exported objects.

Reads maps/supervisor_objects.json (exported by supervisor_export_objects.py)
and writes maps/break_room_supervisor_map.pgm / .yaml.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

RES = 0.02
ORIGIN_X = -8.0
ORIGIN_Y = -4.0
WIDTH = 800
HEIGHT = 640
INFLATE_PIXELS = 5

OBJ = Path("/mnt/d/DS_workspace/Liqingbiao/assignment/maps/supervisor_objects.json")
OUT_PREFIX = Path("/mnt/d/DS_workspace/Liqingbiao/assignment/maps/break_room_supervisor_map")

DEFAULT_SIZES = {
    "Cabinet": (0.7, 0.7),
    "Sofa": (0.9, 2.0),
    "Sink": (0.7, 0.7),
    "SolidBox": (0.5, 0.5),
    "Table": (1.0, 1.0),
    "Wall": (0.0, 0.0),
    "Window": (0.0, 0.0),
}
DISK_RADIUS = {"OfficeChair": 0.35, "PottedTree": 0.45}
IGNORE_TYPES = {"Floor", "Robot", "Monitor", "Keyboard", "Solid", "Door", "CeilingLight", "CeilingSpotLight"}


def world_to_grid(x, y):
    col = int(round((x - ORIGIN_X) / RES))
    row = HEIGHT - 1 - int(round((y - ORIGIN_Y) / RES))
    return col, row


def draw_rect(img, cx, cy, sx, sy, rotation_rad, value=0):
    corners = []
    for dx, dy in [(-sx / 2, -sy / 2), (sx / 2, -sy / 2), (sx / 2, sy / 2), (-sx / 2, sy / 2)]:
        x = cx + dx * math.cos(rotation_rad) - dy * math.sin(rotation_rad)
        y = cy + dx * math.sin(rotation_rad) + dy * math.cos(rotation_rad)
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
    img[(rr - r) ** 2 + (cc - c) ** 2 <= rad * rad] = 0


def main() -> int:
    objects = json.loads(OBJ.read_text(encoding="utf-8"))
    img = np.full((HEIGHT, WIDTH), 205, dtype=np.uint8)

    # Free area from the Floor node, rotated to match the room.
    for obj in objects:
        if obj["type"] == "Floor" and obj.get("size"):
            sx, sy = obj["size"][0], obj["size"][1]
            rot = obj["rotation"][3] if obj.get("rotation") and len(obj["rotation"]) > 3 else 0.0
            draw_rect(img, obj["translation"][0], obj["translation"][1], sx, sy, rot, value=254)
            break

    for obj in objects:
        t = obj["type"]
        if t in IGNORE_TYPES:
            continue
        x, y = obj["translation"][0], obj["translation"][1]
        rot = obj["rotation"][3] if obj.get("rotation") and len(obj["rotation"]) > 3 else 0.0
        size = obj.get("size")
        if t in ("Wall", "Window"):
            if size and len(size) >= 2:
                # Wall size is [thickness, length, height]; unrotated length is along local y.
                sx, sy = size[0], size[1]
                draw_rect(img, x, y, sx, sy, rot, value=0)
            continue
        if t in DISK_RADIUS:
            draw_disk(img, x, y, DISK_RADIUS[t])
            continue
        if size and len(size) >= 2 and size[0] > 0 and size[1] > 0:
            sx, sy = size[0], size[1]
        else:
            sx, sy = DEFAULT_SIZES.get(t, (0.6, 0.6))
        draw_rect(img, x, y, sx, sy, rot, value=0)

    # Inflate occupied cells.
    occ = img == 0
    for _ in range(INFLATE_PIXELS):
        occ[1:, :] |= occ[:-1, :]
        occ[:-1, :] |= occ[1:, :]
        occ[:, 1:] |= occ[:, :-1]
        occ[:, :-1] |= occ[:, 1:]
    img[occ] = 0

    with OUT_PREFIX.with_suffix(".pgm").open("wb") as f:
        header = "P5" + chr(10) + f"{WIDTH} {HEIGHT}" + chr(10) + "255" + chr(10)
        f.write(header.encode())
        f.write(img.tobytes())
    OUT_PREFIX.with_suffix(".yaml").write_text(
        "image: " + OUT_PREFIX.with_suffix(".pgm").name + chr(10) +
        "resolution: " + str(RES) + chr(10) +
        "origin: [" + str(ORIGIN_X) + ", " + str(ORIGIN_Y) + ", 0.0]" + chr(10) +
        "negate: 0" + chr(10) +
        "occupied_thresh: 0.65" + chr(10) +
        "free_thresh: 0.25" + chr(10),
        encoding="utf-8",
    )
    print("saved maps/break_room_supervisor_map.pgm and .yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
