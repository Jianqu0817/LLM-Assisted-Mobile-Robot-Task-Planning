"""Typed data models for the task-planning agent.

The models mirror the three phases of the closed loop:

    Plan -> Validate -> Execute -> Observe -> Recover

- ``SkillCall`` is the only object passed from the planner to the executor.
- ``ValidationResult`` records why a plan was accepted or rejected.
- ``SkillResult`` is the structured observation returned by a skill.
- ``ExecutionFeedback`` is the observed outcome sent back to the planner
  when a bounded replan is attempted.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Location:
    name: str
    x: float
    y: float
    theta: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SkillCall:
    """A single validated call to an allowlisted skill."""

    skill: str
    arguments: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"skill": self.skill, "arguments": self.arguments}


@dataclass
class ValidationResult:
    ok: bool
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SkillResult:
    """Structured result returned by every skill execution.

    Required fields: success, reason, elapsed_time_s.
    Optional fields are used by navigate_to and follow_waypoints.
    """

    success: bool
    reason: str
    elapsed_time_s: float
    position_error_m: Optional[float] = None
    heading_error_rad: Optional[float] = None
    last_reached_index: Optional[int] = None
    total_waypoints: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        extra = data.pop("extra", {}) or {}
        data.update(extra)
        return data


@dataclass
class ExecutionFeedback:
    """Structured observation returned to the planner after a failure.

    This is the "feedback" in *LLM-assisted task planning with execution
    feedback*. It intentionally contains only task-level information: the
    failed call, the observed structured result, the attempted recovery
    message, and already-completed work. It never exposes raw sensor data.
    """

    request: str
    failed_call: SkillCall
    result: SkillResult
    attempt: int
    message: str
    completed_calls: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request": self.request,
            "failed_call": self.failed_call.to_dict(),
            "result": self.result.to_dict(),
            "attempt": self.attempt,
            "message": self.message,
            "completed_calls": self.completed_calls,
        }
