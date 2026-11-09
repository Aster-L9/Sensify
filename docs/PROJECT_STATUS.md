# Sensify: project status and engineering reference

Reference for developers picking up this repository. It records what exists, how it fits together, the rules the code relies on, and what is still open. Status as of 2026-10-22.

| Sprint | Status |
|---|---|
| 1. Platform foundation (auth, shell, dashboard, map, simulator) | Done |
| 2. Detection and evidence (scenarios, ML, trust, alerts, models) | Done; done-when verified in a browser for both roles |
| 3. Investigation and evaluation (incidents, root cause, MITRE, evaluation harness, reports, demo mode) | Done; evaluation e1 recorded (development: all 14 targets met; held-out: 7 of 15 missed) |

Health at the Sprint 3 close (2026-10-23): `pytest` 165 passed; `npx tsc --noEmit` clean; `npm run build` passes; browser walkthrough of both roles passed on the production build. The repository verification of this snapshot is recorded in `docs/SPRINT_3_IMPORT.md`. Dependencies, databases, generated data and trained models are not committed; `docs/SETUP.md` regenerates them.

Sprint 03 handover fixes (DH-01 to DH-10, 2026-10-26): see `docs/sprint3/handover-fixes.md` for decisions (pause/reset, insufficient evidence, alert time filter, validation outcomes) and test evidence. Binding Sprint 3 document: `docs/sprint3/design.md`. Binding Sprint 2 document: `docs/sprint2/design.md` (spec). The ML pipeline is described in `backend/ml/README.md` and the dataset card is written to `backend/ml/data/DATA_CARD.md` when the dataset is generated.

## 1. Rules the code depends on (do not break)

1. **The analysis never sees ground truth.** `backend/app/analysis/` may only use reported telemetry and observable events. `tests/test_isolation.py` parses imports to enforce this. Ground truth lives in `ground_truth_telemetry`, `scenario_ground_truth`, events with `observable = False`, and the scenario columns of `runs`.
2. **Analysts investigate blind.** For analysts, the API never returns a run's `scenario_type`, `method`, `target_segment`, `scenario_params`, `seed`, its ground truth, or the dashboard detection rate. That rate would reveal which runs carried a scenario, so analysts get `runs_flagged` instead. Admin-only checks use `require_admin` and read the role from the database row, not the JWT claim.
3. **Nothing beyond the reveal cutoff.** Every read endpoint clamps to the run's revealed ticks (section 4.2). Alerts for a playing run are rebuilt from per-tick results up to the cutoff, so a window never shows the future.
4. **The test split is for grading only.** Tuning uses the train and validation splits. Missed targets are reported as missed (v1 misses 2 of 8). Never re-tune after looking at test results.
5. **Accounts.** The seeded admin account must be kept. Signup always creates analysts; administrators add analysts or administrators with `POST /users`. Roles are only `admin` or `analyst`; email and password rules live in `app/services/accounts.py` for both paths. An admin cannot demote or deactivate themselves. `DELETE /users/{id}` returns 403 by design (account deletion is disabled); deactivate users instead.
6. **Do not edit the local database by hand.** `database/dummy.db` is created on the first backend start, and an older local database is migrated in place (section 4.7). For experiments, point `DATABASE_URL` at a copy.
7. **Model versions are never overwritten.** Each training run writes the next `backend/model_store/vN`; no trained model is committed to Git. Artifact paths in the database are relative to the model store.
8. **UI language.** Sentence case everywhere; no all-caps eyebrow labels and no middle-dot meta strings. Colour is never the only cue: every state also has a pattern, icon or word. State colours: normal indigo `#7169D5`; anomalous amber `#D97706` (text `#B45309`); low trust rose `#BE185D`, drawn dashed. Severity colours: medium `#B45309`, high `#C2410C`, critical `#B91C1C`. Tokens live in `frontend/src/lib/detection.ts`.
9. **Wording.** Explanations are associative, never causal ("readings at SEG-03 repeat an earlier sequence", not "SEG-03 was hacked"). Classifications are worded as "possible". Sprint 3 follows the same rule.
10. **The investigation package is isolated.** `backend/app/investigation/` is pure: it may use only reported telemetry, observable events and analysis output, never ground truth. `tests/test_isolation.py` covers it as well as `app/analysis/`.
11. **The engine is frozen.** Version "i1" was tuned on the validation split only (min_score 0.35, margin 0.15, gap 36 ticks). `tests/test_engine_freeze.py` compares the engine's output with a snapshot, so an engine change fails the test. Re-tune only with `python -m ml.tune_engine --write-snapshot` and a new engine version.
12. **One look at held-out.** The held-out set (`ml/heldout/`) was built by an author isolated from the investigation code. Its labels are not changed after the first evaluation look and the engine is not tuned on it. Development and held-out results are never pooled. Missed targets are reported as missed.

