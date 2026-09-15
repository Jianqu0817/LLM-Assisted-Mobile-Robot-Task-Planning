"""Offline tests for the Plan -> Validate -> Execute -> Recover loop.

These tests use a fake executor and a fake feedback-aware planner; no ROS 2,
Webots, or LLM API is required.

Run:
    python3 tests/test_task_agent.py
or:
    pytest tests/test_task_agent.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.logger import JsonlLogger
from agent.models import SkillCall, SkillResult
from agent.planner import MockPlanner
from agent.recovery import RecoveryManager
from agent.task_agent import TaskAgent
from agent.validator import Validator


class FakeExecutor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.stopped = 0
        self.recoveries = 0

    def execute(self, call):
        response = self.responses.pop(0)
        return SkillResult(**response)

    def stop(self):
        self.stopped += 1
        return SkillResult(True, "stopped", 0.1)

    def recover_from_obstacle(self):
        self.recoveries += 1
        return SkillResult(True, "obstacle_recovery_completed", 0.5)


class FeedbackAwarePlanner:
    supports_feedback = True

    def __init__(self):
        self.calls = 0

    def plan(self, request, feedback=None):
        self.calls += 1
        if feedback is None:
            return [SkillCall("navigate_to", {"x": 0.0, "y": 0.0, "theta": 0.0})]
        return [SkillCall("navigate_to", {"x": 0.5, "y": -0.5, "theta": 0.0})]


def _run(planner, responses, tmp_path, max_retries=1, allow_replan=False):
    executor = FakeExecutor(responses)
    recovery = RecoveryManager(
        max_retries=max_retries,
        max_replans=1,
        allow_replan=allow_replan,
    )
    logger = JsonlLogger(os.path.join(tmp_path, "log.jsonl"))
    agent = TaskAgent(
        planner=planner,
        validator=Validator(max_steps=5),
        executor=executor,
        recovery=recovery,
        logger=logger,
    )
    outcome = agent.run("Go to storage.")
    return outcome, executor, logger


def test_mock_success(tmp_path):
    outcome, executor, logger = _run(
        MockPlanner(),
        [{"success": True, "reason": "reached", "elapsed_time_s": 1.0}],
        tmp_path,
    )
    assert outcome["success"] is True
    assert outcome["reason"] == "all_skills_completed"


def test_mock_timeout_stops_after_retry(tmp_path):
    outcome, executor, logger = _run(
        MockPlanner(),
        [
            {"success": False, "reason": "timeout", "elapsed_time_s": 1.0},
            {"success": False, "reason": "timeout", "elapsed_time_s": 1.0},
        ],
        tmp_path,
    )
    assert outcome["success"] is False
    assert outcome["reason"] == "timeout"
    assert executor.stopped == 1


def test_feedback_aware_replan(tmp_path):
    planner = FeedbackAwarePlanner()
    outcome, executor, logger = _run(
        planner,
        [
            {"success": False, "reason": "timeout", "elapsed_time_s": 1.0},
            {"success": False, "reason": "timeout", "elapsed_time_s": 1.0},
            {"success": True, "reason": "reached", "elapsed_time_s": 2.0},
        ],
        tmp_path,
        allow_replan=True,
    )
    assert outcome["success"] is True
    assert planner.calls == 2

    events = []
    with open(logger.path, "r", encoding="utf-8") as handle:
        for line in handle:
            events.append(__import__("json").loads(line)["event"])
    assert "feedback_to_planner" in events
    assert "replanned_plan" in events


def test_replan_same_plan_stops(tmp_path):
    class SamePlanPlanner(FeedbackAwarePlanner):
        def plan(self, request, feedback=None):
            return [SkillCall("navigate_to", {"x": 0.0, "y": 0.0, "theta": 0.0})]

    outcome, executor, logger = _run(
        SamePlanPlanner(),
        [
            {"success": False, "reason": "timeout", "elapsed_time_s": 1.0},
            {"success": False, "reason": "timeout", "elapsed_time_s": 1.0},
        ],
        tmp_path,
        allow_replan=True,
    )
    assert outcome["success"] is False
    assert "Replanning produced the same plan" in outcome["message"]


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        test_mock_success(tmp)
        test_mock_timeout_stops_after_retry(tmp)
        test_feedback_aware_replan(tmp)
        test_replan_same_plan_stops(tmp)
    print("all task_agent tests passed")
