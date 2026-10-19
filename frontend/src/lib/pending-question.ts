/**
 * Первый вопрос нового диалога: страница /chat создаёт сессию и передаёт вопрос
 * экрану /chat/[id]. Чтение удаляет вопрос, поэтому повторный эффект
 * (StrictMode, возврат назад) не отправит его второй раз.
 */
const pending = new Map<string, string>();

export function setPendingQuestion(sessionId: string, question: string) {
  pending.set(sessionId, question);
}

export function takePendingQuestion(sessionId: string): string | undefined {
  const question = pending.get(sessionId);
  pending.delete(sessionId);
  return question;
}
