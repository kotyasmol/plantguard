import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { Observation, Plant, PlantHistory, loadDynamics } from "./api";
import { Timeline } from "./Timeline";

function json(payload: unknown, ok = true) {
  return Promise.resolve({ ok, json: () => Promise.resolve(payload) } as Response);
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
    expect(screen.getByText(/фотографии доступны только владельцу/i)).toBeVisible();
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
    fireEvent.click(screen.getByRole("button", { name: "Начать наблюдение" }));

    expect(await screen.findByText("email: некорректный адрес")).toBeVisible();
    expect(screen.queryByText(/object Object/)).not.toBeInTheDocument();
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

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(6));
    expect(await screen.findByText(/заметно пожелтение листа/i)).toBeVisible();
    expect(screen.getAllByRole("button", { name: "Это оно" })).toHaveLength(2);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
