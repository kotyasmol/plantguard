import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { Plant, PlantHistory } from "./api";

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
    expect(screen.getByRole("button", { name: "Подтвердить" })).toBeEnabled();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
