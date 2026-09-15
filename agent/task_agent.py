"""Closed-loop task agent.

This module owns the Plan -> Validate -> Execute -> Observe -> Recover loop:

    plan = planner.plan(request)
    validation = validator.validate_plan(plan)
    for each call:
        result = executor.execute(call)          # observe
        decision = recovery.on_execution_failure(call, result, ...)
        if decision.action == "replan":
            feedback = ExecutionFeedback(...)     # structured observation
            plan = planner.plan(request, feedback)  # close the loop
            revalidate the new plan

The loop is bounded by ``max_retries`` and ``max_replans``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .logger import JsonlLogger
from .models import ExecutionFeedback, SkillCall
from .recovery import RecoveryManager
from .validator import Validator


class TaskAgent:
    def __init__(
        self,
        planner: Any,
        validator: Validator,
        executor: Any,
        recovery: RecoveryManager,
        logger: JsonlLogger,
    ) -> None:
        self.planner = planner
        self.validator = validator
        self.executor = executor
        self.recovery = recovery
        self.logger = logger

    @staticmethod
    def _plan_to_dicts(plan: List[SkillCall]) -> List[Dict[str, Any]]:
        return [call.to_dict() for call in plan]

    @staticmethod
    def _same_plan(a: List[SkillCall], b: List[SkillCall]) -> bool:
        return TaskAgent._plan_to_dicts(a) == TaskAgent._plan_to_dicts(b)

    def run(self, request: str) -> Dict[str, Any]:
        """Execute one natural-language task and return the final outcome."""
        feedback: Optional[ExecutionFeedback] = None
        plan: List[SkillCall] = self.planner.plan(request, feedback)
        self.logger.log(
            "raw_plan",
            request=request,
            plan=self._plan_to_dicts(plan),
        )

        replan_count = 0
        completed_calls: List[Dict[str, Any]] = []

        while True:
            validation = self.validator.validate_plan(plan)
            self.logger.log(
                "validation",
                ok=validation.ok,
                reason=validation.reason,
                details=validation.details,
            )

            if not validation.ok:
                decision = self.recovery.on_validation_failure(
                    validation, request
                )
                self.logger.log("recovery_decision", **decision)
                final: Dict[str, Any] = {
                    "success": False,
                    "reason": validation.reason,
                    "message": decision["message"],
                }
                break

            final = None
            plan_changed = False

            for call in plan:
                attempt = 0
                while True:
                    result = self.executor.execute(call)
                    self.logger.log(
                        "skill_result",
                        call=call.to_dict(),
                        result=result.to_dict(),
                    )

                    if result.success:
                        completed_calls.append(
                            {
                                "call": call.to_dict(),
                                "result": result.to_dict(),
                            }
                        )
                        break

                    decision = self.recovery.on_execution_failure(
                        call, result, attempt, replan_count
                    )
                    self.logger.log(
                        "recovery_decision",
                        call=call.to_dict(),
                        **decision,
                    )

                    if decision["action"] == "retry":
                        attempt += 1
                        continue

                    if decision["action"] == "backup_and_retry":
                        recovery_result = self.executor.recover_from_obstacle()
                        self.logger.log(
                            "recovery_action",
                            action="backup_and_retry",
                            result=recovery_result.to_dict(),
                        )
                        attempt += 1
                        continue

                    if decision["action"] == "replan":
                        feedback = ExecutionFeedback(
                            request=request,
                            failed_call=call,
                            result=result,
                            attempt=attempt,
                            message=decision["message"],
                            completed_calls=completed_calls,
                        )
                        self.logger.log(
                            "feedback_to_planner", **feedback.to_dict()
                        )

                        new_plan = self.planner.plan(request, feedback)
                        self.logger.log(
                            "replanned_plan",
                            plan=self._plan_to_dicts(new_plan),
                        )

                        if self._same_plan(plan, new_plan):
                            final = {
                                "success": False,
                                "reason": result.reason,
                                "failed_call": call.to_dict(),
                                "message": (
                                    "Replanning produced the same plan; "
                                    "stopping safely."
                                ),
                            }
                        else:
                            plan = new_plan
                            replan_count += 1
                            plan_changed = True
                        break

                    # stop_and_report
                    self.executor.stop()
                    final = {
                        "success": False,
                        "reason": result.reason,
                        "failed_call": call.to_dict(),
                        "message": decision["message"],
                    }
                    break

                if plan_changed or final is not None:
                    break

            if plan_changed:
                continue

            if final is not None:
                break

            final = {
                "success": True,
                "reason": "all_skills_completed",
            }
            break

        self.logger.log("final_outcome", **final)
        return final
