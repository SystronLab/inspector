# 5G Core Inspector

An evidence-based Python/FastAPI inspector for Open5GS terminal logs.
It reads only core logs: no database, message broker, AI, packet capture, gNB log
reader, or UE log reader. All attempts, events and deduplication data live in memory.
The existing sibling `5g-core-inspector` project is not used.

## Install

```bash
cd ~/5gCoreInspector/ocudu_parent/inspector
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

Python 3.10 or newer is required. The virtual environment has already been created
and dependencies installed in this workspace.

## Two-terminal workflow

Terminal 1 — start the core:

```bash
cd ~/5gCoreInspector/ocudu_parent/ocudu/docker
sudo docker compose up --build 5gc
```

Terminal 2 — start the inspector before initiating UE registration:

```bash
cd ~/5gCoreInspector/ocudu_parent/inspector
source .venv/bin/activate
sudo -v
sudo docker logs --follow --since 0s open5gs_5gc 2>&1 \
  | python3 app.py --stdin --year 2026
```

Open **http://localhost:8000**. The browser polls once per second.
`--since 0s` reads new logs only; an already registered UE will leave the inspector
in WAITING until a new registration is observed. Stop with Ctrl+C.

Direct Docker mode:

```bash
sudo -v
python3 app.py --docker-container open5gs_5gc --year 2026
```

Direct mode executes `sudo -n docker logs --follow --since 0s open5gs_5gc`
using an argument list, never a shell. `sudo -v` authenticates interactively first;
`-n` ensures the reader fails visibly if credentials or permission are unavailable.
Errors appear in the UI, `/api/health`, and stderr. For stdin, upstream Docker errors
are available because the documented pipeline redirects stderr; EOF disconnects
the source. A silent upstream process exit cannot provide its exit code through stdin.

Replay a saved core log:

```bash
python3 app.py --replay registration.log --year 2026
```

The replay runs immediately; the HTTP server remains available afterward. EOF shows
Disconnected while preserving the final record. A clearly labelled synthetic fixture
is included for a quick demonstration:

```bash
python3 app.py --replay tests/fixtures/success.log --year 2026
```

Options: `--timeout 30` (positive seconds), `--year` (current year by default),
`--host 127.0.0.1`, and `--port 8000`.

## React UI development

The single-page UI includes UE and attempt selectors, registration details, PDU
sessions and a searchable evidence timeline. Uncorrelated evidence is collapsed
and appears only when needed. Text uses dark colours, 16px data values and larger
headings. There is no sidebar, summary-card dashboard or duplicate navigation.
Raw evidence is copyable, layouts are responsive and source errors remain visible.
It continues polling once per second; expanded evidence remains open across updates.


The compiled React application is already in `static/`. Existing startup commands
and **http://localhost:8000** are unchanged; no separate frontend server is needed.
Refresh an already open browser once after updating the UI.

To change the frontend (Node 20.19+ or 22.12+ recommended):

```bash
cd ~/5gCoreInspector/ocudu_parent/inspector/frontend
npm ci
npm run dev
```

Vite serves development UI at `http://localhost:5173/static/` and proxies `/api` to
the running FastAPI application on port 8000. To publish local changes to the usual
FastAPI URL, run `npm run build`. This replaces only generated files in `static/`;
edit source files under `frontend/src/`, not the build output.

```bash
npm run build
npm test
```

The Playwright browser tests use synthetic data and the installed Google Chrome at
`/usr/bin/google-chrome`. Set `CHROME_BIN` to another Chrome/Chromium executable if
needed. They cover UE/attempt switching, filtering, evidence escaping/persistence,
source failure reporting, empty states and mobile overflow. The Python tests also
check the generated entry page and bundled asset, so build first after frontend edits.

## Rules and architecture

`engine.py` owns deterministic matching, identity enrichment, state and events.
`pdu.py` tracks PDU session context, IP assignment and SMF removal.
`app.py` runs the reader and timeout watchdog as asynchronous tasks alongside
FastAPI. `frontend/` contains a React dashboard with reusable components, a polling
hook, Vite build configuration and browser tests. `static/` contains its production
build, served by FastAPI at the existing URL. Raw evidence is rendered as text.
Normal Python startup uses the included build; Node is only needed for UI development.

- `InitialUEMessage` starts an attempt in UE_DETECTED.
- Context lines supply RAN/AMF UE NGAP IDs, TAC and Cell ID.
- SUCI identifies the attempt until an IMSI enriches the same record.
- `Registration request` sets REGISTRATION_IN_PROGRESS.
- Only `Registration complete` sets REGISTERED / SUCCESS.
- Specific catalogue rules can diagnose explicit registration rejects, subscriber
  identification failures, authentication failures and NAS security failures.
