# RESULTS

This file reports each tested instruction, success/failure outcome, elapsed
time, number of skill calls, and recovery actions, as required by the assignment.

---

## 1. Environment / OpenGL verification

| Check | Result |
|---|---|
| WSL version | 2.7.14.0 |
| WSLg version | 1.0.73.2 |
| Ubuntu | 22.04.5 LTS |
| OpenGL renderer | `D3D12 (AMD Radeon RX 9070 XT)` |
| Hardware acceleration | `Accelerated: yes` |
| OpenGL version | 4.2 (Compatibility Profile) |
| `glxgears` | ~140 FPS (unsynced) |
| Webots R2025a | GUI launched successfully in WSLg |
| Extern controllers | `agent0`, `agent1`, `Ros2Supervisor` registered via IPC |

### 1.1 Optional Windows-native Webots mode

The final configuration runs Webots inside WSL2. A native Windows Webots mode
was also validated for comparison:

| Item | Value |
|---|---|
| Windows Webots | `D:/Webots/msys64/mingw64/bin/webots.exe` |
| World access from Windows | `wsl.localhost/Ubuntu-22.04/tmp/...` |
| WSL driver connection | TCP to Windows host (`172.26.224.1:1234`) |
| GUI result | Native Windows window, smooth rendering |

The WSL `webots_ros2_driver` was patched so `get_wsl_ip_address()` uses the
default-route gateway instead of the `/etc/resolv.conf` DNS proxy. Both
controllers then connected successfully and `navigate_to` reached the target
with a 0.049 m position error.

### 1.2 Final WSL/Linux Webots mode

The final default setup uses `/usr/local/webots` inside WSL2. The same ROS 2
skills, validator, recovery, and real LLM planner were re-tested in this mode:

| Test | Result |
|---|---|
| `navigate_to` to storage | success, position error 0.049 m, 23.3 s |
| real LLM multi-waypoint (storage -> workbench, stop) | success, last reached index 1, 24.6 s |

Logs: `logs/linux_llm_success.jsonl`, `logs/linux_llm_visit.jsonl`.

---

## 2. Skill-level tests

### 2.1 `navigate_to`

| Step | Command | Target | Result |
|---|---|---|---|
| 1 | `ros2 run robot_skills navigate_to --x 0.0 --y -0.9 --theta 0.0 --timeout 20` | `(0.0, -0.9, 0.0)` | success |

Measured result:

```json
{
  "success": true,
  "reason": "reached",
  "elapsed_time_s": 7.814,
  "position_error_m": 0.0492,
  "heading_error_rad": 0.000003
}
```

Final GPS: `x = -0.0487`, `y = -0.9070`.

### 2.2 `follow_waypoints`

| Step | Command | Waypoints | Result |
|---|---|---|---|
| 1 | `ros2 run robot_skills follow_waypoints --waypoints '[...]'` | `(0.0,-0.9,0.0)`, `(0.5,-0.5,0.0)` | success |

Measured result:

```json
{
  "success": true,
  "reason": "all_waypoints_reached",
  "elapsed_time_s": 11.302,
  "last_reached_index": 1,
  "total_waypoints": 2
}
```

Final GPS: `x = 0.4574`, `y = -0.5238`.

### 2.3 `follow_waypoints` partial failure

| Step | Waypoints | Timeout | Result |
|---|---|---|---|
| 1 | `(0.20,-0.8686)`, `(5.0,5.0)` | 4 s per waypoint | first waypoint reached, second timeout |

Measured result:

```json
{
  "success": false,
  "reason": "timeout",
  "elapsed_time_s": 5.286,
  "position_error_m": 6.315,
  "heading_error_rad": 0.081,
  "last_reached_index": 0,
  "total_waypoints": 2
}
```

This confirms the requirement to report the last reached waypoint on failure.

### 2.4 `stop()`

| Command | Result |
|---|---|
| `ros2 run robot_skills stop_skill` | `success: true`, `reason: stopped`, `elapsed_time_s: 0.511` |

### 2.5 Obstacle detection and recovery (Level 1)

The `navigate_to` skill checks `/scan` in a cone around the intended motion
direction. A close-range fake scan was used for deterministic testing.

| Scenario | First attempt | Recovery | Second attempt | Final outcome | Log |
|---|---|---|---|---|---|
| Obstacle disappears during recovery | `obstacle_blocked` | back up + rotate, retry once | `reached`, error 0.0497 m | success | `logs/obstacle_recovery_success.jsonl` |
| Obstacle remains | `obstacle_blocked` | back up + rotate, retry once | `obstacle_blocked` | fail, message "Target is blocked by an obstacle." | `logs/obstacle_blocked_failure.jsonl` |

