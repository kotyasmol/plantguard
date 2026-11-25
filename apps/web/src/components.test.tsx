import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AssessmentPanel } from "./AssessmentPanel";
import { CreatePlant } from "./CreatePlant";
import { ObservationComposer } from "./ObservationComposer";
import { PlantWorkspace } from "./PlantWorkspace";
import { MobileNav, Sidebar } from "./Sidebar";
import { Assessment, Identification, Plant, PlantHistory } from "./api";

const plant: Plant = {
  id: "plant-1",
  nickname: "Фикус",
  species_scientific_name: null,
  species_common_name: null,
  species_status: "unconfirmed",
  created_at: "2026-11-20T10:00:00Z",
  updated_at: "2026-11-20T10:00:00Z",
};

const assessment: Assessment = {
  assessment_id: "assessment-1",
  observation_id: "observation-1",
  status: "needs_review",
  risk_level: "medium",
  requires_species_confirmation: true,
  requires_more_data: false,
  conflicting_evidence: false,
  missing_inputs: [],
  evidence: [{ code: "leaf-yellowing", confidence: 0.8, source: "image:test" }],
  recommended_actions: ["Проверить влажность грунта"],
  explanation: "На листе заметно пожелтение.",
  explanation_source: "deterministic",
  policy_version: "2.0",
  model_version: "test",
};

const identification: Identification = {
  observation_id: "observation-1",
  candidates: [{
    species_code: "ficus_benjamina",
    scientific_name: "Ficus benjamina",
    common_name: "Фикус Бенджамина",
    confidence: 0.92,
  }],
  recognized: true,
  needs_review: false,
  model_version: "plantnet-test",
};

describe("form components", () => {
  it("creates a trimmed plant name and supports cancellation", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    const onCancel = vi.fn();
    render(<CreatePlant hasPlants pending={false} error={null} onCreate={onCreate} onCancel={onCancel} />);

    fireEvent.change(screen.getByLabelText("Название растения"), { target: { value: "  Мой фикус  " } });
    fireEvent.click(screen.getByRole("button", { name: /добавить растение/i }));
    await waitFor(() => expect(onCreate).toHaveBeenCalledWith("Мой фикус"));

    fireEvent.click(screen.getByRole("button", { name: "Отмена" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("builds observation data without empty numeric fields and closes from the backdrop", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:preview"),
      revokeObjectURL: vi.fn(),
    });
    const { container, unmount } = render(
      <ObservationComposer plantName="Фикус" pending={false} error={null} onClose={onClose} onSubmit={onSubmit} />,
    );
    expect(document.body.style.overflow).toBe("hidden");
    const file = new File(["image"], "leaf.jpg", { type: "image/jpeg" });
    fireEvent.change(screen.getByLabelText(/добавьте фотографию листа/i), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("Что изменилось?"), { target: { value: "Появился лист" } });
    fireEvent.submit(container.querySelector("form")!);

    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
    const data = onSubmit.mock.calls[0][0] as FormData;
    expect(data.has("photo")).toBe(true);
    expect(data.get("description")).toBe("Появился лист");
    expect(data.has("humidity_pct")).toBe(false);
    expect(data.has("temperature_c")).toBe(false);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
    fireEvent.mouseDown(container.querySelector(".modal-backdrop")!);
    expect(onClose).toHaveBeenCalledTimes(2);
    unmount();
    expect(document.body.style.overflow).toBe("");
  });
});

describe("workspace components", () => {
  it("shows grounded recommendations and confirms a suggested species", () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(
      <AssessmentPanel
        assessment={assessment}
        identification={identification}
        speciesConfirmed={false}
        confirming={false}
        onConfirm={onConfirm}
      />,
    );

    expect(screen.getByText("Проверить влажность грунта")).toBeVisible();
    expect(screen.getByText("широкий каталог")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Это оно" }));
    expect(onConfirm).toHaveBeenCalledWith(identification.candidates[0]);

    rerender(
      <AssessmentPanel
        assessment={assessment}
        identification={identification}
        speciesConfirmed={false}
        confirming
        onConfirm={onConfirm}
      />,
    );
    expect(screen.getByRole("button", { name: "Сохраняем…" })).toBeDisabled();
  });

  it("records a care action and clears its comment", async () => {
    const onCare = vi.fn().mockResolvedValue(undefined);
    const history: PlantHistory = { plant, observations: [], care_events: [], assessments: [] };
    render(
      <PlantWorkspace
        history={history}
        assessment={null}
        dynamics={null}
        identification={null}
        confirming={false}
        carePending={false}
        onAddObservation={vi.fn()}
        onConfirm={vi.fn()}
        onCare={onCare}
      />,
    );

    fireEvent.change(screen.getByLabelText("Что сделали"), { target: { value: "repotted" } });
    fireEvent.change(screen.getByLabelText("Комментарий"), { target: { value: "Новый грунт" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить в историю" }));

    await waitFor(() => expect(onCare).toHaveBeenCalledWith("repotted", "Новый грунт"));
    expect(screen.getByLabelText("Комментарий")).toHaveValue("");
    expect(screen.getByText("История появится после первого наблюдения.")).toBeVisible();
  });

  it("wires desktop and mobile navigation actions", () => {
    const onSelect = vi.fn();
    const onAddPlant = vi.fn();
    const onAddObservation = vi.fn();
    const onLogout = vi.fn();
    render(
      <>
        <Sidebar
          plants={[plant]}
          selectedId={plant.id}
          onSelect={onSelect}
          onAddPlant={onAddPlant}
          onAddObservation={onAddObservation}
          onLogout={onLogout}
        />
        <MobileNav onAddPlant={onAddPlant} onAddObservation={onAddObservation} />
      </>,
    );

    fireEvent.click(screen.getByRole("button", { name: plant.nickname }));
    fireEvent.click(screen.getByRole("button", { name: "Добавить растение" }));
    fireEvent.click(screen.getByRole("button", { name: "Выйти" }));
    fireEvent.click(screen.getByRole("button", { name: "Снимок" }));

    expect(onSelect).toHaveBeenCalledWith(plant.id);
    expect(onAddPlant).toHaveBeenCalledOnce();
    expect(onLogout).toHaveBeenCalledOnce();
    expect(onAddObservation).toHaveBeenCalledOnce();
  });
});
