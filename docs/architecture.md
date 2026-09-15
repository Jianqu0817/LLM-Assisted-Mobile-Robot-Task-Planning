# System Architecture

## 1. High-level data flow

```mermaid
flowchart TD
    U[Natural language request] --> P[Planner<br/>Mock or LLM]
    P -->|raw plan: SkillCall[]| V[Validator]
    V -->|validated plan| E[Skill Executor]
    V -->|rejected| R[Recovery Manager]
    E -->|navigate_to / follow_waypoints / stop| S[RobotSkills ROS 2 node]
    S -->|/agent0/cmd_vel| W[Webots RoboMaster]
    W -->|/agent0/gps, /agent0/compass/bearing, /scan| S
    S -->|SkillResult| E
    E -->|success| E2[Next call / done]
    E -->|failure| R
    R -->|retry / backup_and_retry| E
    R -->|replan| F[ExecutionFeedback]
    F --> P
    R -->|stop_and_report / abort| L[Final outcome]
    P --> L
    V --> L
    E --> L
    R --> L
    F --> L
    L[JSONL Logger]
```

## 2. ASCII fallback

```text
Natural Language
      │
      ▼
┌───────────────┐
│ Planner       │  MockPlanner / LLMPlanner
│ plan(req, fb) │  task-level only, no raw sensors
└──────┬────────┘
       │ raw plan (SkillCall[])
       ▼
┌───────────────┐
│ Validator     │
│ 1 allowlist   │
│ 2 JSON schema │
│ 3 workspace   │
│ 4 step limit  │
└──────┬────────┘
       │ validated plan
       ▼
┌───────────────┐
│ SkillExecutor │
└──────┬────────┘
       │ RobotSkills methods
       ▼
┌───────────────┐
│ RobotSkills   │  ROS 2 node
│ navigate_to   │
│ follow_waypoints│
│ stop          │
└──────┬────────┘
       │ /agent0/cmd_vel
       ▼
┌───────────────┐
│ Webots + ROS2 │
│ RoboMaster    │
└──────┬────────┘
       │ /agent0/gps, /agent0/compass/bearing, /scan
       ▼
┌──────────────────────────────┐
│ Observe: structured result   │
│ success / reason / elapsed   │
└──────┬───────────────────────┘
       │
       ├── success ──────────────► next call or done
       │
       └── failure ──────────────► Recovery Manager
                                     │
                                     ├─ retry (timeout)
                                     ├─ backup_and_retry (obstacle)
                                     ├─ replan with ExecutionFeedback (LLM, bounded)
                                     └─ stop_and_report / abort
```

The dashed feedback edge from the Recovery Manager back to the Planner is the
**execution feedback** channel. It is used only when the planner supports it
(`supports_feedback=True`, i.e. `LLMPlanner` with an API key). The mock planner
deliberately does not consume feedback and relies on rule-based recovery only.

## 3. Module responsibilities

| Module | Responsibility | Key output |
|---|---|---|
| `agent/task_agent.py` | Owns the closed loop: plan, validate, execute, observe, recover | final outcome |
| `agent/planner.py` | Convert text to skill calls; optionally replan from feedback | `SkillCall[]` |
| `agent/registry.py` | Machine-readable skill definitions | JSON Schema / LLM tools |
| `agent/validator.py` | Allowlist, schema, workspace, step limit | `ValidationResult` |
| `agent/executor.py` | Call `RobotSkills` methods through a fixed dispatch table | `SkillResult` |
| `agent/recovery.py` | Bounded recovery decisions: retry / backup / replan / stop | action + message |
| `agent/models.py` | `SkillCall`, `SkillResult`, `ValidationResult`, `ExecutionFeedback` | typed data |
| `agent/logger.py` | Append-only JSONL event log | log records |
| `robot_skills/skills.py` | ROS 2 implementation of the three skills | structured results |
| `robot_skills/navigate_to.py` | CLI for `navigate_to` | JSON result |
| `robot_skills/follow_waypoints.py` | CLI for `follow_waypoints` | JSON result |
| `robot_skills/stop_skill.py` | CLI for `stop` | JSON result |

## 4. Skill interface

Each skill defines:

- `name` and `description`
- typed parameters and valid ranges (JSON Schema)
- preconditions
- success condition and timeout
- structured result with `success`, `reason`, `elapsed_time_s`

The registry is the single source of truth. The same registry generates the
OpenAI-compatible tool list and drives validator schema checks.

## 5. Actuation and feedback

