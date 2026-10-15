export type Role = "trainee" | "instructor" | "admin";

export interface Credentials {
  userId: string;
  pin: string;
  role: Role;
  unitId: string;
}

export interface SessionSummary {
  session_id: string;
  scenario_id: string;
  trainee_id: string;
  selection_mode: "fixed" | "adaptive";
  status: "active" | "completed" | "interrupted";
  rating_eligible: boolean;
  total_score: number | null;
}

export interface ScenarioPoint {
  t_ms: number;
  x_m: number;
  y_m: number;
  altitude_m: number;
}

export interface ScenarioTarget {
  target_id: string;
  entity_class: string;
  affiliation: string;
  t_visible_ms: number;
  trajectory: ScenarioPoint[];
}

export interface Scenario {
  scenario_id: string;
  duration_ms: number;
  profile: { profile_id: string; difficulty: number; skill_tags: string[] };
  targets: ScenarioTarget[];
}

export interface NodeResult {
  node_id: string;
  action: string;
  outcome: string;
  event_id: string | null;
  target_id: string | null;
  detection_delay_ms: number | null;
  timing_band: string | null;
  max_points: number;
  points: number;
}

export interface ScoreReport {
  total_score: number;
  max_score: number;
  interrupted: boolean;
  rating_eligible: boolean;
  node_results: NodeResult[];
}

export interface AdaptiveOption {
  profile_id: string;
  difficulty: number;
  skill_tags: string[];
}

export interface DoctrineSummary {
  doctrine_id: string;
  version: string;
}

export interface SessionSnapshot {
  session_id: string;
  trainee_id: string;
  selection_mode: "fixed" | "adaptive";
  status: "active" | "completed" | "interrupted";
  rating_eligible: boolean;
  rating_applied: boolean;
  scenario: Scenario;
  events: Array<Record<string, unknown>>;
  score: ScoreReport | null;
}

interface LoginResponse {
  user_id: string;
  role: Role;
  unit_id: string;
}

export interface UnitTraineeSummary {
  trainee_id: string;
  completed_sessions: number;
  average_score: number | null;
  rating_eligible_sessions: number;
}

export interface UnitSummary {
  unit_id: string;
  trainees: UnitTraineeSummary[];
  trends: Array<{
    selection_mode: "fixed" | "adaptive";
    completed_sessions: number;
    average_score: number;
    rating_eligible_sessions: number;
  }>;
}

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  credentials?: Pick<Credentials, "userId" | "pin">
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (credentials) {
    headers.set("X-Actor-Id", credentials.userId);
    headers.set("X-Pin", credentials.pin);
  }

  const response = await fetch(`/api${path}`, { ...options, headers });
  const body = (await response.json().catch(() => ({}))) as { detail?: string } & T;
  if (!response.ok) {
    throw new ApiError(body.detail ?? `Local API request failed (${response.status})`);
  }
  return body;
}

