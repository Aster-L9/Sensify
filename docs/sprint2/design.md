# Sensify Sprint 2 — Detection & Evidence: Design

Status: approved for implementation (2026-10-11). Source of scope: `sensify_sprint_breakdown.txt` (Sprint 2) and `Sensify- Mock data.xlsx`.

## 1. Goal and scope

**Goal:** the application surfaces what looks wrong (anomalies) and what looks untrustworthy (telemetry trust).

**Done when:** an admin launches an attack scenario from the UI, and both roles watch it light up the map and the dashboard.

In scope (all Sprint 2 items):

- Scenario injection: physical anomaly, sensor/device fault, and three cyber scenarios (telemetry manipulation, unauthorized control, concealed physical incident), each with ground-truth labels and a control/security event stream on the run's timebase.
- Analysis: an ML normal-behaviour model (training pipeline, versioning, per-segment anomaly scores), process-consistency checks, telemetry-trust scoring with contributing factors, and a threshold-monitoring baseline.
- Mock data: a seeded generator and a generated dataset large enough to train and evaluate on.
- Frontend: scenario builder, model management, alerts page, dashboard extensions, map states, anomaly bands, event strip, trust indicator.
- The Sprint 1 data-contract bugs that block these features (dashboard KPIs, run dates, run telemetry chart, segment panel fields).

Out of scope (Sprint 3): grouping alerts into incidents, root-cause classification, localization of OT layer, MITRE ATT&CK mapping, the held-out evaluation set and A/B/C harness, report export, demo mode.

## 2. Key decisions

| Decision | Choice | Why |
|---|---|---|
| Run engine | Simulate and score the whole run at launch, then **reveal** it at playback speed | Robust (no background writer, survives restarts), deterministic, easy to re-score; both roles see it unfold in sync |
| ML model | Per-segment **Isolation Forest** (scikit-learn) on causal window + neighbour features, trained only on normal runs | Light install, trains in seconds, standard and explainable; neighbour features catch "normal-looking but inconsistent" segments |
| Physics knowledge | Kept in a separate rule-based **consistency** layer, not inside the ML model | Lets Sprint 3 compare threshold vs ML-only vs hybrid cleanly |
| Units | bar, m³/h, °C everywhere | Matches the mock data and the labels the UI already shows |
| Ground truth | Separate tables and columns; the analysis package may not import them (enforced by a test) | Mock-data README: ground truth must never reach the analysis logic |
| Ground truth in the UI | Visible to admins only (they launched the scenario); analysts investigate blind | Keeps the analyst experience honest |
| Database | Schema version 2; on first start the old demo DB is backed up and rebuilt, **user accounts are kept** | No migration tool in the project; demo data is regenerated |
| Timebase | 5-second ticks; runs default to 20 simulated minutes (240 ticks) played at 10× | Mock data uses 5 s sampling; 2-minute demo |

## 3. Simulation

Code: `backend/app/sim/`. Pure Python + numpy; no database access. One entry point, `simulate_run(config) -> RunData`, is used by both the live app and the dataset generator, so training data and demo runs share one physics model.

### 3.1 Topology (config, matches mock-data SEG-01…06)

Flow direction SEG-01 → SEG-06. Each segment's instruments read at the segment **outlet**: pressure p (bar), flow q (m³/h), temperature T (°C). The one exception is SEG-01's flow meter, which is the inlet terminal's **receipt meter** at its inlet. Without it, a leak inside SEG-01 would be invisible, because the inlet header holds pressure. Nominal values at Q = 830 m³/h, valve fully open, pump at 100 %:

