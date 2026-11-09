# Sensify detection model: data and training

Sensify flags a pipeline segment in two independent ways:

1. **Anomaly model.** One Isolation Forest per segment learns what normal operation looks like. It is trained only on normal runs, so it needs no labelled attacks or faults.
2. **Telemetry trust.** Rule-based physics checks compare each segment with its neighbours (flow balance, pressure gradient, implausible jumps, physical range, replayed sequences, flat readings). Each segment gets a trust score of Supported, Review or Contradicted.

A simple threshold alarm (fixed high/low limits and a rate-of-change limit) is evaluated alongside as a baseline, so the model's added value can be measured.

The analysis code (`app/analysis/`) sees only what the instruments report. It never reads ground truth; a test (`tests/test_isolation.py`) checks its imports to guarantee this.

## The mock dataset

`ml/data/` holds 220 simulated 20-minute runs (train 60, validation 50, test 110), produced by the same simulator the app uses. Details, columns and the generation settings are in [data/DATA_CARD.md](data/DATA_CARD.md).

| Split | Used for |
|---|---|
| Train (60 normal runs) | Fitting the forests |
| Validation (20 normal and 30 scenario runs) | Calibrating the alarm threshold and tuning settings |
| Test (20 normal and 90 scenario runs) | Grading each trained version once; never used for tuning |

Regenerate it (same seed, same files) from `backend/` with the virtual environment active:

```bash
python -m ml.generate_dataset            # writes ml/data
python -m ml.generate_dataset --seed 7   # a different but equally valid dataset
```

## Training

From `backend/`:

```bash
python -m ml.train                       # trains the next version into model_store/vN and grades it
python -m ml.train --trees 200 --samples 512 --alpha 0.004
python -m ml.train --activate            # also registers it in the app database and makes it active
```

An administrator can also train from the **Models** page in the app. Training runs in the background and takes 10 to 30 seconds. A new version is not activated until someone presses **Set active**.

| Option | Default | Meaning |
|---|---|---|
| `--trees` | 150 | Trees per segment (50 to 400) |
| `--samples` | 256 | Samples per tree (64 to 1024) |
| `--alpha` | 0.004 | Target share of normal ticks that cross the alarm threshold (0.001 to 0.05) |
| `--generate` | off | Regenerate the dataset first |
| `--register` / `--activate` | off | Add the version to the app database / and make it active |

Each version is written to `model_store/vN/`:

- `model.joblib`: the forests, calibration and the reference profile used by the trust checks
- `metrics.json`: every measure on the test split
- `report.md`: the same results as a readable report
- `manifest.json`: parameters and headline figures

### What the pipeline does

1. Builds 13 features per segment and tick from the reported readings, using only the current and earlier ticks so live and offline scoring agree. The features are pressure, flow, temperature, the differences to each neighbour, the short-term spread, the 5-second step and the change against the last 2 minutes, plus valve opening at SEG-05 and pump speed at SEG-03.
2. Fits one Isolation Forest per segment on the 60 normal training runs.
3. Calibrates the alarm threshold on scores the forests did not train on: 4 out-of-fold passes over the training runs plus the 20 normal validation runs, about 19,000 ticks per segment. The threshold is set so that a share `alpha` of normal ticks cross it.
4. Requires 3 of the last 4 ticks above the threshold before flagging, which suppresses single-tick blips.
5. Grades the version on the test split against the targets in `targets.json`.

## Results of the shipped model (v1)

v1 meets 6 of its 8 targets. The two misses are reported as misses; the test split was not used to tune anything.

| Target | v1 | Goal | Met |
|---|---|---|---|
| Event detection rate, overall | 84.4 % | ≥ 90 % | No |
| Detection rate, weakest scenario type (sensor faults) | 55.6 % | ≥ 75 % | No |
| Tick false-alarm rate on normal runs | 0.035 % | ≤ 1 % | Yes |
| False alert windows per normal run | 0.15 | ≤ 0.5 | Yes |
| Window precision | 98.8 % | ≥ 80 % | Yes |
| Median time to detect | 20 s | ≤ 60 s | Yes |
| Compromised reporting caught by trust | 83.3 % | ≥ 80 % | Yes |
| Honest readings marked low trust | 0.005 % | ≤ 5 % | Yes |

Against the threshold baseline, the model detects more events (84.4 % against 71.1 %) and detects them sooner: 90 % within 52 s, against 520 s for the baseline. The baseline is better at naming the right segment (64 % against 38 %) and raised no false windows on normal runs.

### Known limitations

- **Sensor faults** are the hardest type: a drifting or frozen sensor that stays inside the normal range looks normal to the model. The trust checks catch some of these as inconsistent with the neighbours.
- **Localisation.** Real process changes travel along the line, so neighbouring segments are often flagged together. The model says *that* something happened more reliably than *where*.
- **Held states fade.** The model reacts strongly to a change, such as a valve being driven closed, but once the line settles at the new operating point the score can drop below the threshold while the change is still in place. The unauthorized command itself stays visible on the event timeline.
- **Concealment at the ends of the line** (SEG-01, SEG-06) is harder to expose because those segments have only one neighbour to compare with.

## Investigation engine

On top of the alerts, the investigation engine (`app/investigation/`, version i1) groups alerts and observable events into incidents. Each incident gets one of six outcomes: normal behaviour, possible physical/process anomaly, sensor/device fault, possible cyber manipulation, possible physical/process anomaly with reporting inconsistency, or uncertain. It also gets a localised segment, one or more OT layers (physical process, field device, control, reporting and telemetry), evidence, a timeline, an attack-to-impact chain, MITRE ATT&CK for ICS context and verification checks.

