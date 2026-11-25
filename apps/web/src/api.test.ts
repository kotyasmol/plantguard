import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  confirmSpecies,
  createCareEvent,
  createPlant,
  listPlants,
} from "./api";

function response(payload: unknown, ok = true, status = ok ? 200 : 500): Promise<Response> {
  return Promise.resolve({
    ok,
    status,
    json: () => payload instanceof Error ? Promise.reject(payload) : Promise.resolve(payload),
  } as Response);
}

describe("API client", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("adds bearer and JSON headers to authenticated mutations", async () => {
    const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(
      () => response({}),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createPlant("token", "Фикус");
    await confirmSpecies("token", "plant-1", {
      species_code: "ficus_benjamina",
      scientific_name: "Ficus benjamina",
      common_name: "Фикус Бенджамина",
      confidence: 0.9,
    });
    await createCareEvent("token", "plant-1", "watered", "");

    for (const [, init] of fetchMock.mock.calls) {
      const headers = init?.headers as Headers;
      expect(headers.get("Authorization")).toBe("Bearer token");
      expect(headers.get("Content-Type")).toBe("application/json");
    }
    expect(fetchMock.mock.calls[1][1]?.body).toBe(JSON.stringify({
      scientific_name: "Ficus benjamina",
      common_name: "Фикус Бенджамина",
    }));
    expect(fetchMock.mock.calls[2][1]?.body).toBe(JSON.stringify({
      action_type: "watered",
      notes: null,
    }));
  });

  it("returns a generic message for a non-JSON server failure", async () => {
    vi.stubGlobal("fetch", vi.fn(() => response(new Error("invalid json"), false, 503)));

    await expect(listPlants("token")).rejects.toEqual(
      expect.objectContaining<ApiError>({
        name: "ApiError",
        status: 503,
        message: "Не удалось выполнить запрос",
      }),
    );
  });
});