### 2.6 Real cloud LLM tests

The optional LLM planner was tested with the OpenAI-compatible endpoint
`https://yinli.one/v1` and model `gpt-5.5`. The API key is stored only in the
gitignored `.env` file.

| Instruction | LLM plan | Outcome | Log |
|---|---|---|---|
| `Go to storage.` | `navigate_to(0.0, -0.9, 0.0)` | success, position error 0.0495 m | `logs/llm_success.jsonl` |
| `Visit storage, then workbench, and stop.` | `follow_waypoints([...]), stop()` | success, last reached index 1 | `logs/llm_visit.jsonl` |
| `Go to space_station.` | rejected before execution | `target_out_of_workspace` | `logs/llm_invalid_location.jsonl` |

The plain chat completion and tool-calling paths were also verified with
`scripts/test_llm_api.py`.

### 2.7 Map-based A* navigation with the generated Webots map

A new 200x200 occupancy map (0.02 m/cell, origin `[-2, -2]`) was built from
`/agent0/gps` + `/agent0/compass/bearing` + `/scan` using
`scripts/build_map.py`. The map is aligned with the current `break_room.wbt`
world.

| Mode | Instruction | Result | Elapsed | Log |
|---|---|---|---|---|
| Map (A*) | `Go to storage.` | `map_reached`, 1 path waypoint | 28.8 s | `logs/map_llm_success.jsonl` |
| Direct | `Go to workbench.` | `reached`, position error 0.0494 m | 20.3 s | `logs/direct_llm_success.jsonl` |

The LLM planner is the same in both modes; the skill layer chooses A* map
navigation or direct PID control.

---

## 3. Task-level agent tests

| ID | Instruction | Outcome | Skill calls | Elapsed | Recovery | Log |
|---|---|---|---:|---:|---|---|
| A1 | `Go to storage.` | success | 1 | 7.81 s | none | `logs/success_storage.jsonl` |
| A2 | `Visit storage, then workbench, and stop.` | success | 2 | 11.84 s | none | `logs/success_visit.jsonl` |
| A3 | `Go to space_station.` | rejected | 0 | — | abort + request valid location | `logs/failure_invalid_location.jsonl` |
| A4 | `Go to entrance and fly.` | rejected | 0 | — | abort + unknown skill | `logs/failure_unknown_skill.jsonl` |
| A5 | `Go to charging_station.` (forced 1 s timeout) | failed | 2 | 3.05 s | retry once, then stop + report | `logs/failure_timeout.jsonl` |

### A1: success log

```text
raw_plan:       navigate_to(0.0, -0.9, 0.0)
validation:     plan_valid
skill_result:   success=true, reason=reached, position_error_m=0.0492
final_outcome:  success=true, reason=all_skills_completed
```

### A2: multi-waypoint success log

```text
raw_plan:       follow_waypoints([(0.0,-0.9,0.0), (0.5,-0.5,0.0)]), stop()
validation:     plan_valid
skill_result:   success=true, reason=all_waypoints_reached, last_reached_index=1
skill_result:   stop: success=true
final_outcome:  success=true
```

### A3: invalid location log

```text
raw_plan:       navigate_to(999.0, 999.0, 0.0)
validation:     target_out_of_workspace
recovery:       abort, request a valid location
final_outcome:  success=false, reason=target_out_of_workspace
```

### A4: unknown skill log

```text
raw_plan:       fly_to(0.0, 0.0)
validation:     unknown_skill
recovery:       abort
final_outcome:  success=false, reason=unknown_skill
```

### A5: timeout + bounded retry log

```text
attempt 1:      navigate_to timeout, elapsed 1.51 s
recovery:       retry once
attempt 2:      navigate_to timeout, elapsed 1.54 s
recovery:       stop_and_report
final_outcome:  success=false, reason=timeout
```

---

## 4. Manual control and calibration

### 4.1 Reference keyboard / `cmd_vel` control

| Test | Command | Duration | Before | After | Observation |
|---|---|---:|---|---|---|
| Forward | `linear.x = 0.3` | ~4 s | GPS x = -0.495568 | GPS x = -0.482258 | Δx ≈ +0.0133 m |
| Forward speed | same | — | — | — | `/agent0/gps/speed` ≈ 0.06936 m/s |
| Backward | `linear.x = -0.3` | ~4 s | GPS x = -0.482258 | GPS x = -0.495584 | Δx ≈ -0.0133 m |
| Backward speed | same | — | — | — | `/agent0/gps/speed` ≈ 0.06942 m/s |
| Rotate | `angular.z = 1.0` | ~4 s | GPS y = -1.000016 | GPS y = -0.999080 | Δy ≈ +0.000936 m |

