# Sprint 3 source import and verification

Prepared from the Sprint 3 codebase folder on 9 November 2026, on top of the Sprint 2 import. The repository's charter README, Git history and Sprint 2 hardening are retained.

## What Sprint 3 adds

- **Investigation engine** (`backend/app/investigation/`, engine version i2): groups related anomaly, consistency, trust and event evidence into incidents, then classifies, localises and narrates them. Classifications are worded as possible explanations and can be left uncertain. Like the analysis package, it never reads ground truth, and `tests/test_isolation.py` enforces this.
- **Incidents**: list and detail pages with classification, confidence, evidence, timeline, attack-to-impact chain and MITRE ATT&CK for ICS references. Analysts can resolve and reopen incidents.
- **Reports**: PDF and CSV export for incidents and evaluations (`fpdf2`, with bundled DejaVu fonts).
- **Evaluation**: a harness comparing threshold-only, ML-only and the full hybrid approach on the development test split and an independent held-out set (`backend/ml/heldout/`, 72 runs, frozen). Recorded runs e1 to e4 are in `backend/evaluations/`.
- **Demo mode**: a guided dashboard demo for presentations.
- **Run controls and data handling**: Administrators can pause, resume and reset runs; segment-ticks with too little data are reported as "Not enough data" instead of being scored; alerts can be filtered by run time; validation-split results are stored per model.
- **Access**: Analysts never receive scenario names or settings, and the scenario catalogue (`GET /scenarios`) is Administrator-only.
- **Database**: schema version 4, with in-place upgrades from earlier local databases.
- **Interface**: a revised visual design (palette, typography and motion) across all pages.

The design is recorded in `docs/sprint3/design.md`, and the handover defect fixes and their decisions in `docs/sprint3/handover-fixes.md`.

## Packaging changes

- Kept the Sprint 2 configuration validation. The Sprint 3 folder had restored built-in defaults for `JWT_SECRET`, `ADMIN_PASSWORD` and `ANALYST_PASSWORD`; these were removed again, so the API still refuses to start without configured secrets. `backend/.env.example` stays a blank template, and tests use isolated test-only credentials.
- Kept `backend/app/config.py`, `tests/test_config.py`, `frontend/.env.example`, `docs/SETUP.md` (updated for Sprint 3) and the Sprint 2 evaluation archive, which the Sprint 3 folder did not contain.
- Kept `tests/test_regressions.py`, which also covers UNC and POSIX model paths. Sprint 3's renamed copy with fewer cases (`test_review_fixes.py`) was not added.
- Kept the pinned ESLint 8.57.1 and `eslint-config-next` 14.2.0 and the existing lockfile. The Sprint 3 folder had upgraded them to ESLint 9 and `eslint-config-next` 16, which `next lint` on Next.js 14.2 cannot load. Sprint 3 adds no other frontend dependencies.
- Excluded credential documents, local databases and their `.bak` copies, the generated development dataset, serialized models, the mock-data spreadsheet, the plain-text run instructions that contained demo passwords (their steps are now in `docs/SETUP.md`), internal task plans, dependencies, builds and caches. Added `*.bak` to `.gitignore`.
- Edited `docs/PROJECT_STATUS.md` for the repository: removed demo passwords and references to files outside it. The rest of the document is unchanged.
- Line endings follow `.gitattributes` (LF for source and documentation).

## Verification

Environment: macOS, Python 3.14.7, Node.js 24.21.0, npm 11.19.0.

| Check | Result |
| --- | --- |
| Backend `python -m pytest` (no secrets set in the shell) | 252 passed, 3 subtests passed |
| Frontend `npm ci` | Passed using the existing lockfile |
| Frontend `npm run lint` | Passed with 5 warnings (3 plain-image, 2 run-page effect dependencies) |
| Frontend `npm run build` | Passed: 16 routes, including `/incidents`, `/incidents/[key]` and `/evaluation` |
| Fresh generation, training and activation | Passed with an empty database and random credentials; 6/8 model development targets met, as in Sprint 2 |
| Fresh API startup | Health check passed; both logins succeeded with the configured passwords and the old demo password was rejected; six demo runs were scored; six incidents in four categories and 46 alert windows were produced; incident evidence, timeline and trace endpoints answered |
| Role checks | Analysts received 403 from `GET /scenarios`; both roles could read incidents and evaluations |
| Reports | Incident PDF (4 pages) and CSV, and evaluation PDF, were generated |
| Publication file check | No real environment files, secret values, credential documents, databases, model binaries, generated development data or personal paths selected |

## Evaluation results (e4, engine i2, model v1)

| Data | Targets met (full hybrid) | Notes |
| --- | --- | --- |
| Development test split, 110 runs | 14 of 14 | Event detection 92.2 %, incident detection 93.3 %, classification accuracy 85.7 %, segment localisation 96.0 % |
| Held-out set, 72 runs | 8 of 15 | Missed: event detection (71.7 %), weakest scenario type, median time to detect, compromised-reporting detection, incident detection (80.0 %), classification accuracy (73.2 %) and OT layer accuracy |

The held-out set uses weaker, earlier, slower and longer scenarios than development, and its labels and the engine were not changed after the first look. The held-out misses are reported as missed. Charter acceptance remains a separate evaluation task.

## Remaining limitations

- The imported Next.js 14.2.0 release has a published security advisory, and ESLint 8 and Recharts 2 emit deprecation notices. Dependency maintenance needs review before any public deployment. This import verifies local build and setup only; it is not a deployment security assessment.
- Backend dependencies emit a `crypt` deprecation warning, and Passlib logs a bcrypt version-metadata warning; password hashing and login work.
- The Scrum board and issue statuses were not changed by this source import.
