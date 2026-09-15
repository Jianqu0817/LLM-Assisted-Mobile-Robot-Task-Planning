"""CLI entry point for stop()."""
import json

import rclpy

from .skills import RobotSkills


def main(args=None):
    rclpy.init()
    node = RobotSkills()
    try:
        result = node.stop()
        print(json.dumps(result.to_dict(), indent=2))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
