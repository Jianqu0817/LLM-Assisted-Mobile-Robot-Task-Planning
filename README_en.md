# LLM-Assisted Mobile Robot Task Planning

This repository implements the interview assignment *LLM-Assisted Mobile Robot
Task Planning* on top of Webots R2025a and ROS 2 Humble. A natural-language
request is converted into a small, validated sequence of high-level robot
skills. The large language model can only choose from a fixed allowlist; it
cannot issue velocity commands or execute generated code.

---

## 1. Overview

The system has four layers:

```text
Natural language request
        │
        ▼
Planner (mock or OpenAI-compatible LLM)
        │ raw plan
        ▼
Validator (allowlist, schema, workspace, step limit)
        │ validated calls
        ▼
Skill executor (navigate_to, follow_waypoints, stop)
        │ ROS 2 topics
        ▼
Webots + ROS 2 (RoboMaster agent0)
        │ structured result
        ▼
Recovery (retry / backup / bounded replan / stop)
        │
        └── ExecutionFeedback ──► Planner (replan)
        │
        ▼
JSONL logger
```

Implemented skills:

1. `navigate_to(x, y, theta)` — holonomic position control with final heading
   alignment, position/heading tolerances, and safe timeout.
2. `follow_waypoints(waypoints)` — visits a sequence of waypoints and reports
   the last reached waypoint index if execution fails.
3. `stop()` — publishes zero velocity and returns a structured result.

Every skill returns at least:

```json
{
  "success": true,
  "reason": "reached",
  "elapsed_time_s": 7.81,
  "position_error_m": 0.049,
  "heading_error_rad": 0.000003
}
```

---

## 2. Repository layout

```text
assignment/
├── README.md
├── RESULTS.md
├── .gitignore
├── agent/                       # task-level agent (Python, no Webots dependency)
│   ├── main.py                  # CLI entry point
│   ├── task_agent.py            # closed-loop Plan->Validate->Execute->Recover
│   ├── models.py                # SkillCall, SkillResult, ExecutionFeedback, ...
│   ├── registry.py              # machine-readable skill registry + JSON Schema
│   ├── validator.py             # allowlist / schema / workspace / step limit
│   ├── executor.py              # calls robot_skills
│   ├── planner.py               # MockPlanner and optional LLMPlanner
│   ├── recovery.py              # bounded recovery strategies
│   └── logger.py                # JSONL event logger
├── tests/
│   └── test_task_agent.py       # offline tests for the closed-loop agent
├── ros2_ws/src/robot_skills/    # ROS 2 Python package with the three skills
│   ├── package.xml
│   ├── setup.py
│   └── robot_skills/
│       ├── skills.py            # RobotSkills node and skill implementations
│       ├── navigate_to.py       # CLI wrapper
│       ├── follow_waypoints.py  # CLI wrapper
│       └── stop_skill.py        # CLI wrapper
├── docs/
│   ├── architecture.md          # architecture diagram and data flow
│   ├── environment.md           # WSL2 / Webots / ROS 2 setup notes
│   └── report_materials.md      # raw material for the technical report
└── logs/                        # example JSONL execution logs
    ├── success_storage.jsonl
    ├── success_visit.jsonl
    ├── failure_invalid_location.jsonl
    ├── failure_unknown_skill.jsonl
    └── failure_timeout.jsonl
```

---

## 3. Environment

The reference environment is:

| Component | Version |
|---|---|
| OS | Windows 11 Pro + WSL2 Ubuntu 22.04.5 |
| CPU | AMD Ryzen 7 7700 |
| GPU | AMD Radeon RX 9070 XT (16 GB) |
| RAM | 32 GB |
| Python | 3.10.12 (WSL), Python 3.10+ recommended |
| ROS 2 | Humble |
| Webots | R2025a (Linux `.deb`, installed inside WSL) |
| `webots_ros2` | 2025.0.0 |
| `webots_ros2_robomaster` | 2025.0.0 |

