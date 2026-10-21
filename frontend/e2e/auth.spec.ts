import { expect, test } from "@playwright/test";

import { registerAndLogin } from "./helpers";

test("unauthenticated user is redirected to login with return path", async ({
  page,
}) => {
  await page.goto("/datasources");
  await expect(page).toHaveURL("/login?next=%2Fdatasources");
  await expect(
    page.getByRole("heading", { name: "С возвращением", level: 1 }),
  ).toBeVisible();
});

test("registration opens the overview; the token is not readable from JS", async ({
  page,
}) => {
  const email = await registerAndLogin(page);
  await expect(
    page.getByRole("heading", { name: /Добро пожаловать/ }),
  ).toBeVisible();
  await expect(page.getByText("Вопросов задано")).toBeVisible();
  await expect(page.getByText(email)).toBeVisible();
  expect(await page.evaluate(() => document.cookie)).not.toContain("s2d_token");
});

test("wrong password shows an error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("nobody@suhbat2db.kz");
  await page.getByLabel("Пароль").fill("wrong-password");
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});