### 4.2 Controller calibration for the holonomic navigation

| Command | Observed motion | Approximate response |
|---|---|---|
| `linear.x = 1.0` | ~0.20 m in 2 s | ~0.10 m/s |
| `linear.y = 1.0` | ~0.22 m in 2 s | ~0.11 m/s |
| `angular.z = 5.0` | ~127° in 2 s | ~1.11 rad/s |

The reference `wheels_controller` uses `WHEEL_RADIUS = 0.26` while the URDF
wheel radius is `0.06`. The skill controller therefore uses closed-loop
feedback rather than open-loop timing.

---

## 5. Validation-layer coverage

| Layer | Test | Result |
|---|---|---|
| Allowlist | `fly_to` | rejected as `unknown_skill` |
| Schema / type | missing or wrong-typed arguments | rejected |
| Workspace bounds | `(999, 999)` | rejected as `target_out_of_workspace` |
| Step limit | plan longer than `max_steps` | rejected |
| Retry limit | forced timeout | retried once, then stopped |
| Arbitrary code | LLM output is never executed | enforced by design |

---

## 6. Reproducibility notes

- The reference simulation is launched with:

  ```bash
  ros2 launch webots_ros2_robomaster robot_launch.py
  ```

- Skill-level tests:

  ```bash
  ros2 run robot_skills navigate_to --x 0.0 --y -0.9 --theta 0.0 --timeout 20
  ros2 run robot_skills follow_waypoints --waypoints '[...]' --timeout-per-waypoint 20
  ros2 run robot_skills stop_skill
  ```

- Task-level tests:

  ```bash
  python3 -m agent.main "Go to storage." --log logs/success_storage.jsonl
  python3 -m agent.main "Visit storage, then workbench, and stop." --log logs/success_visit.jsonl
  python3 -m agent.main "Go to space_station." --log logs/failure_invalid_location.jsonl
  python3 -m agent.main "Go to entrance and fly." --log logs/failure_unknown_skill.jsonl
  python3 -m agent.main "Go to charging_station." --nav-timeout 1 --max-retries 1 --log logs/failure_timeout.jsonl
  ```

---

## 7. Known issues observed during testing

1. WSLg GUI input can become unresponsive if the WSLg `msrdc` process is stale;
   `wsl --shutdown` and restarting WSL fixes it.
2. WSL interop (`powershell.exe` from inside WSL) reported `Exec format error`
   in one session. This does not block native Linux Webots or ROS 2.
3. The Webots asset cache must contain the 4893 extracted asset files, otherwise
   world loading stalls on remote PROTO/texture downloads.
4. `rosdep update` timed out due to the Windows local proxy not being mirrored
   into WSL NAT mode; all required dependencies were installed manually.
5. The reference `wheels_controller` per-step logging was disabled for
   performance; this does not affect control behavior.

---

## 8. Log index

| File | Description |
|---|---|
| `logs/success_storage.jsonl` | `Go to storage.` success |
| `logs/success_visit.jsonl` | multi-waypoint success |
| `logs/failure_invalid_location.jsonl` | invalid location rejection |
| `logs/failure_unknown_skill.jsonl` | unknown skill rejection |
| `logs/failure_timeout.jsonl` | timeout, retry, stop and report |
| `logs/obstacle_recovery_success.jsonl` | obstacle blocked, back up + rotate, retry success |
| `logs/obstacle_blocked_failure.jsonl` | obstacle remains after retry, stop and report |
| `logs/llm_success.jsonl` | real LLM single-target success |
| `logs/llm_visit.jsonl` | real LLM multi-waypoint success |
| `logs/llm_invalid_location.jsonl` | real LLM invalid location rejection |
| `logs/linux_llm_success.jsonl` | real LLM single-target success in final WSL/Linux Webots mode |
| `logs/linux_llm_visit.jsonl` | real LLM multi-waypoint success in final WSL/Linux Webots mode |
| `logs/map_llm_success.jsonl` | A* map-mode navigation success |
| `logs/direct_llm_success.jsonl` | direct-mode LLM navigation success |

---

## 9. Redesigned closed-loop regression (2026-09-15)

After the agent was refactored into `TaskAgent` (Plan -> Validate -> Execute ->
Observe -> Recover), the full system was re-tested with the WSL/Linux Webots
simulation running. Logs are stored under `logs/regression_*.jsonl`.

