# LLM 辅助移动机器人任务规划

本仓库实现了面试作业 *LLM-Assisted Mobile Robot Task Planning*，
基于 Webots R2025a 与 ROS 2 Humble。系统将自然语言请求转换为一组少量、经过验证的高层机器人技能调用。
大语言模型只能从固定白名单中选择技能，不能直接发布速度指令，也不能执行生成的代码。

---

## 1. 环境配置与 Setup
参考环境：

| 组件 | 版本 |
|---|---|
| 操作系统 | Windows 11 Pro + WSL2 Ubuntu 22.04.5 |
| CPU | AMD Ryzen 7 7700 |
| GPU | AMD Radeon RX 9070 XT (16 GB) |
| 内存 | 32 GB |
| ROS 2 | Humble |
| Webots | R2025a（Linux `.deb`，安装在 WSL 内） |
| `webots_ros2` | 2025.0.0 |
| `webots_ros2_robomaster` | 2025.0.0 |

详细安装记录（包括 WSLg OpenGL 验证和 Linux-Webots WSL 补丁）见 `docs/environment.md`。

### 3.1 环境前置条件

复现本项目需要：

- 启用 WSLg 的 WSL2（`.wslconfig` 中 `guiApplications=true`）。
- ROS 2 Humble Desktop。
- Webots R2025a 安装在 WSL2 内，默认路径 `/usr/local/webots`。也支持 Windows 原生 Webots 模式作为对比，见 `docs/environment.md`。
- `webots_ros2` 2025.0.0（apt 或源码安装）。
- 参考包 `webots_ros2_robomaster`，包括其 `protos/meshes` 资源与 Webots 资源缓存。

### 3.2 编译技能包

```bash
source /opt/ros/humble/setup.bash
cd ~/ros2_ws
colcon build --symlink-install --packages-select robot_skills
source install/setup.bash
```

验证：

```bash
ros2 pkg executables robot_skills
```

应看到：

```text
robot_skills follow_waypoints
robot_skills navigate_to
robot_skills stop_skill
```

### 3.3 可选的 Windows 原生 Webots 模式

默认模式在 WSL2 内运行 Webots。如果你想要更流畅的 GUI 渲染，可以在 Windows 上原生安装 Webots 作为对比。

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_windows_webots.ps1 -Proxy http://127.0.0.1:7890
```

WSL 内：

```bash
# 应用两个驱动补丁（幂等，需要 root）
sudo python3 scripts/patch_webots_ros2_driver.py

# 启动仿真
bash scripts/start_robomaster.sh

# 停止仿真（同时停止 Windows Webots）
bash scripts/stop_robomaster.sh
```

驱动通过 WSL interop 启动 `D:/Webots/msys64/mingw64/bin/webots.exe`，并通过 TCP 端口 1234 连接。

---

---

## 2. 启动仿真
> **默认模式：** Webots R2025a 在 WSL2 内运行，路径 `/usr/local/webots`，通过 WSLg 显示。
> 环境文件会设置 `WEBOTS_HOME=/usr/local/webots`。可选 Windows 原生模式见 3.3 节。

交互式 WSL 终端：

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
export WEBOTS_HOME=/usr/local/webots
unset TMPDIR

ros2 launch webots_ros2_robomaster robot_launch.py
```

等待控制器连接：

```text
[agent0]: Controller successfully connected to robot in Webots simulation.
[agent1]: Controller successfully connected to robot in Webots simulation.
```

常用话题：

```text
/agent0/cmd_vel         geometry_msgs/msg/Twist
/agent0/gps             geometry_msgs/msg/PointStamped
/agent0/compass/bearing webots_ros2_msgs/msg/FloatStamped
/scan                   sensor_msgs/msg/LaserScan
/imu                    sensor_msgs/msg/Imu
```

---

## 3. 键盘操作
手动键盘遥控（可选）：

```bash
# 使用仓库自带键盘脚本
python3 scripts/keyboard_twist.py --topic /agent0/cmd_vel
```

或 ROS 2 标准键盘遥控：

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r cmd_vel:=/agent0/cmd_vel
```

---

---

## 4. 运行任务级代理（LLM）
代理可以使用确定性的 mock 规划器（无需 API key），也可以使用 OpenAI 兼容规划器。

```bash
cd /mnt/d/DS_workspace/Liqingbiao/assignment
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash

# 成功用例
python3 -m agent.main "Go to storage." --log logs/success_storage.jsonl

# 多航点用例
python3 -m agent.main "Visit storage, then workbench, and stop." --log logs/success_visit.jsonl

# 非法地点
python3 -m agent.main "Go to space_station." --log logs/failure_invalid_location.jsonl

# 未知技能
python3 -m agent.main "Go to entrance and fly." --log logs/failure_unknown_skill.jsonl

# 超时 + 有界重试（测试辅助）
python3 -m agent.main "Go to charging_station." --nav-timeout 1 --max-retries 1 --log logs/failure_timeout.jsonl

