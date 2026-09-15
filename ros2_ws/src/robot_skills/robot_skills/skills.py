"""High-level robot skills for the Webots RoboMaster.

This module exposes a small Python API around three skills:
    - navigate_to(x, y, theta)
    - follow_waypoints(waypoints)
    - stop()

Each skill returns a SkillResult object with at least:
    success, reason, elapsed_time_s
"""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import rclpy
from geometry_msgs.msg import PointStamped, Twist
from sensor_msgs.msg import LaserScan
from rclpy.node import Node
from webots_ros2_msgs.msg import FloatStamped

from .map_planner import MapPlanner


def normalize_angle(angle: float) -> float:
    """Normalize an angle to [-pi, pi]."""
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def clamp(value: float, lower: float, upper: float) -> float:
    """Clamp value into [lower, upper]."""
    return max(lower, min(upper, value))


@dataclass
class SkillResult:
    success: bool
    reason: str
    elapsed_time_s: float
    position_error_m: Optional[float] = None
    heading_error_rad: Optional[float] = None
    last_reached_index: Optional[int] = None
    total_waypoints: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        extra = data.pop("extra", {}) or {}
        data.update(extra)
        return data


class RobotSkills(Node):
    """ROS 2 wrapper around the RoboMaster skills.

    The class subscribes to:
        /<robot_name>/gps              geometry_msgs/PointStamped
        /<robot_name>/compass/bearing  webots_ros2_msgs/FloatStamped

    and publishes:
        /<robot_name>/cmd_vel          geometry_msgs/Twist
    """

    def __init__(self, robot_name: str = "agent0") -> None:
        super().__init__("robot_skills")
        self.robot_name = robot_name

        # Parameters
        self.declare_parameter("pos_tol_m", 0.10)
        self.declare_parameter("heading_tol_rad", 0.15)
        self.declare_parameter("timeout_s", 30.0)
        self.declare_parameter("control_rate_hz", 20.0)
        self.declare_parameter("v_max", 3.0)
        self.declare_parameter("omega_max", 8.0)
        self.declare_parameter("k_v", 4.0)
        self.declare_parameter("k_i_v", 0.6)
        self.declare_parameter("k_d_v", 0.1)
        self.declare_parameter("k_theta", 5.0)
        self.declare_parameter("k_i_theta", 0.5)
        self.declare_parameter("k_d_theta", 0.05)
        self.declare_parameter("integral_max_v", 0.5)
        self.declare_parameter("integral_max_theta", 0.5)
        self.declare_parameter("rotate_in_place_threshold", 0.5)
        self.declare_parameter("obstacle_stop_distance", 0.35)
        self.declare_parameter("obstacle_cone_deg", 30.0)
        self.declare_parameter("scan_timeout_s", 1.0)
        self.declare_parameter("use_map", True)
        self.declare_parameter(
            "map_path",
            os.environ.get(
                "ROBOT_MAP_PATH",
                "/mnt/d/DS_workspace/Liqingbiao/assignment/maps/break_room_world_map.pgm",
            ),
        )

        self.pos_tol_m = float(self.get_parameter("pos_tol_m").value)
        self.heading_tol_rad = float(self.get_parameter("heading_tol_rad").value)
        self.timeout_s = float(self.get_parameter("timeout_s").value)
        self.control_rate_hz = float(self.get_parameter("control_rate_hz").value)
        self.v_max = float(self.get_parameter("v_max").value)
        self.omega_max = float(self.get_parameter("omega_max").value)
        self.k_v = float(self.get_parameter("k_v").value)
        self.k_i_v = float(self.get_parameter("k_i_v").value)
        self.k_d_v = float(self.get_parameter("k_d_v").value)
        self.k_theta = float(self.get_parameter("k_theta").value)
        self.k_i_theta = float(self.get_parameter("k_i_theta").value)
        self.k_d_theta = float(self.get_parameter("k_d_theta").value)
        self.integral_max_v = float(self.get_parameter("integral_max_v").value)
        self.integral_max_theta = float(self.get_parameter("integral_max_theta").value)
        self.rotate_in_place_threshold = float(
            self.get_parameter("rotate_in_place_threshold").value
        )
        self.obstacle_stop_distance = float(
            self.get_parameter("obstacle_stop_distance").value
        )
        self.obstacle_cone_rad = math.radians(
            float(self.get_parameter("obstacle_cone_deg").value)
        )
        self.scan_timeout_s = float(self.get_parameter("scan_timeout_s").value)
        self.use_map = bool(self.get_parameter("use_map").value)
        self.map_path = str(self.get_parameter("map_path").value)
        self.map_planner = None
        self.load_map()

        # State
        self.x: Optional[float] = None
        self.y: Optional[float] = None
        self.yaw: Optional[float] = None
        self._last_gps_stamp: Optional[float] = None
        self.scan: Optional[LaserScan] = None
        self._last_scan_time: float = 0.0

        gps_topic = f"/{self.robot_name}/gps"
        bearing_topic = f"/{self.robot_name}/compass/bearing"
        cmd_topic = f"/{self.robot_name}/cmd_vel"
        scan_topic = "/scan"

        self.create_subscription(PointStamped, gps_topic, self._gps_callback, 10)
        self.create_subscription(FloatStamped, bearing_topic, self._bearing_callback, 10)
        self.create_subscription(LaserScan, scan_topic, self._scan_callback, 10)
        self.cmd_pub = self.create_publisher(Twist, cmd_topic, 10)

        self.get_logger().info(f"RobotSkills ready for {self.robot_name}")
        self.get_logger().info(f"  gps:     {gps_topic}")
        self.get_logger().info(f"  bearing: {bearing_topic}")
        self.get_logger().info(f"  cmd_vel: {cmd_topic}")
        self.get_logger().info(f"  scan:    {scan_topic}")

    # ------------------------------------------------------------------
    # ROS callbacks
    # ------------------------------------------------------------------
    def _gps_callback(self, msg: PointStamped) -> None:
        self.x = float(msg.point.x)
        self.y = float(msg.point.y)
        self._last_gps_stamp = time.monotonic()

    def _bearing_callback(self, msg: FloatStamped) -> None:
        # Webots compass bearing: 0..360 degrees, clockwise positive.
        # ROS yaw: radians, counter-clockwise positive.
        self.yaw = normalize_angle(-math.radians(float(msg.data)))

    def _scan_callback(self, msg: LaserScan) -> None:
        self.scan = msg
        self._last_scan_time = time.monotonic()

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------
    def _spin_once(self, timeout_sec: float = 0.01) -> None:
        rclpy.spin_once(self, timeout_sec=timeout_sec)

    def _publish_twist(
        self, linear_x: float, angular_z: float, linear_y: float = 0.0
    ) -> None:
        twist = Twist()
        twist.linear.x = float(linear_x)
        twist.linear.y = float(linear_y)
        twist.angular.z = float(angular_z)
        self.cmd_pub.publish(twist)

    def _wait_for_pose(self, timeout_s: float = 5.0) -> bool:
        start = time.monotonic()
        while rclpy.ok() and time.monotonic() - start < timeout_s:
            self._spin_once(0.05)
            if self.x is not None and self.y is not None and self.yaw is not None:
                return True
        return False

    def load_map(self) -> None:
        """Load the map if map mode is enabled. On failure, fall back to direct mode."""
        self.map_planner = None
        if not self.use_map:
            return
        try:
            self.map_planner = MapPlanner(self.map_path)
            self.get_logger().info(f"Loaded map: {self.map_path}")
        except Exception as exc:
            self.get_logger().warn(
                f"Map not loaded ({exc}); falling back to direct navigation"
            )
            self.use_map = False

    def _control_period_s(self) -> float:
        return 1.0 / max(self.control_rate_hz, 1.0)

    def _is_direction_blocked(self, direction_rad: float) -> bool:
        """Return True if the scan sees an obstacle in the given body direction."""
        if self.scan is None:
            return False
        if time.monotonic() - self._last_scan_time > self.scan_timeout_s:
            return False
        scan = self.scan
        if not scan.ranges:
            return False

        best = float("inf")
        angle = scan.angle_min
        increment = scan.angle_increment
        for distance in scan.ranges:
            if math.isfinite(distance) and scan.range_min < distance < scan.range_max:
                diff = normalize_angle(angle - direction_rad)
                if abs(diff) <= self.obstacle_cone_rad and distance < best:
                    best = distance
            angle += increment
        return best <= self.obstacle_stop_distance

    def recover_from_obstacle(
        self,
        backup_speed: float = 0.3,
        turn_speed: float = 1.0,
        duration_s: float = 0.6,
    ) -> SkillResult:
        """Back up and rotate to escape a blocked path, then stop."""
        start = time.monotonic()
        period = self._control_period_s()

        end = time.monotonic() + duration_s
        while rclpy.ok() and time.monotonic() < end:
            self._publish_twist(-abs(backup_speed), 0.0, 0.0)
            self._spin_once(period)

        end = time.monotonic() + duration_s
        while rclpy.ok() and time.monotonic() < end:
            self._publish_twist(0.0, turn_speed, 0.0)
            self._spin_once(period)

        self.stop(0.3)
        return SkillResult(
            success=True,
            reason="obstacle_recovery_completed",
            elapsed_time_s=time.monotonic() - start,
        )

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------
    def stop(self, duration_s: float = 0.5) -> SkillResult:
        """Safely stop the robot by publishing zero velocity for a short time."""
        start = time.monotonic()
        while rclpy.ok() and time.monotonic() - start < duration_s:
            self._publish_twist(0.0, 0.0)
            self._spin_once(self._control_period_s())
        self._publish_twist(0.0, 0.0)
        return SkillResult(
            success=True,
            reason="stopped",
            elapsed_time_s=time.monotonic() - start,
        )

    def navigate_to(
        self,
        x: float,
        y: float,
        theta: float = 0.0,
        timeout_s: Optional[float] = None,
        use_map: Optional[bool] = None,
    ) -> SkillResult:
        """Navigate to a target pose.

        If map navigation is enabled and a path can be planned, the path is
        followed by the direct controller. Otherwise the direct controller is
        used, so pure LLM/direct navigation remains available.
        """
        use_map_enabled = self.use_map and self.map_planner is not None
        if use_map is not None:
            use_map_enabled = bool(use_map) and self.map_planner is not None
        if use_map_enabled:
            result = self._navigate_with_map(x, y, theta, timeout_s)
            if result is not None:
                return result
        return self._navigate_direct_to(x, y, theta, timeout_s)

    def _navigate_with_map(
        self,
        x: float,
        y: float,
        theta: float = 0.0,
        timeout_s: Optional[float] = None,
    ) -> Optional[SkillResult]:
        if not self._wait_for_pose(timeout_s=5.0):
            return SkillResult(success=False, reason="no_pose", elapsed_time_s=0.0)
        if self.x is None or self.y is None:
            return None
        try:
            path = self.map_planner.plan(
                (float(self.x), float(self.y)),
                (float(x), float(y)),
                float(theta),
            )
        except Exception as exc:
            self.get_logger().warn(f"Map planning failed: {exc}")
            return None
        if not path:
            self.get_logger().warn(
                "No map path found; falling back to direct navigation"
            )
            return None

        start = time.monotonic()
        last_index = -1
        for index, (wx, wy, wt) in enumerate(path):
            remaining = None
            if timeout_s is not None:
                remaining = max(2.0, float(timeout_s) - (time.monotonic() - start))
            result = self._navigate_direct_to(wx, wy, wt, timeout_s=remaining)
            if not result.success:
                self.stop()
                return SkillResult(
                    success=False,
                    reason=f"map_{result.reason}",
                    elapsed_time_s=time.monotonic() - start,
                    position_error_m=result.position_error_m,
                    heading_error_rad=result.heading_error_rad,
                    last_reached_index=last_index,
                    total_waypoints=len(path),
                )
            last_index = index

        return SkillResult(
            success=True,
            reason="map_reached",
            elapsed_time_s=time.monotonic() - start,
            last_reached_index=last_index,
            total_waypoints=len(path),
        )

    def _navigate_direct_to(
        self,
        x: float,
        y: float,
        theta: float = 0.0,
        timeout_s: Optional[float] = None,
    ) -> SkillResult:
        """Move the robot to (x, y, theta) with independent PID controllers.

        The RoboMaster base is holonomic: it can translate in body-frame x/y
        without first rotating.  We therefore translate directly to the target
        using linear.x/linear.y and only rotate in place for the final heading.

        Three PID controllers run independently:
          - world-frame x error -> vx_world
          - world-frame y error -> vy_world
          - heading error       -> omega
        """
        if not self._wait_for_pose(timeout_s=5.0):
            return SkillResult(
                success=False,
                reason="no_pose",
                elapsed_time_s=0.0,
            )

        if timeout_s is None:
            timeout_s = self.timeout_s

        start = time.monotonic()
        period = self._control_period_s()
        last_time = start

        # PID state
        integral_x = 0.0
        integral_y = 0.0
        integral_theta = 0.0
        prev_ex: Optional[float] = None
        prev_ey: Optional[float] = None
        prev_theta_error: Optional[float] = None

        while rclpy.ok():
            self._spin_once(period)
            if self.x is None or self.y is None or self.yaw is None:
                continue

            now = time.monotonic()
            dt = max(now - last_time, 1e-3)
            if dt > 0.5:
                dt = 0.5
            last_time = now

            dx = float(x) - self.x
            dy = float(y) - self.y
            distance_error = math.hypot(dx, dy)
            theta_error = normalize_angle(float(theta) - self.yaw)

            if (
                distance_error <= self.pos_tol_m
                and abs(theta_error) <= self.heading_tol_rad
            ):
                self._publish_twist(0.0, 0.0)
                self._spin_once(0.2)
                return SkillResult(
                    success=True,
                    reason="reached",
                    elapsed_time_s=time.monotonic() - start,
                    position_error_m=distance_error,
                    heading_error_rad=abs(theta_error),
                )

            if time.monotonic() - start > float(timeout_s):
                self.stop()
                return SkillResult(
                    success=False,
                    reason="timeout",
                    elapsed_time_s=time.monotonic() - start,
                    position_error_m=distance_error,
                    heading_error_rad=abs(theta_error),
                )

            if distance_error > self.pos_tol_m:
                # Position PID: world-frame x/y axes. The heading integrator is
                # reset while translating so a later rotation starts cleanly.
                integral_theta = 0.0
                prev_theta_error = None

                if prev_ex is None:
                    prev_ex = dx
                    prev_ey = dy

                integral_x += dx * dt
                integral_y += dy * dt
                integral_x = clamp(
                    integral_x, -self.integral_max_v, self.integral_max_v
                )
                integral_y = clamp(
                    integral_y, -self.integral_max_v, self.integral_max_v
                )

                derivative_x = (dx - prev_ex) / dt
                derivative_y = (dy - prev_ey) / dt
                prev_ex = dx
                prev_ey = dy

                vx_world = clamp(
                    self.k_v * dx
                    + self.k_i_v * integral_x
                    + self.k_d_v * derivative_x,
                    -self.v_max,
                    self.v_max,
                )
                vy_world = clamp(
                    self.k_v * dy
                    + self.k_i_v * integral_y
                    + self.k_d_v * derivative_y,
                    -self.v_max,
                    self.v_max,
                )

                # Rotate world-frame velocity into the robot body frame.
                cos_yaw = math.cos(self.yaw)
                sin_yaw = math.sin(self.yaw)
                vx_body = cos_yaw * vx_world + sin_yaw * vy_world
                vy_body = -sin_yaw * vx_world + cos_yaw * vy_world

                motion_direction = math.atan2(vy_body, vx_body)
                if self._is_direction_blocked(motion_direction):
                    self.stop()
                    return SkillResult(
                        success=False,
                        reason="obstacle_blocked",
                        elapsed_time_s=time.monotonic() - start,
                        position_error_m=distance_error,
                        heading_error_rad=abs(theta_error),
                    )

                self._publish_twist(vx_body, 0.0, vy_body)
            else:
                # Heading PID: position reached, rotate in place. Position
                # integrators are reset while rotating.
                integral_x = 0.0
                integral_y = 0.0
                prev_ex = None
                prev_ey = None

                if prev_theta_error is None:
                    prev_theta_error = theta_error

                integral_theta += theta_error * dt
                integral_theta = clamp(
                    integral_theta,
                    -self.integral_max_theta,
                    self.integral_max_theta,
                )
                derivative_theta = (theta_error - prev_theta_error) / dt
                prev_theta_error = theta_error

                omega = clamp(
                    self.k_theta * theta_error
                    + self.k_i_theta * integral_theta
                    + self.k_d_theta * derivative_theta,
                    -self.omega_max,
                    self.omega_max,
                )
                self._publish_twist(0.0, omega, 0.0)

    def follow_waypoints(
        self,
        waypoints: Sequence[Any],
        timeout_per_waypoint: Optional[float] = None,
    ) -> SkillResult:
        """Visit a sequence of waypoints.

        A waypoint may be:
            - dict with keys x, y, theta
            - tuple/list (x, y, theta)
        """
        start = time.monotonic()
        last_reached_index = -1
        total = len(waypoints)

        for index, waypoint in enumerate(waypoints):
            if isinstance(waypoint, dict):
                wx = float(waypoint["x"])
                wy = float(waypoint["y"])
                wt = float(waypoint.get("theta", 0.0))
            else:
                wx = float(waypoint[0])
                wy = float(waypoint[1])
                wt = float(waypoint[2]) if len(waypoint) > 2 else 0.0

            result = self.navigate_to(
                wx, wy, wt, timeout_s=timeout_per_waypoint
            )
            if result.success:
                last_reached_index = index
            else:
                self.stop()
                return SkillResult(
                    success=False,
                    reason=result.reason,
                    elapsed_time_s=time.monotonic() - start,
                    position_error_m=result.position_error_m,
                    heading_error_rad=result.heading_error_rad,
                    last_reached_index=last_reached_index,
                    total_waypoints=total,
                )

        return SkillResult(
            success=True,
            reason="all_waypoints_reached",
            elapsed_time_s=time.monotonic() - start,
            last_reached_index=last_reached_index,
            total_waypoints=total,
        )