## 2. Run, build and test

Requirements: Python 3.12 to 3.14; Node 18.17 or newer; Windows 10/11 or macOS 12 or newer (scientific wheels exist only for those). Full setup instructions are in `docs/SETUP.md`.

```bash
# backend (port 8000), from backend/
python -m venv venv && venv\Scripts\activate      # macOS: source venv/bin/activate
pip install -r requirements.txt                   # requirements-dev.txt adds pytest + httpx
uvicorn app.main:app --port 8000                  # do NOT use --reload on Windows (it hangs)

# frontend (port 3000), from frontend/
npm install && npm run dev                        # production: npm run build && npm start

# checks
python -m pytest -q                               # from backend/
npx tsc --noEmit --incremental false -p .         # from frontend/; --incremental false avoids a tsbuildinfo file

# data and model (from backend/)
python -m ml.generate_dataset                     # regenerates ml/data (seed 2026, byte-identical)
python -m ml.train [--trees 150 --samples 256 --alpha 0.004] [--activate]
python -m ml.generate_heldout                     # rebuilds ml/heldout (seed 4242)
python -m ml.tune_engine [--write-snapshot]       # tunes the engine on validation
python -m ml.evaluate --dataset both              # writes evaluations/eN
```

Logins: the seeded accounts take their passwords from `ADMIN_PASSWORD` and `ANALYST_PASSWORD` in `backend/.env`, which have no committed defaults. The Administrator sign-in sends `admin@sensify.local` itself; the analyst signs in as `analyst@sensify.local`.

## 3. Repository map

```
backend/
  app/
    main.py            lifespan: migrate -> create_all -> fail_interrupted_training -> seed; registers routers
    models.py          SQLAlchemy tables (section 4.7)
    schemas.py         pydantic request/response models (ScenarioLaunch, RunCreate, ...)
    auth.py            JWT (HS256), bcrypt, get_current_user, require_admin
    migrate.py         SCHEMA_VERSION = 4; v2 and v3 upgrade in place (runs and users kept); v1 is backed up and rebuilt, keeping users
    seed.py            segments, admin + demo analyst, ensure_seed_model, DEMO_RUNS (seeds 101-106)
    sim/               simulator (no analysis imports)
      topology.py      6 segments, physical constants, PUMP_IDX = 2, VALVE_IDX = 4
      hydraulics.py    quasi-steady solver for the chain (bisection)
      scenarios.py     CATALOG, validate_config (all launch rules), envelope, ScenarioConfig, MAX_SEED
      engine.py        simulate_run(cfg) -> RunData: actual, counterfactual, reported, events, labels
    analysis/          pure functions over ReportedRun; never imports ground truth
      frame.py         ReportedRun, ObservableEvent
      features.py      13 causal features per segment (+ valve_open at SEG-05, pump_speed at SEG-03)
      reference.py     ReferenceProfile fitted on normal runs (pair statistics, noise, limits)
      consistency.py   6 checks + plain-language check_messages
      trust.py         trust score/status/factors
      model.py         DetectorModel: per-segment IsolationForest, cross-fitted calibration, persistence
      threshold.py     threshold-alarm baseline (HI/LO limits + rate of change)
      windows.py       segment_state, flag_windows, build_alerts (summaries, severity), analysis_events
      pipeline.py      analyze_run(reported, model) -> AnalysisOutput
    investigation/     pure engine, version i1: groups alerts and events into classified, localised incidents with
                       evidence, timeline, attack-to-impact chain, MITRE ATT&CK for ICS context and verification checks
    reports/           pdf.py (fpdf2) and csv_export.py; fonts/ holds DejaVu Sans with its license
    services/
      runs.py          utcnow (patch THIS in tests), reveal, resolve_tick, launch_run, scoring_hook, run_out
      scoring.py       reported_from_db, score_run (persists results), results_grid, alerts_for_run
      registry.py      model store, load/activate/register, background training thread
      investigation.py incident persistence and lifecycle around the engine
      evaluations.py   evaluation runs and the ledger; demo.py: demo mode
    routes/            auth, users, topology, runs, telemetry, dashboard, activity,
                       scenarios, run_analysis, ml_models, alerts, incidents, evaluation, reports, demo
  ml/                  generate_dataset.py, dataset.py, metrics.py, train.py, targets.json, README.md, data/,
                       generate_heldout.py, heldout/, evaluate.py, incident_metrics.py, tune_engine.py, targets_investigation.json
  evaluations/e1/      shipped evaluation (report.md, results.json); loaded into the database on first start
  model_store/v1/      model.joblib (2.9 MB), metrics.json, report.md, manifest.json
  tests/               pytest suite (conftest: temp DB and model store per session, tiny_model, no_active_model)
frontend/src/
  app/                 Next.js app router pages (section 6)
  components/          AppShell, Sidebar, TopBar, SegmentDetail, ui/ (KPITile, States, StatusBadge, Toast)
  components/detection/ PipelineSchematic (signature element), AnomalyBandChart, EventStrip, EventDrawer,
                       TrustIndicator, StateLegend, SeverityChip/KindIcons, RunPlayback, MetricTarget, chartFrame
  contexts/AuthContext.tsx   tokens in localStorage; isAdmin
  hooks/               usePolling (pauses when the tab is hidden), useRunData (run + series, polls while playing)
  lib/                 api.ts (typed client), types.ts (API shapes), detection.ts (styles, formatters),
                       scenarios.ts (builder limits/readouts mirroring the backend)
database/dummy.db      local SQLite database (not in Git); created or migrated on first start
docs/sprint2/, sprint3/  design.md (Sprint 3 also handover-fixes.md)
```

