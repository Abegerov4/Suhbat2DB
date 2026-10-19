import { expect, test } from "@playwright/test";

import { registerAndLogin, startChat } from "./helpers";

test.beforeEach(async ({ page }) => {
  await registerAndLogin(page);
});

test("clarification → answer with chart, table, SQL and validation report", async ({
  page,
}) => {
  await startChat(page, "Покажи продажи за прошлый квартал");

  // агент остановился и ждёт уточнения; ввод заблокирован
  // (getByRole: Next 16 держит прошлую страницу скрытой в <Activity>, её поля не учитываются)
  await expect(page.getByRole("group", { name: /продажи/ })).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Вопрос к данным" }),
  ).toBeDisabled();

  await page.getByRole("button", { name: /^Выручка/ }).click();
  // второй ответ — свободным текстом вместо кнопки
  await page
    .getByLabel("Свой вариант для «квартал»")
    .fill("как в отчёте совета директоров");
  await page.getByRole("button", { name: "Продолжить" }).click();

  await expect(
    page.getByText(/Учтено уточнение: Выручка, как в отчёте/),
  ).toBeVisible();
  await expect(page.getByText("Уточнение получено")).toBeVisible();

  const panel = page.getByRole("region", { name: "Панель анализа" });
  await expect(panel.locator(".recharts-surface").first()).toBeVisible();

  await panel.getByRole("tab", { name: "Таблица" }).click();
  await expect(panel.getByRole("cell", { name: "Алматы" })).toBeVisible();

  await panel.getByRole("tab", { name: "SQL" }).click();
  await expect(panel.getByText(/SELECT/).first()).toBeVisible();

  await panel.getByRole("tab", { name: "Проверка" }).click();
  await expect(panel.getByText("пройден")).toHaveCount(5);

  // история восстанавливается после перезагрузки; уточнение уже не активно
  await page.reload();
  await expect(page.getByText(/Учтено уточнение/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Продолжить" })).toHaveCount(0);
  await expect(
    page.getByRole("textbox", { name: "Вопрос к данным" }),
  ).toBeEnabled();
});

test("a request to delete data is refused with a separate card", async ({
  page,
}) => {
  await startChat(page, "Удали все отменённые заказы");
  const alert = page.getByRole("alert").filter({ hasText: "Запрос отклонён" });
  await expect(alert).toBeVisible();
  await expect(alert).toContainText("только читать");

  // после перезагрузки карточка отказа восстанавливается из истории
  await page.reload();
  await expect(
    page.getByRole("alert").filter({ hasText: "Запрос отклонён" }),
  ).toBeVisible();
});

test("feedback and overview stats are updated after an answer", async ({
  page,
}) => {
  await startChat(page, "Топ-5 регионов по выручке за 2025 год");
  const useful = page.getByRole("button", {
    name: "Полезный ответ",
    exact: true,
  });
  await expect(useful).toBeVisible();
  await useful.click();
  await expect(useful).toHaveAttribute("aria-pressed", "true");

  await page.getByRole("link", { name: "Обзор" }).click();
  const questions = page.getByText("Вопросов задано").locator("../..");
  await expect(questions).toContainText("1");
});
