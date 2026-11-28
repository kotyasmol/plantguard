import { randomUUID } from "node:crypto";
import { devices, expect, test } from "@playwright/test";

test.use({ ...devices["Pixel 7"] });

test("mobile owner records watering and disables feeding independently", async ({ page, request }) => {
  const email = `care-${randomUUID()}@example.com`;
  const password = randomUUID();
  const account = await request.post("/api/v1/users", {
    data: { display_name: "Владелец", email, password },
  });
  expect(account.status()).toBe(201);
  const headers = { Authorization: `Bearer ${(await account.json()).access_token}` };
  const plant = await request.post("/api/v1/plants", { headers, data: { nickname: "Фикус" } });
  expect(plant.status()).toBe(201);
  const plantPath = `/api/v1/plants/${(await plant.json()).id}`;
  const earlier = await request.post(`${plantPath}/care-events`, {
    headers, data: { action_type: "watered", performed_at: "2020-01-01T12:00:00Z" },
  });
  expect(earlier.status()).toBe(201);

  await page.goto("/");
  await page.getByRole("button", { name: "Войти", exact: true }).tap();
  await page.getByLabel("Электронная почта").fill(email);
  await page.getByLabel("Пароль", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Войти в профиль" }).tap();

  const panel = page.getByRole("region", { name: "Расписание ухода" });
  const configure = panel.getByRole("button", { name: "Настроить интервалы" });
  await configure.tap();
  await panel.getByLabel("Полив, дней").fill("7");
  await panel.getByLabel("Подкормка, дней").fill("30");
  await panel.getByRole("button", { name: "Сохранить интервалы" }).tap();
  await expect(panel.getByText(/Пора полить/)).toBeVisible();
  await expect(panel.getByText("Отметьте первый уход для расчёта срока.")).toBeVisible();

  const savedEvent = page.waitForResponse(response =>
    response.url().endsWith("/care-events") && response.request().method() === "POST");
  await panel.getByRole("button", { name: "Полито", exact: true }).tap();
  const response = await savedEvent;
  expect(response.status()).toBe(201);
  const event = await response.json();
  expect(event.action_type).toBe("watered");
  const expectedDue = Date.parse(event.performed_at) + 7 * 24 * 60 * 60 * 1000;
  await expect.poll(async () => Date.parse(await panel.locator("time").getAttribute("datetime") ?? ""))
    .toBe(expectedDue);
  await configure.tap();
  await panel.getByLabel("Подкормка, дней").fill("");
  await panel.getByRole("button", { name: "Сохранить интервалы" }).tap();
  await expect(panel.getByRole("button", { name: "Подкормлено" })).toHaveCount(0);
  await page.reload();
  await expect(panel.getByText(/Следующий срок/)).toBeVisible();
  expect(Date.parse(await panel.locator("time").getAttribute("datetime") ?? "")).toBe(expectedDue);
  await expect(panel.getByRole("button", { name: "Подкормлено" })).toHaveCount(0);
});
