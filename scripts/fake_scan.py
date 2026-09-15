#!/usr/bin/env python3
"""Publish a fake LaserScan with a close obstacle for Level 1 testing."""
import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


class FakeScan(Node):
    def __init__(self):
        super().__init__("fake_scan")
        self.pub = self.create_publisher(LaserScan, "/scan", 10)
        self.create_timer(0.01, self.publish)

    def publish(self):
        msg = LaserScan()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "LDS-01"
        msg.angle_min = -math.pi
        msg.angle_max = math.pi
        msg.angle_increment = 2.0 * math.pi / 180.0
        msg.time_increment = 0.0
        msg.scan_time = 0.01
        msg.range_min = 0.1
        msg.range_max = 10.0
        msg.ranges = [0.2] * 180
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = FakeScan()
    try:
        rclpy.spin(node)
    except BaseException:
        pass
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