A detailed setup record, including the WSLg OpenGL verification and the
Linux-Webots WSL patch, is in `docs/environment.md`.

### 3.1 Environment prerequisites

The following are required for reproducibility:

- WSL2 with WSLg enabled (`guiApplications=true` in `.wslconfig`).
- ROS 2 Humble Desktop.
- Webots R2025a installed inside WSL2 at `/usr/local/webots` (default). A native Windows Webots mode is also supported for comparison; see `docs/environment.md`.
- `webots_ros2` 2025.0.0 (apt or source).
- The reference `webots_ros2_robomaster` package, including its `protos/meshes`
  assets and the Webots asset cache described in `docs/environment.md`.

### 3.2 Build the skill package

```bash
source /opt/ros/humble/setup.bash
cd ~/ros2_ws
colcon build --symlink-install --packages-select robot_skills
source install/setup.bash
```

Verify:

```bash
ros2 pkg executables robot_skills
# robot_skills follow_waypoints
# robot_skills navigate_to
# robot_skills stop_skill
```

### 3.3 Optional Windows-native Webots mode

The default setup runs Webots inside WSL2. If you want smoother GUI rendering,
you can optionally install Webots natively on Windows. This mode is documented
for comparison; the assignment results are valid in either mode.

On Windows (PowerShell):

```powershell
# Optional: use the local proxy for the download
powershell -ExecutionPolicy Bypass -File scripts/setup_windows_webots.ps1 -Proxy http://127.0.0.1:7890
```

In WSL:

```bash
# Apply the two driver patches (idempotent; run as root)
sudo python3 scripts/patch_webots_ros2_driver.py

# Start the simulation
bash scripts/start_robomaster.sh

# Stop the simulation (also stops Windows Webots)
bash scripts/stop_robomaster.sh
```

The driver launches `D:/Webots/msys64/mingw64/bin/webots.exe` through WSL
interop and connects to it over TCP port 1234.

### 3.4 Reference package and WSL setup

#### WSL configuration

```powershell
wsl --install -d Ubuntu-22.04
```

Create or edit `C:/Users/<your-name>/.wslconfig`:

```ini
[wsl2]
guiApplications=true
```

Restart WSL:

```powershell
wsl --shutdown
```

Verify WSLg:

```bash
echo $DISPLAY
glxinfo -B | head -20
```

#### Install ROS 2 Humble

```bash
# Add the ROS 2 apt repository
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository universe
sudo apt update

# Install ROS 2 Humble Desktop
sudo apt install -y ros-humble-desktop

# Install colcon and rosdep
sudo apt install -y python3-colcon-common-extensions python3-rosdep2
sudo rosdep init
rosdep update
```

Add ROS 2 to `.bashrc`:

```bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
```

#### Webots and webots_ros2

1. Download the Webots R2025a Linux `.deb` from the Cyberbotics website.
2. Install it inside WSL:

   ```bash
   sudo dpkg -i webots-R2025a.deb
   sudo apt --fix-broken install -y
   ```

3. Install `webots_ros2`:

   ```bash
   sudo apt update
   sudo apt install -y ros-humble-webots-ros2
   ```

#### Reference package webots_ros2_robomaster

```bash
cd ~
git clone https://github.com/MohismLab/webots_ros2_robomaster.git
cd webots_ros2_robomaster

# Download protos/meshes assets (Google Drive folder)
gdown --folder 126Wyz2xYeYT01z5ilD1YH_fYc0rHBA_M
```

#### Webots asset cache

```bash
mkdir -p ~/.cache/Cyberbotics/Webots/assets
unzip assets-R2025a.zip -d ~/.cache/Cyberbotics/Webots/assets
```

See `docs/environment.md` for details.

---
---

## 4. Running the simulation