| Code | Name | Type | Length km | Nominal Δp (bar) | Outlet p (bar) | Equipment |
|---|---|---|---|---|---|---|
| SEG-01 | Dhahran Terminal | terminal (inlet) | 5.8 | 1.0 | 77.0 | inlet pressure control |
| SEG-02 | Pipeline Corridor A | pipeline | 12.3 | 3.0 | 74.0 | — |
| SEG-03 | Pump Station Alpha | pump_station | 3.5 | 0.5 loss, +4.5 pump | 78.0 | pump (speed %) |
| SEG-04 | Pipeline Corridor B | pipeline | 15.7 | 4.0 | 74.0 | — |
| SEG-05 | Valve Station V-12 | valve_station | 3.4 | 0.4 pipe + 0.6 valve | 73.0 | valve (opening %) |
| SEG-06 | Jubail Industrial Terminal | terminal (outlet) | 48.2 | 11.0 | 62.0 | delivery pressure control |

Source pressure P_src = 78.0 bar and delivery pressure P_del = 62.0 bar at nominal.

### 3.2 Hydraulics (quasi-steady, solved every tick)

- Pipe/station friction: Δp_i = k_i · q², with k_i = nominal Δp_i / 830².
- Pump head: H(q, s) = s² · 7.0 − h₂ · q², h₂ = (7.0 − 4.5) / 830², s = speed fraction (0 = stopped).
- Valve loss: Δp_v = k_v,open / max(open, 0.05)² · q², k_v,open = 0.6 / 830².
- Leak in segment j (at mid-segment): q_leak = C · √max(p_mid, 0); flow after the leak = q_upstream − q_leak.
- Blockage in segment j: k_j multiplied by (1 + 4·m·e(t)).
- Solve: march pressures from P_src through the chain for a trial upstream flow and bisect (40 iterations, bracket [0, 2000]) until the outlet pressure equals P_del.
- Dynamics: actual values follow the steady state through a first-order lag (τ = 10 s for p and q, 60 s for T).
- Temperature: inlet 45 °C with slow drift; each segment cools by 0.04 °C/km × L × (830 / q).

### 3.3 Normal behaviour (correlated, seeded, reproducible)

- Per-run operating point: P_src = 78 + U(−1.5, 1.5), P_del = 62 + U(−1.5, 1.5) → base flow ≈ 770–890 m³/h.
- Demand variation: P_del(t) gets a 0.5 bar sinusoid (period 8–15 min, random phase) plus AR(1) noise (φ 0.98, σ 0.05). P_src(t) gets AR(1) noise (φ 0.98, σ 0.03).
- Routine authorized operator actions: in 40 % of runs the valve is set to 85–95 % for 2–4 min; in 30 % the pump speed is set to 93–98 % for 3–5 min. Each logs authorized control events. These are normal behaviour.
- Reported value = actual + Gaussian noise (σ_p 0.08 bar, σ_q 1.5 m³/h, σ_T 0.05 °C), rounded to 0.01 bar / 0.1 m³/h / 0.01 °C.
- Independent RNG streams: environment, operator actions, measurement noise, scenario. This lets the engine re-simulate a **counterfactual** (same run, no injection) for labelling.

### 3.4 Scenario catalog

Common parameters: `target_segment`, `method`, `magnitude` m ∈ [0.1, 1.0], `onset_min` (default 6), `ramp_min` (1), `active_min` (6), `recovery` (default on; 2 min ramp down), `duration_min` (20; 10–30), `playback_speed` (1, 5, 10, 20; default 10), `seed`.

The effect envelope e(t) rises 0→1 over the ramp, holds at 1 while active, and falls 1→0 over recovery (or holds to the end if recovery is off).

