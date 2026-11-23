const API_URL = import.meta.env.VITE_API_URL ?? "";

export type User = {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
};

export type Registration = User & { access_token: string; token_type: "bearer" };

export type Plant = {
  id: string;
  nickname: string;
  species_scientific_name: string | null;
  species_common_name: string | null;
  species_status: "unconfirmed" | "suggested" | "confirmed";
  created_at: string;
  updated_at: string;
};

export type Photo = {
  id: string;
  storage_key: string;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  checksum_sha256: string;
  read_url: string;
};

export type Observation = {
  id: string;
  plant_id: string;
  description: string | null;
  humidity_pct: number | null;
  temperature_c: number | null;
  observed_at: string;
  created_at: string;
  photos: Photo[];
};

export type CareEvent = {
  id: string;
  plant_id: string;
  action_type: string;
  notes: string | null;
  performed_at: string;
  created_at: string;
};

export type PlantHistory = {
  plant: Plant;
  observations: Observation[];
  care_events: CareEvent[];
  assessments: StoredAssessment[];
};

export type StoredAssessment = {
  id: string;
  observation_id: string;
  status: string;
  identified_scientific_name: string | null;
  identification_confidence: number | null;
  finding_code: string | null;
  finding_confidence: number | null;
  risk_level: "unknown" | "low" | "medium" | "high";
  explanation: string | null;
  model_version: string | null;
  created_at: string;
};

export type SpeciesCandidate = {
  species_code: string;
  scientific_name: string;
  common_name: string;
  confidence: number;
};

export type Identification = {
  observation_id: string;
  candidates: SpeciesCandidate[];
  recognized: boolean;
  needs_review: boolean;
  model_version: string;
};

export type Assessment = {
  assessment_id: string;
  observation_id: string;
  status: string;
  risk_level: "unknown" | "low" | "medium" | "high";
  requires_species_confirmation: boolean;
  requires_more_data: boolean;
  conflicting_evidence: boolean;
  missing_inputs: string[];
  evidence: { code: string; confidence: number; source: string }[];
  recommended_actions: string[];
  explanation: string;
  explanation_source: string;
  policy_version: string;
  model_version: string;
};

export type Dynamics = {
  reference_observation_id: string;
  current_observation_id: string;
  comparable: boolean;
  comparison_reasons: string[];
  trend: "improving" | "stable" | "worsening" | "unknown";
  changes: {
    code: string;
    previous_confidence: number;
    current_confidence: number;
    direction: string;
  }[];
  care_events: CareEvent[];
};

async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? "Не удалось выполнить запрос");
  }
  return response.json() as Promise<T>;
}

export function registerUser(displayName: string, email: string): Promise<Registration> {
  return request("/api/v1/users", {
    method: "POST",
    body: JSON.stringify({ display_name: displayName, email }),
  });
}

export function listPlants(token: string): Promise<Plant[]> {
  return request("/api/v1/plants", {}, token);
}

export function createPlant(token: string, nickname: string): Promise<Plant> {
  return request(
    "/api/v1/plants",
    { method: "POST", body: JSON.stringify({ nickname, species_status: "unconfirmed" }) },
    token,
  );
}

export function loadHistory(token: string, plantId: string): Promise<PlantHistory> {
  return request(`/api/v1/plants/${plantId}/history`, {}, token);
}

export function createObservation(
  token: string,
  plantId: string,
  formData: FormData,
): Promise<Observation> {
  return request(`/api/v1/plants/${plantId}/observations`, { method: "POST", body: formData }, token);
}

export function identifyObservation(
  token: string,
  plantId: string,
  observationId: string,
): Promise<Identification> {
  return request(
    `/api/v1/plants/${plantId}/observations/${observationId}/identify`,
    { method: "POST" },
    token,
  );
}

export function assessObservation(
  token: string,
  plantId: string,
  observationId: string,
): Promise<Assessment> {
  return request(
    `/api/v1/plants/${plantId}/observations/${observationId}/assess`,
    { method: "POST" },
    token,
  );
}

export function confirmSpecies(
  token: string,
  plantId: string,
  candidate: SpeciesCandidate,
): Promise<Plant> {
  return request(
    `/api/v1/plants/${plantId}/species`,
    {
      method: "PATCH",
      body: JSON.stringify({
        scientific_name: candidate.scientific_name,
        common_name: candidate.common_name,
      }),
    },
    token,
  );
}

export function createCareEvent(
  token: string,
  plantId: string,
  actionType: string,
  notes: string,
): Promise<CareEvent> {
  return request(
    `/api/v1/plants/${plantId}/care-events`,
    { method: "POST", body: JSON.stringify({ action_type: actionType, notes: notes || null }) },
    token,
  );
}

export function loadDynamics(
  token: string,
  plantId: string,
  currentId: string,
  referenceId: string,
): Promise<Dynamics> {
  return request(
    `/api/v1/plants/${plantId}/observations/${currentId}/dynamics/${referenceId}`,
    {},
    token,
  );
}
