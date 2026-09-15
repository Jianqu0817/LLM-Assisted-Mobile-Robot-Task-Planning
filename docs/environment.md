# WSLg + AMD RX 9070 XT + Webots/ROS 2 环境验证记录

## 1. 硬件与系统

- Windows 11 Pro，Build 26200
- CPU: AMD Ryzen 7 7700, 8C/16T
- RAM: 32GB DDR5-4800
- GPU: AMD Radeon RX 9070 XT, 16GB VRAM
- 存储: Predator GM7 1TB NVMe + Samsung 980 PRO 2TB NVMe
- WSL: 2.7.14.0, WSLg 1.0.73.2, Kernel 6.18.33.2
- Ubuntu: 22.04.5 LTS (WSL2, imported rootfs)
- ROS 2: Humble Desktop
- Webots: R2025a (Linux .deb, installed inside WSL)
- webots_ros2: 2025.0.0 (apt)
- webots_ros2_robomaster: 2025.0.0 (source workspace)

## 2. WSLg OpenGL 验证结果

`glxinfo -B`:

- Renderer: `D3D12 (AMD Radeon RX 9070 XT)`
- Vendor: `Microsoft Corporation`
- Accelerated: `yes`
- OpenGL version: `4.2 (Compatibility Profile) Mesa 23.2.1`
- Direct rendering: `Yes`

`glxgears`:

- 约 140 FPS（unsynced, WSLg）

结论: WSLg 下 AMD RX 9070 XT 的 OpenGL 已硬件加速，可用于 Webots。

## 3. Webots 验证结果

- Webots R2025a 可在 WSLg 中启动 GUI。
- 加载 `webots_ros2_robomaster` 的 `break_room.wbt` 成功。
- `/tmp/webots/ubuntu/1234/ipc/` 下成功注册:
  - `agent0/extern`
  - `agent1/extern`
  - `Ros2Supervisor/extern`
- ROS 2 话题包括:
  - `/agent0/cmd_vel`, `/agent0/cmd_wheels`
  - `/agent0/gps`, `/agent0/gps/speed`
  - `/agent0/camera/camera_info`
  - `/agent0/compass/*`
  - `/agent0/receiver/*`
  - `/scan`, `/scan/point_cloud`, `/imu`, `/joint_states`, `/tf`
- `wheels_controller` 插件成功运行。
- 手动控制验证:
  - 前进 `linear.x=0.3` 约 4s，GPS x 从 -0.4956 变到 -0.4823。
  - 后退后回到约 -0.4956。
  - 旋转 `angular.z=1.0` 约 4s，GPS y 从 -1.0000 变到 -0.9991。
  - 说明 `/agent0/cmd_vel -> wheels_controller -> Webots` 链路有效。

## 4. 关键补丁与工作目录

### 4.1 让 webots_ros2_driver 在 WSL 内使用 Linux Webots

默认 `webots_ros2_driver` 检测到 WSL 后会去启动 Windows 的
`msys64/mingw64/bin/webots.exe`。本环境 Webots 装在 WSL 内，因此需要条件补丁:

文件:
`/opt/ros/humble/local/lib/python3.10/dist-packages/webots_ros2_driver/utils.py`

`is_wsl()` 改为:

```python
def is_wsl():
    webots_home = os.environ.get('WEBOTS_HOME', '')
    if webots_home.startswith('/') and os.path.isfile(os.path.join(webots_home, 'webots')):
        return False
    return 'microsoft-standard' in uname().release
```

使用前建议:
```bash
export WEBOTS_HOME=/usr/local/webots
```

注意: apt 更新 `ros-humble-webots-ros2-driver` 可能覆盖该补丁。

### 4.2 Webots 官方资产缓存

Debian 包的 `/usr/local/webots/projects` 不包含完整资产，世界会尝试从
raw.githubusercontent.com 下载 PROTO/纹理，导致加载缓慢或失败。

解决:
1. 下载 `assets-R2025a.zip`（约 660MB）。
2. 解压到:
   `/home/ubuntu/.cache/Cyberbotics/Webots/assets/`
3. 检查: 4893 个文件，约 842MB。

### 4.3 robomaster 缺失 protos

仓库不含 `protos/meshes`，原脚本用 gdown 从 Google Drive 下载:
`126Wyz2xYeYT01z5ilD1YH_fYc0rHBA_M`

下载后放到:
`/home/ubuntu/webots_ros2_robomaster/protos/`

包含:
- `protos/meshes/Orin.dae`
- `protos/meshes/Robomaster-车体_output.obj`
- `protos/meshes/Robomaster-车轮_output.obj`
- `protos/four_omniwheels.proto`
- `protos/three_omniwheel.proto`

### 4.4 构建 sensing_msgs

`wheels_controller.py` 依赖 `sensing_msgs`，但该包是嵌套包，colcon 默认不会发现。
需要:

```bash
ln -sfn /home/ubuntu/webots_ros2_robomaster/sensing_msgs \
  /home/ubuntu/ros2_ws/src/sensing_msgs

cd /home/ubuntu/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

### 4.5 Webots 临时目录

不要设置 `TMPDIR=/home/ubuntu/tmp`，否则驱动找不到
`/tmp/webots/<user>/<port>/ipc`。使用默认 `/tmp`，并确保 `/tmp/webots` 不存在或
`ubuntu` 用户可写。

### 4.6 .wslconfig

`C:\Users\23668\.wslconfig`:
```ini
[wsl2]
memory=16GB
processors=8
swap=16GB
localhostForwarding=true
guiApplications=true
```

## 5. 启动与停止

启动:
```bash
wsl -d Ubuntu-22.04 -u ubuntu
export WEBOTS_HOME=/usr/local/webots
unset TMPDIR
source /opt/ros/humble/setup.bash
source /home/ubuntu/ros2_ws/install/setup.bash
ros2 launch webots_ros2_robomaster robot_launch.py
```

键盘遥控:
```bash
source /opt/ros/humble/setup.bash
source /home/ubuntu/ros2_ws/install/setup.bash
python3 /home/ubuntu/webots_ros2_robomaster/webots_ros2_robomaster/keyboard_twist.py --topic /agent0/cmd_vel
```

已保存的辅助脚本:
- `D:\DS_workspace\Liqingbiao\start_robomaster.sh`
- `D:\DS_workspace\Liqingbiao\stop_robomaster.sh`
- `D:\DS_workspace\Liqingbiao\test_robomaster_launch.sh`
- `D:\DS_workspace\Liqingbiao\wsl_glxinfo.txt`
- `D:\DS_workspace\Liqingbiao\wsl_glxgears.txt`
- `D:\DS_workspace\Liqingbiao\robomaster_window.png`

## 6. 已知问题

1. `wheels_controller.py` 中 `WHEEL_RADIUS = 0.26` 与实际 URDF 的 0.06 不一致，
   导致实际速度约为命令速度的 1/4。做导航 PID 时需要用反馈闭环，或修正该常量。
2. 当前没有 `/agent0/odom` 话题。可用 `/agent0/gps` 和 `/agent0/compass/bearing`
   自行实现里程计/定位，或启用 `diffdrive_controller` spawner。
3. `rosdep update` 曾因 raw.githubusercontent.com 超时失败；主要依赖已用 apt 手动安装。
4. WSL 检测到 Windows 本地代理 `127.0.0.1:7890`，NAT 模式无法使用，部分下载会走直连。
   如需稳定访问 Google/GitHub，可考虑 `networkingMode=mirrored` 并配置代理。
5. 当前 Webots 窗口为原生 Linux 窗口，通过 WSLg 显示在 Windows 桌面。

## 7. 建议下一步

1. 实现 Part 2 导航技能:
   - `navigate_to(x, y, theta)`
   - `follow_waypoints(waypoints)`
   - `stop()`
2. 用 `/agent0/gps` + `/agent0/compass/bearing` 做位姿反馈，输出 `/agent0/cmd_vel`。
3. 实现 Part 3 技能注册表、参数校验、结构化结果。
4. 实现 Part 4 LLM tool calling、allowlist、validator、有界恢复。
5. 补齐 README、RESULTS.md、4 页双栏报告和 ≤2 分钟演示视频。


---

## 11. Optional Windows-native Webots mode

The default final configuration runs Webots inside WSL2. If you want smoother
GUI rendering, you can optionally install Webots R2025a on Windows and run the
ROS 2 driver in WSL. This mode is documented for comparison.

- Windows Webots path: `D:/Webots`.
- WSL path: `/mnt/d/Webots`.
- Driver launch command: `D:/Webots/msys64/mingw64/bin/webots.exe`.
- The driver communicates with Windows Webots over TCP port 1234.
- Windows Webots listens on `0.0.0.0:1234`; WSL connects to the Windows host
  address (`ip route` default gateway, e.g. `172.26.224.1`).
- `/etc/resolv.conf` in WSL may contain `10.255.255.254` (a DNS proxy), so the
  driver's `get_wsl_ip_address()` was patched to prefer the default gateway.

Start/stop scripts now also kill the Windows Webots process:

```bash
bash /mnt/d/DS_workspace/Liqingbiao/start_robomaster.sh
bash /mnt/d/DS_workspace/Liqingbiao/stop_robomaster.sh
```


### 11.1 Reproduction scripts

The repository provides the Windows-Webots mode scripts:

- `scripts/setup_windows_webots.ps1`: download and silently install Webots
  R2025a to `D:/Webots`.
- `scripts/patch_webots_ros2_driver.py`: apply the `is_wsl()` and
  `get_wsl_ip_address()` patches (run as root).
- `scripts/start_robomaster.sh`: start the simulation.
- `scripts/stop_robomaster.sh`: stop the simulation and the Windows Webots
  process.
