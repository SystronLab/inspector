# Workspace Instructions

Before doing project work, read `PROJECT_CONTEXT.md` and `README.md`. Treat
`PROJECT_CONTEXT.md` as the durable handoff between Codex sessions.

This directory is the active 5G Core Inspector project. The sibling directories
`ocudu/`, `openairinterface5g/`, `srsRAN_4G/`,
`oran-sc-ric/`, `uhd/`, `libzmq/`, and `czmq/` are separate upstream repositories or
runtime dependencies. Do not modify them unless the user explicitly puts one of them
in scope. Preserve their existing build products and local changes.

Follow these project rules:

- Base conclusions on observed Open5GS log evidence. Do not infer protocol success,
  identity correlation, PDU establishment, or release without supporting evidence.
- Preserve raw evidence and surface ambiguity instead of guessing between UEs,
  registration attempts, or PDU sessions.
- Keep runtime state in memory unless the user explicitly changes that requirement.
- Edit React source under `frontend/src/`; do not hand-edit generated files under
  `static/`. Run the frontend build to
  publish UI changes.
- Use synthetic data in committed tests and fixtures. Do not commit subscriber data,
  credentials, private identifiers, or captured production/testbed logs.
- Run verification appropriate to the changed area and report any check that could
  not be run.

After meaningful work, update `PROJECT_CONTEXT.md`. Keep it concise and factual:

- record behavior or architecture that future sessions need;
- record important decisions and why they were made;
- update verification status, known issues, and next steps;
- remove or replace stale statements rather than accumulating a diary;
- never add secrets, private subscriber data, or raw non-synthetic logs.
