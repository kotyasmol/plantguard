import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { Observation, Plant, PlantHistory, loadDynamics } from "./api";
import { Timeline } from "./Timeline";

function json(payload: unknown, ok = true, status = ok ? 200 : 400) {
  return Promise.resolve({ ok, status, json: () => Promise.resolve(payload) } as Response);
}

const plant: Plant = {
  id: "plant-1",
  nickname: "Монстера у окна",
  species_scientific_name: null,
  species_common_name: null,
  species_status: "unconfirmed",
  created_at: "2026-11-23T10:00:00Z",
  updated_at: "2026-11-23T10:00:00Z",
};

const emptyHistory: PlantHistory = { plant, observations: [], care_events: [], assessments: [] };

function observation(id: string, observedAt: string, description: string): Observation {
  return {
    id,
    plant_id: plant.id,
    description,
    humidity_pct: id === "old" ? 48 : 58,
    temperature_c: id === "old" ? 21 : 23,
    observed_at: observedAt,
    created_at: observedAt,
    photos: [{
      id: `photo-${id}`,
      storage_key: `${id}.jpg`,
      original_filename: `${id}.jpg`,
      media_type: "image/jpeg",
      size_bytes: 100,
      checksum_sha256: id.repeat(64).slice(0, 64),
      read_url: `/${id}.jpg`,
    }],
  };
}