| Type | Methods | Allowed targets | Actual process | Reported values at target | Observable events |
|---|---|---|---|---|---|
| `normal` | — | — | normal | honest | routine authorized commands |
| `physical_anomaly` | `leak`, `blockage` | all | leak: C = m·23.1·e(t) (≈ m × 25 % of flow); blockage: k × (1 + 4·m·e) | honest | none |
| `sensor_fault` | `erratic`, `stuck`, `drift`; variable `pressure` or `flow` | all | unchanged | erratic: spikes ±m·12 bar (±m·120 m³/h) on ~40 % of ticks; stuck: frozen at the last pre-onset value; drift: bias growing to m·10 bar (m·100 m³/h) | device diagnostic "Erratic sensor reading" (probability 0.5) |
| `telemetry_manipulation` | `replay`, `bias` | replay: SEG-01, 03, 05, 06; bias: all | replay: covert change at the target's equipment (SEG-01 P_src −m·6 bar; SEG-03 pump speed 1 − 0.35m; SEG-05 valve 1 − 0.7m; SEG-06 P_del +m·5 bar); bias: unchanged | replay: loops an exact copy of the target's own last 2 pre-onset minutes; bias: pressure ± m·8 bar | "Reporting configuration change", authorized unknown (probability 0.75) |
| `unauthorized_control` | `valve_close` (SEG-05), `pump_slowdown`, `pump_stop` (SEG-03) | SEG-05 or SEG-03 | valve steps toward 1 − 0.75m in 3 steps 10 s apart; pump speed → 1 − 0.4m, or 0 for stop | honest | "Valve/Pump command issued" authorized **no**; state-change events per step; security monitor "Command from unregistered workstation" (probability 0.6); authorized operator restore command at recovery |
| `concealed_physical_incident` | `leak` | all | leak as in physical anomaly | synthetic normal: pre-onset mean + fresh normal noise (no exact copies) | none |

Probabilistic evidence (events that may or may not be logged) is drawn from the scenario RNG, so it is reproducible per seed. It makes evidence realistically incomplete for Sprint 3.

### 3.5 Events

One stream per run with fields: `tick`, `timestamp`, `segment`, `source` (Control Layer, Valve V-12, Pump P-3, Reporting Source, Pressure Sensor, Security Monitor, Physical Process, Sensify Analysis), `category` (control, security, device, process, analysis), `event_type`, `authorized` (yes, no, unknown, n/a), `severity` (low, medium, high, critical), `details`, `observable`, `origin` (simulator or analysis).

Events only the simulator could know (e.g. "Leak begins") have `observable = false` and are ground truth. Analysis events are written by the scoring step (§5.7).

### 3.6 Ground truth

Per run (like the mock-data sheet Scenario_Ground_Truth): scenario type, method, target, `event_start_tick`, `event_peak_tick`, `event_end_tick`, expected root cause, manipulated signal/asset, notes.

Expected root cause: normal → Normal Behavior; physical anomaly → Physical/Process Anomaly; sensor fault → Sensor/Device Fault; telemetry manipulation and unauthorized control → Possible Cyber Manipulation; concealed incident → Physical/Process Anomaly + reporting inconsistency.

Per segment per tick: actual values, `phase`, `is_target`, `process_affected` and `reporting_compromised`.
- `phase` is one of baseline, onset, active, peak, recovery, recovered. Peak means the active ticks where the effect is at least 90 % of its maximum.
- `process_affected` is true when |actual − counterfactual| > 4σ for p or q.
- `reporting_compromised` is true when |reported − actual| > 4σ, or a replay/hold is active at that segment.

### 3.7 Playback (reveal)

A run stores `started_at` (wall clock at launch), `tick_seconds` = 5, `duration_ticks` and `playback_speed`. Tick i has timestamp `started_at + 5·i s` (simulated time).

revealed_ticks = min(duration_ticks, floor(elapsed_wall_seconds × speed / 5) + 1).

The run is `active` until all ticks are revealed, then `completed` (status is derived on read and persisted). Every run-scoped read returns only ticks < revealed_ticks; `?at=` may select an earlier tick. The UI labels time as elapsed run time (T+mm:ss).

## 4. Mock dataset and generator

Built by a dedicated subagent on top of `simulate_run`.

