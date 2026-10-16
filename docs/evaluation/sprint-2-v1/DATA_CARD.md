# Sensify mock dataset: data card

Synthetic telemetry, control/security events and ground-truth labels for the six-segment Dhahran → Jubail pipeline (SEG-01 … SEG-06). Every run comes from the simulator the live app uses (`app.sim.engine.simulate_run`), so training data and demo runs share one physics model. The values are mock simulation values, not real measurements. Generator: `backend/ml/generate_dataset.py`.

## Generation

Run from `backend/`:

```
python -m ml.generate_dataset --out ml/data --seed 2026
```

| Setting | Value |
|---|---|
| Base seed | 2026 |
| Runs | 220: train 60, validation 50, test 110 |
| Run length | 20 simulated minutes = 240 ticks of 5 s (playback speed 10, which does not affect the data) |
| Start times | Run k (k = 0, 1, … in run-id order) starts at 2026-09-01T00:00:00 + k h; tick t is stamped start + 5 s × t |
| Run seeds | Unique, drawn without replacement from 0–999,999 by `numpy.random.default_rng(2026)`, which then draws the scenario parameters |
| Scenario parameters | magnitude ~ U(0.3, 1.0), 2 dp; onset ~ U{4, 4.5, …, 10} min; ramp 1 min; active ~ U{4, 4.5, …, 8} min, shortened when needed so the event and its recovery end at least 1 min before the run does; recovery on with probability 0.8 |
| Scenario mix | Each split cycles through the five non-normal types in turn. Within a type, runs cycle through every (method, allowed target) combination of the scenario catalog, and for sensor faults also the variable (pressure, flow). Methods are interleaved so that each recurs within a few runs. One counter per type continues from validation into test, so the two splits start at different combinations. |
| Software | numpy 2.5.4, pandas 3.0.6 |

Running the command again with the same seed and software regenerates identical data files.

## Files

| File | Rows | Size | Contents |
|---|---:|---:|---|
| `runs.csv` | 220 | 19.0 kB | One row per run: split, scenario parameters, seed, start time. Scenario parameters are blank for normal runs; `variable` applies to sensor faults only. |
| `telemetry.csv.gz` | 316,800 | 5.87 MB | One row per run × tick × segment, ordered by run, tick, segment: actual and reported pressure (bar), flow (m³/h) and temperature (°C); valve opening and pump speed in % (blank where the segment has no valve or pump); reported valve and equipment state; ground-truth labels. |
| `events.csv` | 631 | 95.0 kB | Control, security, device and process events on the run's timebase. `observable = False` marks ground-truth-only events. |
| `ground_truth.csv` | 220 | 37.1 kB | One row per run: scenario, target, event start/peak/end as timestamps and ticks (blank for normal runs), expected root cause, manipulated signal or asset, notes. |

Column notes:

- Ground truth, for labelling and evaluation only (the analysis must never read it): the `actual_*` telemetry columns, `scenario_phase`, `is_target`, `process_affected`, `reporting_compromised`, events with `observable = False`, `ground_truth.csv` and the scenario columns of `runs.csv`. The analysis sees the `reported_*` columns, `valve_state`, `equipment_state` and observable events.
- `actual_*` is the underlying process, rounded to 3 decimals. `reported_*` is what the instruments report (0.01 bar, 0.1 m³/h, 0.01 °C, 0.1 %).
- `scenario_phase` is one of baseline, onset, active, peak (active ticks with at least 90 % of the run's maximum effect), recovery, recovered.
- `is_target` marks the scenario's target segment. `process_affected` means actual pressure or flow differs from the same run without the scenario by more than 4σ. `reporting_compromised` means reported differs from actual by more than 4σ, or a replay or hold is active at the segment.
- `n/a` (events `authorized`) and `None` (`manipulated_signal_or_asset` of normal runs) are values, not missing data. pandas reads them as NaN by default; pass `keep_default_na=False, na_values=[""]` to keep them. Blank cells are missing values.

## Splits

Train, validation and test are split by run: every run (all its ticks, segments and events) belongs to exactly one split, so nothing leaks between them. Train holds only normal runs, from which the detector learns normal behaviour. Validation is for tuning, and test is for the reported metrics.

| Scenario type | Train | Validation | Test | Total |
|---|---:|---:|---:|---:|
| normal | 60 | 20 | 20 | 100 |
| physical_anomaly | 0 | 6 | 18 | 24 |
| sensor_fault | 0 | 6 | 18 | 24 |
| telemetry_manipulation | 0 | 6 | 18 | 24 |
| unauthorized_control | 0 | 6 | 18 | 24 |
| concealed_physical_incident | 0 | 6 | 18 | 24 |
| **Total** | **60** | **50** | **110** | **220** |

Scenario coverage (validation and test):

| Scenario type | Method | Variable | Validation | Test | Targets in validation | Targets in test |
|---|---|---|---:|---:|---|---|
| physical_anomaly | leak | – | 3 | 9 | SEG-01, SEG-02, SEG-03 | all six |
| physical_anomaly | blockage | – | 3 | 9 | SEG-01, SEG-02, SEG-03 | all six |
| sensor_fault | erratic | pressure | 1 | 3 | SEG-01 | SEG-02, SEG-03, SEG-05 |
| sensor_fault | erratic | flow | 1 | 3 | SEG-02 | SEG-01, SEG-04, SEG-06 |
| sensor_fault | stuck | pressure | 1 | 3 | SEG-01 | SEG-02, SEG-03, SEG-05 |
| sensor_fault | stuck | flow | 1 | 3 | SEG-02 | SEG-01, SEG-04, SEG-06 |
| sensor_fault | drift | pressure | 1 | 3 | SEG-01 | SEG-02, SEG-03, SEG-05 |
| sensor_fault | drift | flow | 1 | 3 | SEG-02 | SEG-01, SEG-04, SEG-06 |
| telemetry_manipulation | replay | – | 3 | 7 | SEG-01, SEG-03, SEG-05 | SEG-01, SEG-03, SEG-05, SEG-06 |
| telemetry_manipulation | bias | – | 3 | 11 | SEG-01, SEG-02, SEG-03 | all six |
| unauthorized_control | valve_close | – | 2 | 6 | SEG-05 | SEG-05 |
| unauthorized_control | pump_slowdown | – | 2 | 6 | SEG-03 | SEG-03 |
| unauthorized_control | pump_stop | – | 2 | 6 | SEG-03 | SEG-03 |
| concealed_physical_incident | leak | – | 6 | 18 | all six | all six |

## Value ranges

Reported values on the 100 normal runs (all splits), min / mean / max:

| Segment | Pressure (bar) | Flow (m³/h) | Temperature (°C) |
|---|---|---|---|
| SEG-01 Dhahran Terminal | 75.12 / 77.00 / 78.79 | 752.9 / 828.2 / 889.4 | 43.77 / 44.79 / 45.79 |
| SEG-02 Pipeline Corridor A | 72.37 / 74.01 / 75.64 | 752.1 / 828.2 / 888.7 | 43.29 / 44.30 / 45.29 |
| SEG-03 Pump Station Alpha | 76.10 / 77.99 / 79.68 | 751.5 / 828.2 / 889.9 | 43.16 / 44.16 / 45.15 |
| SEG-04 Pipeline Corridor B | 72.06 / 74.00 / 75.86 | 752.6 / 828.2 / 891.4 | 42.56 / 43.53 / 44.55 |
| SEG-05 Valve Station V-12 | 71.16 / 73.00 / 74.89 | 752.4 / 828.2 / 891.6 | 42.38 / 43.39 / 44.44 |
| SEG-06 Jubail Industrial Terminal | 59.48 / 62.03 / 64.73 | 752.0 / 828.2 / 889.0 | 40.38 / 41.46 / 42.56 |

## Events

| Category | Observable | Ground truth only | Total |
|---|---:|---:|---:|
| control | 388 | 24 | 412 |
| security | 35 | 48 | 83 |
| device | 14 | 24 | 38 |
| process | 0 | 98 | 98 |
| **Total** | **437** | **194** | **631** |

Observable events are the evidence a real monitoring system would have: operator and unauthorized commands, equipment state changes, security-monitor alerts, reporting-configuration changes and device diagnostics. Ground-truth-only events (`observable = False`, such as "Leak begins") record what actually happened and are for labelling and evaluation only.

## Calibration against the mock-data workbook

| # | Check | Criterion | Measured | Result |
|---|---|---|---|---|
| 1 | Cadence | Consecutive ticks of every run and segment are exactly 5 s apart (workbook: 5 s sampling) | 315,480 intervals; min 5 s, max 5 s | PASS |
| 2 | Flow | Median of the per-run mean reported flow on normal runs is within 780–880 m³/h (workbook baseline flows 800–853 m³/h) | 829.9 m³/h (per-run means 774.5–877.1 over 100 runs) | PASS |
| 3 | Pressure | Mean reported pressure on normal runs at the pipeline and valve segments SEG-02, SEG-04, SEG-05 each lies within 68–78 bar (workbook baseline 69.8–73.2 bar) | SEG-02 74.01 bar, SEG-04 74.00 bar, SEG-05 73.00 bar | PASS |
| 4 | Noise | Standard deviation of reported − actual pressure on normal runs is within 0.05–0.12 bar | 0.080 bar over 144,000 readings | PASS |

For information only, the mean reported pressure on normal runs at the line's control points: SEG-01 (inlet terminal) 77.00 bar, SEG-03 (pump station outlet) 77.99 bar, SEG-06 (delivery terminal) 62.03 bar. The inlet header and the pump discharge run above the corridor baseline and the delivery terminal runs below it, by design, so they are not compared with the workbook band.

4 of 4 checks pass.

## Not in this dataset

The workbook's analysis columns (anomaly_score, telemetry_trust, incident_flag) are outputs of the system, not part of the generated data. Sensify's analysis computes them from the reported telemetry and observable events.
