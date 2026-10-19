/**
 * Подсветка SQL: только грамматика SQL и две темы, JS-движок регулярных
 * выражений (без WASM). Модуль грузится лениво — при первом показе SQL.
 */
import type { HighlighterCore } from "shiki/core";

let highlighter: Promise<HighlighterCore> | null = null;

function getHighlighter() {
  highlighter ??= (async () => {
    const [{ createHighlighterCore }, { createJavaScriptRegexEngine }] =
      await Promise.all([
        import("shiki/core"),
        import("shiki/engine/javascript"),
      ]);
    return createHighlighterCore({
      themes: [
        import("@shikijs/themes/github-light"),
        import("@shikijs/themes/github-dark"),
      ],
      langs: [import("@shikijs/langs/sql")],
      engine: createJavaScriptRegexEngine(),
    });
  })();
  return highlighter;
}

export async function highlightSql(sql: string): Promise<string> {
  const h = await getHighlighter();
  return h.codeToHtml(sql, {
    lang: "sql",
    themes: { light: "github-light", dark: "github-dark" },
    defaultColor: false,
  });
}