- CLI: `python -m ml.generate_dataset --out ml/data --seed 2026` (from `backend/`).
- Files (gzip CSV, column names follow the mock-data workbook):
  - `runs.csv`: run_id, split, scenario_type, method, target_segment, magnitude, onset/ramp/active/recovery, duration, seed, start_time.
  - `telemetry.csv.gz`: one row per run/segment/tick with timestamp, run_id, segment_id, tick, scenario_phase, actual_ and reported_ pressure_bar / flow_m3h / temperature_c, valve_state, pump_speed_pct, equipment_state, is_target, process_affected, reporting_compromised.
  - `events.csv`: the mock-data Control_Security_Events columns plus category, observable and tick.
  - `ground_truth.csv`: the mock-data Scenario_Ground_Truth columns plus ticks.
  - `DATA_CARD.md`: generation settings, split sizes, value ranges, and a calibration check against the workbook's baseline ranges (pressure 68–78 bar, flow 780–880 m³/h, 5 s cadence).
- Splits by run (no leakage):
  - `train`: 60 normal runs
  - `validation`: 20 normal + 30 scenario runs
  - `test`: 20 normal + 90 scenario runs
- Scenario runs cycle through every type, allowed target and method, with magnitude ~ U(0.3, 1.0), onset 4–10 min, active 4–8 min, and recovery on in 80 % of runs.
- The workbook's analysis columns (anomaly_score, telemetry_trust, incident_flag) are outputs of our system, so they are not part of the generated data.

## 5. Analysis

Code: `backend/app/analysis/`. Inputs are **reported** telemetry and **observable** events only. Every computation at tick t uses data from ticks ≤ t (causal), so precomputing a whole run gives the same answers a live system would.

### 5.1 Features (per segment, per tick)

Levels: p, q, T. Neighbour differences: p_up − p, p − p_down, q − q_up, q_down − q (0 where no neighbour). Short-window (6 ticks) std of p and q. One-tick absolute change of p and q. Change versus the mean of the previous 24 ticks for p and q (expanding window early in a run). Equipment state where present: valve opening and pump speed. Standardised with training means and stds.

### 5.2 ML normal-behaviour model

- One `IsolationForest` per segment (n_estimators 150, max_samples 256, random_state fixed), fitted on train-split normal runs. Normal runs are used for training the way an operator would select verified-normal history; scenario labels are used only for evaluation.
- Calibration per segment is **cross-fitted** on unseen normal ticks. Each of 4 training folds is scored by a forest fitted without it, and the validation normal runs are scored by the final forest (about 19,000 ticks per segment).
  - raw = −score_samples(x)
  - thr = quantile(raw, 1 − α), where α is the target tick false-alarm rate (default **0.004**, chosen on the validation split)
  - scale = (thr − median(raw)) / 3, so the median normal tick scores about 0.05
  - score = sigmoid((raw − thr) / scale)
  - **0.5 is the decision threshold** (drawn as the threshold line).
- Persistence: `ml_flag` at t when score ≥ 0.5 in at least **3 of the last 4** ticks.
- Why: calibrating on only the validation runs (2,400 ticks per segment) put the 99.5th-percentile threshold on about five extreme samples. False alarms then ran 3–5× above α, driven by routine authorized pump and valve changes.

### 5.3 Reference profile (learned from training data, stored with the model version)

Per adjacent pair: mean and std of the flow difference, and a fitted relation Δp ≈ a + b·q² with residual std. Per segment: noise std of p, q, T, and normal range limits. Used by the consistency checks and the threshold baseline.

### 5.4 Process-consistency checks (per segment, per tick)

Each check returns `ok`, `warn` or `fail`, a value, and a plain-language message:

1. **Flow balance** with each neighbour: z = (pair flow difference − mean) / std on a 3-tick mean; warn |z| > 4, fail > 8.
2. **Pressure gradient** with each neighbour: residual of the observed Δp against a + b·q²; same thresholds.
3. **Implausible change:** a one-tick jump > 6σ in p or q while both neighbours and the segment's other variable stay within 2σ.
4. **Range:** values outside physical limits (p < 0 or > 120 bar, q < 0 or > 2000 m³/h).
5. **Replay signature:** the last 12 reported (p, q) pairs exactly equal an earlier 12-tick sequence in the run.
6. **Flatline:** 24-tick std of p or of q < 0.25 × noise std. Either variable counts, because a stuck sensor freezes only the value it measures.

