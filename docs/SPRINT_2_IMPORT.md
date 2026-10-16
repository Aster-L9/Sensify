# Sprint 2 source import and verification

Prepared from `Sensify.zip` on 16 October 2026, retaining the repository's existing charter README, license and Git history.

## Packaging changes

- Imported the Sprint 2 simulator, scenarios, detection/trust/consistency pipeline, model registry, API routes, frontend screens and tests. The new simulator package replaces the Sprint 1 simulator module.
- Retained required environment validation for JWT signing and seeded account passwords. Blank environment templates replace real configuration; tests use isolated test-only credentials.
- Excluded credential documents, the local SQLite database, generated training data, serialized models, dependencies, builds and caches. Preserved supplied evaluation JSON/Markdown under `docs/evaluation/sprint-2-v1/`.
- Documented generation, training and activation for a fresh checkout.
- Repaired the frontend lockfile and aligned ESLint/config with the imported Next.js 14.2.0 release so `npm ci`, lint and build complete.
- Fixed model-artifact resolution for legacy Windows absolute paths on macOS/Linux. The existing regression test now covers drive-letter, UNC and POSIX paths.

## Verification

Environment: Python 3.12.14, Node.js 24.21.0, npm 11.19.0.

| Check | Result |
| --- | --- |
| Pinned backend development dependencies | Installed successfully in an isolated environment |
| Backend `python -m pytest` | 121 passed, 3 subtests passed; 1 deprecation warning |
| Frontend `npm ci` | Passed using the repaired lockfile |
| Frontend `npm run lint` | Passed with 6 existing warnings |
| Frontend `npm run build` | Passed, including TypeScript checks and page generation |
| Fresh generation/training/activation | Passed using an isolated empty database and random temporary credentials |
| Fresh API startup | Health check, both logins, six segments and six scored demo runs passed |
| Regenerated evaluation | Metrics and target comparisons exactly matched the supplied v1 snapshot: 6/8 development targets met |
| Publication file check | No real environment files, source environment secret values, credential documents, databases, model binaries, generated datasets, dependencies or caches selected |

## Remaining limitations

The two development evaluation misses are overall event detection and weakest-scenario detection (sensor faults); see the archived report. Charter acceptance remains a separate evaluation task.

Lint reports four existing plain-image optimization warnings and two run-page effect-dependency warnings. Backend dependencies emit a `crypt` deprecation warning, and Passlib logs a bcrypt version-metadata warning; password hashing and both login checks succeeded.

The imported Next.js 14.2.0 dependency emits an npm security warning. Next.js and other dependency maintenance require review before public deployment. ESLint 8 and Recharts 2 also emit deprecation notices. This import verifies the supplied application's build and local setup; it is not a deployment security assessment.

The Scrum board and issue statuses were not changed by this source import.
