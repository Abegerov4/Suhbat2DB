import { expect, test } from "@playwright/test";

import { registerAndLogin, startChat } from "./helpers";

test("on a phone the analysis panel opens as a sheet", async ({ page }) => {
  await registerAndLogin(page);
  await startChat(page, "Топ-5 регионов по выручке за 2025 год");
  const open = page.getByRole("button", { name: /Открыть в панели анализа/ });
  await expect(open).toBeVisible();
  await open.click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.getByRole("tab", { name: "Таблица" })).toBeVisible();
  // страница не прокручивается по горизонтали
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
