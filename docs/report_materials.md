# LLM-Assisted Mobile Robot Task Planning — Report Materials

> 本文件用于整理作业技术报告可用的素材：平台配置、实验数据、架构设计、实现细节、
> 结果表格、失败案例、局限性、参考文献和报告结构建议。可按需裁剪到 4 页双栏正文。

---

## 0. 使用建议

- 正文优先保留：问题定义、系统架构、技能接口设计、导航实现、validator/recovery、
  实验设置与结果、局限性。
- 环境配置、完整命令、资产缓存修复、WSL 补丁等放附录或 GitHub README。
- 实验数据可直接引用本文档表格；图表建议见第 13 节。
- 引用外部代码/模型/教程时使用第 14 节链接。

---

## 1. 可作为报告亮点/贡献点的内容

1. 在 **WSL2 + WSLg** 上实现了 **AMD RX 9070 XT 的 OpenGL 硬件加速**，并成功运行
   Webots R2025a 原生 Linux GUI，无需双系统或 VMware。
2. 打通了完整的 **Webots ↔ ROS 2 Humble ↔ webots_ros2_driver** 链路，extern
   controller 通过 IPC 成功注册并连接。
3. 完整复现 `webots_ros2_robomaster` 2025.0.0 参考仿真，修复了
   `protos/meshes` 缺失、`sensing_msgs` 未构建、Webots 资产缓存缺失、
   WSL 平台误判等问题。
4. 给出了从**自然语言 → LLM tool call → validator → skill executor → Webots**
   的安全任务规划架构草案，包括 allowlist、参数校验、工作空间边界、最大步数/重试。
5. 提出了结构化技能接口和恢复策略，可覆盖成功、非法位置、超时、不可达等场景。

---

## 2. 问题定义与设计目标

### 2.1 任务定义

系统接收自然语言指令，例如：

- "Go to `storage`."
- "Visit `storage`, then `workbench`, and stop."
- 非法请求：目标位置在工作空间外。

系统输出一个经过验证的小规模技能调用序列，由 Webots 中的 RoboMaster 移动机器人执行。

### 2.2 设计目标

- **安全性**：LLM 不得直接发布速度指令或执行任意生成代码。
- **可靠性**：每个技能有明确 contract、超时、成功条件和结构化结果。
- **可验证性**：validator 分阶段拒绝未知技能、错误参数、越界目标、超步数计划。
- **可恢复性**：失败后有有界恢复策略，并记录完整决策日志。
- **可复现性**：环境、依赖、启动命令、实验数据全部可追溯。

### 2.3 非目标

- 不使用 LLM 生成代码或 shell 命令。
- 不要求端到端学习控制；PID/反馈控制即可。
- 不追求复杂导航栈；允许简单导航并清晰说明 goal/success/timeout。

---

## 3. 系统架构

### 3.1 建议架构图（文字版）

```text
Natural Language Request
        │
        ▼
┌─────────────────────┐
│  LLM Planner        │  OpenAI-compatible function calling
│  (mock or real)     │  只能从 skill registry 选择技能
└─────────┬───────────┘
          │ raw plan (JSON)
          ▼
┌─────────────────────┐
│  Validator          │
│  1. schema / type   │
│  2. allowlist       │
│  3. workspace bounds│
│  4. preconditions   │
│  5. max steps/retry │
└─────────┬───────────┘
          │ validated calls
          ▼
┌─────────────────────┐
│  Skill Executor     │
│  navigate_to        │
│  follow_waypoints   │
│  stop               │
└─────────┬───────────┘
          │ ROS 2 actions/topics
          ▼
┌─────────────────────┐
│  Webots + ROS 2     │
│  RoboMaster agent0  │
└─────────┬───────────┘
          │ structured result
          ▼
┌─────────────────────┐
│  Recovery / Logger  │
│  bounded retry,     │
│  ask valid location,│
│  stop + report      │
└─────────────────────┘
```

### 3.2 模块职责