## 4. Backend architecture

### 4.1 Topology

Flow runs SEG-01 to SEG-06 (Dhahran to Jubail). Instruments read at each segment outlet, except SEG-01, whose receipt meter sits at the inlet so a leak at SEG-01 is visible. Nominal flow is 830 m³/h; inlet pressure is 78 bar and delivery pressure 62 bar.

| Code | Name | Type | Equipment |
|---|---|---|---|
| SEG-01 | Dhahran Terminal | terminal | inlet_control |
| SEG-02 | Pipeline Corridor A | pipeline | none |
| SEG-03 | Pump Station Alpha | pump_station | pump P-3 |
| SEG-04 | Pipeline Corridor B | pipeline | none |
| SEG-05 | Valve Station V-12 | valve_station | valve V-12 |
| SEG-06 | Jubail Industrial Terminal | terminal | delivery_control |

### 4.2 Run engine: simulate, then reveal

`launch_run` simulates the whole run, stores reported telemetry, ground truth and events, then scores it at once with the active model. Reads reveal it progressively:

`revealed_ticks = min(duration_ticks, floor(played_s * playback_speed / 5) + 1)`, where `played_s` is wall time since start minus `paused_seconds`, frozen at `paused_at` while paused. Status is `completed` once every tick is revealed, else `paused` or `active`. Admins pause, resume and reset (rewind the same run to T+00:00, paused) through `/runs/{id}/pause|resume|reset`.

Ticks are 5 s; runs last 10 to 30 min (default 20 min = 240 ticks); playback speeds are 1, 5, 10 or 20. Every viewer sees the same moment. The design has no background writer and survives restarts. Tests control time by monkeypatching `app.services.runs.utcnow`; call it as `runs_service.utcnow()`, never import it by name.

### 4.3 Scenarios (`app/sim/scenarios.py`)

| Type | Methods (allowed targets) | Strength (0.1 to 1) means |
|---|---|---|
| normal | none; demand drift plus routine authorized operator adjustments | n/a |
| physical_anomaly | leak, blockage (all segments) | leak of about 25 × m % of flow; resistance × (1 + 4m) |
| sensor_fault | erratic, stuck, drift (all); variable pressure or flow | spikes up to ±12m bar / ±120m m³/h; stuck ignores m; drift +10m bar / +100m m³/h |
| telemetry_manipulation | replay (SEG-01, 03, 05, 06); bias (all) | replay: recorded readings replayed **while the process is covertly changed** at the target's equipment; bias: ±8m bar on reported pressure |
| unauthorized_control | valve_close (SEG-05); pump_slowdown, pump_stop (SEG-03) | valve to (1 − 0.75m) open; pump to (1 − 0.4m) speed; stop ignores m |
| concealed_physical_incident | leak (all), with the target's readings held at normal-looking levels | as for a leak |

Timing: onset 1 to 28 min; ramp 0.5 to 5; active 1 to 25; recovery (2 min) optional; onset + ramp + active + recovery must be ≤ duration − 1 for event types. The seed is 0 to 2³¹ − 1 (random if omitted); the same seed and settings reproduce the same run. `validate_config` is the single authority for these rules; `frontend/src/lib/scenarios.ts` mirrors them for inline messages.

