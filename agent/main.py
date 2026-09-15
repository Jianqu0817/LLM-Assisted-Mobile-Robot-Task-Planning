"""CLI entry point for the task-planning agent."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

import rclpy
from robot_skills.skills import RobotSkills

from .executor import SkillExecutor
from .logger import JsonlLogger
from .planner import LLMPlanner, MockPlanner
from .recovery import RecoveryManager
from .task_agent import TaskAgent
from .validator import Validator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LLM-assisted robot task planner")
    parser.add_argument("request", type=str, help="Natural language request")
    parser.add_argument(
        "--log",
        type=str,
        default="/tmp/robot_task_agent.jsonl",
        help="JSONL log file path",
    )
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument(
        "--max-replans",
        type=int,
        default=1,
        help="Maximum number of LLM replans after execution feedback.",
    )
    parser.add_argument(
        "--navigation-mode",
        choices=["map", "direct"],
        default="map",
        help="Use A* map navigation or direct PID control.",
    )
    parser.add_argument(
        "--nav-timeout",
        type=float,
        default=None,
        help="Override navigation timeout in seconds (useful for recovery tests).",
    )
    parser.add_argument(
        "--planner",
        choices=["mock", "llm"],
        default="mock",
        help="Use the deterministic mock planner or an OpenAI-compatible LLM planner.",
    )
    return parser


def run(
    request: str,
    log_path: str,
    max_steps: int,
    max_retries: int,
    planner_name: str,
    nav_timeout: Optional[float] = None,
    navigation_mode: str = "map",
    max_replans: int = 1,
) -> int:
    rclpy.init()
    skills = RobotSkills()
    if nav_timeout is not None:
        skills.timeout_s = float(nav_timeout)
    skills.use_map = navigation_mode == "map"
    skills.load_map()
    try:
        planner = MockPlanner() if planner_name == "mock" else LLMPlanner()
        validator = Validator(max_steps=max_steps)
        executor = SkillExecutor(skills)
        recovery = RecoveryManager(
            max_retries=max_retries,
            max_replans=max_replans,
            allow_replan=bool(
                getattr(planner, "supports_feedback", False)
                and getattr(planner, "api_key", None)
            ),
        )
        logger = JsonlLogger(log_path)

        agent = TaskAgent(
            planner=planner,
            validator=validator,
            executor=executor,
            recovery=recovery,
            logger=logger,
        )
        final = agent.run(request)
        print(json.dumps(final, indent=2))
        return 0 if final.get("success") else 1
    finally:
        try:
            skills.stop()
        except Exception:
            pass
        skills.destroy_node()
        rclpy.shutdown()


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(
        request=args.request,
        log_path=args.log,
        max_steps=args.max_steps,
        max_retries=args.max_retries,
        planner_name=args.planner,
        nav_timeout=args.nav_timeout,
        navigation_mode=args.navigation_mode,
        max_replans=args.max_replans,
    )


if __name__ == "__main__":
    sys.exit(main())