- A UE context release before completion and a timeout locate the stopped stage but
  do not invent an exact cause. `Unknown UE by SUCI` is not itself a failure: it is
  present in a successful registration flow and requires later explicit failure evidence.
- The default timeout is 30 seconds. Startup/SBI warnings and gNB connectivity do
  not start or reject attempts. An explicit `Deregistration request` after success sets DEREGISTERED (grey) and
  emits DEREGISTRATION_REQUESTED with exact evidence and a request timestamp.
  This state means a request was observed, not that protocol completion was proven.
  The original SUCCESS result, completion time and duration are preserved.
  Requests with conflicting IMSI/SUCI remain uncorrelated; requests without identity
  are accepted only when there is one uniquely compatible UE. Requests before a successful registration are ignored.

Successful logs currently expose no Authentication or Security Mode milestones, so
the inspector never claims those stages succeeded. An explicit failure can still
identify Authentication or NAS Security as the failure stage. The parser matches AMF/GMM
messages for registration evidence and strips ANSI colors and tolerates Docker
prefixes when parsing, while preserving original evidence (without line terminators).
Repeated identical raw lines are ignored. Each event has type, timestamp, timestamp
source, session ID, state, status, identifier snapshot and raw evidence. Timeout
events have `rawEvidence: null` and `timestampSource: timer`; no log evidence is invented.

Open5GS `MM/DD HH:mm:ss.SSS` timestamps use the configured year and retain local,
timezone-unspecified ISO timestamps. Valid log timestamps determine durations;
missing timestamps use local receipt time, explicitly labelled `receipt`. Invalid
calendar timestamps are ignored. Use a single calendar year per run; automatic
year rollover and out-of-order stream reconstruction are not supported.

Live idle timeouts use a monotonic clock from receipt of the initial message.
Timestamped logs also advance timeout checks, which makes replay independent of
playback speed. Replay EOF alone does not prove timeout: an incomplete replay
remains in progress unless a later timestamp establishes the deadline.

## Multiple UEs and correlation limits

Multiple registration attempts can be active concurrently, with independent timeout
clocks. Every distinct InitialUEMessage starts an attempt. Exact duplicate lines
remain deduplicated. The UI groups attempts by observed IMSI, then SUCI, with a
separate entry for each unidentified attempt. Select a UE and an attempt to view its
registration, PDU sessions and timeline. Known SUCI/IMSI associations group history
without inventing an IMSI in an older record. A selected attempt stays selected as
new logs arrive; the default view follows the most recently started attempt.

Rules match compatible IMSI, SUCI and AMF/RAN UE NGAP IDs. New identifiers can enrich
an attempt only when a unique compatible candidate exists. Anonymous messages are
accepted only with a single compatible active attempt. No SUCI-to-IMSI mathematical
conversion, nearest-timestamp matching or most-recent-UE guessing is performed.
RAN IDs can be reused; conflicting identifiers prevent assignment.

**The logs determine how much multi-UE correlation is possible.** The actual INFO
logs sometimes omit all identifiers (`InitialUEMessage`, `Registration request`).
If two active attempts could own a line, it is retained under **Uncorrelated evidence**
with its reason and raw text. In particular, an IMSI-only completion cannot safely
resolve two SUCI-only concurrent attempts without a linking message. Such attempts
may time out even though an uncorrelated completion exists. Uncorrelated lines are
not automatically reassigned later. This is visible uncertainty, not a proven reject.
Logs must be ordered and captured from before registration for complete histories.
Tests demonstrate interleaving with explicit linking identifiers; simultaneous real
multi-UE traffic has not been verified in this one-UE testbed.

## PDU session evidence

Each registration record has a `pduSessions` array. Each entry stores an internal ID,
nullable `pduSessionId`, DNN, IPv4/IPv6, slice SST/SD, observation timestamps, state,
and evidence events. Registration status and duration stay independent of PDU state.

| Observed core message | Result |
| --- | --- |
| GMM `UE SUPI[...] DNN[...] ... smContextRef[...]` | CONTEXT_OBSERVED; extract DNN and slice |
| SMF `UE SUPI[...] DNN[...] IPv4[...] IPv6[...]` | IP_ASSIGNED if a nonempty address is present |
| AMF `[imsi-...:<psi>:<state>] .../modify` | Enrich PDU ID only; no establishment-success inference |
| SMF `Removed Session: UE IMSI:[...] DNN:[<dnn>:<psi>] ...` | RELEASED, meaning SMF session removal was observed |
| AMF `[imsi-...:<psi>] Release SM Context [state:...]` | Add release-context evidence only |

The PDU ID formats were checked against `src/smf/context.c` and
`src/amf/nsmf-handler.c` in the running Open5GS container. An address log does not
prove full NAS establishment, user-plane reachability or successful data transfer.
There is deliberately no ESTABLISHED label without explicit supporting evidence.
Deregistration alone does not mark PDU sessions released, nor do global SMF/UPF
session counters or PFCP association messages.

