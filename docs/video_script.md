# Demonstration Video Script (≤ 2 minutes)

Target length: 105–115 seconds. Narration in English or Chinese. Add subtitles.

| Time | Visual | Voice-over / subtitle |
|---:|---|---|
| 0:00–0:08 | Windows desktop with WSL terminal and Webots window | "This is an LLM-assisted robot task-planning system on ROS 2 Humble and Webots R2025a." |
| 0:08–0:20 | Show `ros2 launch webots_ros2_robomaster robot_launch.py`; controllers connect | "The reference simulation starts and both robot controllers connect through Webots IPC." |
| 0:20–0:32 | Show `ros2 topic list` and `ros2 topic echo /agent0/gps --once` | "The robot exposes GPS, compass, scan, and camera topics; the skill layer uses GPS and bearing." |
| 0:32–0:48 | Run `python3 -m agent.main "Go to storage." --log logs/success_storage.jsonl` | "The mock planner selects navigate_to. The validator accepts the call, and the robot reaches storage with a 4.9 cm position error." |
| 0:48–1:02 | Show the JSONL log lines: raw_plan, validation, skill_result, final_outcome | "Every step is logged: plan, validation, skill result, and final outcome." |
| 1:02–1:18 | Run `python3 -m agent.main "Visit storage, then workbench, and stop."` | "The multi-waypoint request is executed as follow_waypoints plus stop." |
| 1:18–1:34 | Run `python3 -m agent.main "Go to space_station."`; show rejection | "An out-of-workspace location is rejected before execution, and the recovery module asks for a valid location." |
| 1:34–1:48 | Run `python3 -m agent.main "Go to entrance and fly."`; show rejection | "An unknown skill is rejected by the allowlist." |
| 1:48–2:00 | Run the forced-timeout command; show retry and stop-and-report | "A navigation timeout is retried once. If it fails again, the robot stops safely and reports the failure." |

Notes:

- Use an interactive WSL terminal for keyboard teleoperation, not `wsl -e bash -lc`.
- Label any accelerated or pre-recorded segment.
- Keep the Webots window at 1280×800 for a responsive recording.
- Show the final GPS or the JSONL `final_outcome` for each scenario.

---

## Optional obstacle safety segment (12–15 s)

If time permits, add this segment to demonstrate Level 1:

1. Start the fake obstacle publisher:
   ```bash
   (timeout 1.5 python3 scripts/fake_scan.py &)
   sleep 0.3
   ```
2. Run:
   ```bash
   python3 -m agent.main "Go to storage." --max-retries 1 \
     --log logs/obstacle_recovery_success.jsonl
   ```
3. Show the log sequence:
   ```text
   skill_result: obstacle_blocked
   recovery_decision: backup_and_retry
   recovery_action: obstacle_recovery_completed
   skill_result: reached
   final_outcome: success
   ```
4. Optional failure branch: run the fake obstacle for a longer time and show:
   ```text
   skill_result: obstacle_blocked
   recovery_decision: backup_and_retry
   skill_result: obstacle_blocked
   recovery_decision: stop_and_report
   final_outcome: failure, "Target is blocked by an obstacle."
   ```

This demonstrates the safety stop and bounded recovery without modifying the
Webots world file.