Pair checks are attributed to segments. A segment whose pair checks fail on **both** sides is the **odd one out** (strong attribution). Failing on one side only gives weak attribution to both members of that pair. Chain-end segments (SEG-01, SEG-06) have one side, so they can only receive weak attribution. Concealment at a chain end is therefore a genuinely hard case.

### 5.5 Telemetry trust (per segment, per tick)

Trust measures whether the **reported values are believable**. It is separate from whether the process is anomalous: an unauthorized valve closure is anomalous but trusted.

trust = clip(1 − Σ wₖ·sₖ, 0, 1), smoothed with EMA (α 0.5). Initial weights:

| Factor | From | Weight |
|---|---|---|
| Neighbour disagreement | checks 1–2: odd one out / one side only | 0.45 / 0.20 |
| Implausible change | check 3 (or 4) | 0.35 |
| Replay signature | check 5 | 0.60 |
| Flatline | check 6 | 0.25 |
| Reporting-path event | observable reporting-config change with unknown/no authorization on this segment in the last 5 min | 0.25 |

Status: **Supported** ≥ 0.70, **Review** 0.40–0.70, **Contradicted** < 0.40 (the mock data's three labels).

Every tick stores its contributing factors with a human-readable detail, e.g. "Reported flow 842 m³/h vs SEG-05 690 m³/h (−18 %)". Weights and persistence may be tuned on the **validation** split only.

### 5.6 Threshold baseline

Classic SCADA-style alarms, kept for comparison in Sprint 3. Per segment and variable: HI/LO limits = training mean ± 4σ (pooled across normal runs), plus a rate-of-change alarm at 6 noise σ per tick. Output: alarm windows per segment and variable.

### 5.7 Segment state, alerts and analysis events

- **Map state** at tick t: `low_trust` if trust status ≠ Supported, else `anomalous` if ml_flag, else `normal`.
- **Alerts** (flagged windows): consecutive non-normal ticks per segment, gaps ≤ 2 ticks merged, minimum 2 ticks.
  - Stored with start/end/peak tick, peak score, minimum trust, kinds (anomaly, low_trust), model version and a summary.
  - Severity: critical if peak ≥ 0.9 or min trust < 0.4; high if peak ≥ 0.7 or min trust < 0.55; else medium.
- **Analysis events** (`origin = analysis`, source Sensify Analysis), written to the event stream:
  - "High anomaly score" when a window starts and when it peaks ≥ 0.9
  - "Telemetry consistency warning" when a check starts failing
  - "Telemetry trust degraded" when trust status drops
- Scoring is a pure function `analyze_run(reported, observable_events, model_version) -> results, alerts, analysis_events`, persisted at launch and on re-score. Re-scoring replaces that run's results, alerts and analysis events.

## 6. Training pipeline, metrics and model registry

### 6.1 Pipeline

Code: `backend/ml/`. CLI from `backend/`: `python -m ml.train [--generate] [--trees 150] [--samples 256] [--alpha 0.005] [--register] [--activate]`. The same function runs from the API in a background thread.

Steps:
1. Load the dataset (generate it first if missing or `--generate`).
2. Split by run.
3. Build features.
4. Fit scalers and per-segment forests.
5. Calibrate on validation normal runs.
6. Build the reference profile and threshold limits.
7. Evaluate on the test split (ML-only, threshold baseline, and trust).
8. Write `model_store/vN/model.joblib` (compressed), `metrics.json` and `report.md`.
9. Optionally register and activate it in the database.

The repository ships **v1**, trained by this pipeline on the generated dataset, so the app works on first start.

### 6.2 Metrics (test split)

- **Event detection rate**, overall and per scenario type: a scenario run counts as detected if any `ml_flag` (any segment) falls within [event_start, event_end + 12 ticks]. For the threshold baseline, "flag" means any baseline alarm.
- **Time to detect:** median and 90th percentile of first flag − event_start, in seconds.
- **False-alarm rate:** flagged segment-ticks on normal runs, and false alert windows per normal run.
- **Window precision:** flagged windows overlapping an event window ÷ all flagged windows.
- **Localization hit rate:** detected events whose highest-scoring segment is the target.
- **ROC-AUC (segment-tick):**
  - Positives: target-segment ticks in the onset, active and peak phases.
  - Negatives: all normal-run segment-ticks.
- **Trust:** share of reporting-compromised runs where the target reaches Review/Contradicted during the compromise, and the low-trust rate on honest runs.

The same detection metrics are computed for the threshold baseline, for side-by-side comparison.

### 6.3 Targets (proposed; editable in `ml/targets.json`)

| Metric | Target |
|---|---|
| Event detection rate (overall) | ≥ 90 % |
| Detection rate per scenario type | ≥ 75 % |
| Tick false-alarm rate on normal runs | ≤ 1 % |
| False alert windows per normal run | ≤ 0.5 |
| Window precision | ≥ 80 % |
| Median time to detect | ≤ 60 s |
| Compromised-reporting detection (trust) | ≥ 80 % |
| Low-trust rate on honest runs | ≤ 5 % |

Results are reported honestly against the targets; a missed target is shown as missed, not hidden.

### 6.4 Registry

Each version has: version number, algorithm, params, dataset summary, feature-spec version, metrics, targets, status (training, ready, failed), is_active (exactly one), artifact path, created_by, created_at, training seconds and error. Activating a version does not re-score old runs automatically; admins can re-score a run.

## 7. Data model (SQLite, schema version 2)

| Table | Contents |
|---|---|
| `meta` | key/value; `schema_version = 2` |
| `users` | unchanged; **rows preserved** through migration |
| `segments` | id, code, name, segment_type, order_index, coordinates, length_km, diameter_mm, design_pressure_bar, equipment, config_json |
| `runs` | id, name, description, scenario_type, method, target_segment_id, scenario_params (JSON), seed, tick_seconds, duration_ticks, playback_speed, started_at, status, created_by, created_at, ended_at, model_version_id |
| `telemetry` | **reported only**: run, segment, tick, timestamp, pressure_bar, flow_m3h, temperature_c, valve_open_pct, pump_speed_pct, equipment_state |
| `ground_truth_telemetry` | actual values, phase, is_target, process_affected, reporting_compromised |
| `scenario_ground_truth` | per-run summary (§3.6) |
| `events` | §3.5 fields plus model_version_id for analysis events |
| `model_versions` | §6.4 |
| `analysis_results` | run, segment, tick, model_version_id, anomaly_score, ml_flag, trust_score, trust_status, trust_factors (JSON), checks (JSON), baseline_alarms (JSON), state |
| `alerts` | §5.7 |
| `activity_log` | unchanged; new actions: scenario_launched, model_trained, model_activated, run_rescored |

`control_events` and `security_events` are replaced by `events`. `incidents` is left untouched for Sprint 3.

**Migration on startup.** If `schema_version` ≠ 2:
1. Copy the database file to `dummy.db.sprint1.bak`.
2. Keep the `users` rows; drop and recreate every other table.
3. Seed.

**Seeding:**
- The six segments from the topology config.
- Default admin/analyst accounts, if missing.
- Model v1 registered and activated from `model_store/v1`.
- Six completed demo runs (one per scenario type, fixed seeds, started 1–5 days ago), scored with v1.

The old 30-second background simulator is removed.

## 8. API

All run-scoped reads apply the reveal cutoff. Roles: **both** = admin and analyst; **admin** = admin only (analysts get 403).

| Method & path | Role | Purpose |
|---|---|---|
| GET `/scenarios` | both | Catalog: types, methods, allowed targets, parameter ranges and defaults, descriptions |
| POST `/scenarios` | admin | Launch a scenario run: simulate, store, score with the active model; returns the run |
| GET `/runs`, `/runs/{id}` | both | Scenario fields (type, method, target, params) included for admins only; progress (revealed/duration) for all |
| GET `/runs/{id}/state?at=` | both | Per segment at a tick: reported values, anomaly score, trust score/status, state, open alerts |
| GET `/telemetry?run_id&segment_id&from_tick&to_tick` | both | Reported telemetry only |
| GET `/runs/{id}/events` | both | Observable and analysis events (filters: category, segment) |
| GET `/runs/{id}/anomalies` | both | Score series per segment, threshold, flagged windows |
| GET `/runs/{id}/consistency` | both | Check results per segment (series and latest) |
| GET `/runs/{id}/telemetry-trust` | both | Trust series and current contributing factors per segment |
| GET `/runs/{id}/baseline-alarms` | both | Threshold-baseline alarm windows |
| POST `/runs/{id}/score` | admin | Re-score the run with the active model |
| GET `/runs/{id}/ground-truth` | admin | Scenario summary and per-tick labels |
| GET `/alerts` | both | Flagged windows across runs; filters: run, segment, severity, kind, from/to, limit |
| GET `/models`, `/models/{id}` | both | Versions, metrics, targets (the page itself is admin-only) |
| POST `/models/train` | admin | Train a new version in the background; poll `/models/{id}` |
| POST `/models/{id}/activate` | admin | Set the active version |
| GET `/dashboard/summary` | both | Existing fields plus: anomaly count (24 h and total), detection rate {detected, total} (admins only; `null` for analysts), runs with findings {flagged, completed}, current trust alerts, alerts per day (14 days, by kind), active-run playback state, live averages from the active or latest run |
| GET `/topology` | both | Segments with the new fields |

The dashboard detection rate counts completed scenario runs (counting a run while it plays, or showing the figure to analysts, would reveal that a run carried a scenario). A run is detected if any alert (any segment) overlaps [event_start, event_end + 12 ticks]. It uses `scenario_ground_truth` for display only: it is an evaluation figure and never feeds the analysis.

## 9. Frontend

The UI is built with the **frontend-design** skill. It extends the existing Sensify identity (brand indigo, Inter + JetBrains Mono, light glass cards) rather than restyling the whole app.

### 9.1 Visual language for detection

- **States** (never colour alone; each has a pattern, an icon and a text label):
  - normal: brand indigo, solid line
  - anomalous: amber, thicker solid line, warning icon
  - low trust: magenta/rose, dashed line, shield icon
  - Review vs Contradicted: lighter vs full intensity
- **Anomaly band:** score area on a 0–1 axis under the telemetry chart, a dashed threshold line at 0.5, and shaded flagged windows across the telemetry chart.
- **Event strip:** a lane under the chart on the same x-axis. Marker shape and colour encode category, and authorized = no is outlined in red. Clicking a marker opens an event detail drawer.
- **Trust indicator:** a segmented meter (Supported / Review / Contradicted) with the score, plus the contributing factors in plain language with their weights.
- **Contrast:** colours meet WCAG AA contrast against the background.

### 9.2 Pages

- **Navigation:** Dashboard, Pipeline Map, Simulation Runs, **Alerts** (both), **Scenario Builder** (admin), **Models** (admin), User Management (admin), My Profile.
- **Scenario Builder** (`/scenarios`, admin):
  - Scenario type cards.
  - A clickable pipeline schematic for the target segment (invalid targets disabled).
  - Method selector and a magnitude slider with a type-specific label (e.g. "Leak ≈ 12 % of flow").
  - Timing controls, run length, playback speed and seed.
  - A timeline preview showing the baseline/onset/active/recovery bands.
  - Launch, which opens the live run view.
- **Models** (`/models`, admin):
  - Active model card with metrics against targets.
  - Train form (trees, samples, target false-alarm rate) with live training status.
  - Versions table with Set active.
  - Version detail: metric cards with target pass/fail, per-scenario detection bars (ML vs threshold baseline), time to detect, trust metrics and training configuration.
- **Alerts** (`/alerts`, both):
  - Filters: run, segment, severity, kind.
  - Table: severity, segment, run, T+start–end, duration, peak score, trust, summary.
  - Rows link to the run view at that tick. Live updates while a run plays.
- **Dashboard:**
  - Fix existing tiles with real values (average pressure and total flow from the active or latest run, segments by current state).
  - Add an anomaly-count tile, a detection-rate tile, a trust-alert panel (low-trust segments now, plus recent trust alerts with their top factor) and an anomalies-over-time chart (alerts per day, 14 days, by kind).
- **Map:**
  - A run selector and time scrubber (play/pause, Live), stored in the URL (`?run=&t=`).
  - Segments drawn by state, with a legend.
  - A rebuilt segment panel: values, valve/pump state, mini pressure/flow charts with the anomaly band, event strip and trust indicator.
- **Run detail** (`/runs/[id]`):
  - Header: playback progress, admin re-score button, admin ground-truth card.
  - Segment tabs, synchronized pressure and flow charts with the anomaly band, event strip and event drawer.
  - The run's alerts, a consistency summary, and toggleable baseline alarm markers.
- **Runs list:** dates fixed, scenario columns for admins, and a "Launch scenario" button.

Live views poll every 2 s while a run is active and stop when it completes; the dashboard polls every 5 s.

## 10. Testing and acceptance

**Backend (pytest, `backend/tests`, dev dependencies in `requirements-dev.txt`):**
- Simulator: same seed gives identical output; normal values stay within the calibrated ranges.
- Physics direction checks: valve closure → upstream p up, q down; leak → downstream q down; replay → exact copies.
- Counterfactual labels behave as specified.
- Ground-truth isolation: an AST import check on `app/analysis` and `ml` feature code.
- Feature causality: changing future ticks does not change features at t.
- Consistency checks, trust factors, windowing and metrics on handcrafted cases.
- API tests on a temporary database: roles, reveal cutoff (no future ticks), launch → scored results, train/activate with a tiny dataset, migration preserving users.

**ML:**
- A pipeline smoke test on a small generated dataset.
- A full pipeline run producing v1 and its report, with metrics compared to targets.

**Frontend:**
- `tsc --noEmit` and `next build`.
- A scripted browser walkthrough of the done-when scenario:
  1. The admin launches telemetry manipulation and unauthorized control from the builder.
  2. The target segments change state on the map and the dashboard counters move.
  3. The analyst sees the same.
  4. The analyst cannot open the admin pages.

## 11. Delivery phases

1. **Simulation and data foundation:** topology config, simulator, scenarios, events, ground truth, schema v2 with migration and seeding, launch and reveal APIs, and the dataset generator plus generated dataset (subagent).
2. **Analysis and ML:** features, Isolation Forest pipeline, calibration, consistency, trust, threshold baseline, alerts, registry and background training, analysis APIs, dashboard summary; train and ship v1; tune on validation; metrics report.
3. **Frontend** (frontend-design skill): shared detection components, builder, models, alerts, map, run detail, dashboard; fix Sprint 1 data bugs; browser walkthrough; docs (README, running instructions, ML README, data card).

New runtime dependencies: `numpy`, `pandas`, `scikit-learn`. Wheels must exist for Python 3.12–3.14; verify before pinning.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Isolation Forest misses subtle cases (small magnitudes, concealment at the last segment) | Neighbour features, persistence tuning on validation, consistency/trust layer; report misses honestly; ambiguous cases feed Sprint 3 |
| Database growth (~4,300 rows per run) | Bulk inserts; demo seed limited to 6 runs |
| Model artifact size | 150 trees × 256 samples × 6 segments, compressed joblib; target < 10 MB |
| Install size | numpy/pandas/scikit-learn wheels only; no deep-learning frameworks |
| Background training thread on Windows | Single short-lived thread; status persisted in `model_versions`; no auto-reload |