The engine also emits control, security, device and process events (some only probabilistically, for example a logged reporting-configuration change in 75 % of manipulation runs). Ground-truth labels per tick and segment come from comparing the run with a counterfactual run without the scenario.

### 4.4 Analysis (`app/analysis/`)

- **Features:** pressure, flow and temperature; differences to each neighbour; 6-tick spread; 5 s step; change against the previous 2 minutes. Everything is causal, so live and offline scoring agree.
- **Model:** one IsolationForest per segment (150 trees, 256 samples), trained only on normal runs. Calibration is cross-fitted: out-of-fold scores from 4 train folds plus validation normal runs, about 19,000 ticks per segment. It is set so a share α = 0.004 of normal ticks reach the threshold. Scores are mapped to 0 to 1 with the threshold at 0.5, scale (threshold − median) / 3. A tick is flagged when 3 of the last 4 scores reach the threshold (`PERSIST_K, PERSIST_N`).
- **Consistency checks:** `flow_balance` and `pressure_gradient` (pairwise z on 15 s means; warn at 4, fail at 8; the odd-one-out rule assigns the fault to the segment bad on both sides), `implausible_change`, `range`, `replay` (a 12-tick sequence repeats exactly), `flatline` (pressure *or* flow flat for 2 min).
- **Trust:** penalties neighbour_strong 0.45, neighbour_weak 0.20, implausible 0.35, replay 0.60, flatline 0.25, reporting_event 0.25 (counts for 5 min). An EMA with α 0.5 smooths the score. Status is Supported at ≥ 0.70, Review at ≥ 0.40, otherwise Contradicted. Every non-ok check carries a penalty (guarded by `test_every_failed_check_lowers_trust`). A segment-tick whose own pressure or flow is missing, with fewer than 4 of its last 6 readings, or with no reporting neighbour is **Insufficient** ("Not enough data"): no trust or anomaly score, state `insufficient`, never an alert window, never counted as questioned trust by the engine.
- **State per tick and segment:** `low_trust` if trust is not Supported, else `anomalous` if ML-flagged, else `normal`.
- **Alerts:** windows of non-normal state; gaps of up to 2 ticks merge; windows shorter than 2 ticks drop. Severity is critical if the peak is ≥ 0.9 or the lowest trust < 0.40, high if the peak is ≥ 0.7 or the lowest trust < 0.55, otherwise medium. Summaries say what was seen in plain language, with the check or trust detail.
- **Threshold baseline:** fixed HI/LO limits and a rate-of-change alarm per variable; kept only for comparison.

### 4.5 Scoring and model registry

- `score_run` writes `analysis_results` (per tick and segment: score, flag, trust, factors, checks, baseline, state), `alerts` and analysis events (`events.origin = 'analysis'`), and sets `run.model_version_id`.
- A run launched with no active model stays unscored. After a model is activated, `POST /runs/{id}/score` (the "Re-score with active model" button) scores it.
- Training (`POST /models/train`) runs in a daemon thread and writes `model_store/vN`. Versions are never auto-activated. `fail_interrupted_training` marks stale `training` rows failed at startup.
- With `GENERATE_IF_MISSING`, the dataset is generated if `ml/data` is absent.

### 4.6 Data and model results

- **Dataset (`ml/data`):** 220 runs. Train has 60 normal runs. Validation has 20 normal and 30 scenario runs. Test has 20 normal and 90 scenario runs. In total that is 316,800 telemetry rows (telemetry.csv.gz, 5.9 MB). The source spreadsheet `Sensify- Mock data.xlsx` was only a reference.
- **Model v1 meets 6 of 8 targets (`ml/targets.json`).** Missed: overall detection 84.4 % (goal 90 %) and the weakest type, sensor faults, 55.6 % (goal 75 %). Met: tick false-alarm rate 0.035 %, 0.15 false windows per normal run, window precision 98.8 %, median time to detect 20 s, compromised reporting caught 83.3 %, honest readings marked low trust 0.005 %.
- **Against the threshold baseline:** detection 84.4 % vs 71.1 %; 90th-percentile time to detect 52 s vs 520 s. The baseline localises better (64 % vs 38 %).

### 4.7 Database (SQLite) and migration

