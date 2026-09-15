"""Bounded recovery strategies for validation and execution failures.

Recovery is intentionally rule-based and bounded:

- validation failures abort before any robot motion;
- ``timeout`` retries the same skill once;
- ``obstacle_blocked`` backs up, rotates, and retries once;
- after the retry budget is exhausted, an LLM planner may be asked once to
  replan using the structured execution feedback;
- if replanning is unavailable or exhausted, the robot stops and reports.
"""
from __future__ import annotations

from typing import Any, Dict

from .models import SkillCall, SkillResult, ValidationResult


class RecoveryManager:
    def __init__(
        self,
        max_retries: int = 1,
        max_replans: int = 1,
        allow_replan: bool = False,
    ) -> None:
        self.max_retries = int(max_retries)
        self.max_replans = int(max_replans)
        self.allow_replan = bool(allow_replan)

    def on_validation_failure(
        self, validation: ValidationResult, request: str
    ) -> Dict[str, Any]:
        if validation.reason == "target_out_of_workspace":
            return {
                "action": "abort",
                "message": (
                    "The requested location is outside the configured workspace. "
                    "Please choose a valid location such as entrance, storage, "
                    "workbench, or charging_station."
                ),
            }
        if validation.reason == "unknown_skill":
            return {
                "action": "abort",
                "message": "The plan contains an unknown skill and was rejected.",
            }
        if validation.reason == "too_many_steps":
            return {
                "action": "abort",
                "message": "The plan exceeds the maximum number of steps.",
            }
        return {
            "action": "abort",
            "message": f"Plan rejected by validator: {validation.reason}",
        }

    def on_execution_failure(
        self,
        call: SkillCall,
        result: SkillResult,
        attempt: int,
        replan_count: int = 0,
    ) -> Dict[str, Any]:
        """Decide the next bounded action after a skill returned failure."""

        if result.reason == "obstacle_blocked":
            if attempt < self.max_retries:
                return {
                    "action": "backup_and_retry",
                    "message": (
                        f"Obstacle detected during {call.skill}; backing up and "
                        f"retrying ({attempt + 1}/{self.max_retries})."
                    ),
                }
            if self.allow_replan and replan_count < self.max_replans:
                return {
                    "action": "replan",
                    "message": (
                        f"Obstacle still blocked after {attempt + 1} attempt(s); "
                        f"asking the planner for a new plan using execution "
                        f"feedback."
                    ),
                }
            return {
                "action": "stop_and_report",
                "message": "Target is blocked by an obstacle.",
            }

        if result.reason == "timeout":
            if attempt < self.max_retries:
                return {
                    "action": "retry",
                    "message": (
                        f"Skill {call.skill} timed out; retrying once "
                        f"({attempt + 1}/{self.max_retries})."
                    ),
                }
            if self.allow_replan and replan_count < self.max_replans:
                return {
                    "action": "replan",
                    "message": (
                        f"Skill {call.skill} timed out after {attempt + 1} "
                        f"attempt(s); asking the planner for a new plan using "
                        f"execution feedback."
                    ),
                }
            return {
                "action": "stop_and_report",
                "message": f"Skill {call.skill} timed out and was not resolved.",
            }

        return {
            "action": "stop_and_report",
            "message": f"Skill {call.skill} failed with reason {result.reason}.",
        }
