# Sprint 3 design: investigation and evaluation

Status: draft for approval, 2026-10-22. Scope source: `sensify_sprint_breakdown.txt`, Sprint 3. Builds on `docs/sprint2/design.md` and the handoff in `docs/PROJECT_STATUS.md`.

## 1. Intent

Sprint 2 shows *what* looks wrong and *what* looks untrustworthy. Sprint 3 turns that into a defensible interpretation that can be checked. Sensify groups the findings of a run into incidents and says what kind of problem each one most likely is, or that it can't tell. It says where the problem is and lays out the evidence in time order, then proves the approach against simpler baselines on data it was never tuned on.

The project closes with this sprint. Done when: an examiner is walked from login → dashboard → map → incident → evidence → comparative results, and a demo mode can tell that story reliably at the expo. Scope is the application and its code only (no final report or presentation).

## 2. Goals, non-goals, anti-goals

**Goals**
- An investigation engine. It groups alerts and events into incidents and orders the evidence by time. It classifies each incident into one of five categories or Uncertain, localises it to a segment and OT layer or abstains, and reconstructs a timeline and, when one exists, an attack-to-impact chain. It also adds MITRE ATT&CK for ICS context and text-only verification actions.
- An evaluation that compares threshold-only, ML-only and the full hybrid across all success criteria. It runs on the development test split and on a new held-out set built without sight of the investigation engine, and reports each separately.
- Pages: an incidents list, the investigation view, evaluation results, the remaining dashboard tiles, PDF/CSV export, and a demo mode.

**Non-goals**
- No automated response: Sensify never issues or suggests control commands.
- No LLM. Every conclusion comes from rules over computed evidence and is reproducible.
- No new scenario types, no change to the ML model, and no real-plant integration.

**Anti-goals (would be failures even if everything "works")**
- Causal wording ("the attacker closed the valve"). Language stays associative: "an unauthorized valve command at T+02:00 was followed by…".
- An Uncertain result that is really an error state, or that never appears. Uncertain must be a reasoned, first-class answer that occurs on genuinely ambiguous evidence.
- Any leak of scenario or ground truth to analysts, including through incident text, the demo guide or exports.
- Tuning on the test split or the held-out set, or quietly dropping missed targets.

## 3. Constraints carried over

All rules in `docs/PROJECT_STATUS.md` §1 still hold. In particular:
- The analysis and investigation code never reads ground truth.
- Nothing is shown beyond the reveal cutoff.
- Analysts never see scenario details.
- `model_store/v1` and `database/dummy.db` are not edited.
- The UI follows the Sprint 2 language: sentence case, and colour is never the only cue.

Runtime: Python 3.12–3.14 on Windows and macOS 12+, wheels only. Node 18+. Everything works offline.

## 4. Approaches considered (decided)

| | Approach | Trade-off | Decision |
|---|---|---|---|
| A | **Rule-based evidence scoring.** Category rules weigh evidence; scores become a confidence; Uncertain when evidence is weak or split | Explainable and evidence-linked; generalises to unseen settings; rules can miss unanticipated patterns | **Chosen.** The charter asks for "defensible interpretation with evidence", associative wording, a genuine Uncertain path and abstention, which this delivers directly |
| B | Trained classifier on incident features | Likely more accurate in-distribution; can't show its reasoning beyond feature weights; overfits the simulator, risky on the held-out set | Rejected |
| C | Rules plus a learned confidence calibrator | More moving parts for a small gain | Rejected |

Demo mode is presenter-led (an examiner is walked through it). It must still be readable for a visitor following it alone.

## 5. Investigation engine

A new pure package, `backend/app/investigation/`. It takes the same inputs whether called from the database (live app) or from `analyze_run` output (evaluation), and returns identical results for identical inputs. `tests/test_isolation.py` is extended to cover it: no imports of ground truth, the database or the simulator internals.

### 5.1 Inputs ("run evidence"), all up to a cutoff tick