Tables: `meta` (schema version), `users`, `segments`, `runs`, `telemetry` (reported only), `ground_truth_telemetry`, `scenario_ground_truth`, `events`, `model_versions`, `analysis_results`, `alerts`, `incidents` (extended in schema 3 with classification, confidence, evidence, timeline and lifecycle status), `evaluation_runs` (the evaluation ledger), `activity_log`.

On startup, `migrate_if_needed` upgrades a version 2 or 3 database in place, keeping runs and users (v4 adds run playback columns and makes `analysis_results.trust_score` nullable by rebuilding that table). For a version 1 database (no `meta`) it copies the file to `<db>.sprint1.bak`, rebuilds the schema keeping users, and reseeds 6 analysed demo runs: normal, a leak at SEG-04, an erratic sensor at SEG-02, a replay at SEG-03, a valve closure at SEG-05, and a concealed leak at SEG-04. Later starts do nothing. The schema version is now 4. A 20-minute run stores about 4,300 rows (inserted in bulk).

## 5. API reference

All routes need a bearer token except `/auth/login`, `/auth/register` and `/auth/refresh`. "Admin" means `require_admin`.

| Method and path | Access | Notes |
|---|---|---|
| POST /auth/register, /auth/login, /auth/refresh | public | register always creates an analyst; access token 30 min, refresh 7 days |
| GET /auth/me; POST /auth/change-password | user | |
| GET/POST /users, PATCH /users/{id} | admin | DELETE /users/{id} always 403 |
| GET /topology | user | segments with coordinates, diameter, design pressure, equipment |
| GET /runs?status=&limit= (max 200) ; GET /runs/{id} | user | scenario fields and seed admin-only |
| POST /runs | admin | quick normal run |
| GET /runs/{id}/state?at= | user | per-segment state, readings, trust and factors at a tick (clamped) |
| GET /runs/{id}/events | user | observable events up to the cutoff |
| GET /runs/{id}/ground-truth | admin | |
| GET /telemetry?run_id=&segment_id=&from_tick=&to_tick=&limit= (max 5000) | user | reported values only, up to the cutoff |
| GET /runs/{id}/anomalies, /telemetry-trust, /consistency, /baseline-alarms | user | series up to the cutoff; empty when unscored |
| POST /runs/{id}/score | admin | 409 when no model is active |
| GET /scenarios | user | catalog, segments, speeds, defaults |
| POST /scenarios | admin | 400 with a readable message on invalid settings |
| GET /alerts?run_id=&segment_id=&severity=&kind=&from_tick=&to_tick=&limit= | user | newest first; `ongoing` for windows open at the cutoff; time range keeps windows that overlap it (inclusive) |
| POST /runs/{id}/pause, /resume, /reset | admin | shared playback control; 409 when the action does not apply |
| GET /models, /models/{id} | user | |
| POST /models/train, /models/{id}/activate | admin | train: trees 50 to 400, samples 64 to 1024, alpha 0.001 to 0.05; 409 if already training |
| GET /dashboard/summary | user | `detection` is null for analysts; `runs_flagged` for all. Sprint 3 adds `incidents_by_classification`, `open_investigations`, `latest_evaluation` and `demo_run_id` |
| GET /activity | user | analysts see an allow-list (run and scenario activity) |
| GET /incidents | user | filters and sort |
| GET /runs/{id}/incidents | user | incidents of one run |
| GET /incidents/{key}, then /evidence, /timeline, /trace, /mitre, /recommendations | user | |
| PATCH /incidents/{key} | user | lifecycle: Developing, Investigating, Resolved; any signed-in user; can reopen |
| POST /evaluation | admin | runs a new evaluation |
| GET /evaluation, /evaluation/latest, /evaluation/{id} | user | |
| GET /reports/incident/{key}?format=pdf or csv | user | |
| GET /reports/evaluation/{id}?format=pdf or csv | user | |
| POST /demo | admin | starts the demo |
| GET /demo | user | demo state for the guide |

## 6. Frontend pages