The engine is pure code. Like the analysis, it never sees ground truth, and `tests/test_isolation.py` checks its imports. Its settings were tuned on the validation split only and then frozen: min score 0.35, margin 0.15 and a gap of 36 ticks. `tests/test_engine_freeze.py` compares its output with a stored snapshot.

```bash
python -m ml.tune_engine                    # tunes on the validation split
python -m ml.tune_engine --write-snapshot   # also writes the freeze snapshot
```

## Held-out set

`ml/heldout/` has 72 runs, 20 of them ambiguous. It was built by `python -m ml.generate_heldout` (seed 4242) by an author isolated from the investigation code, with settings outside the development range (weaker strength, other onset times, longer ramps and runs). Labels come from scenario settings and observable events. See [heldout/HELDOUT_CARD.md](heldout/HELDOUT_CARD.md).

## Evaluation

`python -m ml.evaluate --dataset both` compares three systems and writes `evaluations/eN/` (`report.md` and `results.json`). Evaluation e1 ships with the app and is loaded into the database on first start.

| System | What it is |
|---|---|
| A. Threshold only | Fixed high/low limits and a rate-of-change alarm |
| B. ML only | The Isolation Forest anomaly flags alone |
| C. Full hybrid | Flags, trust checks and the investigation engine |

Two datasets are scored: the development test split (110 runs) and the held-out set (72 runs). They are never pooled. Detection, false-alarm and timing measures use the same functions as the model grading. Incident measures (incident detection, classification accuracy, decision coverage, ambiguity handled, segment localisation, OT layer accuracy, and incidents per normal run) compare each system's incidents with the run's labels, which are used only for scoring. Classification and layer accuracy apply to system C only. Ambiguous held-out runs count as handled when the outcome is one of the acceptable outcomes listed for that run. Targets are in `targets.json` (Sprint 2) and `targets_investigation.json` (Sprint 3).

The one-look rule: the held-out set is evaluated once the engine is frozen, its labels are not changed afterwards, and the engine is never tuned on it. Missed targets are reported as missed.

### Results of evaluation e1 (engine i1, model v1)

Development (test split, 110 runs). The hybrid met all 14 targets.

| Criterion | A. Threshold only | B. ML only | C. Full hybrid |
|---|---|---|---|
| Event detection | 64/90 (71.1 %) | 76/90 (84.4 %) | 83/90 (92.2 %) |
| False alert windows per normal run | 0.000 | 0.150 | 0.150 |
| Median time to detect (s) | 35.000 | 20.000 | 15.000 |
| Incident detection | 52/90 (57.8 %) | 75/90 (83.3 %) | 84/90 (93.3 %) |
| Classification accuracy | not available | not available | 60/70 (85.7 %) |
| Decision coverage | not available | not available | 70/84 (83.3 %) |
| Segment localisation | 35/52 (67.3 %) | 41/75 (54.7 %) | 72/75 (96.0 %) |
| OT layer accuracy | not available | not available | 61/75 (81.3 %) |
| Unexplained incidents per normal run | 0.000 | 0.150 | 0.100 |

Held-out (72 runs). The hybrid missed 7 of its 15 targets.

| Criterion | A. Threshold only | B. ML only | C. Full hybrid |
|---|---|---|---|
| Event detection | 13/60 (21.7 %) | 32/60 (53.3 %) | 43/60 (71.7 %) |
| False alert windows per normal run | 0.000 | 0.167 | 0.167 |
| Median time to detect (s) | 70.000 | 137.500 | 75.000 |
| Incident detection | 9/60 (15.0 %) | 30/60 (50.0 %) | 48/60 (80.0 %) |
| Classification accuracy | not available | not available | 30/41 (73.2 %) |
| Decision coverage | not available | not available | 41/48 (85.4 %) |
| Ambiguity handled | not available | not available | 14/20 (70.0 %) |
| Segment localisation | 9/9 (100.0 %) | 22/30 (73.3 %) | 41/45 (91.1 %) |
| OT layer accuracy | not available | not available | 30/45 (66.7 %) |
| Unexplained incidents per normal run | 0.000 | 0.167 | 0.000 |

Held-out targets for system C that were missed:

| Target | Value | Goal |
|---|---|---|
| Event detection rate (overall) | 0.717 | >= 0.9 |
| Detection rate per scenario type (lowest) | 0.583 | >= 0.75 |
| Median time to detect (s) | 75.000 | <= 60 |
| Compromised-reporting detection (trust) | 0.750 | >= 0.8 |
| Incident detection | 0.800 | >= 0.9 |
| Classification accuracy (decided incidents) | 0.732 | >= 0.8 |
| OT layer accuracy | 0.667 | >= 0.8 |

The other eight held-out targets were met, including decision coverage (0.854), ambiguous runs with an acceptable outcome (0.700, goal 0.6), segment localisation (0.911) and zero unexplained incidents per normal run. On held-out data, 3 of 7 physical-anomaly runs were reported as normal behaviour and 4 of 7 reporting-inconsistency runs as sensor fault. Segment localisation for A and B on held-out data rests on few runs (9 and 30), so read those figures with care. The complete tables and confusion matrices are in `evaluations/e1/report.md`.