- Per tick and segment:
  - anomaly score and ML flag;
  - trust score, status and factors;
  - status of each consistency check (`flow_balance`, `pressure_gradient`, `implausible_change`, `range`, `replay`, `flatline`) and the odd-one-out mask;
  - segment state;
  - reported pressure, flow, temperature, valve opening and pump speed.
- Alert windows (Sprint 2).
- Observable events: control commands with `authorized` yes/no, equipment state changes, security events (unregistered workstation, reporting-configuration change) and device diagnostics.
- Topology: segment order, neighbours, and which equipment sits where (pump P-3 at SEG-03, valve V-12 at SEG-05).

The engine may also derive its own signals from these observable inputs. The first is **setpoint departure**: the reported valve or pump position differs from the last authorized command for that equipment. It covers the Sprint 2 limitation where a held change fades below the anomaly threshold. These detectors live only in `app/investigation/`. `app/analysis/` is not changed, so Sprint 2 alerts, map states, stored results and the published v1 metrics stay exactly as they are.

### 5.2 Grouping into incidents

The charter says "group related anomalies *and events*", so an incident can start from either:
- an alert window; or
- an **opening event**, even with no alert nearby: an unauthorized command (`authorized = no`), a security event, a reporting-configuration change, a device diagnostic, or the start of a setpoint departure. Authorized operator commands never open an incident; they are attached as evidence, usually to explain one as normal behaviour.

Windows and opening events in a run are linked into one incident when either:
- the gap between them is no more than **G** ticks (G tuned on the validation split; start at 36 ticks = 3 minutes); or
- a condition is still open across the gap. Conditions: a segment in the incident is still not Supported; an unauthorized command hasn't been reversed by a later command on the same equipment; or a setpoint departure is still active.

Other events are attached as evidence when they fall between 5 minutes before the incident's first item and its end; 5 minutes is the longest ramp. Events on the incident's segments or equipment are also attached when they fall between the previous incident's end and this incident's end. Several incidents per run are possible.

Each incident also records:
- `detected_tick`: the first flagged tick;
- `start_tick` and `end_tick`;
- a stable key `"{run_id}-{start_tick}"`, which stays the same as more of the run is revealed.

Normal runs can produce incidents (false alarms). The engine is expected to explain those as normal behaviour where an authorized operator change accounts for them.

### 5.3 Evidence items

Every conclusion cites evidence items. Each item has:

| Field | Meaning |
|---|---|
| `id` | stable within the incident |
| `kind` | telemetry anomaly, consistency check, trust drop, control event, security event, device event, equipment state, setpoint departure, recovery |
| `tick`, `end_tick`, `segment` | where and when |
| `observation` | what was seen, in plain words ("Reported flow at SEG-04 fell 12 % while SEG-03 held steady") |
| `interpretation` | what it is consistent with ("consistent with product leaving the line between SEG-03 and SEG-04") |
| `supports` | which categories it counts towards, with weight |
| `link` | target in the app: run view at tick and segment, or the event |

### 5.4 Classification: five categories plus Uncertain

The categories follow the mock-data spreadsheet and `EXPECTED_ROOT_CAUSE`.

| Category | Typical evidence (rules weigh these; weights tuned on validation) | OT layer |
|---|---|---|
| **Normal behaviour** | windows coincide (± 1 min) with *authorized* operator commands on the equipment that moved; response size is in line with routine changes; no trust contradiction | Control (authorized) |
| **Possible physical/process anomaly** | honest readings: anomalies on one or more segments with trust Supported; a physically consistent flow-balance or pressure-gradient break; no unauthorized command or reporting event near onset | Physical process |
| **Sensor/device fault** | a problem confined to one segment and usually one variable (implausible jumps, flat readings, out of range, or a gradient mismatch only there); neighbours show no real process change; a device diagnostic adds weight | Field device |
| **Possible cyber manipulation** | (a) an unauthorized command followed within 2 minutes by a process response at or next to that equipment, with honest readings; a security-monitor event adds weight; **or** (b) a replay signature, or a reporting-configuration change at a segment whose readings are contradicted | Control (a) / Reporting (b) |
| **Possible physical/process anomaly with reporting inconsistency** | a contradicted (odd-one-out) segment while its neighbours show a real process change pointing at that segment; no replay signature and no reporting event | Physical process + reporting |
| **Uncertain** | top score below a minimum, or top two within a margin, or strong evidence for incompatible categories | abstain unless the evidence shared by the top hypotheses fixes it |

