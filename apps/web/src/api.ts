export type ObservationValidationResult = {
  request_id: string;
  status: "validated";
  received_at: string;
  persisted: false;
  analysis_started: false;
  message: string;
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function validateObservation(
  formData: FormData,
): Promise<ObservationValidationResult> {
  const response = await fetch(`${API_URL}/api/v1/observations/validate`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? "Не удалось проверить данные");
  }

  return response.json() as Promise<ObservationValidationResult>;
}