> **Default mode:** Webots R2025a runs inside WSL2 at `/usr/local/webots` and
> is displayed through WSLg. `WEBOTS_HOME=/usr/local/webots` is set by the
> environment file. The optional native Windows Webots mode is described in
> section 3.3.

Terminal A (interactive WSL terminal):

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
export WEBOTS_HOME=/usr/local/webots
unset TMPDIR

ros2 launch webots_ros2_robomaster robot_launch.py
```

Wait until the controllers connect:

```text
[agent0]: Controller successfully connected to robot in Webots simulation.
[agent1]: Controller successfully connected to robot in Webots simulation.
```

Useful topics:

```text
/agent0/cmd_vel       geometry_msgs/msg/Twist
/agent0/gps           geometry_msgs/msg/PointStamped
/agent0/compass/bearing webots_ros2_msgs/msg/FloatStamped
/scan                 sensor_msgs/msg/LaserScan
/imu                  sensor_msgs/msg/Imu
```

Manual keyboard teleoperation (optional):

```bash
# Reference script from webots_ros2_robomaster
cd ~/webots_ros2_robomaster/webots_ros2_robomaster
python3 keyboard_twist.py --topic /agent0/cmd_vel
```

or the smoother ROS 2 teleop:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -r cmd_vel:=/agent0/cmd_vel
```

---

## 5. Running the task-level agent

The agent can be run with the deterministic mock planner (no API key needed) or
with an OpenAI-compatible planner.

```bash
cd ~/assignment          # repository root
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash

# Success case
python3 -m agent.main "Go to storage." \
  --log logs/success_storage.jsonl

# Multi-waypoint case
python3 -m agent.main "Visit storage, then workbench, and stop." \
  --log logs/success_visit.jsonl

# Invalid location
python3 -m agent.main "Go to space_station." \
  --log logs/failure_invalid_location.jsonl

# Unknown skill
python3 -m agent.main "Go to entrance and fly." \
  --log logs/failure_unknown_skill.jsonl

# Timeout + bounded retry (testing helper)
python3 -m agent.main "Go to charging_station." \
  --nav-timeout 1 --max-retries 1 \
  --log logs/failure_timeout.jsonl

# Timeout + one bounded LLM replan (only when --planner llm)
python3 -m agent.main "Go to charging_station." --planner llm \
  --nav-timeout 1 --max-retries 1 --max-replans 1 \
  --log logs/llm_replan_timeout.jsonl
```

The final outcome is printed as JSON, and every intermediate step is written to
the JSONL log:

```text
raw_plan
validation
skill_result
recovery_decision
skill_result
recovery_decision
feedback_to_planner    (only when a bounded LLM replan is used)
replanned_plan
validation
skill_result
final_outcome
```

### 5.1 Optional real LLM planner

Copy `.env.example` to `.env` and fill in your key:

```bash
cp .env.example .env
# then edit .env:
#   OPENAI_BASE_URL=https://yinli.one/v1
#   OPENAI_API_KEY=<your-key>
#   OPENAI_MODEL=gpt-5.5
```

The `.env` file is gitignored and must never be committed.

Test the API directly:

```bash
python3 scripts/test_llm_api.py
```

Run the task agent with the real LLM planner:

```bash
python3 -m agent.main "Go to storage." --planner llm --log logs/llm_success.jsonl
```

If no key is configured, or the API call fails, `LLMPlanner` prints a warning
and falls back to `MockPlanner`, so the rest of the system remains testable.

When `--planner llm` is used and a navigation skill fails after its retry
budget, the agent sends the structured execution result back to the LLM and
asks for a new plan. The new plan is validated from scratch and the number of
replans is bounded by `--max-replans` (default 1). The mock planner does not
consume feedback; it uses rule-based retry / backup / stop-and-report only.

---

## 6. Map-based A* navigation (optional)

### 6.1 Recommended: precise Supervisor map generation

This method uses the Webots Supervisor API to read the true position, size and
rotation of every scene object, producing the map that best matches the
simulated world.