- **Scoring.** Each category's score is the weighted sum of its supporting evidence, capped and normalised to 0–1. Confidence comes from the top score and its margin over the runner-up, shown as a number with a word (Low below 0.5, Moderate, High from 0.75).
- **Uncertain is first-class.** The result carries the two leading hypotheses with their scores, the evidence that fits each, and what would tell them apart. Example: a pressure offset at one segment with no reporting event and no device diagnostic fits both a sensor fault and telemetry manipulation.
- **Tuning discipline.** Thresholds (minimum score, margin, G, weights) are tuned on the *validation* split only, then frozen in a versioned config (`engine_version`, e.g. `i1`).

### 5.5 Localisation

- **Segment.** Chosen per category:
  - cyber via control: the commanded equipment's segment;
  - reporting manipulation or reporting inconsistency: the contradicted segment;
  - sensor fault: the single segment with failing checks;
  - physical anomaly: the segment at the centre of the strongest honest flow-balance or pressure-gradient break.
- **OT layer.** Physical process, field device, control, or reporting/telemetry; two layers for the reporting-inconsistency category. Purdue level is shown as secondary text.
- **Abstention.** When two candidate segments are close, or the evidence doesn't single one out, the result is "Not localised", with the reason ("evidence spans SEG-03 and SEG-04 equally").

### 5.6 Timeline

Chronological evidence items, each with observation and interpretation, matching the spreadsheet's Investigation_Timeline. The timeline includes events, the first flag per segment, trust drops and recoveries, check failures starting and clearing, and alert windows. Wording is associative throughout ("followed by", "coincides with", "consistent with"); never "caused".

### 5.7 Attack-to-impact chain

Built only for possible cyber manipulation and for reporting inconsistency. The chain is an ordered set of stages. Only stages backed by evidence appear:

1. **Access:** a security event, such as a command from an unregistered workstation.
2. **Action:** an unauthorized command, or a reporting-configuration change.
3. **Equipment:** a valve or pump state change.
4. **Process:** the real process change on segments.
5. **Visibility:** readings replayed or held, so trust is contradicted.
6. **Detection:** Sensify's first alert.

With fewer than two backed stages, there is no chain, and the UI hides the section entirely.

### 5.8 MITRE ATT&CK for ICS context

The mapping is context, never attribution: it lists techniques *consistent with* the evidence. It is shown only for possible cyber manipulation and reporting inconsistency. Uncertain says no mapping is given until the cause is clearer. IDs are to be checked against the ATT&CK for ICS matrix during the build.

| Evidence | Techniques (tactic) |
|---|---|
| Command from an unregistered workstation | T0848 Rogue Master (Initial Access) |
| Unauthorized valve or pump command | T0855 Unauthorized Command Message (Impair Process Control); T0836 Modify Parameter (Impair Process Control) |
| Equipment moved and process changed | T0831 Manipulation of Control (Impact); T0828 Loss of Productivity and Revenue (Impact) |
| Replayed or held readings | T0856 Spoof Reporting Message (Impair Process Control / Evasion); T0832 Manipulation of View (Impact) |
| Real change hidden behind normal-looking readings | T0832 Manipulation of View; T0829 Loss of View (Impact) |

### 5.9 Recommended verification actions (text only)

A fixed playbook per category with segment and equipment filled in. Wording follows the spreadsheet's verification_action column. Actions are checks, never commands. Examples:
- "Verify with the control room whether the valve V-12 command at T+02:00 was authorized; review the engineering-workstation log."
- "Compare SEG-03's reported values with independent measurements before relying on them."

Uncertain lists the checks that would separate its two hypotheses. A fixed note states that Sensify never issues control commands.

### 5.10 Severity, status and live runs