| 模块 | 职责 | 关键输出 |
|---|---|---|
| Planner | 接收自然语言，生成技能调用计划 | `SkillCall[]` |
| Registry | 提供技能描述、参数 schema、范围 | machine-readable tool list |
| Validator | allowlist、类型、范围、工作空间、步数/重试校验 | `ValidationResult` |
| Executor | 按序调用技能，收集结构化结果 | `SkillResult[]` |
| Recovery | 对失败做有界响应 | `RecoveryDecision` |
| Logger | 记录原始计划、观测结果、恢复决策、最终结果 | JSONL logs |
| ROS Skill Layer | `navigate_to`、`follow_waypoints`、`stop` | ROS 2 topics/actions |

### 3.3 数据流伪代码

```python
plan = llm.plan(user_request, tools=registry.as_tool_schema())
for call in plan.calls:
    validation = validator.validate(call, state)
    if not validation.ok:
        decision = recovery.handle_validation_failure(validation)
        break
    result = executor.execute(call)
    logger.record(call, result)
    if not result.success:
        decision = recovery.handle_execution_failure(result)
        if decision.action == "abort":
            break
        # bounded retry only
```

---

## 4. 实验平台与可复现环境

### 4.1 硬件

| 项目 | 值 |
|---|---|
| 主机 | ASUS 台式机 |
| OS | Windows 11 Pro, Build 26200 |
| CPU | AMD Ryzen 7 7700, 8C/16T, 3.8GHz |
| RAM | 32GB DDR5-4800 (2 × 16GB) |
| GPU | AMD Radeon RX 9070 XT, 16GB VRAM |
| 磁盘 | Predator GM7 1TB NVMe + Samsung 980 PRO 2TB NVMe |
| 显示驱动 | AMD 32.0.31021.5001 |

### 4.2 软件栈

| 组件 | 版本 |
|---|---|
| Windows Subsystem for Linux | WSL 2.7.14.0 |
| WSL Kernel | 6.18.33.2-2 |
| WSLg | 1.0.73.2 |
| Direct3D | 1.611.1-81528511 |
| DXCore | 10.0.26100.1-240331-1435.ge-release |
| Linux 发行版 | Ubuntu 22.04.5 LTS (WSL2, imported rootfs) |
| Mesa | 23.2.1-1ubuntu3.1~22.04 |
| ROS 2 | Humble Desktop |
| `webots_ros2` | 2025.0.0 |
| Webots | R2025a (Linux `.deb`) |
| `webots_ros2_robomaster` | 2025.0.0 |

### 4.3 WSL 配置

`C:\Users\23668\.wslconfig`：

```ini
[wsl2]
memory=16GB
processors=8
swap=16GB
localhostForwarding=true
guiApplications=true
```

### 4.4 关键路径

```text
Webots:              /usr/local/webots
ROS 2:               /opt/ros/humble
ROS 2 workspace:     /home/ubuntu/ros2_ws
robomaster source:   /home/ubuntu/webots_ros2_robomaster
Webots asset cache:  /home/ubuntu/.cache/Cyberbotics/Webots/assets
Webots IPC temp:     /tmp/webots/ubuntu/1234/ipc
```

---

## 5. WSLg 下 AMD OpenGL 兼容性实验

### 5.1 实验目的

验证 WSLg 是否能把 AMD RX 9070 XT 的 OpenGL 调用硬件加速，而不是退化到
`llvmpipe` 软件渲染，从而判断 Webots GUI 是否可行。

### 5.2 实验命令

```bash
glxinfo -B
vblank_mode=0 timeout 12 glxgears
xeyes
```

### 5.3 实验结果

| 指标 | 结果 |
|---|---|
| direct rendering | Yes |
| Accelerated | yes |
| Vendor | Microsoft Corporation |
| Renderer | `D3D12 (AMD Radeon RX 9070 XT)` |
| Device | `D3D12 (AMD Radeon RX 9070 XT)` |
| OpenGL core | 4.2 |
| OpenGL compatibility | 4.2 |
| OpenGL ES | 3.1 |
| Mesa version | 23.2.1-1ubuntu3.1~22.04.3 |
| Video memory reported | 32133 MB (shared + dedicated) |
| `glxgears` | 约 143.9 FPS / 138.4 FPS（两次 5s 统计） |
| `xeyes` | 窗口正常显示 |

