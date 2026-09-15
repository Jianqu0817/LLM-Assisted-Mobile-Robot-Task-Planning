"""Validation layer for LLM-proposed skill calls."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import jsonschema

from .locations import is_in_workspace
from .models import SkillCall, ValidationResult
from .registry import ALLOWED_SKILLS, SKILL_REGISTRY


class Validator:
    """Multi-layer validator: allowlist, schema, workspace bounds, step limit."""

    def __init__(self, max_steps: int = 5) -> None:
        self.max_steps = int(max_steps)

    def validate_plan(self, plan: List[SkillCall]) -> ValidationResult:
        if not isinstance(plan, list):
            return ValidationResult(False, "plan_not_list")
        if len(plan) == 0:
            return ValidationResult(False, "empty_plan")
        if len(plan) > self.max_steps:
            return ValidationResult(
                False,
                "too_many_steps",
                {"steps": len(plan), "max_steps": self.max_steps},
            )
        for index, call in enumerate(plan):
            result = self.validate_call(call)
            if not result.ok:
                result.details["call_index"] = index
                return result
        return ValidationResult(True, "plan_valid", {"steps": len(plan)})

    def validate_call(self, call: SkillCall) -> ValidationResult:
        if not isinstance(call, SkillCall):
            return ValidationResult(False, "call_not_skill_call")
        if call.skill not in ALLOWED_SKILLS:
            return ValidationResult(
                False,
                "unknown_skill",
                {"skill": call.skill, "allowed": list(ALLOWED_SKILLS)},
            )

        # Workspace bounds are checked before schema so out-of-workspace
        # requests are reported with a semantic reason.
        if call.skill == "navigate_to":
            x = call.arguments.get("x")
            y = call.arguments.get("y")
            if (
                isinstance(x, (int, float))
                and not isinstance(x, bool)
                and isinstance(y, (int, float))
                and not isinstance(y, bool)
                and not is_in_workspace(float(x), float(y))
            ):
                return ValidationResult(
                    False,
                    "target_out_of_workspace",
                    {"x": x, "y": y},
                )

        if call.skill == "follow_waypoints":
            waypoints = call.arguments.get("waypoints")
            if isinstance(waypoints, list):
                for index, waypoint in enumerate(waypoints):
                    if not isinstance(waypoint, dict):
                        continue
                    x = waypoint.get("x")
                    y = waypoint.get("y")
                    if (
                        isinstance(x, (int, float))
                        and not isinstance(x, bool)
                        and isinstance(y, (int, float))
                        and not isinstance(y, bool)
                        and not is_in_workspace(float(x), float(y))
                    ):
                        return ValidationResult(
                            False,
                            "waypoint_out_of_workspace",
                            {"waypoint_index": index, "x": x, "y": y},
                        )

        schema = SKILL_REGISTRY[call.skill]["parameters"]
        try:
            jsonschema.validate(instance=call.arguments, schema=schema)
        except jsonschema.ValidationError as exc:
            return ValidationResult(
                False,
                "schema_invalid",
                {
                    "skill": call.skill,
                    "error": exc.message,
                    "path": list(exc.path),
                },
            )

        if call.skill == "navigate_to":
            x = float(call.arguments["x"])
            y = float(call.arguments["y"])
            if not is_in_workspace(x, y):
                return ValidationResult(
                    False,
                    "target_out_of_workspace",
                    {"x": x, "y": y},
                )

        if call.skill == "follow_waypoints":
            for index, waypoint in enumerate(call.arguments["waypoints"]):
                x = float(waypoint["x"])
                y = float(waypoint["y"])
                if not is_in_workspace(x, y):
                    return ValidationResult(
                        False,
                        "waypoint_out_of_workspace",
                        {"waypoint_index": index, "x": x, "y": y},
                    )

        return ValidationResult(True, "valid", {"skill": call.skill})