- **Severity.** The highest severity of the incident's alert windows, raised to critical for cyber manipulation with an equipment change.
- **Status.**
  - *Developing* while the run is still playing (not editable);
  - *Investigating* by default once the run completes;
  - *Resolved* when any signed-in user marks it, with an optional note. It can be reopened.
  - Changes are logged in activity as `incident_resolved` and `incident_reopened`.
- **Live runs.** Incidents are recomputed from data up to the reveal cutoff on each request. Classification can change as evidence arrives, which is realistic and shown as "Developing". Completed runs are investigated once at scoring and stored.
- **Re-scoring** a run replaces its incidents and keeps statuses whose key still matches.

## 6. Evaluation

### 6.1 Systems compared

| System | Flags | Localisation | Classification |
|---|---|---|---|
| A. Threshold only | threshold-baseline alarms | segment with the most alarm ticks | none (reported as "not available") |
| B. ML only | ML flags | segment with the highest score | none |
| C. Full hybrid | segment state (ML + trust) plus the event stream and the engine's own signals, grouped into incidents by the engine (§5.2) | engine localisation (with abstention) | engine classification |

Only C sees events; using the event stream is what "full hybrid" adds. A and B are grouped into incidents with the same gap rule G but without events or open-condition bridging, so incident counts compare like-for-like.

### 6.2 Datasets

- **Development:** the existing test split (110 runs; never used for tuning). The validation split stays the tuning set.
- **Held-out:** a new set in `backend/ml/heldout/`, same file format as `ml/data` plus extra label columns. A **separate agent builds it without access to the investigation engine or the analysis package.** It may read `app/sim`, `ml/generate_dataset.py`, `ml/dataset.py` and the data card. Its generator lives at `ml/generate_heldout.py` and is reproducible from a seed.
  - **Settings outside the development range:**
    - strength 0.1–0.3 (development 0.3–1.0);
    - onsets of 1–4 min and 10–18 min (development 4–10);
    - ramps of 2–5 min (development 1);
    - active phases of 9–15 min;
    - runs of 25–30 min (development 20);
    - recovery off more often.
  - **Deliberately ambiguous cases, about a quarter of the set:**
    - a false offset with no logged reporting change;
    - a slow sensor drift;
    - a small leak at SEG-01 or SEG-06;
    - an unauthorized command with no security-monitor event;
    - a scenario overlapping a routine authorized operator change.
  - **Size:** about 60–90 runs across all types, including normal runs.
  - **Labels:** each run carries `expected_category`, `acceptable_outcomes` (for example `["Sensor/device fault", "Uncertain"]`), `expected_segment`, `expected_ot_layer` and an `ambiguity_note`. These are used only by the harness.
- **One-look rule.** The engine authors don't inspect held-out results until the engine is frozen. The held-out evaluation is run once per frozen engine version.

### 6.3 Success criteria (targets in `ml/targets.json`)

The existing eight Sprint 2 targets still apply (detection, false alarms, precision, time to detect, trust). New investigation targets are proposed below and are editable.

| Criterion | Definition | Proposed goal |
|---|---|---|
| Incident detection | scenario runs with an incident overlapping the event window | ≥ 90 % |
| Classification accuracy | decided (not Uncertain) incidents whose category matches | ≥ 80 % |
| Decision coverage | detected scenario incidents that are decided | ≥ 70 % |
| Ambiguity handled | ambiguous held-out runs whose outcome is in `acceptable_outcomes` | ≥ 60 % (held-out only) |
| Segment localisation | localised incidents on the right segment | ≥ 75 % |
| OT layer accuracy | layer given and correct | ≥ 80 % |
| Unexplained incidents | incidents on normal runs not classed as normal behaviour, per run | ≤ 0.3 |

For systems A and B, criteria they can't produce are shown as "not available", which is itself part of the comparison. Development and held-out results are always shown side by side and never pooled. Missed targets are shown as missed.

