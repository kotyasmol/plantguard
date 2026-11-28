import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { EnvironmentPanel } from "./EnvironmentPanel";

function response(payload: unknown, ok = true) {
  return { ok, status: ok ? 200 : 500, json: async () => payload } as Response;
}

function openPanel() {
  render(<EnvironmentPanel token="session" plantId="fern" />);
  fireEvent.click(screen.getByText("Показания среды"));
}

afterEach(() => vi.unstubAllGlobals());

it("loads history, accepts a zero humidity reading and charts only measured values", async () => {
  const old = { id: "r1", plant_id: "fern", occurred_at: "2026-11-27T10:00:00Z", humidity_pct: 25, temperature_c: null };
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => init?.method === "POST"
    ? response({ ...old, id: "r2", occurred_at: "2026-11-28T10:00:00Z", humidity_pct: 0 })
    : response([old]));
  vi.stubGlobal("fetch", fetchMock);
  openPanel();
  expect(await screen.findByText("Для этого показателя пока нет измерений.")).toBeVisible();
  const submit = screen.getByRole("button", { name: "Сохранить показания" });
  fireEvent.click(submit);
  expect(screen.getByRole("status")).toHaveTextContent("Введите температуру или влажность.");
  const input = screen.getByLabelText("Влажность, %");
  fireEvent.change(input, { target: { value: "101" } });
  expect(input).toBeInvalid();
  fireEvent.change(input, { target: { value: "0" } });
  fireEvent.click(submit);
  expect(await screen.findByText("Показания сохранены.")).toBeVisible();
  expect(fetchMock).toHaveBeenLastCalledWith("/api/v1/plants/fern/environment-readings",
    expect.objectContaining({ method: "POST", body: '{"humidity_pct":0}' }));
  expect(screen.getByRole("img", { name: "График влажности" }).querySelectorAll("circle")).toHaveLength(2);
  expect(screen.getByText(/Последнее значение 0 %/)).toBeVisible();
  fireEvent.change(screen.getByLabelText("Показатель на графике"), { target: { value: "temperature_c" } });
  expect(screen.getByText("Для этого показателя пока нет измерений.")).toBeVisible();
});

it("retries loading history and keeps the entered temperature after a failed save", async () => {
  const reading = { id: "r1", plant_id: "fern", occurred_at: "2026-11-27T10:00:00Z", humidity_pct: null, temperature_c: -5 };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response({}, false))
    .mockResolvedValueOnce(response([reading])).mockResolvedValueOnce(response({}, false)));
  openPanel();
  fireEvent.click(await screen.findByRole("button", { name: "Повторить" }));
  expect(await screen.findByRole("img", { name: "График температуры" })).toBeVisible();
  const input = screen.getByLabelText("Температура, °C");
  fireEvent.change(input, { target: { value: "-3.25" } });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить показания" }));
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Не удалось сохранить"));
  expect(input).toHaveValue(-3.25);
});
