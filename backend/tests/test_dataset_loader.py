import pandas as pd

from ml.dataset import load_dataset
from ml.generate_dataset import generate_dataset


def test_loader_keeps_literal_na_strings(tmp_path):
    generate_dataset(tmp_path, seed=7, n_train_normal=1, n_val_normal=1, n_val_scenario=1, n_test_normal=1, n_test_scenario=1)
    events = pd.read_csv(tmp_path / "events.csv", keep_default_na=False)
    run_id = pd.read_csv(tmp_path / "runs.csv")["run_id"].iloc[0]
    extra = {col: "" for col in events.columns}
    extra.update({"event_id": "EV-99999", "timestamp": "2026-09-01T00:00:10", "run_id": run_id, "tick": 2,
                  "segment_id": "SEG-02", "event_source": "Pressure Sensor", "category": "device",
                  "event_type": "Erratic sensor reading", "authorized": "n/a", "severity": "medium",
                  "details": "test", "observable": True})
    pd.concat([events, pd.DataFrame([extra])]).to_csv(tmp_path / "events.csv", index=False)

    runs = {r.run_id: r for r in load_dataset(tmp_path)}
    device = [e for e in runs[run_id].reported.events if e.event_type == "Erratic sensor reading"]
    assert device and device[0].authorized == "n/a"
    assert all(isinstance(e.authorized, str) for r in runs.values() for e in r.reported.events)