### 5.4 讨论点

- 渲染器显示 `D3D12 (AMD Radeon RX 9070 XT)`，说明 WSLg 使用 **Mesa D3D12
  gallium driver** 将 Linux OpenGL 翻译为 Direct3D 12 调用，硬件加速成立。
- Vendor 显示 `Microsoft Corporation` 是 WSLg/D3D12 翻译层特征，不代表软件渲染。
- OpenGL 4.2 已满足 Webots 常见需求；但高于 4.2 的可选特性可能不可用。
- 该验证说明 **无需 VMware/双系统** 即可在 Windows 主机上运行 Webots GUI。

### 5.5 报告中可写的一句话

> WSLg exposes a hardware-accelerated OpenGL 4.2 context backed by the Mesa
> D3D12 driver on the AMD Radeon RX 9070 XT, achieving ~140 FPS in glxgears and
> allowing Webots R2025a to run natively inside WSL2.

---

## 6. Webots + ROS 2 集成实验

### 6.1 实验目的

验证 `webots_ros2_robomaster` 参考仿真能在 WSLg 内启动，并且 Webots 与 ROS 2 的
extern controller 链路工作。

### 6.2 实验命令

```bash
export WEBOTS_HOME=/usr/local/webots
unset TMPDIR
source /opt/ros/humble/setup.bash
source /home/ubuntu/ros2_ws/install/setup.bash
ros2 launch webots_ros2_robomaster robot_launch.py
```

### 6.3 实验结果

- Webots 世界成功加载：
  `/tmp/..._world_with_URDF_robot.wbt (No Project) - Webots R2025a`
- Extern controller IPC 注册成功：

```text
/tmp/webots/ubuntu/1234/ipc/agent0/extern
/tmp/webots/ubuntu/1234/ipc/agent1/extern
/tmp/webots/ubuntu/1234/ipc/Ros2Supervisor/extern
```

- ROS 2 日志关键行：

```text
[agent0]: Controller successfully connected to robot in Webots simulation.
[agent1]: Controller successfully connected to robot in Webots simulation.
[wheels_controller]: Set speed: FL=0, FR=0, RL=0, RR=0
```

### 6.4 观察到的话题

| 话题 | 类型 | 说明 |
|---|---|---|
| `/agent0/cmd_vel` | `geometry_msgs/msg/Twist` | 速度指令入口 |
| `/agent0/cmd_wheels` | `sensing_msgs/msg/WheelSpeed` | 四轮速度指令入口 |
| `/agent0/gps` | `geometry_msgs/msg/PointStamped` | 位置反馈 |
| `/agent0/gps/speed` | `std_msgs/msg/Float32` | 速度反馈 |
| `/agent0/compass/bearing` | `std_msgs/msg/Float64` | 朝向反馈候选 |
| `/agent0/camera/camera_info` | `sensor_msgs/msg/CameraInfo` | 相机信息 |
| `/agent0/receiver/*` | 多种 | 通信/信号 |
| `/scan` | `sensor_msgs/msg/LaserScan` | 激光雷达 |
| `/scan/point_cloud` | `sensor_msgs/msg/PointCloud2` | 激光点云 |
| `/imu` | `sensor_msgs/msg/Imu` | IMU |
| `/joint_states` | `sensor_msgs/msg/JointState` | 关节状态 |
| `/tf`, `/tf_static` | TF | 坐标变换 |
| `/clock` | `rosgraph_msgs/msg/Clock` | 仿真时间 |

### 6.5 集成问题与修复

