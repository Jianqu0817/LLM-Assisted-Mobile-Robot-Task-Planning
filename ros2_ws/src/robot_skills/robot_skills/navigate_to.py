"""CLI entry point for navigate_to."""
import argparse
import json

import rclpy

from .skills import RobotSkills


def main(args=None):
    parser = argparse.ArgumentParser(description="navigate_to(x, y, theta)")
    parser.add_argument("--x", type=float, required=True)
    parser.add_argument("--y", type=float, required=True)
    parser.add_argument("--theta", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--map", dest="use_map", action="store_true", default=None)
    parser.add_argument("--no-map", dest="use_map", action="store_false")
    parser.add_argument("--map-path", type=str, default=None)
    parsed, _ = parser.parse_known_args(args)

    rclpy.init()
    node = RobotSkills()
    if parsed.use_map is not None or parsed.map_path is not None:
        if parsed.use_map is not None:
            node.use_map = parsed.use_map
        if parsed.map_path is not None:
            node.map_path = parsed.map_path
        node.load_map()
    try:
        result = node.navigate_to(parsed.x, parsed.y, parsed.theta, parsed.timeout)
        print(json.dumps(result.to_dict(), indent=2))
    finally:
        node.stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
