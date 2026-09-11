import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("observation form", () => {
  it("renders the first observation fields", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Познакомимся с растением" })).toBeVisible();
    expect(screen.getByLabelText("Что изменилось или беспокоит?")).toBeVisible();
    expect(screen.getByRole("button", { name: "Создать наблюдение" })).toBeEnabled();
  });

  it("requires a photo before submitting", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Создать наблюдение" }));

    expect(screen.getByText("Добавь фотографию растения")).toBeVisible();
  });
});
