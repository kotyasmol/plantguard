import { randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

test("owner assesses a plant twice and sees the change over time", async ({ page }) => {
  const photo = resolve("apps/web/public/plant-background.jpg");
  await page.goto("/");
  await page.getByLabel("Как к вам обращаться").fill("Владелец растения");
  await page.getByLabel("Электронная почта").fill(`browser-${randomUUID()}@example.com`);
  await page.getByLabel("Пароль", { exact: true }).fill(randomUUID());
  await page.getByRole("button", { name: "Начать наблюдение" }).click();

  await page.getByLabel("Название растения").fill("Папоротник");
  await page.getByRole("main").getByRole("button", { name: "Добавить растение" }).click();
  await expect(page.getByRole("heading", { name: "Папоротник" })).toBeVisible();

  for (const description of ["Первое наблюдение", "Повторное наблюдение"]) {
    await page.getByRole("button", { name: "Новое наблюдение", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog.locator('input[type="file"]').setInputFiles(photo);
    await dialog.getByLabel("Что изменилось?").fill(description);
    const assessment = page.waitForResponse(response =>
      response.request().method() === "POST" && response.url().endsWith("/assess"));
    await dialog.getByRole("button", { name: "Сохранить и оценить" }).click();
    expect((await assessment).ok()).toBe(true);
    await expect(page.locator(".assessment-copy")).toHaveText(/\S/);
    await expect(page.getByText(description, { exact: true }).first()).toBeVisible();
  }

  await expect(page.getByText("Динамика", { exact: true })).toBeVisible();
  await expect(page.getByText("2 снимка", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Папоротник" })).toBeVisible();
  await expect(page.getByText("2 снимка", { exact: true })).toBeVisible();
  await expect(page.locator(".assessment-copy")).toHaveText(/\S/);
});
