"""Machine-readable skill registry for LLM tool calling and validation."""
from __future__ import annotations

from typing import Any, Dict, List

from .locations import WORKSPACE_MAX_X, WORKSPACE_MAX_Y, WORKSPACE_MIN_X, WORKSPACE_MIN_Y

ALLOWED_SKILLS: List[str] = ["navigate_to", "follow_waypoints", "stop"]

_X_MIN = WORKSPACE_MIN_X
_X_MAX = WORKSPACE_MAX_X
_Y_MIN = WORKSPACE_MIN_Y
_Y_MAX = WORKSPACE_MAX_Y

_NAVIGATE_TO_PARAMETERS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "x": {"type": "number", "minimum": _X_MIN, "maximum": _X_MAX},
        "y": {"type": "number", "minimum": _Y_MIN, "maximum": _Y_MAX},
        "theta": {
            "type": "number",
            "minimum": -3.14159,
            "maximum": 3.14159,
            "default": 0.0,
        },
    },
    "required": ["x", "y"],
    "additionalProperties": False,
}

_FOLLOW_WAYPOINTS_PARAMETERS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "waypoints": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "x": {"type": "number", "minimum": _X_MIN, "maximum": _X_MAX},
                    "y": {"type": "number", "minimum": _Y_MIN, "maximum": _Y_MAX},
                    "theta": {
                        "type": "number",
                        "minimum": -3.14159,
                        "maximum": 3.14159,
                        "default": 0.0,
                    },
                },
                "required": ["x", "y"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["waypoints"],
    "additionalProperties": False,
}

_STOP_PARAMETERS: Dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

SKILL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "navigate_to": {
        "name": "navigate_to",
        "description": (
            "Move the mobile robot to a target pose (x, y, theta) in the configured "
            "laboratory workspace. Reports success only when position and heading "
            "tolerances are met, and stops safely on timeout."
        ),
        "parameters": _NAVIGATE_TO_PARAMETERS,
        "preconditions": ["robot_available", "not_estopped"],
        "success_condition": "position_error_m <= 0.10 and heading_error_rad <= 0.15",
        "timeout_s": 30.0,
        "result_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "reason": {"type": "string"},
                "elapsed_time_s": {"type": "number"},
                "position_error_m": {"type": "number"},
                "heading_error_rad": {"type": "number"},
            },
            "required": ["success", "reason", "elapsed_time_s"],
        },
    },
    "follow_waypoints": {
        "name": "follow_waypoints",
        "description": (
            "Visit a sequence of waypoints in order. If execution fails, report the "
            "index of the last reached waypoint."
        ),
        "parameters": _FOLLOW_WAYPOINTS_PARAMETERS,
        "preconditions": ["robot_available", "not_estopped"],
        "success_condition": "all waypoints reached",
        "timeout_s": 30.0,
        "result_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "reason": {"type": "string"},
                "elapsed_time_s": {"type": "number"},
                "last_reached_index": {"type": "integer"},
                "total_waypoints": {"type": "integer"},
            },
            "required": ["success", "reason", "elapsed_time_s"],
        },
    },
    "stop": {
        "name": "stop",
        "description": "Safely stop the robot by publishing zero velocity.",
        "parameters": _STOP_PARAMETERS,
        "preconditions": [],
        "success_condition": "zero velocity published",
        "timeout_s": 2.0,
        "result_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "reason": {"type": "string"},
                "elapsed_time_s": {"type": "number"},
            },
            "required": ["success", "reason", "elapsed_time_s"],
        },
    },
}


def get_llm_tools() -> List[Dict[str, Any]]:
    """Return an OpenAI-compatible tool list generated from the registry."""
    tools = []
    for name in ALLOWED_SKILLS:
        skill = SKILL_REGISTRY[name]
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": skill["name"],
                    "description": skill["description"],
                    "parameters": skill["parameters"],
                },
            }
        )
    return tools


def get_skill(name: str) -> Dict[str, Any]:
    return SKILL_REGISTRY[name]
