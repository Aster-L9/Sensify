# Sensify detection model: data and training

Sensify flags a pipeline segment in two independent ways:

1. **Anomaly model.** One Isolation Forest per segment learns what normal operation looks like. It is trained only on normal runs, so it needs no labelled attacks or faults.
2. **Telemetry trust.** Rule-based physics checks compare each segment with its neighbours (flow balance, pressure gradient, implausible jumps, physical range, replayed sequences, flat readings). Each segment gets a trust score of Supported, Review or Contradicted.

A simple threshold alarm (fixed high/low limits and a rate-of-change limit) is evaluated alongside as a baseline, so the model's added value can be measured.

The analysis code (`app/analysis/`) sees only what the instruments report. It never reads ground truth; a test (`tests/test_isolation.py`) checks its imports to guarantee this.

## The mock dataset

The default generator produces 220 simulated 20-minute runs (train 60, validation 50, test 110) in `ml/data/`, using the same simulator as the app. Generated datasets and model binaries are excluded from Git. Details of the supplied evaluation dataset are preserved in the [Sprint 2 data card](../../docs/evaluation/sprint-2-v1/DATA_CARD.md); each new dataset also gets its own generated data card.

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
python -m ml.train --generate --activate # first setup: generate, train, register and activate
python -m ml.train                       # later: train the next version using existing data
python -m ml.train --trees 200 --samples 512 --alpha 0.004
python -m ml.train --activate            # also registers it in the app database and makes it active
```

An administrator can also train from the **Models** page in the app. Training runs in the background; duration depends on the machine and dataset. A new version is not activated until someone presses **Set active**.

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

## Supplied Sprint 2 evaluation (v1)

The supplied v1 evaluation records 6 of its 8 development targets met. Its [metrics, report, manifest and data card](../../docs/evaluation/sprint-2-v1/) are retained as an evaluation snapshot, separate from runtime artifacts. The two misses are reported as misses. These figures come from the supplied archive. A fresh generation/training run during import verification reproduced the archived metrics exactly. Different parameters or library versions may change results. The source pipeline separates train, validation and test splits; these development targets differ from the charter acceptance targets in the root README.

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