```bash
# Step 1: export scene objects (starts a dedicated Webots instance briefly)
bash scripts/run_supervisor_export.sh

# Step 2: build the occupancy grid from the exported objects
python3 scripts/build_map_from_supervisor.py
```

Outputs:

```text
maps/supervisor_objects.json
maps/break_room_supervisor_map.pgm
maps/break_room_supervisor_map.yaml
```

The default map is `maps/break_room_supervisor_map.pgm`.

![Current default map](maps/break_room_supervisor_map.png)

Current named locations:

| Name | x | y |
|---|---|---|
| entrance | 0.0 | 3.0 |
| storage | -2.152373937677039 | -1.363206790893182 |
| workbench | 4.8 | 0.0 |
| charging_station | -2.17 | 1.95 |

Workspace bounds: `x ∈ [-7.0, 7.0]`, `y ∈ [-4.0, 7.0]`.

Current motion and safety parameters:

| Parameter | Value | Meaning |
|---|---|---|
| `v_max` | 2.25 | maximum linear speed (m/s) |
| `omega_max` | 6.0 | maximum angular speed (rad/s) |
| `obstacle_stop_distance` | 0.15 | front danger stop distance (m) |
| `wall_clearance_threshold` | 0.30 | side wall safety threshold (m) |
| `min_gap_width_m` | 0.45 | minimum passable gap width (m) |
| `gap_check_distance_m` | 1.5 | gap detection range (m) |
| `min_traversable_clearance_px` | 0.15 m | A* minimum obstacle clearance |

### 6.2 Optional: laser-scan mapping

A 2D occupancy map can be built from the current Webots world using
ground-truth GPS, compass bearing, and `/scan`:

```bash
python3 scripts/build_map.py --output maps/break_room_map --duration 240
```

This produces:

```text
maps/break_room_map.pgm
maps/break_room_map.yaml
```

`navigate_to` then supports two modes:

| Mode | How to run | Behavior |
|---|---|---|
| Direct | `--navigation-mode direct` | LLM plan, then direct PID control |
| Map | `--navigation-mode map` | LLM plan, then A* on the map, then direct control follows the path |

Examples:

```bash
python3 -m agent.main "Go to storage." --planner llm --navigation-mode map
python3 -m agent.main "Go to workbench." --planner llm --navigation-mode direct
```

The LLM planner is unchanged at the task level: it still only selects
`navigate_to`, `follow_waypoints`, and `stop`. The map is used inside the
skill layer. Unknown and occupied cells are treated as non-traversable; if A*
cannot find a path, the skill falls back to direct PID control, so pure
LLM/direct navigation remains available.

The A* planner now:

- penalizes cells close to walls, so paths prefer the center of corridors;
- treats cells closer than `0.15 m` to an obstacle as non-traversable, so
  narrow gaps are avoided;
- requires the same minimum clearance when simplifying straight-line paths.

If the repository is cloned to a different path, point the skill at the map:

```bash
export ROBOT_MAP_PATH=/path/to/assignment/maps/break_room_supervisor_map.pgm
```

or pass `--map-path /path/to/break_room_supervisor_map.pgm` to the skill CLI.

### 6.3 Skill-level flags

```bash
ros2 run robot_skills navigate_to --map --x 0.0 --y -0.9 --theta 0.0 --timeout 60
ros2 run robot_skills navigate_to --no-map --x 0.5 --y -0.5 --theta 0.0 --timeout 60
```

## 6. Obstacle safety (Level 1)

`navigate_to` subscribes to `/scan` and performs several safety checks:

1. **Front danger detection**: if the nearest valid range in the motion cone
   is below `obstacle_stop_distance` (default 0.15 m), the skill stops.
2. **Narrow gap detection**: if the free gap in front is smaller than
   `min_gap_width_m` (default 0.45 m), the skill stops instead of squeezing in.
