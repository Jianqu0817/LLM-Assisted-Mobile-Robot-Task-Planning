"""CLI entry point for follow_waypoints."""
import argparse
import json

import rclpy

from .skills import RobotSkills


def main(args=None):
    parser = argparse.ArgumentParser(description="follow_waypoints(waypoints)")
    parser.add_argument(
        "--waypoints",
        type=str,
        required=True,
        help='JSON list, e.g. \'[{"x":-0.3,"y":-1.0,"theta":0.0}]\'',
    )
    parser.add_argument("--timeout-per-waypoint", type=float, default=None)
    parser.add_argument("--map", dest="use_map", action="store_true", default=None)
    parser.add_argument("--no-map", dest="use_map", action="store_false")
    parser.add_argument("--map-path", type=str, default=None)
    parsed, _ = parser.parse_known_args(args)

    waypoints = json.loads(parsed.waypoints)

    rclpy.init()
    node = RobotSkills()
    if parsed.use_map is not None or parsed.map_path is not None:
        if parsed.use_map is not None:
            node.use_map = parsed.use_map
        if parsed.map_path is not None:
            node.map_path = parsed.map_path
        node.load_map()
    try:
        result = node.follow_waypoints(
            waypoints, timeout_per_waypoint=parsed.timeout_per_waypoint
        )
        print(json.dumps(result.to_dict(), indent=2))
    finally:
        node.stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