| Route | Roles | Contents |
|---|---|---|
| `/`, `/login`, `/register` | public | role toggle (admin: password only); analyst signup |
| `/dashboard` | both | live line (schematic), KPI tiles, 14-day alert chart, readings in doubt, recent runs, activity; a Sprint 3 row with incidents by classification, open investigations and the latest evaluation; demo guide (admin "Start demo", analyst "Follow the demo") |
| `/map` | both | Leaflet map coloured by state; run selector; playback; segment panel; URL state `?run=&t=&seg=` (bad values fall back with a notice) |
| `/runs`, `/runs/[id]` | both | run list; run view with anomaly band charts, event strip, trust, checks, alerts, playback, URL state; admin-only ground-truth overlay and re-score |
| `/incidents`, `/incidents/[key]` | both | incident list with filters; incident view with classification, evidence, timeline, attack-to-impact chain, MITRE context, verification checks, recommendations, lifecycle and report download |
| `/evaluation` | both view, admin runs | systems A, B and C on development and held-out data, targets, confusion, report download |
| `/alerts` | both | filters (run, segment, reason, severity) in the URL; windows grouped by run |
| `/scenarios` | admin | type cards, schematic target picker, strength readout, timing preview, launch summary |
| `/models` | admin | active model against targets, train panel with live status, versions with Set active, ML vs baseline detail |
| `/admin/users`, `/profile` | admin / both | user management; password change |

The sidebar has Incidents and Evaluation entries. Non-admins who open `/scenarios`, `/models` or `/admin/users` see "Access Restricted", and the API refuses them independently.

## 7. Environment variables (`backend/.env`, template in `.env.example`)

`DATABASE_URL` (default `sqlite:///../database/dummy.db`), `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_USERNAME`, `SEED_DEMO_RUNS`, `MODEL_STORE_DIR`, `SENSIFY_DATASET_DIR`. Frontend: `NEXT_PUBLIC_API_URL` in `frontend/.env.local`. `.env` files are git-ignored.

## 8. Known limitations (documented, accepted)

- Held-out misses (evaluation e1, system C, 72 runs): event detection 71.7 % (goal 90 %), lowest per-scenario detection rate 0.583 (goal 0.75), median time to detect 75 s (goal 60 s), compromised-reporting detection 0.750 (goal 0.8), incident detection 80.0 % (goal 90 %), classification accuracy 73.2 % (goal 80 %) and OT layer accuracy 66.7 % (goal 80 %). These are reported as missed. On development data the hybrid met all 14 targets.
- On held-out data, 3 of 7 physical-anomaly runs were reported as normal behaviour, and 4 of 7 reporting-inconsistency runs as sensor fault.
- Sensor faults are the weakest type: drift or a frozen value inside the normal range looks normal.
- Localisation: process changes travel along the line, so neighbouring segments are often flagged together (including during a replay, because it hides a real process change).
- Held states fade: after a change such as a valve driven closed, the score settles below the threshold within about 2 minutes while the change persists. The unauthorized command stays on the event strip.
- Concealment at SEG-01 and SEG-06 is harder to expose, because those segments have only one neighbour.
- The threshold baseline raises rate alarms at replay loop seams (realistic; kept).

## 9. Deferred minor issues (open)

- `next build` skips ESLint: eslint 9 and eslint-config-next 16 are incompatible with Next 14.2's `next lint`. The build still passes. Fixing it means downgrading devDependencies (eslint 8, eslint-config-next 14.2), which may surface lint errors that then fail the build.
- `start_training` checks for a running job, then inserts. Two simultaneous POSTs can produce a 500 instead of a 409.
- `/runs`, `/alerts` and `/dashboard/summary` work over every run, so cost grows linearly with run count. The UI requests at most 200 runs.
- Small duplication: `GRACE_TICKS`, the scenario `DEFAULTS`, and unused Sprint 1 schemas.
- There is no "delete run" endpoint, although the Sprint 1 brief lists delete as an admin action.

## 10. Next steps

- Improve held-out detection and OT layer accuracy. Any engine change needs a new engine version and tuning on validation only. The current held-out set has had its one look, so a fresh one is needed to claim a result.
- An LLM is not used. If one is added, use it only as an optional, labelled narrative over computed evidence, with a template fallback and off by default. Classification, localisation, MITRE mapping and recommendations stay rule-based and reproducible.

## 11. Gotchas

- Windows: stopping a background `npm run dev`/`npm start` shell can leave the node child holding port 3000. Find it by port, check its command line, then kill it. A stray dev server writes into `.next` and corrupts a concurrent `npm run build`.
- `uvicorn --reload` hangs on Windows; restart manually.
- pandas must read the dataset CSVs with `keep_default_na=False, na_values=[""]`, otherwise the literal values `n/a` and `None` turn into NaN (handled in `ml/dataset.py`).
- `tsc` without `--incremental false` leaves `tsconfig.tsbuildinfo` in `frontend/`; delete it if created.
- Browser testing with Playwright writes `.playwright-mcp/` into the project root; delete it afterwards.
- A `.sprint1.bak` file appears next to the database after the first start; `*.bak` is git-ignored.
