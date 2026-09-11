export type ObservationCreated = {
  observation_id: string;
  status: "queued";
  received_at: string;
  message: string;
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function createObservation(formData: FormData): Promise<ObservationCreated> {
  const response = await fetch(`${API_URL}/api/v1/observations`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? "Не удалось сохранить наблюдение");
  }

  return response.json() as Promise<ObservationCreated>;
}
