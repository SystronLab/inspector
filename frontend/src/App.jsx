import React, { useState } from "react";
import { useInspector } from "./useInspector";
import { Status, Fields, Evidence, readable } from "./components/Common";
import Timeline from "./components/Timeline";
import PduSessions from "./components/PduSessions";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faCircleNodes,
  faClockRotateLeft,
  faServer,
  faShieldHalved,
  faSimCard,
} from "@fortawesome/free-solid-svg-icons";

const blank = {
  state: "WAITING",
  registrationStatus: "WAITING",
  events: [],
  pduSessions: [],
};
export default function App() {
  const { snapshot, error } = useInspector();
  const [selection, setSelection] = useState("");
  const [attempt, setAttempt] = useState("");
  const {
    health,
    attempts = [],
    ues = [],
    waiting = blank,
  } = snapshot || {};
  const ue = ues.find((u) => u.identity === selection) || ues.at(-1);
  const choices = ue
    ? attempts.filter((r) => ue.sessionIds.includes(r.sessionId))
    : [];
  const record =
    choices.find((r) => r.sessionId === attempt) || choices.at(-1) || waiting;
  const connected = Boolean(health?.logSource.connected && !error);
  const sourceError = error || health?.logSource.error;
  return (
    <>
      <header className="page-header">
        <div className="header-inner">
          <div>
            <a className="lab-brand" href="https://systronlab.github.io/">
              <span>SYS</span>TRON LAB
            </a>
            <h1><FontAwesomeIcon icon={faCircleNodes} /> 5G Core Inspector</h1>
          </div>
          <div className="source-status">
            <span><FontAwesomeIcon icon={faServer} /> Core log connection</span>
            <strong className={`connection ${connected ? "connected" : ""}`}>
              <i />
              {connected ? "Connected" : "Disconnected"}
            </strong>
            <span className="refresh-note">Updates every second</span>
          </div>
        </div>
      </header>
      <main>
      {sourceError && (
        <div className="notice danger" role="alert">
          <strong>
            {error ? "Inspector connection interrupted" : "Log source error"}
          </strong>
          <p>
            {sourceError}
            {error && " · Showing the last received snapshot."}
          </p>
        </div>
      )}
      {health?.linesProcessed === 0 && !sourceError && (
        <div className="notice">
          <strong>Waiting for core logs</strong>
          <p>
            Start the reader before registering a UE. Run sudo -v before the
            stdin pipeline.
          </p>
        </div>
      )}
      <div className="selectors">
        <label>
          <span className="label-title"><FontAwesomeIcon icon={faSimCard} /> UE</span>
          <select
            aria-label="UE"
            value={ue?.identity || ""}
            onChange={(e) => {
              setSelection(e.target.value);
              setAttempt("");
            }}
          >
            {ues.length ? (
              ues.map((u) => (
                <option value={u.identity} key={u.identity}>
                  {u.identity}
                </option>
              ))
            ) : (
              <option value="">Waiting for UE</option>
            )}
          </select>
        </label>
        <label>
          <span className="label-title"><FontAwesomeIcon icon={faClockRotateLeft} /> Registration attempt</span>
          <select
            aria-label="Registration attempt"
            value={record.sessionId || ""}
            onChange={(e) => {
              setSelection(ue?.identity || "");
              setAttempt(e.target.value);
            }}
          >
            {choices.length ? (
              choices.map((r) => (
                <option value={r.sessionId} key={r.sessionId}>
                  {r.sessionId} · {r.startedAt?.replace("T", " ")}
                </option>
              ))
            ) : (
              <option value="">No attempts</option>
            )}
          </select>
        </label>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2><FontAwesomeIcon icon={faShieldHalved} /> Registration</h2>
          <Status state={record.state} />
        </div>
        <h3 className="identity-value">
          {record.imsi || record.suci || "Waiting for UE detection"}
        </h3>
        <div className="registration-result">
          <p>
            Registration result: <strong>{record.registrationStatus}</strong>
          </p>
          <p className="duration">
            Duration: <strong>{record.durationMs ?? "—"} ms</strong>
          </p>
        </div>
        {record.state === "DEREGISTERED" && (
          <p className="explanation">
            Deregistration request observed; the successful registration result
            is preserved.
          </p>
        )}
        <Fields
          fields={[
            ["SUCI", record.suci],
            ["IMSI", record.imsi],
            ["RAN UE NGAP ID", record.ranUeNgapId],
            ["AMF UE NGAP ID", record.amfUeNgapId],
            ["TAC", record.tac],
            ["Cell ID", record.cellId],
            ["Registration started", record.startedAt],
            ["Registration completed", record.completedAt],
            ["Deregistration requested", record.deregistrationRequestedAt],
          ]}
        />
        {record.state === "FAILED" && (
          <div className={`failure-panel confidence-${record.diagnosisConfidence}`} role="alert">
            <h3>Registration failed</h3>
            <Fields fields={[
              ["Failed at", readable(record.failureStage)],
              ["Last confirmed stage", readable(record.lastSuccessfulStage)],
              ["Reason", record.failureReason],
              ["Protocol cause", record.protocolCause || "Not provided by core"],
              ["Confidence", record.diagnosisConfidence === "EXACT" ? "Exact" : record.diagnosisConfidence === "STAGE_LEVEL" ? "Stage-level" : "Unknown"],
              ["Duration", record.durationMs == null ? null : `${record.durationMs} ms`],
            ]} />
            <Evidence raw={record.failureEvidence?.rawLogLine} label="Evidence from Open5GS" />
          </div>
        )}
      </section>
      <PduSessions sessions={record.pduSessions} />
      <Timeline key={record.sessionId} events={record.events} />
      </main>
      <footer className="page-footer">
        <div className="footer-inner">
          <span><FontAwesomeIcon icon={faCircleNodes} /> 5G Core Inspector</span>
          <span>Open5GS log diagnostics</span>
        </div>
      </footer>
    </>
  );
}