# 超时 + 一次有界 LLM 重规划（仅当 --planner llm）
python3 -m agent.main "Go to charging_station." --planner llm --nav-timeout 1 --max-retries 1 --max-replans 1 --log logs/llm_replan_timeout.jsonl
```

最终结果以 JSON 打印，所有中间步骤写入 JSONL 日志：

```text
raw_plan
validation
skill_result
recovery_decision
skill_result
recovery_decision
feedback_to_planner    （仅当使用有界 LLM 重规划时）
replanned_plan
validation
skill_result
final_outcome
```

### 5.1 可选真实 LLM 规划器

复制 `.env.example` 为 `.env` 并填入 key：

```bash
cp .env.example .env
```

`.env` 内容：

```text
OPENAI_BASE_URL=https://yinli.one/v1
OPENAI_API_KEY=<your-key>
OPENAI_MODEL=gpt-5.5
```

`.env` 已被 gitignore，绝不能提交。

直接测试 API：

```bash
python3 scripts/test_llm_api.py
```

使用真实 LLM 规划器运行任务代理：

```bash
python3 -m agent.main "Go to storage." --planner llm --log logs/llm_success.jsonl
```

如果没有配置 key，或者 API 调用失败，`LLMPlanner` 会打印警告并回退到 `MockPlanner`，因此系统其余部分仍可测试。

当使用 `--planner llm` 且导航技能在重试预算耗尽后仍然失败时，代理会把结构化执行结果发回 LLM，请求新计划。新计划会重新验证，重规划次数由 `--max-replans` 限制（默认 1）。Mock 规划器不消费反馈，只使用规则式重试 / 后退避障 / 停止上报。

---

---

## 5. 系统概览
系统包含四层：

```text
自然语言请求
        │
        ▼
规划器 Planner（mock 或 OpenAI 兼容 LLM）
        │ 原始计划 raw plan
        ▼
验证器 Validator（白名单、Schema、工作空间、步数限制）
        │ 通过验证的调用
        ▼
技能执行器 Skill Executor（navigate_to, follow_waypoints, stop）
        │ ROS 2 话题
        ▼
Webots + ROS 2（RoboMaster agent0）
        │ 结构化结果
        ▼
恢复 Recovery（重试 / 后退避障 / 有界重规划 / 停止）
        │
        └── ExecutionFeedback ──► Planner（重新规划）
        │
        ▼
JSONL 日志
```

已实现的技能：

1. `navigate_to(x, y, theta)` — 全向位置控制 + 最终航向对齐，带位置/航向容差与安全超时。
2. `follow_waypoints(waypoints)` — 依次访问一组航点，失败时报告最后到达的航点下标。
3. `stop()` — 发布零速度，并返回结构化结果。

每个技能至少返回：

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

---

## 6. 仓库结构
```text
assignment/
├── README.md
├── RESULTS.md
├── .gitignore
├── agent/                       # 任务级代理（纯 Python，不依赖 Webots）
│   ├── main.py                  # CLI 入口
│   ├── task_agent.py            # Plan->Validate->Execute->Recover 闭环
│   ├── models.py                # SkillCall, SkillResult, ExecutionFeedback 等
│   ├── registry.py              # 机器可读技能注册表 + JSON Schema
│   ├── validator.py             # 白名单 / Schema / 工作空间 / 步数限制
│   ├── executor.py              # 调用 robot_skills
│   ├── planner.py               # MockPlanner 和可选 LLMPlanner
│   ├── recovery.py              # 有界恢复策略
│   └── logger.py                # JSONL 事件日志
├── tests/
│   └── test_task_agent.py       # 闭环代理离线测试
├── ros2_ws/src/robot_skills/    # ROS 2 Python 技能包
│   ├── package.xml
│   ├── setup.py
│   └── robot_skills/
│       ├── skills.py            # RobotSkills 节点与技能实现
│       ├── navigate_to.py       # CLI 封装
│       ├── follow_waypoints.py  # CLI 封装
│       └── stop_skill.py        # CLI 封装
├── docs/
│   ├── architecture.md          # 架构图与数据流
│   ├── environment.md           # WSL2 / Webots / ROS 2 环境配置说明
│   └── report_materials.md      # 技术报告原始材料
└── logs/                        # 示例 JSONL 执行日志
    ├── success_storage.jsonl
    ├── success_visit.jsonl
    ├── failure_invalid_location.jsonl
    ├── failure_unknown_skill.jsonl
    └── failure_timeout.jsonl