describe("photo archive", () => {
  it("shows saved photos chronologically and lets the user review progress", () => {
    render(<Timeline
      observations={[
        observation("new", "2026-02-01T12:00:00Z", "Появился новый лист"),
        observation("old", "2026-01-01T12:00:00Z", "Листья были поникшими"),
      ]}
      careEvents={[]}
    />);

    expect(screen.getByRole("heading", { name: "Архив снимков" })).toBeVisible();
    expect(screen.getByText("2 снимка")).toBeVisible();
    const archive = screen.getByLabelText("Снимки растения по датам");
    const archiveButtons = within(archive).getAllByRole("button");
    expect(archiveButtons[0]).toHaveAccessibleName(/1 января/);
    expect(archiveButtons[1]).toHaveAccessibleName(/1 февраля/);

    fireEvent.click(archiveButtons[0]);
    const viewer = screen.getByRole("dialog");
    expect(within(viewer).getByText("Листья были поникшими")).toBeVisible();
    expect(within(viewer).getByText("48%")).toBeVisible();

    fireEvent.click(within(viewer).getByRole("button", { name: "Следующий снимок" }));
    expect(within(viewer).getByText("Появился новый лист")).toBeVisible();
    expect(within(viewer).getByText("58%")).toBeVisible();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("PlantGuard workflow", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:preview"),
      revokeObjectURL: vi.fn(),
    });
  });

  it("starts with private profile onboarding", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Понимайте свои растения" })).toBeVisible();
    expect(screen.getByLabelText("Как к вам обращаться")).toBeVisible();
    expect(screen.getByLabelText("Электронная почта")).toBeVisible();
    expect(screen.getByLabelText("Пароль")).toBeVisible();
    expect(screen.getByText(/фотографии доступны только после входа/i)).toBeVisible();
  });

  it("shows the unread count and acknowledges an alert from mobile navigation", async () => {
    localStorage.setItem("plantguard_access_token", "secret-token");
    const alert = {
      id: "alert-1", plant_id: plant.id, alert_code: "humidity_too_low", severity: "critical",
      occurred_at: "2026-11-27T09:00:00Z", acknowledged_at: null as string | null,
    };
    let fail = true;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/alerts")) return json([{ ...alert }]);
      if (path.endsWith("/plants")) return json([plant]);
      if (path.endsWith("/history")) return json(emptyHistory);
      if (path.endsWith("/alerts/alert-1/acknowledge") && init?.method === "POST") {
        if (fail) { fail = false; return json({}, false); }
        alert.acknowledged_at = "2026-11-28T10:00:00Z";
        return json({ ...alert });
      }
      throw new Error(path);
    }));
    render(<App />);
    const mobile = within(screen.getByRole("navigation", { name: "Мобильная навигация" }));
    fireEvent.click(await mobile.findByRole("button", { name: /Уведомления.*1/ }));
    expect(await screen.findByText("Низкая влажность")).toBeVisible();
    const read = screen.getByRole("button", { name: "Отметить прочитанным" });
    await waitFor(() => expect(read).toBeEnabled());
    fireEvent.click(read);
    expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось отметить");
    fireEvent.click(read);
    expect(await screen.findByText("Прочитано")).toBeVisible();
    expect(mobile.getByRole("button", { name: "Уведомления" })).toBeVisible();
    fireEvent.click(mobile.getByRole("button", { name: "Главная" }));
    expect(await screen.findByRole("heading", { name: plant.nickname })).toBeVisible();
  });

  it("registers a profile and offers to create the first plant", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/api/v1/users")) {
        return json({
          ...plant,
          id: "user-1",
          email: "katya@example.com",
          display_name: "Екатерина",
          access_token: "secret-token",
          token_type: "bearer",
        });
      }
      if (path.endsWith("/api/v1/plants")) return json([]);
      return json({ detail: "unexpected" }, false);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.change(screen.getByLabelText("Как к вам обращаться"), { target: { value: "Екатерина" } });
    fireEvent.change(screen.getByLabelText("Электронная почта"), { target: { value: "katya@example.com" } });
    fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "safe-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Начать наблюдение" }));

    expect(await screen.findByRole("heading", { name: "Начнём с вашей зелёной коллекции" })).toBeVisible();
    expect(localStorage.getItem("plantguard_access_token")).toBe("secret-token");
  });

  it("renders structured validation errors as readable text", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({
      detail: [{ loc: ["body", "email"], msg: "некорректный адрес", type: "value_error" }],
    }, false)));
    render(<App />);

    fireEvent.change(screen.getByLabelText("Как к вам обращаться"), { target: { value: "Екатерина" } });
    fireEvent.change(screen.getByLabelText("Электронная почта"), { target: { value: "wrong@example.com" } });
    fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "safe-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Начать наблюдение" }));

    expect(await screen.findByText("email: некорректный адрес")).toBeVisible();
    expect(screen.queryByText(/object Object/)).not.toBeInTheDocument();
  });

  it("creates the first plant and supports a clean sign out", async () => {
    localStorage.setItem("plantguard_access_token", "secret-token");
    const created = { ...plant, id: "created-plant", nickname: "Калатея" };
    const createdHistory = { ...emptyHistory, plant: created };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/api/v1/plants") && !init?.method) return json([]);
      if (path.endsWith("/api/v1/plants") && init?.method === "POST") return json(created);
      if (path.endsWith(`/api/v1/plants/${created.id}/history`)) return json(createdHistory);
      return json({ detail: "unexpected" }, false);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Начнём с вашей зелёной коллекции" })).toBeVisible();
    fireEvent.change(screen.getByLabelText("Название растения"), { target: { value: "Калатея" } });
    fireEvent.click(screen.getAllByRole("button", { name: /добавить растение/i }).at(-1)!);

    expect(await screen.findByRole("heading", { name: "Калатея" })).toBeVisible();
    expect(localStorage.getItem("plantguard_selected_plant")).toBe(created.id);
    fireEvent.click(screen.getByRole("button", { name: "Выйти" }));
    expect(screen.getByRole("heading", { name: "Понимайте свои растения" })).toBeVisible();
    expect(localStorage.getItem("plantguard_access_token")).toBeNull();
  });

  it("signs an existing user in and restores the plant list", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/api/v1/sessions")) return json({
        id: "user-1",
        email: "katya@example.com",
        display_name: "Екатерина",
        created_at: "2026-11-23T10:00:00Z",
        access_token: "new-secret-token",
        token_type: "bearer",
      });
      if (path.endsWith("/api/v1/plants")) return json([]);
      return json({ detail: "unexpected" }, false);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /^Войти$/ }));
    fireEvent.change(screen.getByLabelText("Электронная почта"), { target: { value: "katya@example.com" } });
    fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "safe-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Войти в профиль" }));

    expect(await screen.findByRole("heading", { name: "Начнём с вашей зелёной коллекции" })).toBeVisible();
    expect(localStorage.getItem("plantguard_access_token")).toBe("new-secret-token");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/sessions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "katya@example.com", password: "safe-password" }),
      }),
    );
  });

  it("requests observation dynamics with the API method expected by the server", async () => {
    const fetchMock = vi.fn(() => json({}));
    vi.stubGlobal("fetch", fetchMock);

    await loadDynamics("secret-token", "plant-1", "current-1", "reference-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/plants/plant-1/observations/current-1/dynamics/reference-1",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("creates an observation and shows the grounded assessment", async () => {
    localStorage.setItem("plantguard_access_token", "secret-token");
    let history: PlantHistory = emptyHistory;
    const observation = {
      id: "observation-1",
      plant_id: plant.id,
      description: "Край листа пожелтел",
      humidity_pct: 52,
      temperature_c: 23,
      observed_at: "2026-11-23T12:00:00Z",
      created_at: "2026-11-23T12:00:00Z",
      photos: [{
        id: "photo-1",
        storage_key: "photo.jpg",
        original_filename: "leaf.jpg",
        media_type: "image/jpeg",
        size_bytes: 100,
        checksum_sha256: "a".repeat(64),
        read_url: "/photo.jpg",
      }],
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/api/v1/plants") && !init?.method) return json([plant]);
      if (path.endsWith(`/api/v1/plants/${plant.id}/history`)) return json(history);
      if (path.endsWith(`/api/v1/plants/${plant.id}/observations`) && init?.method === "POST") {
        expect((init.body as FormData).has("humidity_pct")).toBe(false);
        expect((init.body as FormData).has("temperature_c")).toBe(false);
        history = { ...emptyHistory, observations: [observation] };
        return json(observation);
      }
      if (path.endsWith("/identify")) return json({
        observation_id: observation.id,
        candidates: [{
          species_code: "monstera_deliciosa",
          scientific_name: "Monstera deliciosa",
          common_name: "Монстера деликатесная",
          confidence: .91,
        }, {
          species_code: "epipremnum_aureum",
          scientific_name: "Epipremnum aureum",
          common_name: "Эпипремнум золотистый",
          confidence: .06,
        }],
        recognized: true,
        needs_review: false,
        model_version: "test",
      });
      if (path.endsWith("/assess")) return json({
        assessment_id: "assessment-1",
        observation_id: observation.id,
        status: "succeeded",
        risk_level: "medium",
        requires_species_confirmation: true,
        requires_more_data: false,
        conflicting_evidence: false,
        missing_inputs: [],
        evidence: [{ code: "leaf-yellowing", confidence: .9, source: "image:test" }],
        recommended_actions: ["Проверить влажность субстрата и состояние дренажа"],
        explanation: "Есть признаки, которым стоит уделить внимание. Заметно пожелтение листа.",
        explanation_source: "deterministic",
        policy_version: "2.0",
        model_version: "test",
      });
      if (path.endsWith("/species") && init?.method === "PATCH") {
        const confirmed = {
          ...plant,
          species_scientific_name: "Monstera deliciosa",
          species_common_name: "Монстера деликатесная",
          species_status: "confirmed" as const,
        };
        history = { ...history, plant: confirmed };
        return json(confirmed);
      }
      if (path.endsWith("/care-events") && init?.method === "POST") return json({
        id: "care-1",
        plant_id: plant.id,
        action_type: "watered",
        notes: "Полив 200 мл",
        performed_at: "2026-11-23T13:00:00Z",
        created_at: "2026-11-23T13:00:00Z",
      });
      return json({ detail: "unexpected" }, false);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Монстера у окна" })).toBeVisible();
    fireEvent.click(screen.getAllByRole("button", { name: /новое наблюдение/i })[0]);
    const file = new File(["image"], "leaf.jpg", { type: "image/jpeg" });
    fireEvent.change(screen.getByLabelText(/добавьте фотографию листа/i), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("Что изменилось?"), { target: { value: "Край листа пожелтел" } });
    expect(screen.getByRole("button", { name: "Сохранить и оценить" })).toBeEnabled();
    fireEvent.submit(screen.getByRole("dialog").querySelector("form")!);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(7));
    expect(await screen.findByText(/заметно пожелтение листа/i)).toBeVisible();
    expect(screen.getAllByRole("button", { name: "Это оно" })).toHaveLength(2);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    fireEvent.click(screen.getAllByRole("button", { name: "Это оно" })[0]);
    expect(await screen.findByText("подтверждён")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Комментарий"), { target: { value: "Полив 200 мл" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить в историю" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/plants/${plant.id}/care-events`,
      expect.objectContaining({ method: "POST" }),
    ));
  });

  it("keeps a saved observation visible when one analysis provider fails", async () => {
    localStorage.setItem("plantguard_access_token", "secret-token");
    let history: PlantHistory = emptyHistory;
    const saved = observation("saved", "2026-11-24T12:00:00Z", "Лист поник");
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/api/v1/plants") && !init?.method) return json([plant]);
      if (path.endsWith(`/api/v1/plants/${plant.id}/history`)) return json(history);
      if (path.endsWith(`/api/v1/plants/${plant.id}/observations`) && init?.method === "POST") {
        history = { ...emptyHistory, observations: [saved] };
        return json(saved);
      }
      if (path.endsWith("/identify")) return json({ detail: "Сервис распознавания временно недоступен" }, false);
      if (path.endsWith("/assess")) return json({
        assessment_id: "assessment-saved",
        observation_id: saved.id,
        status: "needs_review",
        risk_level: "unknown",
        requires_species_confirmation: true,
        requires_more_data: true,
        conflicting_evidence: false,
        missing_inputs: ["species_confirmation"],
        evidence: [],
        recommended_actions: ["Добавьте описание изменений"],
        explanation: "Наблюдение сохранено, но данных пока недостаточно.",
        explanation_source: "deterministic",
        policy_version: "2.0",
        model_version: "test",
      });
      return json({ detail: "unexpected" }, false);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    expect(await screen.findByRole("heading", { name: plant.nickname })).toBeVisible();
    fireEvent.click(screen.getAllByRole("button", { name: /новое наблюдение/i })[0]);
    fireEvent.change(screen.getByLabelText(/добавьте фотографию листа/i), {
      target: { files: [new File(["image"], "leaf.jpg", { type: "image/jpeg" })] },
    });
    fireEvent.submit(screen.getByRole("dialog").querySelector("form")!);

    expect(await screen.findByText("Наблюдение сохранено, но данных пока недостаточно.")).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent(/наблюдение сохранено.*сервис распознавания/i);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByText("Лист поник")).toBeVisible();
  });

  it("ignores a stale history response after switching plants", async () => {
    localStorage.setItem("plantguard_access_token", "secret-token");
    const secondPlant = { ...plant, id: "plant-2", nickname: "Калатея" };
    const secondHistory = { ...emptyHistory, plant: secondPlant };
    let resolveFirstHistory!: (response: Response) => void;
    const firstHistory = new Promise<Response>((resolve) => { resolveFirstHistory = resolve; });
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/api/v1/plants")) return json([plant, secondPlant]);
      if (path.endsWith(`/api/v1/plants/${plant.id}/history`)) return firstHistory;
      if (path.endsWith(`/api/v1/plants/${secondPlant.id}/history`)) return json(secondHistory);
      return json({ detail: "unexpected" }, false);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: secondPlant.nickname }));
    expect(await screen.findByRole("heading", { name: secondPlant.nickname })).toBeVisible();

    resolveFirstHistory({
      ok: true,
      status: 200,
      json: () => Promise.resolve(emptyHistory),
    } as Response);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));

    expect(screen.getByRole("heading", { name: secondPlant.nickname })).toBeVisible();
    expect(screen.queryByRole("heading", { name: plant.nickname })).not.toBeInTheDocument();
  });

  it("clears an expired local session instead of leaving a blank workspace", async () => {
    localStorage.setItem("plantguard_access_token", "expired-token");
    vi.stubGlobal("fetch", vi.fn(() => json({ detail: "Недействительный токен" }, false, 401)));

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Понимайте свои растения" })).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("Сессия истекла");
    expect(localStorage.getItem("plantguard_access_token")).toBeNull();
  });
});