**How each system is scored**
- **The eight Sprint 2 targets** are computed on each system's per-tick flags with the existing `ml/metrics.py` definitions: windows, precision and time to detect. For C, the flags are the segment states.
- **Incident detection** for A and B uses their own incidents (flags grouped by G). For C it uses the engine's incidents, including those opened by events.
- **False incidents.** Two rows are always shown:
  - **incidents per normal run**, for all three systems;
  - **unexplained incidents per normal run**, which leaves out incidents C explains as normal behaviour. A and B can't explain, so for them it equals the first row.
- **Which incident is scored on a scenario run.** The *event incident* is the one overlapping the event window (start to end plus the 1-minute grace); if several overlap, the one with the most evidence items. Incidents entirely before or after the window are counted as "incidents outside the event". They are not errors when C classes them as normal behaviour.
- **Category matching** is exact. On the development split the expected category comes from the scenario type through `EXPECTED_ROOT_CAUSE`; Uncertain counts against coverage, not accuracy. A confusion matrix is shown so near-misses are visible (such as a concealed incident called a physical anomaly). For the two-layer category, OT layer accuracy requires both layers.

### 6.6 The one look at held-out results

- **The freeze covers decision logic only:** grouping, opening events, classification rules, weights, thresholds, localisation and abstention, versioned as `engine_version`. Presentation stays editable after the freeze: wording, timeline text, chain rendering, MITRE text, actions and evidence links. A test snapshots decisions on the validation split so that a presentation change can't silently alter them.
- **Development test and held-out results are each computed once per frozen version.**
- **Defects found at the look** (a crash, a harness bug) may be fixed. If the fix changes any decision, the engine becomes a new version (i2) and is rerun. The shipped evaluation then shows i1's first look *and* i2's rerun, with a disclosure of what changed. The first look is never replaced.
- **Held-out labels** may be corrected only by the held-out author, during its own review before the look. A label error noticed afterwards is disclosed next to the results, never silently corrected.

### 6.4 Harness and storage

- `python -m ml.evaluate [--dataset dev|heldout|both]` runs all three systems with the active model and writes `evaluations/eN/{results.json, report.md}`.
- `POST /evaluation` (admin) runs the same harness in a background thread, as training does; `GET /evaluation` and `GET /evaluation/{id}` are open to both roles.
- A finished evaluation of v1 with engine `i1` ships with the app (`backend/evaluations/e1`). It is seeded into the database at migration, so the evaluation page and dashboard snapshot are populated on first start.

## 7. Reports

- `GET /reports/incident/{id}?format=pdf|csv` and `GET /reports/evaluation/{id}?format=pdf|csv` return a file download.
- **PDF** is made on the backend with fpdf2 (pure Python). A Unicode font is bundled (Inter, OFL) so m³, ≥ and → render. Contents:
  - incident report: classification, confidence, location, timeline, chain, MITRE context, actions and evidence list;
  - evaluation report: the A/B/C table for development and held-out, plus targets.
- **CSV:**
  - incident: one row per evidence item;
  - evaluation: one row per system × dataset × criterion.
- Reports respect the viewer's role: analysts' files never contain scenario fields.

## 8. Demo mode

- **Curated run.** A fixed configuration and seed: unauthorized valve closure at SEG-05, with the security-monitor event present. The seed is pinned by a test that asserts the story (incident classified as possible cyber manipulation, with a chain of at least four stages). It runs 10 minutes at 10× (about one minute of playback) and is named neutrally ("Demo run").
- **Start.** An admin presses "Start demo" on the dashboard. Analysts can follow the latest demo run from the same place.
- **Guide.** A docked panel with six stops: dashboard → map → incident list → investigation view → evidence → comparative results. Each stop has:
  - one sentence of narration built only from analyst-visible data (for example "Sensify grouped 3 alerts at SEG-05 into one incident");
  - a "Show me" button that deep-links to the right page, tick and segment;
  - a waiting state until its data exists.

  Progress is kept per viewer and survives reloads. The guide can be closed and reopened.

## 9. Data model (schema version 3)

