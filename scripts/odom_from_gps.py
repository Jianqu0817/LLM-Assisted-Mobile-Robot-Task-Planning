#!/usr/bin/env python3
"""Publish a smooth odometry estimate from Webots GPS + compass.

slam_toolbox expects nav_msgs/Odometry and an odom->base_link TF. The
RoboMaster reference world has no /agent0/odom, so we synthesize it from
ground-truth GPS and compass bearing. The odom frame is aligned with the
initial world pose; map->odom will be estimated by slam_toolbox.
"""
from __future__ import annotations

import math

import rclpy
from geometry_msgs.msg import PointStamped, TransformStamped, Twist, Pose, Quaternion
from nav_msgs.msg import Odometry
from rclpy.node import Node
from tf2_ros import TransformBroadcaster
from webots_ros2_msgs.msg import FloatStamped


def normalize_angle(a: float) -> float:
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a


class OdomFromGps(Node):
    def __init__(self) -> None:
        super().__init__("odom_from_gps")
        self.x = None
        self.y = None
        self.yaw = None
        self.last_x = None
        self.last_y = None
        self.last_yaw = None
        self.last_time = None

        self.create_subscription(PointStamped, "/agent0/gps", self._gps_cb, 10)
        self.create_subscription(
            FloatStamped, "/agent0/compass/bearing", self._bearing_cb, 10
        )
        self.odom_pub = self.create_publisher(Odometry, "/agent0/odom", 10)
        self.tf_broadcaster = TransformBroadcaster(self)
        self.create_timer(0.05, self._publish)

    def _gps_cb(self, msg: PointStamped) -> None:
        self.x = float(msg.point.x)
        self.y = float(msg.point.y)

    def _bearing_cb(self, msg: FloatStamped) -> None:
        self.yaw = normalize_angle(-math.radians(float(msg.data)))

    @staticmethod
    def _yaw_to_quat(yaw: float) -> Quaternion:
        q = Quaternion()
        q.z = math.sin(yaw * 0.5)
        q.w = math.cos(yaw * 0.5)
        return q

    def _publish(self) -> None:
        if self.x is None or self.y is None or self.yaw is None:
            return
        now = self.get_clock().now().to_msg()

        # Simple finite-difference twist.
        vx = vy = vth = 0.0
        if self.last_x is not None and self.last_time is not None:
            dt = max(1e-3, float(now.sec + 1e-9 * now.nanosec
                                 - self.last_time.sec
                                 - 1e-9 * self.last_time.nanosec))
            dx = self.x - self.last_x
            dy = self.y - self.last_y
            dyaw = normalize_angle(self.yaw - self.last_yaw)
            cos_y = math.cos(self.yaw)
            sin_y = math.sin(self.yaw)
            # World-frame velocity rotated into the current body frame.
            vx = (cos_y * dx + sin_y * dy) / dt
            vy = (-sin_y * dx + cos_y * dy) / dt
            vth = dyaw / dt

        self.last_x, self.last_y, self.last_yaw = self.x, self.y, self.yaw
        self.last_time = now

        q = self._yaw_to_quat(self.yaw)

        pose = Pose()
        pose.position.x = self.x
        pose.position.y = self.y
        pose.position.z = 0.0
        pose.orientation = q

        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_link"
        odom.pose.pose = pose
        odom.twist.twist = Twist()
        odom.twist.twist.linear.x = vx
        odom.twist.twist.linear.y = vy
        odom.twist.twist.angular.z = vth
        self.odom_pub.publish(odom)

        tf = TransformStamped()
        tf.header.stamp = now
        tf.header.frame_id = "odom"
        tf.child_frame_id = "base_link"
        tf.transform.translation.x = self.x
        tf.transform.translation.y = self.y
        tf.transform.translation.z = 0.0
        tf.transform.rotation = q
        self.tf_broadcaster.sendTransform(tf)


def main() -> int:
    rclpy.init()
    node = OdomFromGps()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