| 问题 | 根因 | 修复 |
|---|---|---|
| 启动 Windows `webots.exe` 失败 | `webots_ros2_driver` 检测到 WSL 后默认启动 Windows Webots | 条件修改 `is_wsl()`：若 `WEBOTS_HOME` 是 Linux 路径且存在 `webots` 可执行文件则返回 False |
| 世界加载卡住 | Debian Webots 不含完整 assets，远程下载 PROTO/纹理超时 | 下载 `assets-R2025a.zip` 并解压到 `~/.cache/Cyberbotics/Webots/assets`（4893 文件，842MB） |
| `wheels_controller` 崩溃 | 嵌套包 `sensing_msgs` 未被 colcon 发现 | 增加 symlink 到 workspace 并重新 `colcon build` |
| extern controller 找不到 | 设置 `TMPDIR` 后 Webots 临时目录不在 `/tmp/webots` | 取消 `TMPDIR`，使用默认 `/tmp/webots` |
| robomaster 缺少 meshes | 仓库不含 `protos/meshes` | 从 Google Drive 下载并放入 `protos/`（696MB） |

### 6.6 WSL 平台判断补丁

文件：
`/opt/ros/humble/local/lib/python3.10/dist-packages/webots_ros2_driver/utils.py`


```python
def is_wsl():
    webots_home = os.environ.get('WEBOTS_HOME', '')
    if webots_home.startswith('/') and os.path.isfile(os.path.join(webots_home, 'webots')):
        return False
    return 'microsoft-standard' in uname().release
```

报告说明：

> Because Webots is installed natively inside WSL, the original WSL detection of
> `webots_ros2_driver` incorrectly targets a Windows `webots.exe`. We patch the
> platform predicate to distinguish "WSL with native Linux Webots" from
> "WSL launching Windows Webots".

---

## 7. 手动控制/基础控制实验

### 7.1 实验目的

验证 `cmd_vel` 能驱动 Webots 中的 RoboMaster，并获取位置反馈，为 Part 2 导航提供基础。

### 7.2 实验方法

向 `/agent0/cmd_vel` 发布 `geometry_msgs/msg/Twist`，通过 `/agent0/gps`
和 `/agent0/gps/speed` 观察运动。

### 7.3 实验数据

| 实验 | 指令 | 持续时间 | 运动前 GPS | 运动后 GPS | 观测 |
|---|---|---:|---|---|---|
| 前进 | `linear.x=0.3` | ~4s | x=-0.495568 | x=-0.482258 | Δx≈+0.01331m |
| 前进时速度 | 同上 | — | — | — | `/agent0/gps/speed`≈0.06936 m/s |
| 后退 | `linear.x=-0.3` | ~4s | x=-0.482258 | x=-0.495584 | Δx≈-0.01333m |
| 后退时速度 | 同上 | — | — | — | `/agent0/gps/speed`≈0.06942 m/s |
| 旋转 | `angular.z=1.0` | ~4s | y=-1.000016 | y=-0.999080 | Δy≈+0.000936m |

### 7.4 结果分析

- `cmd_vel → wheels_controller → Webots` 链路有效，前进、后退、旋转都能改变 GPS 位置。
- 实际线速度约 `0.069 m/s`，而命令速度 `0.3 m/s`，比例约 `0.23`。
- 该比例和参考控制器中的 `WHEEL_RADIUS = 0.26` 与 URDF 实际轮半径 `0.06`
  之比一致：`0.06 / 0.26 ≈ 0.2308`。
- 报告可写：参考实现在速度标定上存在偏差，因此导航控制器应使用闭环反馈，
  或修正轮半径常量。

### 7.5 控制链路的实现细节

```text
/agent0/cmd_vel  (Twist)
        │
        ▼
wheels_controller plugin
  - 订阅 Twist 和 WheelSpeed
  - 根据差速/四轮模型计算四个电机速度
  - 通过 Webots motor.setVelocity() 驱动
        │
        ▼
Webots RoboMaster S1
        │
        ▼
/agent0/gps, /agent0/gps/speed, /imu, /scan ...
```

重要细节：