Migration v2 → v3 is additive and keeps everything:
- replace the unused Sprint 1 `incidents` placeholder;
- add `incident_evidence` (or JSON on the incident; builder's choice) and `evaluation_runs`;
- investigate already-scored completed runs;
- seed evaluation e1.

The v1 → v3 path (a Sprint 1 `dummy.db`) still works.

`incidents`, at minimum: id, run_id, key, model_version_id, engine_version, start/end/detected tick, classification, confidence, runner-up hypothesis, segment_id (nullable), ot_layer (nullable), localisation note, severity, summary, status, resolved_by/at and note, and the timeline, chain, MITRE and actions data.

## 10. API (charter list plus what the pages need)

| Method and path | Access | Notes |
|---|---|---|
| GET /incidents?run_id=&classification=&status=&severity=&segment_id=&sort= | both | across runs; only incidents whose start is revealed |
| GET /runs/{id}/incidents | both | |
| GET /incidents/{key} (+ /evidence, /timeline, /trace, /mitre, /recommendations) | both | live incidents truncated at the cutoff; `trace` is 404 or empty when no chain exists |
| PATCH /incidents/{key} | both | status Investigating ↔ Resolved with note; completed runs only |
| POST /evaluation; GET /evaluation, /evaluation/{id} | run: admin; read: both | 409 while one is running |
| GET /reports/incident/{key}, /reports/evaluation/{id} | both | `format=pdf\|csv` |
| POST /demo | admin | launches the curated run; returns run id |
| GET /dashboard/summary | both | adds incidents by classification, open investigations, latest evaluation snapshot |

## 11. Frontend

### 11.1 Visual language additions

The base is the Sprint 2 language: Inter, tabular numerals, brand indigo, white panels, sentence case, and colour plus icon plus word. New elements:
- **Classification marks.** Each outcome has its own icon (never reused from the segment-state icons) and word, with colour as the third cue:
  - normal behaviour: user-check, indigo;
  - physical/process anomaly: droplets, amber text `#B45309`;
  - sensor/device fault: gauge, slate `#475569`;
  - possible cyber manipulation: crosshair, crimson `#9F1239`;
  - reporting inconsistency: eye-off, purple `#7E22CE`;
  - Uncertain: circle-help, neutral grey with a dashed outline. It is never styled as an error.
- **Signature element: the evidence rail.** A horizontal time axis aligned to the run's ticks (reusing the chart frame so it lines up with the Sprint 2 charts). It has lanes for control and security events, equipment, process, trust and Sensify findings. The attack-to-impact chain sits above it as linked stages, each pointing at its evidence on the rail. This is the one bold element; everything around it stays quiet.
- **Confidence** is a short meter with a number and a word; Uncertain shows two hypothesis bars instead.

### 11.2 Pages

- **Incidents (`/incidents`, both).**
  - Sortable, filterable table: classification mark, confidence, location (or "Not localised"), run, detected at (T+), duration, severity, status, evidence count.
  - Filters for classification, status, severity, run and segment, kept in the URL. Empty state included.
- **Investigation view (`/incidents/[key]`, both).** Reads like a case file.
  - Header: classification, confidence, location with OT layer or the abstention reason, severity, status control, and PDF/CSV export.
  - Summary sentence, then the evidence rail with the chain (chain hidden when none exists).
  - Expandable evidence grouped by kind, each item linking to the run view at its tick and segment, or to the event.
  - Timeline list (observation and interpretation), MITRE context, and verification actions with the "never issues control commands" note.
  - Uncertain renders the two hypotheses side by side with "what would tell them apart".
- **Evaluation (`/evaluation`, both; running it is admin-only).**
  - A/B/C metrics table and a grouped bar chart per criterion. Held-out results are visually distinct: a hatched or outlined bar pattern plus the label "Held-out", never colour alone.
  - Development and held-out are never merged. Targets show as Met or Missed.
  - Run panel with live status (admin); history of evaluation runs; export.
- **Dashboard completion (both).**
  - Incidents-by-classification tile (counts per outcome, linking to the filtered list).
  - Open investigations panel (newest Investigating or Developing incidents).
  - Latest evaluation snapshot (hybrid vs threshold headline, development and held-out, link to the page).
  - "Start demo" for admins, "Follow the demo" for analysts.
- **Navigation.** Add Incidents and Evaluation for both roles, between Alerts and Scenario Builder.
- **Links in.** Alerts rows and the run view link to the incident containing them.

## 12. Testing and acceptance

- **Unit tests per rule:** one or more synthetic cases per category, and a genuinely ambiguous case returning Uncertain with two hypotheses. Also localisation abstention and chain present/absent.
- **Isolation:** the investigation package never imports ground truth; the held-out generator never imports `app.analysis` or `app.investigation` (AST tests).
- **Freeze:** a snapshot of decisions on the validation split fails if any change alters a decision without bumping `engine_version`.
- **Reveal:** an incident of a playing run equals the engine's output on data truncated at the cutoff; no future events appear.
- **Analyst blind:** incident, report, dashboard and demo payloads for analysts contain no scenario fields.
- **Consistency:** engine output from database inputs equals output from `analyze_run` inputs for the same run.
- **Evaluation:** the harness runs on a tiny dataset; development and held-out stay separate; the shipped e1 matches a rerun.
- **Done-when walkthrough** in a browser on a fresh copy of `dummy.db`, production build, both roles:
  - login → dashboard → map → incident → evidence → comparative results;
  - demo mode end to end;
  - PDF/CSV downloads open;
  - analysts can resolve incidents and are blocked from admin actions.
- `npm run build`, `tsc`, and the full `pytest` suite pass. A final fresh-reviewer pass, as in Sprint 2.

## 13. Delivery phases

1. Rebuild the Python environment (the old scratch one is damaged). Schema v3 and migration. Investigation package with tests, tuned on validation.
2. **In parallel:** the held-out set, built by an isolated agent.
3. Evaluation harness, API, shipped e1. The engine's decision logic is frozen first and held-out is run once (§6.6); presentation work may continue in phases 4–5.
4. Incident services and APIs, reports, demo endpoint, dashboard summary.
5. Frontend: incidents, investigation view, evaluation, dashboard, demo guide, navigation.
6. Docs (README, running instructions, PROJECT_STATUS, ml README), walkthrough, final review, cleanup.

## 14. Risks

| Risk | Mitigation |
|---|---|
| Rules fit the simulator but miss held-out cases | Rules are written from physical reasoning, not from test cases; held-out results reported honestly, including misses |
| Uncertain over- or under-used | Coverage and ambiguity targets pull in opposite directions; both reported |
| Demo seed stops telling the story after an engine change | A test pins the demo story |
| PDF fonts or Unicode | Bundled TTF; a test renders a report |
| Time | Reuse Sprint 2 components and alert machinery; phases 1 and 2 run in parallel |

## 15. Left to the builder

- Exact rule weights, thresholds and G (tuned on validation).
- Evidence storage (table vs JSON).
- Response field names beyond those listed.
- PDF layout.
- Exact tints within the stated palette.
- The demo seed (subject to the pinned-story test).
- How many held-out runs per type (within about 60–90).

## 16. Calls made by the designer (check these)

- Outcomes are the five categories from the mock data plus Uncertain.
- Incident status runs Developing → Investigating ↔ Resolved; any signed-in user may resolve.
- `GET /incidents`, `PATCH /incidents/{key}` and `POST /demo` are added beyond the charter's API list, because the pages need them.
- The demo story is unauthorized valve closure at SEG-05.
- Report PDFs are generated with fpdf2 and a bundled font.
- The investigation targets in §6.3 are proposals.
- An evaluation is shipped (e1) so the pages aren't empty.
- Opening events and a setpoint-departure signal start incidents (§5.2). New detectors live only in `app/investigation/`; Sprint 2 analysis is unchanged.
- Scoring rules for A/B/C, event-incident selection, exact category matching (§6.3).
- The one-look rule, and a freeze that covers decisions, not presentation (§6.6).
- The MITRE mapping in §5.8 is a proposal.
