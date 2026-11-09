"""The curated demo run: a fixed scenario admins launch from the dashboard and analysts follow blind."""
DEMO_CONFIG = {
    "scenario_type": "unauthorized_control", "method": "valve_close", "target_segment": "SEG-05",
    "magnitude": 0.9, "onset_min": 2, "ramp_min": 0.5, "active_min": 4, "duration_min": 10,
    "playback_speed": 10, "seed": 1,
}
