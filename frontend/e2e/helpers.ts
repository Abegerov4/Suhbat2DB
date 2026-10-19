import { expect, type Page } from "@playwright/test";

/** Новый аналитик на каждый тест: тесты не зависят друг от друга и от пароля admin. */
export async function registerAndLogin(page: Page) {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@suhbat2db.kz`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Пароль").fill("e2e-password-123");
  await page.getByRole("button", { name: "Создать аккаунт" }).click();
  await expect(page).toHaveURL("/");
  return email;
}

/** Новый диалог с демо-источником; первый вопрос — пример со страницы /chat. */
export async function startChat(page: Page, question: string) {
  await page.goto("/chat");
  const example = page.getByRole("button", { name: question });
  await expect(example).toBeEnabled(); // источник проиндексирован
  await example.click();
  await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/);
}
