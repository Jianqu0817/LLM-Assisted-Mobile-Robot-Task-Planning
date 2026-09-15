"""Execute validated skill calls through the ROS 2 robot_skills API.

The executor is the only component that talks to the concrete skill
implementation. The rest of the agent only sees ``SkillCall`` and
``SkillResult`` objects.
"""
from __future__ import annotations

from typing import Any, Dict

from robot_skills.skills import RobotSkills

from .models import SkillCall, SkillResult

# Fixed dispatch table. It deliberately mirrors the allowlist in
# ``agent/registry.py`` and is never user/LLM configurable.
_SKILL_METHODS: Dict[str, str] = {
    "navigate_to": "navigate_to",
    "follow_waypoints": "follow_waypoints",
    "stop": "stop",
}


def _to_skill_result(raw: Any) -> SkillResult:
    return SkillResult(
        success=raw.success,
        reason=raw.reason,
        elapsed_time_s=raw.elapsed_time_s,
        position_error_m=getattr(raw, "position_error_m", None),
        heading_error_rad=getattr(raw, "heading_error_rad", None),
        last_reached_index=getattr(raw, "last_reached_index", None),
        total_waypoints=getattr(raw, "total_waypoints", None),
        extra=getattr(raw, "extra", {}) or {},
    )


class SkillExecutor:
    def __init__(self, skills: RobotSkills) -> None:
        self.skills = skills

    def execute(self, call: SkillCall) -> SkillResult:
        method_name = _SKILL_METHODS.get(call.skill)
        if method_name is None:
            return SkillResult(False, "unknown_skill", 0.0)

        method = getattr(self.skills, method_name)
        raw = method(**call.arguments)
        return _to_skill_result(raw)

    def stop(self) -> SkillResult:
        return _to_skill_result(self.skills.stop())

    def recover_from_obstacle(self) -> SkillResult:
        return _to_skill_result(self.skills.recover_from_obstacle())
