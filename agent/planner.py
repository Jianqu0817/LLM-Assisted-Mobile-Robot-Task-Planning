"""Planner implementations: deterministic mock and optional LLM planner.

The planner is a task-level planner only. It converts a natural-language
request into a small, allowlisted sequence of ``SkillCall`` objects. It has
no access to raw sensor data and cannot issue velocity commands.

When execution feedback is available, an ``LLMPlanner`` receives a compact
``ExecutionFeedback`` object and is asked to produce a new plan. This is the
"execution feedback" channel of the Plan -> Validate -> Execute -> Recover
loop.
"""
from __future__ import annotations

import json
import os
import re
from typing import List, Optional

from .locations import get_location
from .models import ExecutionFeedback, SkillCall


class PlannerError(Exception):
    pass


class MockPlanner:
    """Rule-based planner used for development and offline testing.

    It understands the three required request patterns:
      1. Go to <location>.
      2. Visit <A>, then <B>, and stop.
      3. Invalid request (unknown location or unknown skill).

    The mock planner does not consume execution feedback; it is
    deterministic by design. Task-level recovery for mock plans is
    therefore limited to rule-based retry / backup / stop-and-report.
    """

    supports_feedback = False

    def plan(
        self, request: str, feedback: Optional[ExecutionFeedback] = None
    ) -> List[SkillCall]:
        text = request.strip()

        # Unknown skill test, e.g. "Go to entrance and fly."
        if re.search("fly", text, flags=re.IGNORECASE):
            return [SkillCall("fly_to", {"x": 0.0, "y": 0.0})]

        # 1) "Go to <location>."
        match = re.fullmatch(r"[Gg]o to ([A-Za-z_ ]+)[.]?", text)
        if match:
            name = match.group(1).strip().replace(" ", "_").lower()
            location = get_location(name)
            if location is not None:
                return [
                    SkillCall(
                        "navigate_to",
                        {"x": location.x, "y": location.y, "theta": location.theta},
                    )
                ]
            return [
                SkillCall("navigate_to", {"x": 999.0, "y": 999.0, "theta": 0.0})
            ]

        # 2) "Visit <A>, then <B>, and stop."
        match = re.fullmatch(
            r"[Vv]isit ([A-Za-z_ ]+),[ ]*then ([A-Za-z_ ]+),?[ ]*and stop[.]?",
            text,
        )
        if match:
            names = [
                match.group(1).strip().replace(" ", "_").lower(),
                match.group(2).strip().replace(" ", "_").lower(),
            ]
            waypoints = []
            for name in names:
                location = get_location(name)
                if location is None:
                    return [
                        SkillCall(
                            "navigate_to", {"x": 999.0, "y": 999.0, "theta": 0.0}
                        )
                    ]
                waypoints.append(
                    {"x": location.x, "y": location.y, "theta": location.theta}
                )
            return [
                SkillCall("follow_waypoints", {"waypoints": waypoints}),
                SkillCall("stop", {}),
            ]

        # Default invalid plan.
        return [SkillCall("navigate_to", {"x": 999.0, "y": 999.0, "theta": 0.0})]


class LLMPlanner:
    """OpenAI-compatible function-calling planner.

    Config is read from environment variables or from a .env file:
        OPENAI_BASE_URL  (default https://yinli.one/v1)
        OPENAI_API_KEY
        OPENAI_MODEL     (default gpt-5.5)

    The LLM sees:
      - the original request,
      - the available named locations,
      - the workspace bounds,
      - the tool list generated from the skill registry,
      - optionally, a structured ExecutionFeedback after a failed execution.

    It never sees raw sensor data and never controls the robot directly.
    """

    supports_feedback = True

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except Exception:
            pass

        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.5")
        self.base_url = base_url or os.getenv(
            "OPENAI_BASE_URL", "https://yinli.one/v1"
        )
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._fallback = MockPlanner()

    def _build_messages(
        self, request: str, feedback: Optional[ExecutionFeedback]
    ) -> List[dict]:
        from .locations import (
            LOCATIONS,
            WORKSPACE_MAX_X,
            WORKSPACE_MAX_Y,
            WORKSPACE_MIN_X,
            WORKSPACE_MIN_Y,
        )

        location_lines = chr(10).join(
            f"- {loc.name}: x={loc.x}, y={loc.y}, theta={loc.theta}"
            for loc in LOCATIONS.values()
        )
        bounds = (
            f"x in [{WORKSPACE_MIN_X}, {WORKSPACE_MAX_X}], "
            f"y in [{WORKSPACE_MIN_Y}, {WORKSPACE_MAX_Y}]"
        )
        system_prompt = (
            "You are a robot task planner. Select only from the provided "
            "skills. Do not generate code or shell commands."
            + chr(10) + chr(10)
            + "Available named locations:"
            + chr(10)
            + location_lines
            + chr(10) + chr(10)
            + f"Workspace bounds: {bounds}."
            + chr(10)
            + "Use navigate_to for a single target pose and follow_waypoints "
            + "for an ordered list of targets. If the user explicitly asks "
            + "to stop, include a stop tool call after the movement tools."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request},
        ]

        if feedback is not None:
            feedback_text = (
                "The previous plan was executed but failed. Observed "
                "structured feedback:"
                + chr(10)
                + json.dumps(feedback.to_dict(), indent=2)
                + chr(10) + chr(10)
                + "Produce a new plan that still satisfies the original "
                + "request. Use only the provided tools. You may choose a "
                + "different valid named location or split the task into "
                + "navigate_to calls if that is more likely to succeed. If "
                + "the request cannot be satisfied safely, return an empty "
                + "tool call list."
            )
            messages.append({"role": "user", "content": feedback_text})

        return messages

    def plan(
        self, request: str, feedback: Optional[ExecutionFeedback] = None
    ) -> List[SkillCall]:
        if not self.api_key:
            return self._fallback.plan(request)

        try:
            from openai import OpenAI
        except ImportError:
            return self._fallback.plan(request)

        from .registry import get_llm_tools

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=self._build_messages(request, feedback),
                tools=get_llm_tools(),
                tool_choice="auto",
            )
        except Exception as exc:
            print(
                f"[LLMPlanner] API call failed: {exc}; "
                "falling back to MockPlanner."
            )
            return self._fallback.plan(request)

        message = response.choices[0].message
        if not message.tool_calls:
            # The LLM explicitly declined to plan (or returned no tool call).
            return []

        calls: List[SkillCall] = []
        try:
            for tool_call in message.tool_calls:
                arguments = json.loads(tool_call.function.arguments or "{}")
                calls.append(SkillCall(tool_call.function.name, arguments))
        except Exception as exc:
            print(
                f"[LLMPlanner] Failed to parse tool calls: {exc}; "
                "falling back to MockPlanner."
            )
            return self._fallback.plan(request)

        # Rule-based repair: if the user asked to stop and the LLM did not
  
        # Rule-based repair: if the user asked to stop and the LLM did not
        # include an explicit stop call, append one.
        if "stop" in request.lower() and not any(
            call.skill == "stop" for call in calls
        ):
            calls.append(SkillCall("stop", {}))
        return calls