```

---

---

## 7. 基于地图的 A* 导航
可以使用真实 GPS、罗盘航向和 `/scan` 建立 2D 占据栅格地图：

```bash
python3 scripts/build_map.py --output maps/break_room_map --duration 240
```

生成：

```text
maps/break_room_map.pgm
maps/break_room_map.yaml
```

也可以直接使用世界文件几何结构生成全房间地图：

```bash
python3 scripts/build_map_from_world.py
```

生成：

```text
maps/break_room_world_map.pgm
maps/break_room_world_map.yaml
```

`navigate_to` 支持两种模式：

| 模式 | 运行方式 | 行为 |
|---|---|---|
| Direct | `--navigation-mode direct` | LLM 规划后直接 PID 控制 |
| Map | `--navigation-mode map` | LLM 规划后先 A* 规划，再由直接控制跟踪路径 |

示例：

```bash
python3 -m agent.main "Go to storage." --planner llm --navigation-mode map
python3 -m agent.main "Go to workbench." --planner llm --navigation-mode direct
```

LLM 规划器在任务层面保持不变：它仍然只选择 `navigate_to`、`follow_waypoints`、`stop`。地图只在技能层使用。未知与占据格视为不可通行；如果 A* 找不到路径，技能会回退到直接 PID 控制。

如果仓库克隆到其他路径，请通过环境变量指定地图：

```bash
export ROBOT_MAP_PATH=/path/to/assignment/maps/break_room_world_map.pgm
```

或在技能 CLI 中传入 `--map-path /path/to/break_room_world_map.pgm`。

### 6.1 技能级 CLI

三个技能也可以直接测试：

```bash
ros2 run robot_skills navigate_to --x 0.0 --y -0.9 --theta 0.0 --timeout 20

ros2 run robot_skills follow_waypoints --waypoints '[{"x":0.0,"y":-0.9,"theta":0.0},{"x":0.5,"y":-0.5,"theta":0.0}]' --timeout-per-waypoint 20

ros2 run robot_skills stop_skill
```

### 6.2 障碍安全（Level 1）

`navigate_to` 订阅 `/scan`，并检查预期运动方向周围的锥形区域。如果最近有效距离小于 `obstacle_stop_distance`（默认 0.35 m），技能会停车并返回：

```json
{"success": false, "reason": "obstacle_blocked"}
```

随后任务级代理执行有界恢复：

1. 后退 0.6 s；
2. 原地旋转 0.6 s；
3. 重试导航一次；
4. 如果重试仍被阻挡，停车并报告 `Target is blocked by an obstacle.`

假激光测试工具在 `scripts/fake_scan.py`，它会在 `/scan` 上发布近距离 LaserScan，便于不改世界文件进行测试。

---

---

## 8. 验证与安全
验证器实现六层检查：

1. 计划长度与最大步数；
2. 固定白名单：只允许 `navigate_to`、`follow_waypoints`、`stop`；
3. JSON Schema 类型、必填字段和范围检查；
4. 工作空间边界；
5. 技能前置条件；
6. 重试次数限制（默认 `max_retries=1`）。

LLM 从不被允许生成 Python、Shell 或 ROS 命令。执行器只把三个白名单技能名映射到 Python 方法。

### 7.1 有界恢复

| 失败类型 | 恢复动作 |
|---|---|
| 未知技能 | 拒绝计划，中止并上报 |
| 参数缺失 / 类型错误 | 拒绝计划，中止并上报 |
| 目标超出工作空间 | 拒绝计划，请求有效位置 |
| 导航超时 | 重试一次；再次失败则停止并上报 |
| 计划过长 | 拒绝计划，中止并上报 |

---

---

## 9. 结果
完整测试表见 `RESULTS.md`。摘要：

| 测试 | 结果 |
|---|---|
| `Go to storage.` | 成功，位置误差 0.049 m，7.81 s |
| `Visit storage, then workbench, and stop.` | 成功，last reached index 1，11.30 s |
| `Go to space_station.` | 拒绝：目标超出工作空间 |
| `Go to entrance and fly.` | 拒绝：未知技能 |
| 强制导航超时 | 重试一次后停止并上报 |

示例日志在 `logs/`。

---

---

## 10. 已知限制
- 默认配置在 WSL2 内通过 WSLg 运行 Webots，存在一定的 D3D12 转换和 Xwayland 合成开销，流畅度不如可选的 Windows 原生 Webots 模式，但足以完成作业。
- 参考 `wheels_controller` 使用 `WHEEL_RADIUS = 0.26`，而 URDF 轮半径为 `0.06`；技能控制器使用反馈补偿。
- 参考环境没有 `/agent0/odom` 话题；位置来自 `/agent0/gps`，航向来自 `/agent0/compass/bearing`。
- `rosdep update` 可能因 Windows 本地代理未镜像到 WSL NAT 模式而超时；所需依赖通过 apt 安装。
- 用于原生 Linux Webots 的 WSL 驱动补丁可能被 `ros-humble-webots-ros2-driver` 的 apt 升级覆盖。

---

---

## 11. 参考链接
1. ROS 2 Humble — https://docs.ros.org/en/humble/
2. Webots R2025a — https://cyberbotics.com/
3. `webots_ros2` — https://github.com/cyberbotics/webots_ros2
4. `webots_ros2_robomaster` — https://github.com/MohismLab/webots_ros2_robomaster
5. WSLg — https://github.com/microsoft/wslg
6. Mesa D3D12 — https://docs.mesa3d.org/drivers/d3d12.html
7. OpenAI 兼容函数调用 — https://platform.openai.com/docs/guides/function-calling
