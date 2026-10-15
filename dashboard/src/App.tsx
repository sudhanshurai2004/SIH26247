import { useEffect, useMemo, useState } from "react";

import {
  api,
  Credentials,
  ScenarioPoint,
  ScenarioTarget,
  SessionSnapshot,
  SessionSummary,
  UnitSummary
} from "./api";

const canManageSessions = (role: Credentials["role"]) => role === "admin" || role === "instructor";

function interpolate(pointA: ScenarioPoint, pointB: ScenarioPoint, tMs: number) {
  const span = pointB.t_ms - pointA.t_ms;
  const progress = span === 0 ? 0 : (tMs - pointA.t_ms) / span;
  return {
    x: pointA.x_m + (pointB.x_m - pointA.x_m) * progress,
    y: pointA.y_m + (pointB.y_m - pointA.y_m) * progress
  };
}

function positionAt(target: ScenarioTarget, tMs: number) {
  const points = target.trajectory;
  for (let index = 0; index < points.length - 1; index += 1) {
    if (points[index].t_ms <= tMs && tMs <= points[index + 1].t_ms) {
      return interpolate(points[index], points[index + 1], tMs);
    }
  }
  const last = points[points.length - 1];
  return { x: last.x_m, y: last.y_m };
}

function eventLabel(event: Record<string, unknown>) {
  const type = typeof event.event_type === "string" ? event.event_type : "event";
  const offset = typeof event.t_offset_ms === "number" ? `${event.t_offset_ms} ms` : "no offset";
  return `${type} · ${offset}`;
}