- `wheels_controller` 有 **1.5 秒命令超时**，超时后自动把速度置零。
  因此 `navigate_to` 必须以 ≥2Hz（建议 10–20Hz）持续发布 `cmd_vel`。
- `stop()` 可以发布零 `Twist`，也可以依赖 1.5 秒超时自动停止；建议显式发布零指令。
- 当前没有 `/agent0/odom`。可自行积分 `/agent0/gps` 与 `/agent0/compass/bearing`，
  或启用 `diffdrive_controller` spawner。

---

## 8. Part 2 导航技能设计草案

### 8.1 坐标与单位

- 使用 Webots world frame。
- 位置单位：米。
- 角度单位：弧度。
- 朝向归一化到 `[-π, π]`。
- 位置反馈：`/agent0/gps`。
- 朝向反馈候选：`/agent0/compass/bearing` 或 `/imu`。
- 速度指令：`/agent0/cmd_vel`。

### 8.2 `navigate_to(x, y, theta)`

建议控制律：

```text
ex = x_target - x
ey = y_target - y
distance_error = sqrt(ex^2 + ey^2)
heading_to_target = atan2(ey, ex)
heading_error = normalize_angle(heading_to_target - yaw)
theta_error = normalize_angle(theta_target - yaw)

v = Kp * distance_error
omega = K_heading * heading_error + K_theta * theta_error
```

结束条件：

```text
distance_error <= pos_tol_m
and abs(theta_error) <= heading_tol_rad
```

安全与边界：

```text
timeout_s = 20~30
if elapsed > timeout: publish zero Twist and return timeout
```

结构化结果：

```json
{
  "success": false,
  "reason": "timeout",
  "position_error_m": 0.31,
  "heading_error_rad": 0.12,
  "elapsed_time_s": 20.0
}
```

### 8.3 `follow_waypoints(waypoints)`

- 顺序调用 `navigate_to`。
- 失败时返回最后到达的 waypoint：

```json
{
  "success": false,
  "reason": "nav_timeout",
  "last_reached_index": 1,
  "total_waypoints": 3,
  "elapsed_time_s": 42.7
}
```

- 建议限制最大 waypoint 数，避免长计划。

### 8.4 `stop()`

- 发布零 `Twist` 到 `/agent0/cmd_vel`。
- 等待至少一个控制周期。
- 返回：

```json
{
  "success": true,
  "reason": "stopped",
  "elapsed_time_s": 0.2
}
```

### 8.5 状态机建议

```text
IDLE → NAVIGATING → SUCCESS
               ↘ TIMEOUT → STOP → FAILED
               ↘ INVALID_TARGET → REPORT
```

---

## 9. Part 3 技能接口设计草案

### 9.1 建议使用 Pydantic / JSON Schema

每个技能定义：

| 字段 | 说明 |
|---|---|
| `name` | 技能名 |
| `description` | 给 LLM 的简短描述 |
| `parameters` | 类型、范围、默认值 |
| `preconditions` | 机器人状态、前置条件 |
| `success_condition` | 判定成功条件 |
| `timeout_s` | 超时时间 |
| `result_schema` | 结构化结果 schema |

### 9.2 技能 registry 示例

```json
{
  "skills": [
    {
      "name": "navigate_to",
      "description": "Move the robot to a target pose.",
      "parameters": {
        "x": {"type": "number", "min": -1.5, "max": 1.5},
        "y": {"type": "number", "min": -1.5, "max": 1.5},
        "theta": {"type": "number", "min": -3.14159, "max": 3.14159}
      },
      "preconditions": ["robot_available", "not_estopped"],
      "success_condition": "position_error_m <= 0.15 and heading_error_rad <= 0.15",
      "timeout_s": 25
    }
  ]
}
```

### 9.3 结构化结果字段

```json
{
  "success": true,
  "reason": "reached",
  "position_error_m": 0.08,
  "heading_error_rad": 0.05,
  "elapsed_time_s": 12.4
}
```

---

