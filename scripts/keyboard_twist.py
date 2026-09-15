#!/usr/bin/env python3
"""Keyboard teleop with the same keys as webots_ros2_robomaster/keyboard_twist.py.

The only difference from the reference script is the default speed constants:
the reference uses LINEAR_SPEED = 0.2 m/s and ANGULAR_SPEED = 2.0 rad/s.
Here the defaults are 3x the original linear command and 2x the original
angular command, giving a moderate mapping speed.
"""
import argparse
import sys
import termios
import tty

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


class KeyboardPublisher(Node):
    def __init__(self, topic_name: str, linear: float, angular: float) -> None:
        super().__init__("keyboard_cmd_vel_publisher")
        self.publisher_ = self.create_publisher(Twist, topic_name, 10)
        self.linear = linear
        self.angular = angular
        self.get_logger().info(
            f"Publishing to {topic_name}; "
            f"linear={self.linear} m/s, angular={self.angular} rad/s"
        )

    def get_key(self) -> str:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            key = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return key

    def run(self) -> None:
        self.get_logger().info(
            "Keys: [W] forward, [S] back, [A] left, [D] right, "
            "[Q/E] rotate, [SPACE] stop, [C] quit"
        )
        try:
            while rclpy.ok():
                key = self.get_key().lower()
                twist = Twist()

                if key == "w":
                    twist.linear.x = self.linear
                elif key == "s":
                    twist.linear.x = -self.linear
                elif key == "a":
                    twist.linear.y = self.linear
                elif key == "d":
                    twist.linear.y = -self.linear
                elif key == "q":
                    twist.angular.z = self.angular
                elif key == "e":
                    twist.angular.z = -self.angular
                elif key == " ":
                    twist = Twist()
                elif key == "c":
                    return
                else:
                    continue

                self.publisher_.publish(twist)
        except KeyboardInterrupt:
            self.publisher_.publish(Twist())
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Keyboard teleop for the RoboMaster.")
    parser.add_argument(
        "--topic",
        type=str,
        default="/agent0/cmd_vel",
        help="Twist topic to publish.",
    )
    parser.add_argument("--linear", type=float, default=0.8)
    parser.add_argument("--angular", type=float, default=5.0)
    args = parser.parse_args()

    rclpy.init()
    node = KeyboardPublisher(args.topic, args.linear, args.angular)
    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