PDU lines must explicitly identify an observed IMSI. Within that UE, match PDU ID
when present and compatible DNN/address/slice fields; enrich a unique compatible
session when its ID is absent. Different DNNs/addresses can form separate sessions.
If multiple sessions fit, retain the line as uncorrelated. Same-DNN simultaneous
sessions with no distinguishing identifiers cannot be separated reliably. A new
observation after release starts a new session generation. Delayed SMF removal
searches existing sessions across registration attempts; ambiguous matches do not
change either session. Missing earlier registration evidence remains uncorrelated.

Attempts, PDU sessions, events and deduplication data accumulate in memory until
restart. Use bounded testbed runs; no database or disk runtime state is introduced.

## Failure diagnosis and confidence

Each failed attempt reports the last confirmed stage, failure stage, reason, optional
protocol cause, confidence, failure timestamp, duration from `InitialUEMessage`, UE
identifiers, and exact evidence. The canonical `REGISTRATION_FAILED` event carries the
same diagnosis. Rules live separately in `failure_rules.py` so captured evidence can
be reviewed before the catalogue is extended.

Each registration also exposes `networkFunctions`, containing only core functions
seen in evidence correlated to that attempt. GMM log components are presented as AMF;
they are not incorrectly counted as a separate network function. Unrelated global NF
startup and service-discovery messages do not add functions to a UE attempt.

- `EXACT`: a matching Open5GS error, reject, or failure line explicitly identifies
  the cause.
- `STAGE_LEVEL`: the observed sequence establishes where progress stopped, but the
  precise cause is absent. Timeouts are stage-level because silence cannot prove why
  registration stopped.
- `UNKNOWN`: neither a reliable stage nor cause can be established. No record is
  created merely because no `InitialUEMessage` was observed; in that situation inspect
  the UE, RF, RRC, and gNB-to-AMF path.

Capture a real failed attempt from before the UE connects:

```bash
sudo docker logs --follow --since 0s open5gs_5gc 2>&1 \
  | tee failed-registration.log
```

New exact rules should be added only after checking real failed-registration logs.
`Cannot find SUCI [<status>]` was verified from this deployment on 2026-09-07 and
is diagnosed as an exact subscriber-identification failure; the numeric status is
preserved without assigning an undocumented meaning. The other initial subscriber,
authentication, NAS-security, registration-reject, and context-release strings are
conservative synthetic candidates and remain unverified against this deployment.
Synthetic test fixtures are labelled as such and must not be treated as captured
Open5GS output.

## API

- `GET /api/health`: application status, source connected flag, mode, container name,
  source error, lines processed (including duplicates), matched event count, UE count
  (including unidentified attempts), uncorrelated-line count.
- `GET /api/registration`: latest attempt, or a WAITING record before any attempt.
- `GET /api/registration?sessionId=registration-1`: one attempt; 404 if unknown.
- `GET /api/registrations`: all attempts, including PDU sessions and evidence.
- `GET /api/ues`: grouped identities and their registration session IDs.
- `GET /api/events`: all events; optional `?sessionId=registration-1` filter.
- `GET /api/uncorrelated`: raw evidence that could not be uniquely correlated.

Container name is reported for direct Docker mode; stdin/replay cannot independently
verify their source container and report null. In stdin mode, Connected means the
input pipe has delivered data and has not reached EOF. Authenticate with `sudo -v`
before the pipeline so its redirected stderr cannot hide a password prompt. In Docker mode it means the log process is attached; process
errors change this to Disconnected.

## Verification in this workspace

All tests use explicitly synthetic data. Coverage includes registration, durations,
identifiers, independent timeouts, failure, duplicates, noise, deregistration, malformed
lines, concurrent UEs, conflicting/anonymous evidence, PDU addresses and removal,
multiple PDU sessions, re-registration history, delayed removal, API and source errors.
Run `python -m pytest -q` from this directory.

The real container's retained terminal logs were replayed from a temporary file,
`/tmp/registration-inspector-pdu-real.log` (not bundled). They contained one IMSI,
`imsi-001010123456780`, across four registration attempts. The latest observed attempt
started at `2026-09-06T16:12:39.180`, completed at `16:12:39.728` (**548 ms**), and
subsequently deregistered. Its PDU session was ID **1**, DNN **internet**, IPv4
**10.45.1.2**, slice SST **1** / SD **0xffffff**. SMF removal at `16:12:47.476` set its
PDU state to RELEASED. The earlier supplied `15:44:57.741` registration still measures
**538 ms** in history. These are different attempts.

The live Docker source is available; no new UE registration or traffic was triggered
for verification. Multi-UE behavior is verified with synthetic interleaved inputs,
not a real concurrent multi-UE capture. The browser UI and API are also checked
against real-log replay before restarting the live reader.
