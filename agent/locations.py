"""Named locations and workspace bounds for the simulated laboratory."""
from __future__ import annotations

from typing import Dict, Optional

from .models import Location

WORKSPACE_MIN_X = -7.0
WORKSPACE_MAX_X = 7.0
WORKSPACE_MIN_Y = -4.0
WORKSPACE_MAX_Y = 7.0

LOCATIONS: Dict[str, Location] = {
    "entrance": Location("entrance", 0.0, 2.0, 0.0),
    "storage": Location("storage", -2.152373937677039, -1.363206790893182, 0.0),
    "workbench": Location("workbench", 4.8, 0.0, 0.0),
    "charging_station": Location("charging_station", -2.17, 1.95, 0.0),
}


def get_location(name: str) -> Optional[Location]:
    return LOCATIONS.get(name.strip().lower())


def location_names() -> list:
    return sorted(LOCATIONS.keys())


def is_in_workspace(x: float, y: float) -> bool:
    return (
        WORKSPACE_MIN_X <= float(x) <= WORKSPACE_MAX_X
        and WORKSPACE_MIN_Y <= float(y) <= WORKSPACE_MAX_Y
    )
