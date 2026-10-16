# Sensify anomaly model v1

Trained 2026-10-11T18:51:59+00:00 in 18.05 s. Algorithm: per-segment Isolation Forest (feature spec `f1`), trained only on normal runs; evaluated on the held-out test split.

## Parameters

- `n_estimators`: 150
- `max_samples`: 256
- `alpha`: 0.004
- `random_state`: 2026

## Dataset

| Split | Runs by scenario type |
|---|---|
| train | normal: 60 |
| validation | concealed_physical_incident: 6, normal: 20, physical_anomaly: 6, sensor_fault: 6, telemetry_manipulation: 6, unauthorized_control: 6 |
| test | concealed_physical_incident: 18, normal: 20, physical_anomaly: 18, sensor_fault: 18, telemetry_manipulation: 18, unauthorized_control: 18 |

## Targets

| Target | Value | Goal | Met |
|---|---|---|---|
| Event detection rate (overall) | 0.8444 | >= 0.9 | **no** |
| Detection rate per scenario type (lowest) | 0.5556 | >= 0.75 | **no** |
| Tick false-alarm rate on normal runs | 0.0003472 | <= 0.01 | yes |
| False alert windows per normal run | 0.15 | <= 0.5 | yes |
| Window precision | 0.9884 | >= 0.8 | yes |
| Median time to detect (s) | 20 | <= 60 | yes |
| Compromised-reporting detection (trust) | 0.8333 | >= 0.8 | yes |
| Low-trust rate on honest runs | 4.96e-05 | <= 0.05 | yes |

## Detection by scenario type (ML vs threshold baseline)

| Scenario type | ML detected | Threshold baseline detected |
|---|---|---|
| concealed_physical_incident | 15/18 (83.3 %) | 10/18 (55.6 %) |
| physical_anomaly | 16/18 (88.9 %) | 13/18 (72.2 %) |
| sensor_fault | 10/18 (55.6 %) | 10/18 (55.6 %) |
| telemetry_manipulation | 18/18 (100.0 %) | 17/18 (94.4 %) |
| unauthorized_control | 17/18 (94.4 %) | 14/18 (77.8 %) |

## Other measures

| Measure | ML | Threshold baseline |
|---|---|---|
| Overall detection rate | 84.4 % | 71.1 % |
| Median / p90 time to detect | 20 s / 52 s | 35 s / 520 s |
| Tick false-alarm rate (normal runs) | 0.035 % | 0.0 % |
| False alert windows per normal run | 0.15 | 0.00 |
| Window precision | 98.8 % | 100.0 % |
| Localization hit rate | 38.2 % | 64.1 % |
| ROC-AUC (segment-tick) | 0.933 | n/a |

## Telemetry trust

- Compromised-reporting runs where the target lost trust: 83.3 % (54 runs)
- Low-trust rate on honest runs: 0.005 %

Missed targets are reported as missed. Scenario labels were used only to compute these figures.