## 10. Part 4 LLM 规划、验证与恢复设计

### 10.1 安全要求映射

| 作业要求 | 设计 |
|---|---|
| 固定 allowlist | 只允许 `navigate_to`、`follow_waypoints`、`stop` |
| 未知技能 | allowlist 直接拒绝 |
| 缺失/类型错误 | JSON Schema / Pydantic 校验 |
| 目标越界 | 工作空间边界校验 `x,y ∈ workspace` |
| 步数/重试超限 | `max_steps`, `max_retries` |
| 禁止任意代码 | 执行器只调用 ROS skill，不 eval/exec |
| 结构化结果 | 每个 skill 返回 `success/reason/elapsed_time_s` |

### 10.2 Validator 分层

```text
Layer 1: JSON parse / schema
Layer 2: allowlist
Layer 3: parameter types and ranges
Layer 4: workspace bounds
Layer 5: preconditions and state
Layer 6: max steps / max retries
```

### 10.3 Recovery 策略

| 失败类型 | 有界恢复 |
|---|---|
| 未知技能 | 拒绝计划，记录，终止 |
| 参数类型/缺失 | 拒绝该调用，请求重规划一次 |
| 目标越界 | 询问有效位置；若仍非法则终止 |
| 导航超时 | 重试导航一次；第二次失败则 stop + report |
| 不可达 | stop 并报告 `unreachable` |
| 步数超限 | 截断计划，报告 `plan_too_long` |

### 10.4 日志建议

建议 JSONL，每条包含：

```json
{
  "timestamp": "...",
  "user_request": "...",
  "raw_plan": [],
  "validation": {},
  "skill_result": {},
  "recovery_decision": "...",
  "final_outcome": "..."
}
```

---

## 11. 建议的实验/测试用例

| 编号 | 指令 | 类型 | 预期结果 |
|---|---|---|---|
| T1 | "Go to storage." | 成功 | 到达 storage，success=true |
| T2 | "Visit storage, then workbench, and stop." | 成功 | 两个 waypoint 顺序到达 |
| T3 | "Go to space_station." | 非法位置 | validator 拒绝，请求有效位置 |
| T4 | "Go to entrance and fly." | 未知技能 | allowlist 拒绝 |
| T5 | 导航超时 | 失败恢复 | 重试一次，失败后 stop + report |
| T6 | 工作空间外坐标 | 边界 | validator 拒绝 |
| T7 | 超过最大步数 | 步数限制 | 截断/拒绝 |
| T8 | 缺失参数 | 类型校验 | 拒绝并记录 |

---

## 12. 安全考虑

- **固定 allowlist**：LLM 只能从三个技能中选择。
- **禁止代码执行**：不执行 LLM 生成的 Python / shell / ROS 命令。
- **Schema 校验**：所有参数必须通过类型、范围、必填字段检查。
- **工作空间边界**：目标必须位于配置的实验室范围内。
- **最大步数与重试**：防止无限循环和长计划。
- **超时安全停止**：导航超时后发布零速度。
- **结构化结果**：所有执行结果可审计。
- **密钥管理**：`.env` + `.gitignore`，不提交 API key。
- **依赖固定**：记录 Webots R2025a、ROS 2 Humble、`webots_ros2` 2025.0.0。

---

## 13. 局限性与未来工作

### 13.1 局限性

1. WSLg 使用 Mesa D3D12 翻译层，OpenGL 4.2；高级 OpenGL 特性可能受限。
2. 当前参考实现没有 `/agent0/odom`，位置反馈依赖 GPS，朝向需要自行处理。
3. `wheels_controller` 的轮半径常量与实际 URDF 不一致，导致速度标定误差。
4. Webots Debian 包缺少完整 assets，需要额外缓存 842MB。
5. WSL NAT 模式无法使用 Windows 本地代理，部分远程依赖下载不稳定。
6. `webots_ros2_driver` 的 WSL 平台判断补丁可能被 apt 更新覆盖。
7. 实验只在仿真中进行，未涉及真实机器人。

