# Sensify

## AI-Assisted Cyber-Physical Incident Investigation Platform

Sensify is an academic software platform for investigating unusual behavior in a simulated petroleum pipeline. It combines machine-learning anomaly detection with process relationships, telemetry reliability, and control/security events to help users understand what happened, where it happened, and which explanation the evidence supports.

A pressure drop can indicate a physical disturbance, a faulty sensor, an expected control operation, or possible cyber manipulation. Sensify brings these observations into one investigation workflow, with evidence and uncertainty visible to the user.

**Project:** SE 499 Senior Project, Semester 261, Prince Sultan University, College of Computer and Information Sciences, Software Engineering Department.  
**Supervisor:** Dr. Mona Alkanhal.  
**Development status:** Sprint 2 source is available. The charter roadmap below distinguishes delivered source from acceptance; story completion is tracked on the Scrum board. Sprint 3 investigation and reporting work remains planned.

## Current application

The Sprint 2 implementation includes six simulated pipeline segments, reproducible normal/fault/cyber scenarios, a per-segment Isolation Forest detection pipeline, threshold comparison, process-consistency and telemetry-trust checks, model training/version management, alerts, and synchronized run playback. The web application uses Next.js / React; the API uses FastAPI / SQLAlchemy with local SQLite storage.

See [setup and verification](docs/SETUP.md) to run it, and [model training and evaluation](backend/ml/README.md) for data generation, model activation, and known limitations. Generated datasets, trained binaries, databases, credentials, dependencies, and caches are excluded; the setup regenerates them locally. The [supplied Sprint 2 evaluation](docs/evaluation/sprint-2-v1/report.md) records six of eight development targets met, including the two misses; fresh training reproduced those metrics during import verification. These are separate from the charter acceptance targets below.

## Planned capabilities

- Simulate approximately 5–8 connected pipeline segments with synchronized pressure, flow, valve-state, and equipment-state records.
- Introduce configurable physical/process disturbances, sensor/device faults, and three cybersecurity scenarios: telemetry manipulation, unauthorized control manipulation, and a concealed physical incident.
- Train and validate one primary ML approach on designated normal-operation data, then record anomaly scores and detection times.
- Check process consistency across variables, equipment states, and neighboring segments.
- Assess whether reported telemetry is supported, contradicted, or insufficiently verified by available evidence.
- Correlate measurements and control/security events to classify, localize, and reconstruct incidents.
- Explore findings through a clickable pipeline diagram, synchronized trends, alerts, incident timelines, and verification guidance.
- Display justified MITRE ATT&CK for ICS mappings for implemented scenario behaviors.
- Compare threshold monitoring, ML-only detection, and the full hybrid investigation approach; export incident and evaluation reports as PDF and CSV.

## Investigation workflow

1. An Admin configures a reproducible simulation run and, where required, a controlled scenario.
2. The simulator generates observable operational measurements and events using a common simulation clock.
3. Detection and analysis produce anomaly scores, process-consistency findings, and telemetry-trust assessments.
4. The investigation engine groups related evidence and produces supported classifications, locations, timelines, and attack-to-impact traces.
5. An Analyst inspects the pipeline, reviews the evidence and uncertainty, and follows suggested verification steps.
6. Separate ground-truth records support repeatable evaluation of the three approaches.

### Incident categories

- Normal
- Possible Physical/Process Anomaly
- Sensor/Device Fault
- Possible Cyber Manipulation
- Uncertain

Anomaly scores do not establish an incident's cause. Timing alone does not establish causation. Unsupported locations and event chains must remain undetermined, and incomplete or conflicting evidence must be visible.

## Architecture

The planned system consists of a role-based web application, a protected backend API, simulation and collection components, detection and analysis components, an incident investigation engine, and evaluation/reporting components.

| Component | Responsibility |
| --- | --- |
| Web application | Dashboard, interactive pipeline map, investigation views, administration |
| Backend API | Authentication, role-based access, requests and results |
| Simulation and collection | Pipeline model, virtual OT/SCADA, scenario injection, measurement and event collection |
| Detection and analysis | ML anomaly detection, process consistency, telemetry trust |
| Incident investigation | Classification, localization, evidence correlation, timelines, impact tracing |
| Storage | Application records, operational data, model versions, separate evaluation ground truth |
| Evaluation and reports | Threshold, ML-only, and hybrid comparisons; downloadable results |

**Evaluation independence is essential:** hidden simulator state and scenario ground-truth labels must never be used as operational inputs to produce investigation findings. Training, validation, and final test data must have documented separation. Runs must retain configuration, random seed where applicable, model version, and analysis settings.

