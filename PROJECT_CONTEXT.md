# 5G Core Inspector — Project Context

Last updated: 2026-09-07

## Current project

`inspector/` is the active application. It is an in-place Python 3.10+ FastAPI
service with a React/Vite frontend for deterministic, evidence-based analysis of
Open5GS logs. Do not create another inspector or replace this application.

Runtime state is intentionally in memory. The application has no database, broker,
AI, packet capture, gNB reader, or UE reader. The parent directory is not a Git
repository. Sibling source trees are out of scope unless the user explicitly says
otherwise.

## Architecture

- `inspector/app.py`: CLI, API/static hosting, Docker/stdin/replay readers, and the
  asynchronous 250 ms timeout watchdog.
- `inspector/engine.py`: registration attempts, correlation, progress state,
  diagnostic state, events, evidence, deduplication, and network-function metadata.
- `inspector/failure_rules.py`: dedicated declarative failure-rule catalogue.
- `inspector/pdu.py`: conservative correlated PDU-session evidence.
- `inspector/frontend/src/`: editable React UI.
- `inspector/static/`: generated Vite build; never edit it directly.
- `inspector/tests/`: synthetic Python and Playwright tests unless explicitly noted.

## Registration and diagnosis contract

Progress remains `WAITING`, `UE_DETECTED`, `REGISTRATION_IN_PROGRESS`, `REGISTERED`,
or `FAILED` (existing post-success `DEREGISTERED` behavior is preserved). Verified
success sequence: `InitialUEMessage`, `Registration request`, `Registration complete`.
Only `Registration complete` proves success. Current successful logs do not expose
successful Authentication or NAS Security milestones; never fabricate them.

Failure stages are `BEFORE_CORE`, `NGAP_NAS`, `SUBSCRIBER_IDENTIFICATION`,
`AUTHENTICATION`, `NAS_SECURITY`, `REGISTRATION_COMPLETION`,
`AFTER_REGISTRATION_REQUEST`, and `UNKNOWN`. Records/events expose
`lastSuccessfulStage`, `failureStage`, `failureReason`, `protocolCause`,
`diagnosisConfidence`, structured `failureEvidence`, `failedAt`, and `durationMs`.
Confidence is `EXACT`, `STAGE_LEVEL`, or `UNKNOWN`. Silence never becomes an exact
cause. Timeout defaults to 30 seconds and creates no record without an observed
`InitialUEMessage`.

Correlation priority is IMSI/SUPI, SUCI, AMF UE NGAP ID, RAN UE NGAP ID, then one
uniquely compatible active attempt. Preserve SUCI-to-IMSI enrichment. Never attach a
conflicting explicit identity. Duplicate raw lines and repeated failures are ignored.
Post-success release or deregistration evidence must not convert success to failure.

## Verified failure evidence

A real attempt made after changing the UE identity produced this sequence (subscriber
identifiers are intentionally omitted): GMM logged `Cannot find SUCI [404]`, then AMF
logged `Registration reject [7]`.

`failure_rules.py` therefore contains the deployment-verified `suci_not_found` rule.
It reports `SUBSCRIBER_IDENTIFICATION`, reason “Core could not find the subscriber for
the SUCI”, confidence `EXACT`, and preserves `404` without inventing its meaning.
`Unknown UE by SUCI` alone remains non-failure evidence because it also occurs in the
successful flow. Other initial failure patterns are conservative synthetic candidates
until confirmed using real failed-registration logs.

## Current UI decisions

- Title is **5G Core Inspector**.
- Full-width header/footer use the SYSTRON Lab forest-green theme. The header links
  `SYSTRON LAB` to `https://systronlab.github.io/`.
- Font Awesome icons are installed and used sparingly.
- Footer reads `5G Core Inspector` and `Open5GS log diagnostics`; do not restore
  “Developed at SYSTRON Lab” unless requested.
- The visible confidence-explanation paragraph was removed.
- The uncorrelated-evidence section is hidden from the UI, but
  `/api/uncorrelated` remains available.
- `networkFunctions` remains in the API/model, but “Network functions involved” is
  hidden from the UI.
- Timeline events do not display the `Log timestamp` source label.
- Failure panels show stage, last confirmed stage, reason, protocol cause, confidence,
  duration, and expandable exact Open5GS evidence.

## Verification baseline

Latest completed verification:

```text
.venv/bin/python -m pytest -q     64 passed
npm --prefix frontend run build  passed
npm --prefix frontend test       7 passed
```

Python emits two dependency deprecation warnings and one harmless TestClient stdin
transport cleanup warning. Playwright emits a `NO_COLOR`/`FORCE_COLOR` warning.
The known-good synthetic replay still reaches `REGISTERED` in 538 ms.

After frontend changes, always rebuild so FastAPI serves the current UI. Start future
work by reading this file and `inspector/README.md`, then inspect current code before
editing. Update this handoff after meaningful changes without storing subscriber
identifiers, credentials, or raw private logs.