3. **Side wall repulsion**: if the left or right clearance is below
   `wall_clearance_threshold` (default 0.30 m), the robot steers away and
   slows down.
4. **Narrow-channel speed scaling**: the tighter the side clearances, the
   slower the robot moves, down to 25% of its commanded speed.

When stopped, the task-level agent performs a bounded recovery:

1. Back up for 0.6 s.
2. Rotate in place for 0.6 s.
3. Retry navigation once.
4. If the retry is also blocked, stop and report `Target is blocked by an obstacle.`

The fake laser scan test utility is in `scripts/fake_scan.py`; it publishes a
close-range `LaserScan` on `/scan` for testing without changing the world file.

## 6. Skill-level CLI

The three skills can also be tested directly:

```bash
ros2 run robot_skills navigate_to --x 0.0 --y -0.9 --theta 0.0 --timeout 20

ros2 run robot_skills follow_waypoints \
  --waypoints '[{"x":0.0,"y":-0.9,"theta":0.0},{"x":0.5,"y":-0.5,"theta":0.0}]' \
  --timeout-per-waypoint 20

ros2 run robot_skills stop_skill
```

---

## 7. Validation and safety

The validator implements six layers:

1. Plan length and maximum step count.
2. Fixed allowlist: only `navigate_to`, `follow_waypoints`, `stop`.
3. JSON Schema type, required-field, and range checks.
4. Workspace bounds: `x, y ∈ [-1.5, 1.5]`.
5. Skill-specific preconditions.
6. Retry limit (`max_retries=1` by default).

The LLM never receives permission to generate Python, shell, or ROS commands.
The executor maps only the three allowlisted skill names to Python methods.

### 7.1 Bounded recovery

| Failure | Recovery |
|---|---|
| Unknown skill | Reject plan, abort, report |
| Missing / wrong-typed argument | Reject plan, abort, report |
| Target outside workspace | Reject plan, ask for a valid location |
| Navigation timeout | Retry once; if it fails again, stop and report |
| Plan too long | Reject plan, abort, report |

---

## 8. Results

See `RESULTS.md` for the full test table. Summary:

| Test | Result |
|---|---|
| `Go to storage.` | success, position error 0.049 m, 7.81 s |
| `Visit storage, then workbench, and stop.` | success, last reached index 1, 11.30 s |
| `Go to space_station.` | rejected: target outside workspace |
| `Go to entrance and fly.` | rejected: unknown skill |
| Forced navigation timeout | retried once, then stopped and reported |

Example logs are in `logs/`.

---

## 9. Known limitations

- The default configuration runs Webots inside WSL2 through WSLg. It has
  some D3D12 translation and software Xwayland compositing overhead, so it is
  less responsive than the optional native Windows Webots mode, but it is
  sufficient for the assignment.
- The reference `wheels_controller` uses `WHEEL_RADIUS = 0.26` while the URDF
  wheel radius is `0.06`; the skill controller compensates with feedback.
- There is no `/agent0/odom` topic in the reference setup; position comes from
  `/agent0/gps` and heading from `/agent0/compass/bearing`.
- `rosdep update` can time out because the Windows local proxy is not mirrored
  into WSL NAT mode. The required dependencies are installed via apt.
- The WSL driver patch for native Linux Webots may be overwritten by an apt
  upgrade of `ros-humble-webots-ros2-driver`.

---

## 10. References

1. ROS 2 Humble — https://docs.ros.org/en/humble/
2. Webots R2025a — https://cyberbotics.com/
3. `webots_ros2` — https://github.com/cyberbotics/webots_ros2
4. `webots_ros2_robomaster` — https://github.com/MohismLab/webots_ros2_robomaster
5. WSLg — https://github.com/microsoft/wslg
6. Mesa D3D12 — https://docs.mesa3d.org/drivers/d3d12.html
7. OpenAI-compatible function calling — https://platform.openai.com/docs/guides/function-calling
