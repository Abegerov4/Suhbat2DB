import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { registerAndLogin, startChat } from "./helpers";

/** Нарушения WCAG 2.1 AA уровня serious/critical (тот же движок axe, что у Lighthouse). */
async function violations(page: Page) {
  const { violations } = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map(
      (v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`,
    );
}

test("login page has no serious accessibility violations", async ({ page }) => {
  await page.goto("/login");
  expect(await violations(page)).toEqual([]);
});

test("overview and chat with an answer have no serious accessibility violations", async ({
  page,
}) => {
  await registerAndLogin(page);
  expect(await violations(page)).toEqual([]);

  await startChat(page, "Топ-5 регионов по выручке за 2025 год");
  await expect(
    page.getByRole("button", { name: "Полезный ответ", exact: true }),
  ).toBeVisible();
  expect(await violations(page)).toEqual([]);

  await startChat(page, "Покажи продажи за прошлый квартал");
  await expect(page.getByRole("button", { name: "Продолжить" })).toBeVisible();
  expect(await violations(page)).toEqual([]);
});