| ID | Instruction | Planner / mode | Outcome | Skill calls | Recovery action | Log |
|---|---|---|---:|---|---:|---|
| R1 | `Go to storage.` | mock / direct | success, 18.58 s, error 0.0494 m | 1 | none | `logs/regression_mock_storage.jsonl` |
| R2 | `Visit storage, then workbench, and stop.` | mock / direct | success, 38.27 s total | 2 | none | `logs/regression_mock_visit.jsonl` |
| R3 | `Go to storage.` | mock / map (A*) | success, 17.73 s, `map_reached` | 1 | none | `logs/regression_map_storage.jsonl` |
| R4 | `Go to space_station.` | mock | rejected before execution | 0 | abort, `target_out_of_workspace` | `logs/regression_invalid_location.jsonl` |
| R5 | `Go to entrance and fly.` | mock | rejected before execution | 0 | abort, `unknown_skill` | `logs/regression_unknown_skill.jsonl` |
| R6 | `Go to charging_station.` | mock / direct, forced 1 s timeout | failed | 2 attempts | retry once, then stop_and_report | `logs/regression_timeout.jsonl` |
| R7 | `Go to storage.` + fake obstacle (disappears) | mock / direct | success after recovery, error 0.0500 m | 2 attempts | backup_and_retry, then retry success | `logs/regression_obstacle_recovery.jsonl` |
| R8 | `Go to storage.` + fake obstacle (remains) | mock / direct | failed | 2 attempts | backup_and_retry, then stop_and_report | `logs/regression_obstacle_blocked.jsonl` |
| R9 | `Go to storage.` | real LLM / direct | success, 16.43 s, error 0.0499 m | 1 | none | `logs/regression_llm_storage.jsonl` |
| R10 | `Visit storage, then workbench, and stop.` | real LLM / direct | success, 38.70 s total | 2 | none | `logs/regression_llm_visit.jsonl` |
| R11 | `Go to space_station.` | real LLM | rejected before execution | 0 | LLM returned empty plan; abort, `empty_plan` | `logs/regression_llm_invalid.jsonl` |
| R12 | `Go to charging_station.` | real LLM / direct, forced 1 s timeout | failed | 4 attempts | retry, then **replan with execution feedback**, then retry, stop_and_report | `logs/regression_llm_replan_timeout.jsonl` |

R12 is the key new result for the feedback loop. The log sequence is:

```text
raw_plan:       navigate_to(-0.5, 0.0)      (charging_station)
skill_result:   timeout
recovery_decision: retry
skill_result:   timeout
recovery_decision: replan
feedback_to_planner: structured ExecutionFeedback sent to LLM
replanned_plan: navigate_to(0.0, -0.9)      (storage, chosen by LLM)
validation:     plan_valid
skill_result:   timeout (still forced to 1 s)
recovery_decision: stop_and_report
final_outcome:  failed, reason=timeout
```

This demonstrates that the LLM receives the observed execution result and
produces a new task-level plan that is validated from scratch before any robot
motion. The loop remains bounded by `--max-replans`.

### 9.1 PID controller verification (2026-09-15)

After replacing the direct-mode controller with independent PID controllers
(x, y, and heading), the following tests were repeated with the WSL/Linux
Webots simulation:

| ID | Instruction | Planner / mode | Result | Log |
|---|---|---|---:|---|
| P1 | `Go to storage.` | mock / direct PID | success, 5.62 s, error 0.0482 m | `logs/regression_pid_storage.jsonl` |
| P2 | `Visit storage, then workbench, and stop.` | mock / direct PID | success, 10.42 s total | `logs/regression_pid_visit.jsonl` |

The PID gains are configurable ROS 2 parameters:
`k_v`, `k_i_v`, `k_d_v`, `k_theta`, `k_i_theta`, `k_d_theta`,
`integral_max_v`, `integral_max_theta`.

### 9.2 Fast-mode multi-waypoint test (2026-09-15)

Command:

```bash
python3 -m agent.main "Go to storage, then visit the charging, go back to storage, and stop." --planner llm --navigation-mode direct --log logs/llm_storage_charging_storage_fast.jsonl
```

Result: `success`, `follow_waypoints` reached all 3 waypoints (`last_reached_index=2`) plus `stop`.
The LLM plan was `follow_waypoints([storage, charging_station, storage])` followed by `stop`.

Webots was launched with `mode:=fast` via `scripts/start_robomaster_fast.ps1`.
In this WSL environment, `fast` mode reduces GUI overhead but the measured sim/wall
clock ratio was only about 0.6:1 during a 5 s idle window, so the current
bottleneck is the two-robot Webots simulation and ROS 2 driver/camera load,
not the GUI. A simpler single-robot world or disabling camera topics would
speed up future recordings.
