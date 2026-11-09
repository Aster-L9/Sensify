# Evaluation: engine i2, model v1

Created 2026-11-04T15:40:15+00:00. Development and held-out results are never pooled.

## Development (test split) (110 runs)

| Criterion | A. Threshold only | B. ML only | C. Full hybrid |
|---|---|---|---|
| Event detection | 64/90 (71.1 %) | 76/90 (84.4 %) | 83/90 (92.2 %) |
| Tick false-alarm rate on normal runs | 0.000 | 0.00035 | 0.00035 |
| False alert windows per normal run | 0.000 | 0.150 | 0.150 |
| Window precision | 1.000 | 0.988 | 0.989 |
| Median time to detect (s) | 35.000 | 20.000 | 15.000 |
| Incident detection | 52/90 (57.8 %) | 75/90 (83.3 %) | 84/90 (93.3 %) |
| Classification accuracy | not available | not available | 60/70 (85.7 %) |
| Decision coverage | not available | not available | 70/84 (83.3 %) |
| Ambiguity handled | not available | not available | not available |
| Segment localisation | 35/52 (67.3 %) | 41/75 (54.7 %) | 72/75 (96.0 %) |
| OT layer accuracy | not available | not available | 61/75 (81.3 %) |
| Incidents per normal run | 0.000 | 0.150 | 0.150 |
| Unexplained incidents per normal run | 0.000 | 0.150 | 0.100 |
| Incidents outside the event | 0 | 37 | 14 |

### Targets (system C)

| Target | Value | Goal | Result |
|---|---|---|---|
| Event detection rate (overall) | 0.922 | >= 0.9 | met |
| Detection rate per scenario type (lowest) | 0.833 | >= 0.75 | met |
| Tick false-alarm rate on normal runs | 0.00035 | <= 0.01 | met |
| False alert windows per normal run | 0.150 | <= 0.5 | met |
| Window precision | 0.989 | >= 0.8 | met |
| Median time to detect (s) | 15.000 | <= 60 | met |
| Compromised-reporting detection (trust) | 0.833 | >= 0.8 | met |
| Low-trust rate on honest runs | 0.00005 | <= 0.05 | met |
| Incident detection (scenario runs with an incident in the event window) | 0.933 | >= 0.9 | met |
| Classification accuracy (decided incidents) | 0.857 | >= 0.8 | met |
| Decision coverage (detected incidents that are decided) | 0.833 | >= 0.7 | met |
| Segment localisation | 0.960 | >= 0.75 | met |
| OT layer accuracy | 0.813 | >= 0.8 | met |
| Unexplained incidents per normal run | 0.100 | <= 0.3 | met |

### Confusion, system C (expected, then reported)

- cyber_manipulation: cyber_manipulation 26, physical_anomaly 3, sensor_fault 4, uncertain 3
- normal_behaviour: normal_behaviour 1, sensor_fault 1, uncertain 1
- physical_anomaly: physical_anomaly 14, uncertain 2
- reporting_inconsistency: physical_anomaly 1, reporting_inconsistency 8, uncertain 5
- sensor_fault: normal_behaviour 1, reporting_inconsistency 1, sensor_fault 12, uncertain 4

## Held-out (72 runs)

| Criterion | A. Threshold only | B. ML only | C. Full hybrid |
|---|---|---|---|
| Event detection | 13/60 (21.7 %) | 32/60 (53.3 %) | 43/60 (71.7 %) |
| Tick false-alarm rate on normal runs | 0.000 | 0.00031 | 0.00031 |
| False alert windows per normal run | 0.000 | 0.167 | 0.167 |
| Window precision | 1.000 | 0.985 | 0.987 |
| Median time to detect (s) | 70.000 | 137.500 | 75.000 |
| Incident detection | 9/60 (15.0 %) | 30/60 (50.0 %) | 48/60 (80.0 %) |
| Classification accuracy | not available | not available | 30/41 (73.2 %) |
| Decision coverage | not available | not available | 41/48 (85.4 %) |
| Ambiguity handled | not available | not available | 14/20 (70.0 %) |
| Segment localisation | 9/9 (100.0 %) | 22/30 (73.3 %) | 41/45 (91.1 %) |
| OT layer accuracy | not available | not available | 30/45 (66.7 %) |
| Incidents per normal run | 0.000 | 0.167 | 0.167 |
| Unexplained incidents per normal run | 0.000 | 0.167 | 0.000 |
| Incidents outside the event | 1 | 20 | 11 |

### Targets (system C)

| Target | Value | Goal | Result |
|---|---|---|---|
| Event detection rate (overall) | 0.717 | >= 0.9 | missed |
| Detection rate per scenario type (lowest) | 0.583 | >= 0.75 | missed |
| Tick false-alarm rate on normal runs | 0.00031 | <= 0.01 | met |
| False alert windows per normal run | 0.167 | <= 0.5 | met |
| Window precision | 0.987 | >= 0.8 | met |
| Median time to detect (s) | 75.000 | <= 60 | missed |
| Compromised-reporting detection (trust) | 0.750 | >= 0.8 | missed |
| Low-trust rate on honest runs | 0.000 | <= 0.05 | met |
| Incident detection (scenario runs with an incident in the event window) | 0.800 | >= 0.9 | missed |
| Classification accuracy (decided incidents) | 0.732 | >= 0.8 | missed |
| Decision coverage (detected incidents that are decided) | 0.854 | >= 0.7 | met |
| Ambiguous runs with an acceptable outcome (held-out only) | 0.700 | >= 0.6 | met |
| Segment localisation | 0.911 | >= 0.75 | met |
| OT layer accuracy | 0.667 | >= 0.8 | missed |
| Unexplained incidents per normal run | 0.000 | <= 0.3 | met |

### Confusion, system C (expected, then reported)

- cyber_manipulation: cyber_manipulation 18, sensor_fault 2, uncertain 3
- normal_behaviour: normal_behaviour 2
- physical_anomaly: normal_behaviour 3, physical_anomaly 3, uncertain 1
- reporting_inconsistency: reporting_inconsistency 1, sensor_fault 4, uncertain 2
- sensor_fault: reporting_inconsistency 2, sensor_fault 8, uncertain 1