| Signal | Topic | Type |
|---|---|---|
| Velocity command | `/agent0/cmd_vel` | `geometry_msgs/msg/Twist` |
| Position feedback | `/agent0/gps` | `geometry_msgs/msg/PointStamped` |
| Heading feedback | `/agent0/compass/bearing` | `webots_ros2_msgs/msg/FloatStamped` |
| Laser scan | `/scan` | `sensor_msgs/msg/LaserScan` |
| IMU | `/imu` | `sensor_msgs/msg/Imu` |

Heading conversion:

```text
yaw = normalize_angle(-radians(bearing_degrees))
```

because the Webots compass bearing is clockwise-positive while ROS yaw is
counter-clockwise-positive.

## 6. Control loop

`navigate_to` uses independent PID controllers for the world-frame x/y errors and the final heading:

```text
ex = x_target - x
ey = y_target - y
vx_world = clamp(k_v*ex + k_i_v*integral_x + k_d_v*derivative_x, -v_max, v_max)
vy_world = clamp(k_v*ey + k_i_v*integral_y + k_d_v*derivative_y, -v_max, v_max)

vx_body =  cos(yaw) * vx_world + sin(yaw) * vy_world
vy_body = -sin(yaw) * vx_world + cos(yaw) * vy_world

if position error > tolerance:
    command (vx_body, vy_body, 0)
else:
    command (0, 0, clamp(k_theta*e_theta + k_i_theta*integral_theta + k_d_theta*derivative_theta, -omega_max, omega_max))
```

Success condition:

```text
position_error_m <= 0.05
and heading_error_rad <= 0.10
```

Timeout behavior:

```text
on timeout: publish zero velocity, return success=false, reason="timeout"
```

## 7. Validation layers

```text
Layer 1: plan length / max steps
Layer 2: fixed allowlist
Layer 3: JSON Schema (types, required fields, ranges)
Layer 4: workspace bounds x,y in [-1.5, 1.5]
Layer 5: preconditions
Layer 6: retry / replan limits
```

## 8. Execution feedback and bounded replan

After a skill fails, the Recovery Manager chooses one bounded action:

| Failure | First response | After budget exhausted |
|---|---|---|
| `timeout` | retry same call once | replan once with feedback, then stop_and_report |
| `obstacle_blocked` | back up, rotate, retry once | replan once with feedback, then stop_and_report |
| other | stop_and_report | stop_and_report |

When `replan` is selected, `TaskAgent` builds an `ExecutionFeedback` containing
only task-level information:

```json
{
  "request": "Go to storage.",
  "failed_call": {"skill": "navigate_to", "arguments": {"x": 0.0, "y": -0.9}},
  "result": {"success": false, "reason": "timeout", "elapsed_time_s": 31.2},
  "attempt": 1,
  "message": "Skill navigate_to timed out ...",
  "completed_calls": []
}
```

The planner is called again with this feedback. The new plan is validated from
scratch before any robot motion. If the planner returns the same plan, the
agent stops safely instead of looping.

## 9. Logging schema

Each JSONL record contains at least:

```json
{
  "timestamp": 1789386896.945,
  "event": "skill_result",
  "call": {"skill": "navigate_to", "arguments": {...}},
  "result": {"success": true, "reason": "reached", "elapsed_time_s": 7.81}
}
```

Event sequence for a successful task:

```text
raw_plan -> validation -> skill_result -> final_outcome
```

Event sequence when execution feedback is used:

```text
raw_plan -> validation
          -> skill_result -> recovery_decision (retry)
          -> skill_result -> recovery_decision (replan)
          -> feedback_to_planner -> replanned_plan
          -> validation -> skill_result
          -> final_outcome
```

## 10. Obstacle safety layer (Level 1)

`navigate_to` subscribes to `/scan` and computes the minimum valid range inside a
cone around the intended body-frame motion direction:

```text
motion_direction = atan2(vy_body, vx_body)
blocked = min_range_in_cone(motion_direction, 30 deg) < 0.35 m
```

If blocked:

```text
stop()
return SkillResult(success=False, reason="obstacle_blocked", ...)
```

The task-level recovery then executes `RobotSkills.recover_from_obstacle()`:

```text
back up 0.6 s
rotate 0.6 s
stop 0.3 s
retry navigate_to once
```

If the retry is blocked again and a feedback-aware planner is available, the
agent sends the observed result back to the planner for one bounded replan.
Otherwise it stops and reports the target as blocked.

## 11. Map-based A* navigation

A 2D occupancy grid is built from the Webots world using ground-truth pose and
`/scan`:

```text
/agent0/gps + /agent0/compass/bearing + /scan
        ↓
scripts/build_map.py
        
- if no path is found, the skill falls back to direct PID control

The LLM planner is unchanged; it still only selects `navigate_to`,
`follow_waypoints`, and `stop`.
