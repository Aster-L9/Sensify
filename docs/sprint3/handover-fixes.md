# Sprint 03 handover: developer completion report

Response to `Sensify Sprint 03 Developer Handover.md` (25 October 2026). Prepared 26 October 2026.

All ten defects are **Fixed, awaiting retest**. Nothing here marks a QA case as passed. Owner and target dates are still to be assigned by the team. The verification gaps (V-01 to V-05) and test-maintenance items (TM-01 to TM-03) are out of scope, except where noted below.

## Build and environment

- The source tree has no Git metadata. The snapshot taken before the changes is outside the repository; ask the developer for it if a diff is needed.
- Database schema version **4**. On first start, a version 2 or 3 database is upgraded in place, keeping runs, analysis results and users:
  - `runs` gains `paused_at` and `paused_seconds`;
  - `analysis_results.trust_score` becomes nullable. SQLite cannot relax a NOT NULL column in place, so the table is rebuilt with every row copied across.
- `backend/model_store/v1/validation.json` is a new file (see DH-09). No existing model file was changed.
- Checks run on 26 October 2026 (Windows 11, Python 3.13):
  - `pytest`: 222 passed, made up of 165 existing tests and 57 new ones (56 in `tests/test_sprint3_handover.py`, 1 in `tests/test_migration.py`);
  - `npx tsc --noEmit`: clean;
  - `npm run build`: passes.
- The browser checks were run against a copy of the demo database, not the live one. They covered dashboard, run, map, alerts, users, models, incidents and scenarios.

## Decisions recorded

The handover asked for these to be agreed before implementation. They are written here so the team can confirm or change them.

| Topic | Decision |
|---|---|
| **Pause/reset semantics (DH-02)** | **Pause** freezes the shared reveal position for every viewer and endpoint. **Resume** continues from the same tick with no jump. **Reset** rewinds the **same run** to T+00:00 and leaves it paused. The run keeps its seed, settings, stored measurements and analysis rows, so nothing old and new is mixed and the replay is identical. Analyst incident statuses on that run return to Investigating, because those incidents have not yet happened in the replay. Only administrators can pause, resume or reset. Pausing a completed run is refused (409); a completed run can be reset. |
| **Evidence sufficiency (DH-08)** | A segment-tick is **Insufficient** (shown as "Not enough data") when any of these holds: its own pressure or flow is missing; fewer than 4 of its last 6 readings (30 s) arrived; or no neighbouring segment reported, so it cannot be cross-checked. Such a segment-tick has no trust score and no anomaly score. It is neither Supported nor a flag: it never creates an alert window, and the investigation engine does not count it as questioned trust. Trust smoothing restarts when readings return. Analysis rows saved before this change came from complete simulator data, so they stay valid unchanged. |
| **Alert time filter (DH-10)** | `from_tick` and `to_tick` are run time in 5 s ticks from each run's start, both inclusive. A window matches if it **overlaps** the range. The filter is applied before pagination and never shows anything beyond the reveal cutoff. A reversed range returns 400; a negative tick returns 422. The UI takes run time as `m` or `m:ss`. |
| **Validation outcomes (DH-09)** | The measures are the same as for the test split: detection, time to detect, tick false alarms, false windows per normal run, window precision and compromised-reporting detection. They are computed on the validation split (50 runs) and stored with their split, run counts and how they were produced. Validation normal runs are part of calibration, and alpha was chosen on validation, so the UI labels these as development figures. The test split stays the unbiased estimate. |

## Per-defect status

