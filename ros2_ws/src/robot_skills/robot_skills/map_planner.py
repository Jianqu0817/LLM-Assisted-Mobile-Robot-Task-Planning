"""A* planner on a 2D occupancy grid (PGM/YAML).

The map is treated conservatively:
  - 254 (free)     : traversable
  - 0   (occupied) : not traversable
  - 205 (unknown)  : not traversable, except for the start/goal cells
"""
from __future__ import annotations

import heapq
import math
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

Cell = Tuple[int, int]
Waypoint = Tuple[float, float, float]

FREE_VALUE = 254
OCCUPIED_VALUE = 0
UNKNOWN_VALUE = 205
WHITESPACE = bytes([32, 9, 13, 10])


def _read_pgm(path: Path):
    data = path.read_bytes()
    pos = 0
    tokens = []
    while len(tokens) < 4:
        while pos < len(data) and data[pos] in WHITESPACE:
            pos += 1
        if pos < len(data) and data[pos] == 35:  # '#'
            while pos < len(data) and data[pos] not in (13, 10):
                pos += 1
            continue
        start = pos
        while pos < len(data) and data[pos] not in WHITESPACE:
            pos += 1
        tokens.append(data[start:pos])
    magic, width_b, height_b, maxval_b = tokens
    if magic != b"P5":
        raise ValueError("Only binary P5 PGM is supported")
    width = int(width_b)
    height = int(height_b)
    maxval = int(maxval_b)
    pos += 1  # skip whitespace after maxval
    raw = data[pos:pos + width * height]
    if len(raw) != width * height:
        raise ValueError("PGM data size mismatch")
    return width, height, raw


def _parse_yaml(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    resolution = None
    origin_x = None
    origin_y = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("resolution:"):
            resolution = float(stripped.split(":", 1)[1].strip())
        elif stripped.startswith("origin:"):
            inside = stripped.split("[", 1)[1].split("]", 1)[0]
            parts = [part.strip() for part in inside.split(",")]
            origin_x = float(parts[0])
            origin_y = float(parts[1])
    if resolution is None or origin_x is None or origin_y is None:
        raise ValueError("YAML missing resolution or origin")
    return resolution, origin_x, origin_y


class MapPlanner:
    def __init__(self, pgm_path: str, yaml_path: Optional[str] = None) -> None:
        self.pgm_path = Path(pgm_path)
        if yaml_path is None:
            yaml_path = str(self.pgm_path.with_suffix(".yaml"))
        self.yaml_path = Path(yaml_path)
        self.width, self.height, self.data = _read_pgm(self.pgm_path)
        self.resolution, self.origin_x, self.origin_y = _parse_yaml(self.yaml_path)

    def value(self, col: int, row: int) -> int:
        if not (0 <= col < self.width and 0 <= row < self.height):
            return OCCUPIED_VALUE
        return self.data[row * self.width + col]

    def is_free(self, col: int, row: int) -> bool:
        return self.value(col, row) == FREE_VALUE

    def is_unknown(self, col: int, row: int) -> bool:
        return self.value(col, row) == UNKNOWN_VALUE

    def world_to_grid(self, x: float, y: float) -> Cell:
        col = int(round((x - self.origin_x) / self.resolution))
        row = self.height - 1 - int(round((y - self.origin_y) / self.resolution))
        return col, row

    def grid_to_world(self, col: int, row: int):
        x = self.origin_x + (col + 0.5) * self.resolution
        y = self.origin_y + (self.height - 1 - row + 0.5) * self.resolution
        return x, y

    @staticmethod
    def _neighbors(col: int, row: int):
        return [
            (col + 1, row, 1.0),
            (col - 1, row, 1.0),
            (col, row + 1, 1.0),
            (col, row - 1, 1.0),
            (col + 1, row + 1, math.sqrt(2.0)),
            (col + 1, row - 1, math.sqrt(2.0)),
            (col - 1, row + 1, math.sqrt(2.0)),
            (col - 1, row - 1, math.sqrt(2.0)),
        ]

    @staticmethod
    def _heuristic(c0: int, r0: int, c1: int, r1: int) -> float:
        dc = abs(c1 - c0)
        dr = abs(r1 - r0)
        return max(dc, dr) + (math.sqrt(2.0) - 1.0) * min(dc, dr)

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

    def _line_free(self, c0: int, r0: int, c1: int, r1: int) -> bool:
        for c, r in self._bresenham(c0, r0, c1, r1):
            if not self.is_free(c, r):
                return False
        return True

    def plan_cells(self, start_xy, goal_xy) -> Optional[List[Cell]]:
        start = self.world_to_grid(*start_xy)
        goal = self.world_to_grid(*goal_xy)
        if not (0 <= start[0] < self.width and 0 <= start[1] < self.height):
            return None
        if not (0 <= goal[0] < self.width and 0 <= goal[1] < self.height):
            return None
        if not (self.is_free(*start) or self.is_unknown(*start)):
            return None
        if not (self.is_free(*goal) or self.is_unknown(*goal)):
            return None

        open_heap = [(0.0, start)]
        came_from = {}
        g_score = {start: 0.0}
        closed = set()

        while open_heap:
            _, current = heapq.heappop(open_heap)
            if current in closed:
                continue
            closed.add(current)
            if current == goal:
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path

            for nc, nr, move_cost in self._neighbors(*current):
                neighbor = (nc, nr)
                if neighbor in closed:
                    continue
                if not (0 <= nc < self.width and 0 <= nr < self.height):
                    continue
                if not self.is_free(nc, nr):
                    if neighbor != goal:
                        continue
                tentative = g_score[current] + move_cost
                if tentative < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative
                    f = tentative + self._heuristic(nc, nr, goal[0], goal[1])
                    heapq.heappush(open_heap, (f, neighbor))
        return None

    def simplify(self, cells: List[Cell]) -> List[Cell]:
        if len(cells) <= 2:
            return cells
        simplified = [cells[0]]
        i = 0
        while i < len(cells) - 1:
            j = len(cells) - 1
            while j > i + 1:
                if self._line_free(*cells[i], *cells[j]):
                    break
                j -= 1
            simplified.append(cells[j])
            i = j
        return simplified

    def plan(self, start_xy, goal_xy, goal_theta: float = 0.0) -> Optional[List[Waypoint]]:
        cells = self.plan_cells(start_xy, goal_xy)
        if cells is None:
            return None
        cells = self.simplify(cells)
        if len(cells) < 2:
            return None
        points = [self.grid_to_world(c, r) for c, r in cells]
        waypoints: List[Waypoint] = []
        for i, (x, y) in enumerate(points[1:], start=1):
            if i < len(points) - 1:
                nx, ny = points[i + 1]
                theta = math.atan2(ny - y, nx - x)
            else:
                theta = goal_theta
            waypoints.append((x, y, theta))
        return waypoints