## User roles

**Analyst:** inspect runs, telemetry, alerts, incidents, evidence, timelines, evaluation results, and reports.  
**Admin:** all Analyst capabilities, plus management of accounts, simulation runs, scenarios, models, and evaluation execution. Permissions must be enforced in both the interface and the API.

## Scrum roadmap

The backlog follows the charter's 21 user stories. Each issue retains its story ID, priority, and acceptance criteria. Source delivery does not by itself establish that a story meets every acceptance criterion. Use the live board for current story status and acceptance evidence.

| Sprint | Charter window | Status | Stories | Completion milestone |
| --- | --- | --- | --- | --- |
| 1 — Platform Foundation | Weeks 2–5 | Source delivered | US-01–US-07 | Users can log in, open a run, and explore pipeline conditions with permissions enforced. |
| 2 — Detection and Evidence | Weeks 5–9 | Source delivered | US-08–US-14 | An Admin can launch a scenario, and both roles can inspect anomalies and supporting evidence. |
| 3 — Investigation and Evaluation | Weeks 9–13 | Todo | US-15–US-21 | Users can follow an incident from detection to explanation and review comparative results. |

Browse the [user-story issues](../../issues) and the repository's [Projects tab](../../projects) for the Scrum board.

## Evaluation targets

These are preliminary charter acceptance targets for controlled simulation experiments, not achieved results.

| Measure | Target |
| --- | --- |
| Anomaly detection F1 | ≥ 0.75 |
| Incident classification macro F1 | ≥ 0.70 |
| Affected segment identification | ≥ 80% of eligible scenarios |
| Faulty/manipulated telemetry-source identification | ≥ 75% of applicable scenarios |
| False-positive rate | ≤ 10% of evaluated normal observation units |
| Relevant cyber/control event identification | ≥ 80% of supported cyber scenarios |
| Major-event timeline ordering | ≥ 80% of supported scenarios |
| Principal attack-to-impact sequence reconstruction | ≥ 75% of supported scenarios |

Evaluation will also record detection delay and representative-user task outcomes. Before final testing, define scoring units, scenario eligibility, handling of Uncertain outcomes, and event-matching rules. Use the same applicable test data across approaches, report scenario counts and observed errors, and distinguish development results from independently prepared held-out results.

## Scope and constraints

The core is a software prototype using synthetic data and a simplified virtual OT/SCADA environment. Development, evaluation, and documentation fit a planned 14-week period, with five students and a maximum proposed budget of 2,000 SAR. A small water-based demonstrator is a stretch deliverable after the core software and evaluation are complete.

Out of scope: real petroleum-company data or infrastructure, production SCADA/DCS integration, autonomous control or emergency shutdown decisions, production-grade hydraulics, definitive attack attribution, full predictive maintenance, a complete SIEM/IDS/IPS, comprehensive attack-framework coverage, adversarial learning, CCTV, facial recognition, and real petroleum handling.

## Team

The charter proposes the following work-area leads; all members also contribute to integration, testing, documentation, and presentation.

| Team member | Proposed lead area |
| --- | --- |
| Ghala Aljarallah | Pipeline simulator, topology, normal operational data |
| Renad Alsukayt | Dataset preparation, ML training/evaluation, threshold monitoring |
| Layan Algublan | Fault/cyber scenarios, event recording, MITRE ATT&CK for ICS mappings |
| Donia Aldawsari | Consistency/trust checks, evidence correlation, classification, timelines |
| Layla Albelbisi | Authentication, user management, dashboard, backend/interface integration |

## Development and contribution

See the [Sprint 2 import and verification record](docs/SPRINT_2_IMPORT.md) for packaging changes, test results and remaining dependency warnings.

The Sprint 2 source uses a Next.js / React frontend and a FastAPI / SQLAlchemy backend with a locally generated SQLite database. See [local setup instructions](docs/SETUP.md) for installation, environment configuration, initial model training, local accounts, and automated checks. Configure your own secrets using the committed `.env.example` templates; local environment files, databases, dependencies, and build caches are excluded from Git.

- Link branches and pull requests to the relevant user-story issue.
- Review the story's acceptance criteria before implementation and record validation evidence before marking it Done.
- Preserve common run, timestamp, and source identifiers across component interfaces.
- Keep credentials outside source code and exclude private participant records and secrets from commits.
- Review scope, schedule, budget, or acceptance-criteria changes with the team and supervisor, then update the backlog and relevant documentation.

The final project submission is planned to include the integrated prototype, requirements/design documentation, experimental results, and an end-to-end investigation demonstration. Unmet targets and incomplete requirements must be documented with their impact and follow-up.