### 13.2 未来工作

- 实现 `/agent0/odom` 或启用 `diffdrive_controller`。
- 增加导航 PID 参数整定实验，比较不同容差/超时。
- 加入动态环境障碍、不可达目标、人工失败注入。
- 将 mock planner 替换为真实 OpenAI-compatible LLM，比较不同模型 tool call 正确率。
- 增加单元测试覆盖 validator 的所有拒绝路径。
- 将环境封装为 Docker/WSL 一键脚本，提高可复现性。

---

## 14. 报告结构建议（4 页双栏）

| 章节 | 建议页数 | 内容 |
|---|---:|---|
| Abstract | 0.2 | 任务、方法、主要结果 |
| I. Introduction | 0.4 | 问题定义、设计目标、贡献 |
| II. System Architecture | 0.7 | 架构图、模块职责、技能接口 |
| III. Implementation | 1.0 | 导航、tool calling、validator、recovery |
| IV. Experiments | 0.9 | 环境、测试用例、结果表、失败案例 |
| V. Discussion | 0.5 | 局限性、安全、复现性 |
| VI. Conclusion | 0.2 | 总结与下一步 |
| References | 不计入 | 外部依赖链接 |

### 14.1 评分映射

| 评分项 | 报告中对应内容 |
|---|---|
| Simulation and basic control 10% | 第 4、5、6、7 节 |
| Navigation skills 15% | 第 7、8 节 |
| Skill interface 10% | 第 8、9 节 |
| LLM planning and validation 10% | 第 10、11 节 |
| Code quality and reproducibility 5% | 第 4 节 + README |
| Technical report 25% | 全文结构 |
| Demonstration video 25% | 第 15 节录制建议 |

---

## 15. 演示视频建议

建议 ≤2 分钟，包含：

1. 5s：环境说明（WSLg + Webots + ROS 2）。
2. 20s：启动仿真，展示 Webots 窗口和 ROS 2 话题。
3. 20s：手动控制或 `navigate_to` 到目标。
4. 20s：`follow_waypoints` 多目标。
5. 20s：非法位置请求被 validator 拒绝。
6. 20s：导航超时 → 重试/停止 → 最终报告。
7. 5s：结果日志/结构。

字幕与旁白必须齐全；加速片段要标注。

---

## 16. 参考文献/链接

1. ROS 2 Humble documentation — https://docs.ros.org/en/humble/
2. Webots R2025a — https://cyberbotics.com/
3. Webots GitHub Release R2025a — https://github.com/cyberbotics/webots/releases/tag/R2025a
4. `webots_ros2` — https://github.com/cyberbotics/webots_ros2
5. `webots_ros2_robomaster` — https://github.com/MohismLab/webots_ros2_robomaster
6. WSLg documentation — https://github.com/microsoft/wslg
7. Mesa D3D12 driver — https://docs.mesa3d.org/drivers/d3d12.html
8. OpenAI-compatible function calling — https://platform.openai.com/docs/guides/function-calling
9. ROS MCP Server — https://github.com/robotmcp/ros-mcp-server
10. Pydantic — https://docs.pydantic.dev/

---

## 17. 原始文件/日志索引

| 文件 | 内容 |
|---|---|
| `WSL_ENV_SETUP.md` | 环境搭建、补丁、启动方式 |
| `wsl_glxinfo.txt` | `glxinfo -B` 完整输出 |
| `wsl_glxgears.txt` | `glxgears` 输出 |
| `webots_window.png` | Webots 窗口截图 |
| `robomaster_window.png` | robomaster 仿真窗口截图 |
| `ros2_install.log` | ROS 2 安装日志 |
| `webots_ros2_install.log` | webots_ros2 安装日志 |
| `colcon_build.log` / `colcon_build2.log` | 工作区构建日志 |
| `robomaster_launch_test2.log` | 参考仿真启动与控制器连接日志 |
| `start_robomaster.sh` / `stop_robomaster.sh` | 启动/停止脚本 |