function LoginPanel({ onAuthenticated }: { onAuthenticated: (credentials: Credentials) => void }) {
  const [userId, setUserId] = useState("");
  const [pin, setPin] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function authenticate(bootstrap: boolean) {
    setBusy(true);
    setMessage(null);
    try {
      const credentials = bootstrap
        ? await api.bootstrap(userId, pin)
        : await api.login(userId, pin);
      onAuthenticated(credentials);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Local login failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">SIH PS 26247 · OFFLINE TRAINING</p>
        <h1 id="page-title">Threat Simulation Trainer</h1>
        <p className="lead">
          Local seeded scenarios, replay, and after-action review. No telemetry, weapon, or
          targeting interface is present.
        </p>
      </section>
      <form
        className="login-card"
        onSubmit={(event) => {
          event.preventDefault();
          void authenticate(false);
        }}
      >
        <h2>Local sign in</h2>
        <label>
          User ID
          <input value={userId} onChange={(event) => setUserId(event.target.value)} required />
        </label>
        <label>
          PIN
          <input
            inputMode="numeric"
            type="password"
            value={pin}
            onChange={(event) => setPin(event.target.value)}
            required
          />
        </label>
        {message ? <p className="form-message" role="alert">{message}</p> : null}
        <button disabled={busy} type="submit">Sign in locally</button>
        <button
          className="secondary-button"
          disabled={busy}
          type="button"
          onClick={() => void authenticate(true)}
        >
          First run: create local admin
        </button>
      </form>
    </main>
  );
}

export default function App() {
  const [credentials, setCredentials] = useState<Credentials | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selectedSession, setSelectedSession] = useState<SessionSnapshot | null>(null);
  const [replayMs, setReplayMs] = useState(0);
  const [traineeId, setTraineeId] = useState("trainee-001");
  const [scenarioSeed, setScenarioSeed] = useState(42);
  const [notice, setNotice] = useState<string | null>(null);
  const [trends, setTrends] = useState<Array<Record<string, unknown>>>([]);
  const [unitSummary, setUnitSummary] = useState<UnitSummary | null>(null);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [doctrines, setDoctrines] = useState<Array<{ doctrine_id: string; version: string }>>([]);
  const [doctrineYaml, setDoctrineYaml] = useState("");
  const [newUserId, setNewUserId] = useState("trainee-001");
  const [newUserPin, setNewUserPin] = useState("3456");
  const [newUserRole, setNewUserRole] = useState<Credentials["role"]>("trainee");
  const [newUserUnitId, setNewUserUnitId] = useState("local-unit");
  const [backupName, setBackupName] = useState("trainer-backup");

  async function refreshSessions(activeCredentials: Credentials, selectedId?: string) {
    try {
      const nextSessions = await api.listSessions(activeCredentials);
      setSessions(nextSessions);
      const id = selectedId ?? selectedSession?.session_id;
      if (id) {
        const snapshot = await api.getSession(activeCredentials, id);
        setSelectedSession(snapshot);
        setReplayMs(0);
      }
      if (canManageSessions(activeCredentials.role)) {
        const [nextTrends, nextUnitSummary, nextRatings, nextDoctrines] = await Promise.all([
          api.getTrends(activeCredentials),
          api.getUnitSummary(activeCredentials, activeCredentials.unitId),
          api.getRatings(activeCredentials, traineeId),
          api.getDoctrines(activeCredentials)
        ]);
        setTrends(nextTrends);
        setUnitSummary(nextUnitSummary);
        setRatings(nextRatings);
        setDoctrines(nextDoctrines);
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not refresh local data.");
    }
  }

  useEffect(() => {
    if (credentials) {
      void refreshSessions(credentials);
    }
  }, [credentials]);

  const targetPositions = useMemo(() => {
    if (!selectedSession) {
      return [];
    }
    return selectedSession.scenario.targets.map((target) => ({
      target,
      position: positionAt(target, replayMs)
    }));
  }, [replayMs, selectedSession]);

  async function selectSession(sessionId: string) {
    if (!credentials) {
      return;
    }
    try {
      const snapshot = await api.getSession(credentials, sessionId);
      setSelectedSession(snapshot);
      setReplayMs(0);
      setNotice(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not load the session.");
    }
  }

  async function createDemoSession() {
    if (!credentials) {
      return;
    }
    try {
      const sessionId = await api.createDemoSession(credentials, traineeId, scenarioSeed);
      await refreshSessions(credentials, sessionId);
      setNotice(`Created local seeded session ${sessionId}.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not create the demo session.");
    }
  }

  async function createAdaptiveSession() {
    if (!credentials) {
      return;
    }
    try {
      const created = await api.createAdaptiveDemoSession(credentials, traineeId, scenarioSeed);
      await refreshSessions(credentials, created.sessionId);
      setNotice(`Created adaptive ${created.profileId} session ${created.sessionId}.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not create the adaptive session.");
    }
  }

  async function uploadDoctrine() {
    if (!credentials || !doctrineYaml.trim()) {
      setNotice("Paste a validated local doctrine YAML document first.");
      return;
    }
    try {
      const doctrine = await api.uploadDoctrine(credentials, doctrineYaml);
      setDoctrineYaml("");
      await refreshSessions(credentials);
      setNotice(`Stored local doctrine ${doctrine.doctrine_id} ${doctrine.version}.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not store the doctrine.");
    }
  }

  async function createLocalUser() {
    if (!credentials) {
      return;
    }
    try {
      const user = await api.createUser(
        credentials,
        newUserId,
        newUserPin,
        newUserRole,
        newUserUnitId
      );
      setNotice(`Created local ${user.role} ${user.user_id} in ${user.unit_id}.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not create the local user.");
    }
  }

  async function createBackup() {
    if (!credentials) {
      return;
    }
    try {
      const backup = await api.createBackup(credentials, backupName);
      setNotice(`Created controlled local backup at ${backup.path}.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not create the local backup.");
    }
  }

  async function scoreSelectedSession() {
    if (!credentials || !selectedSession) {
      return;
    }
    try {
      await api.scoreSession(credentials, selectedSession.session_id);
      await refreshSessions(credentials, selectedSession.session_id);
      setNotice("Local AAR score updated.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not score the selected session.");
    }
  }

  if (!credentials) {
    return <LoginPanel onAuthenticated={setCredentials} />;
  }

  return (
    <main className="dashboard-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">OFFLINE AAR DASHBOARD</p>
          <h1>Training review</h1>
        </div>
        <div className="identity">
          <span>{credentials.userId}</span>
          <span className="role-pill">{credentials.role}</span>
          <span className="role-pill">{credentials.unitId}</span>
          <button className="secondary-button" onClick={() => setCredentials(null)} type="button">
            Sign out
          </button>
        </div>
      </header>

      {notice ? <p className="notice" role="status">{notice}</p> : null}

      <section className="dashboard-grid">
        <aside className="panel session-panel">
          <div className="panel-heading">
            <h2>Sessions</h2>
            <button onClick={() => void refreshSessions(credentials)} type="button">Refresh</button>
          </div>
          {canManageSessions(credentials.role) ? (
            <div className="session-create">
              <label>
                Trainee ID
                <input value={traineeId} onChange={(event) => setTraineeId(event.target.value)} />
              </label>
              <label>
                Seed
                <input
                  min="0"
                  onChange={(event) => setScenarioSeed(Number(event.target.value))}
                  type="number"
                  value={scenarioSeed}
                />
              </label>
              <button onClick={() => void createDemoSession()} type="button">Create fixed demo</button>
              <button className="secondary-button" onClick={() => void createAdaptiveSession()} type="button">
                Create adaptive demo
              </button>
            </div>
          ) : null}
          <ul className="session-list">
            {sessions.map((session) => (
              <li key={session.session_id}>
                <button
                  className={selectedSession?.session_id === session.session_id ? "session active" : "session"}
                  onClick={() => void selectSession(session.session_id)}
                  type="button"
                >
                  <strong>{session.scenario_id}</strong>
                  <span>{session.status} · {session.selection_mode}</span>
                  <span>{session.total_score === null ? "Not scored" : `${session.total_score}/${100}`}</span>
                </button>
              </li>
            ))}
          </ul>
          {sessions.length === 0 ? <p className="muted">No local sessions yet.</p> : null}
        </aside>

        <section className="panel replay-panel">
          <div className="panel-heading">
            <h2>Deterministic replay</h2>
            {selectedSession ? <span>{replayMs} ms</span> : null}
          </div>
          {selectedSession ? (
            <>
              <div className="radar" aria-label="Abstract plan-view replay">
                <span className="radar-center" aria-hidden="true" />
                {targetPositions.map(({ target, position }) => (
                  <span
                    className={`radar-target ${target.affiliation}`}
                    key={target.target_id}
                    style={{
                      left: `${Math.max(4, Math.min(96, 50 + position.x / 32))}%`,
                      top: `${Math.max(4, Math.min(96, 50 - position.y / 32))}%`
                    }}
                    title={`${target.target_id} · ${target.entity_class}`}
                  />
                ))}
              </div>
              <label className="replay-slider">
                Replay offset
                <input
                  max={selectedSession.scenario.duration_ms}
                  min="0"
                  onChange={(event) => setReplayMs(Number(event.target.value))}
                  step="100"
                  type="range"
                  value={replayMs}
                />
              </label>
              <p className="muted">
                Trajectory data is precomputed. This plan view exposes no targeting or weapon control.
              </p>
            </>
          ) : (
            <p className="muted">Select a session to inspect its local replay.</p>
          )}
        </section>

        <section className="panel aar-panel">
          <div className="panel-heading">
            <h2>Per-node AAR</h2>
            {canManageSessions(credentials.role) && selectedSession && selectedSession.status !== "active" ? (
              <button onClick={() => void scoreSelectedSession()} type="button">Score session</button>
            ) : null}
          </div>
          {selectedSession?.score ? (
            <>
              <p className="score-total">
                {selectedSession.score.total_score} / {selectedSession.score.max_score}
                {selectedSession.score.rating_eligible ? " · rating eligible" : " · excluded from rating"}
              </p>
              <ol className="node-results">
                {selectedSession.score.node_results.map((result) => (
                  <li key={result.node_id} className={`outcome-${result.outcome}`}>
                    <strong>{result.action}</strong>
                    <span>{result.outcome}</span>
                    <span>{result.points}/{result.max_points}</span>
                    {result.detection_delay_ms !== null ? (
                      <small>{result.detection_delay_ms} ms from t_visible · {result.timing_band}</small>
                    ) : null}
                  </li>
                ))}
              </ol>
            </>
          ) : (
            <p className="muted">This session has not been scored yet.</p>
          )}
        </section>

        <section className="panel timeline-panel">
          <div className="panel-heading"><h2>Event timeline</h2></div>
          {selectedSession ? (
            <ol className="timeline">
              {selectedSession.events.map((event, index) => <li key={`${event.event_id ?? "event"}-${index}`}>{eventLabel(event)}</li>)}
            </ol>
          ) : <p className="muted">No session selected.</p>}
        </section>

        {canManageSessions(credentials.role) ? (
          <section className="panel trends-panel">
            <div className="panel-heading"><h2>Unit trends · {credentials.unitId}</h2></div>
            {unitSummary?.trends.length ? (
              <ul className="trend-list">
                {unitSummary.trends.map((trend) => (
                  <li key={trend.selection_mode}>
                    <strong>{trend.selection_mode}</strong>
                    <span>{trend.completed_sessions} scored sessions</span>
                    <span>average {trend.average_score}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="muted">No scored local sessions available for this unit.</p>}
            <h3>Per-trainee AAR</h3>
            {unitSummary?.trainees.length ? (
              <ul className="trend-list">
                {unitSummary.trainees.map((trainee) => (
                  <li key={trainee.trainee_id}>
                    <strong>{trainee.trainee_id}</strong>
                    <span>{trainee.completed_sessions} scored sessions</span>
                    <span>
                      {trainee.average_score === null
                        ? "no score yet"
                        : `average ${trainee.average_score}`}
                    </span>
                  </li>
                ))}
              </ul>
            ) : <p className="muted">No trainees are assigned to this local unit.</p>}
            {credentials.role === "admin" && trends.length ? (
              <p className="muted">Admin-wide mode trends are available through the local API.</p>
            ) : null}
          </section>
        ) : null}

        {canManageSessions(credentials.role) ? (
          <section className="panel management-panel">
            <div className="panel-heading"><h2>Local instructor tools</h2></div>
            <div className="management-grid">
              <div>
                <h3>Selected trainee ratings</h3>
                {Object.keys(ratings).length ? (
                  <ul className="rating-list">
                    {Object.entries(ratings).map(([skill, rating]) => (
                      <li key={skill}><span>{skill}</span><strong>{rating.toFixed(1)}</strong></li>
                    ))}
                  </ul>
                ) : <p className="muted">No eligible scored attempts for this trainee.</p>}
              </div>
              <div>
                <h3>Validated doctrines</h3>
                <ul className="doctrine-list">
                  {doctrines.map((doctrine) => (
                    <li key={`${doctrine.doctrine_id}-${doctrine.version}`}>
                      {doctrine.doctrine_id} · {doctrine.version}
                    </li>
                  ))}
                </ul>
                <label>
                  Upload local doctrine YAML
                  <textarea
                    onChange={(event) => setDoctrineYaml(event.target.value)}
                    placeholder="Paste a contract-valid, training-only doctrine YAML document"
                    rows={7}
                    value={doctrineYaml}
                  />
                </label>
                <button onClick={() => void uploadDoctrine()} type="button">Validate and store doctrine</button>
              </div>
            </div>
          </section>
        ) : null}

        {credentials.role === "admin" ? (
          <section className="panel admin-panel">
            <div className="panel-heading"><h2>Local administration</h2></div>
            <div className="management-grid">
              <div className="compact-form">
                <h3>Create local user</h3>
                <label>
                  User ID
                  <input value={newUserId} onChange={(event) => setNewUserId(event.target.value)} />
                </label>
                <label>
                  PIN
                  <input
                    inputMode="numeric"
                    onChange={(event) => setNewUserPin(event.target.value)}
                    type="password"
                    value={newUserPin}
                  />
                </label>
                <label>
                  Role
                  <select
                    onChange={(event) => setNewUserRole(event.target.value as Credentials["role"])}
                    value={newUserRole}
                  >
                    <option value="trainee">Trainee</option>
                    <option value="instructor">Instructor</option>
                    <option value="admin">Admin</option>
                  </select>
                </label>
                <label>
                  Unit ID
                  <input
                    onChange={(event) => setNewUserUnitId(event.target.value)}
                    value={newUserUnitId}
                  />
                </label>
                <button onClick={() => void createLocalUser()} type="button">Create local user</button>
              </div>
              <div className="compact-form">
                <h3>Controlled backup</h3>
                <p className="muted">Writes only below the local trainer backup directory.</p>
                <label>
                  Backup name
                  <input value={backupName} onChange={(event) => setBackupName(event.target.value)} />
                </label>
                <button onClick={() => void createBackup()} type="button">Create SQLite backup</button>
              </div>
            </div>
          </section>
        ) : null}
      </section>
    </main>
  );
}