| ID | Status | Change | Automated evidence |
|---|---|---|---|
| DH-01 | Fixed, awaiting retest | `POST /users/` creates Analyst or Admin accounts (201) through the same shared validation as registration (`app/services/accounts.py`). Extra fields are rejected (422), so a payload cannot set its own hash. The Users page has an Add user form. The sign-in page's Administrator option now has an editable email (prefilled with the seeded admin), so added administrators can sign in. An admin cannot remove their own admin role or deactivate themselves. | `test_admin_creates_accounts_that_can_sign_in` (both roles), `test_admin_create_rejects_bad_and_duplicate_input_without_records`, `test_only_admins_can_create_users`, `test_admin_cannot_lock_themselves_out` |
| DH-02 | Fixed, awaiting retest | `POST /runs/{id}/pause`, `/resume` and `/reset` (admin). The state is stored on the run row, so it survives a restart. The run view and the map show "Pause run", "Resume run" and "Reset" (reset asks for confirmation), kept separate from the viewer-only Replay. The dashboard and top bar show the paused state. | `test_pause_freezes_every_view_and_resume_continues_without_a_jump`, `test_reset_rewinds_the_same_run_and_replays_identical_values`, `test_reset_of_a_completed_run_and_completion_after_pauses`, `test_only_admins_control_playback` |
| DH-03 | Fixed, awaiting retest | Emails must have a local part, a single `@` and a dotted domain. This applies to registration and to admin-created accounts. | `test_malformed_email_is_rejected` (12 malformed forms), `test_valid_email_is_accepted_and_normalised`, `test_register_rejects_bare_at_and_creates_nothing` |
| DH-04 | Fixed, awaiting retest | `UserUpdate.role` accepts only `admin` or `analyst`; anything else returns 422 and nothing is stored. At startup, existing accounts with an unsupported role are listed in the log, not rewritten. The Users page labels such a role as unsupported. | `test_unsupported_role_is_rejected_and_not_stored` (6 cases), `test_role_change_takes_effect_and_deactivation_blocks` |
| DH-05 | Fixed, awaiting retest | Telemetry, run events and alerts return 422 for a malformed or non-positive `segment_id` and 404 for one that does not exist. Incidents return 404 for an unknown segment code. An empty list now always means a real segment with no readings. The Alerts page explains an unknown segment in the URL instead of quietly showing all segments. `/runs/{id}/state` always lists all six segments; a segment with no stored reading shows as "Not enough data" instead of disappearing. | `test_invalid_and_missing_segments_are_errors_not_empty_data` |
| DH-06 | Fixed, awaiting retest | The Users page shows "No users match" with the query and a Clear search button. This is distinct from an empty directory, from loading and from an error. Escape clears the search. | Browser check only, no automated UI test (see below). |
| DH-07 | Fixed, awaiting retest | **Every version is stored as `vN/model.joblib`, relative to the model store with forward slashes**, so the same database row works on any machine and in any folder. At startup, older stored paths (Windows drive, UNC, POSIX absolute or backslash relative) are rewritten to that form when the store holds the file; otherwise they are left alone. A relative `MODEL_STORE_DIR` or `SENSIFY_DATASET_DIR` in `.env` now means relative to `backend/`, not to the folder the server was started from. When reading, `artifact_file` also recognises Windows drive, UNC and POSIX absolute paths on any platform, and backslash relative paths. A path that cannot be used falls back to the same version's copy in the store. A missing file raises a clear `ArtifactUnavailable`. Such a version cannot be activated, and the Models page marks it "Model file missing". | `test_unusable_artifact_paths_fall_back_to_the_same_version` (5 cases), `test_relative_artifact_paths_resolve_in_the_store`, `test_missing_artifact_is_a_clear_error`, `test_new_versions_store_a_portable_relative_path`, `test_startup_rewrites_legacy_paths_to_the_portable_form` (4 cases), `test_a_path_without_a_store_copy_is_left_alone`, `test_relative_store_setting_is_relative_to_the_backend_folder`. These run on Windows only so far; **macOS: Not Run.** |
| DH-08 | Fixed, awaiting retest | Insufficient trust outcome, as decided above. Changes: trust analysis, model scoring (no score where a feature is missing), segment state `insufficient`, alert windows, API, map, schematic, trust indicator and dashboard. An ORM bulk-insert default that would have stored missing trust as 1.0 was found and removed. | `test_all_missing_measurements_are_not_supported`, `test_partial_gap_neighbour_gap_and_recovery`, `test_genuine_conflict_still_lowers_trust_with_gaps_elsewhere`, `test_persisted_incomplete_records_score_as_insufficient` (deletes real stored rows, re-scores, then reads them back through the API), `test_trust_handles_a_run_shorter_than_the_recent_window` |
| DH-09 | Fixed, awaiting retest | Training records `validation` beside the test `metrics`. `GET /models/{id}` returns `validation` (null for versions that never recorded it) plus `has_validation` and `artifact_available`. `python -m ml.validation_metrics --version N` adds the outcomes for an older version as a separate `validation.json`, marked "computed after training". This was run for v1: validation 27 of 30 detected and 0.25 false windows per normal run, against test 76 of 90 and 0.15. The Models page shows validation and test side by side. | `test_training_records_validation_outcomes_with_provenance`, `test_versions_without_validation_report_none` |
| DH-10 | Fixed, awaiting retest | `GET /alerts?from_tick=&to_tick=` with overlap semantics, as decided above. The Alerts page has a "Run time" from/to filter kept in the URL, and an empty result names the range. | `test_alert_time_filter_uses_window_overlap`, `test_alert_time_filter_never_reaches_past_the_reveal_cutoff` |

## Limits and notes for retest

- **Investigation engine.** One change was made: "questioned trust" in `investigation/evidence.py` now counts only Review and Contradicted, not every status other than Supported. On any data without missing readings, the engine's output is identical, and `test_engine_freeze` still passes against the i1 snapshot. The engine version therefore stays **i1**, and evaluation e1 still stands. Please confirm the team agrees this does not need a new engine version.
- **DH-06 and the DH-02 UI** were checked in a browser, but there are no automated UI tests. Capture the J-01 and J-02 retests as the handover asks.
- **Reset is not a new run.** If the team would rather reset create a fresh run, that is a decision to revisit; the API shape would change.
- **Missing readings and alerts.** "Not enough data" does not raise an alert, so a long telemetry outage appears on the map, the run view and the dashboard, but not in the Alerts list. Decide whether outages should get their own alert kind.
- **V-01 (partly addressed).** The run view and map segment panels now show the recorded valve state (Open, a partial opening such as 32 % open, or Closed) at SEG-05 and the pump state with its speed (Running or Stopped) at SEG-03. Other segments say there is no valve or pump. Closed and Stopped are highlighted. The team still needs to confirm this meets US-05 / FR-03.
- **TM-01.** Email and required-field rules now live in one reusable unit (`app/services/accounts.py`), which TM-01 can test directly.
- **Test accounts.** No live database or team account was used. Browser checks used a copy of the database, and the test suite creates uniquely named accounts in a temporary database.

## UI refresh in the same delivery

The user asked for a less cluttered, more animated interface alongside the fixes. The behaviour is unchanged apart from the fixes above.

- **Look.** One typeface (Archivo) and a cool canvas with white sheets. The sidebar navigation is grouped into Monitor, Investigate and Administer.
- **Dashboard.** Restructured into one live-line hero with a single stat strip, then two independent column stacks. Content is the same as before.
- **Motion.** Product flows along the schematic while a run plays and stops when it is paused. Other motion: the line draws in on load, figures count up, the navigation and tab indicators slide, pages ease in, and toasts show how long they stay.
- **Reduced motion.** With `prefers-reduced-motion` set, all of this motion is switched off.