export const api = {
  async bootstrap(userId: string, pin: string): Promise<Credentials> {
    const response = await request<LoginResponse>("/bootstrap", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, pin })
    });
    return {
      userId: response.user_id,
      pin,
      role: response.role,
      unitId: response.unit_id
    };
  },

  async login(userId: string, pin: string): Promise<Credentials> {
    const response = await request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, pin })
    });
    return {
      userId: response.user_id,
      pin,
      role: response.role,
      unitId: response.unit_id
    };
  },

  listSessions(credentials: Credentials): Promise<SessionSummary[]> {
    return request<SessionSummary[]>("/sessions", {}, credentials);
  },

  getSession(credentials: Credentials, sessionId: string): Promise<SessionSnapshot> {
    return request<SessionSnapshot>(`/sessions/${encodeURIComponent(sessionId)}`, {}, credentials);
  },

  async createDemoSession(credentials: Credentials, traineeId: string, seed: number): Promise<string> {
    const scenario = await request<Scenario>(
      "/scenarios/v0",
      {
        method: "POST",
        body: JSON.stringify({
          seed,
          profile: {
            profile_id: "intro-single-target",
            difficulty: 1,
            skill_tags: ["detection", "classification", "assessment", "response"]
          }
        })
      },
      credentials
    );
    const session = await request<{ session_id: string }>(
      "/sessions",
      {
        method: "POST",
        body: JSON.stringify({ trainee_id: traineeId, scenario, selection_mode: "fixed" })
      },
      credentials
    );
    return session.session_id;
  },

  async createAdaptiveDemoSession(
    credentials: Credentials,
    traineeId: string,
    seed: number
  ): Promise<{ sessionId: string; profileId: string }> {
    const options: AdaptiveOption[] = [
      { profile_id: "adaptive-detection", difficulty: 1, skill_tags: ["detection"] },
      { profile_id: "adaptive-classification", difficulty: 2, skill_tags: ["classification"] },
      { profile_id: "adaptive-assessment", difficulty: 3, skill_tags: ["assessment"] },
      { profile_id: "adaptive-response", difficulty: 2, skill_tags: ["response"] }
    ];
    const choice = await request<AdaptiveOption>(
      "/adaptive/next",
      { method: "POST", body: JSON.stringify({ trainee_id: traineeId, options }) },
      credentials
    );
    const scenario = await request<Scenario>(
      "/scenarios/v1",
      {
        method: "POST",
        body: JSON.stringify({
          seed,
          profile: choice,
          swarm_size: 3,
          clutter_count: 2,
          terrain: "rural",
          time_of_day: "day",
          weather: "clear"
        })
      },
      credentials
    );
    const session = await request<{ session_id: string }>(
      "/sessions",
      {
        method: "POST",
        body: JSON.stringify({ trainee_id: traineeId, scenario, selection_mode: "adaptive" })
      },
      credentials
    );
    return { sessionId: session.session_id, profileId: choice.profile_id };
  },

  async scoreSession(credentials: Credentials, sessionId: string): Promise<ScoreReport> {
    const response = await request<{ report: ScoreReport }>(
      `/sessions/${encodeURIComponent(sessionId)}/score`,
      {
        method: "POST",
        body: JSON.stringify({ doctrine_id: "generic-demo-v1", version: "1.0.0" })
      },
      credentials
    );
    return response.report;
  },

  getRatings(credentials: Credentials, traineeId: string): Promise<Record<string, number>> {
    return request<Record<string, number>>(
      `/ratings/${encodeURIComponent(traineeId)}`,
      {},
      credentials
    );
  },

  getTrends(credentials: Credentials): Promise<Array<Record<string, unknown>>> {
    return request<Array<Record<string, unknown>>>("/trends", {}, credentials);
  },

  getUnitSummary(credentials: Credentials, unitId: string): Promise<UnitSummary> {
    return request<UnitSummary>(`/units/${encodeURIComponent(unitId)}/summary`, {}, credentials);
  },

  getDoctrines(credentials: Credentials): Promise<DoctrineSummary[]> {
    return request<DoctrineSummary[]>("/doctrines", {}, credentials);
  },

  uploadDoctrine(credentials: Credentials, yamlText: string): Promise<DoctrineSummary> {
    return request<DoctrineSummary>(
      "/doctrines",
      { method: "POST", body: JSON.stringify({ yaml_text: yamlText }) },
      credentials
    );
  },

  createUser(
    credentials: Credentials,
    userId: string,
    pin: string,
    role: Role,
    unitId: string
  ): Promise<{ user_id: string; role: Role; unit_id: string }> {
    return request<{ user_id: string; role: Role; unit_id: string }>(
      "/users",
      { method: "POST", body: JSON.stringify({ user_id: userId, pin, role, unit_id: unitId }) },
      credentials
    );
  },

  createBackup(credentials: Credentials, name: string): Promise<{ path: string }> {
    return request<{ path: string }>(
      "/backups",
      { method: "POST", body: JSON.stringify({ name }) },
      credentials
    );
  }
};
