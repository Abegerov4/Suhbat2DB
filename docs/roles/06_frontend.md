# Role 6. Frontend

**Status: completed** (October 2026). Screenshots are in the [README](../../README.md#interface).

**Aim:** a web interface where a person without SQL knowledge asks questions and answers clarifications. The answer comes together with the SQL, the validation report, a table and a chart.
**Depends on:** role 3 (API + SSE), role 5 (the real agent).
**Needed for:** user testing, the demo at the defence.

Contracts: [`CONTRACTS.md` §1–2](../CONTRACTS.md).

## Stack
Next.js 16 (App Router, `cacheComponents`) · React 19 · TypeScript · Tailwind CSS 4 · shadcn/ui (Radix, Nova preset) · TanStack Query · Recharts 3 · shiki (SQL highlighting) · motion (animations) · components from [AI Elements](https://ai-sdk.dev/elements) and [Magic UI](https://magicui.design) · `openapi-typescript` (types from the backend OpenAPI) · Vitest (unit) · Playwright + axe-core (e2e and accessibility).

The visual style follows the [app-1 dashboard (shadcnstore, 21st.dev)](https://21st.dev/@shadcnstore/components/app-1): a sidebar, a sticky header, KPI cards, a chart with a gradient. The component was not copied: the 21st output did not contain the `app-1-utils/*` files, and the attached components were written for Tailwind 3. The layout is assembled from current shadcn components for Tailwind 4 and React 19. The interface language is Russian.

## Structure

```text
frontend/src/
├── proxy.ts                       # no cookie → /login (optimistic check)
├── app/
│   ├── api/[...path]/route.ts     # BFF proxy /api/* → FastAPI, JWT from the httpOnly cookie, SSE stream
│   ├── api/auth/{login,logout}/   # login puts the token into an httpOnly cookie
│   ├── (auth)/{login,register}/
│   └── (app)/                     # sidebar + pages
│       ├── page.tsx               # Overview: KPIs, activity, SQL validation, dialogues, sources
│       ├── chat/                  # new dialogue, sample questions
│       ├── chat/[sessionId]/      # chat + analysis panel
│       └── datasources/[id]/      # data sources and the schema browser
├── components/{layout,dashboard,chat,analysis,datasources,ui}/
├── hooks/use-agent-stream.ts      # POST → SSE → turn state
└── lib/{api,sse,turn,chart,format,highlight,queries}.ts
```

## Tasks

### 6.1 Skeleton
- [x] Next.js, Tailwind 4, shadcn/ui, light, dark and system themes (`next-themes`)
- [x] API types: `npm run gen:api` → `src/lib/api/schema.d.ts`. SSE event types are not in OpenAPI and are written by hand following CONTRACTS §2
- [x] Authorisation through a **Backend for Frontend**: the JWT is kept in an httpOnly cookie (`SameSite=Lax`), is not accessible to JavaScript, and the route handler adds it to the requests to FastAPI. Modifying requests from a foreign `Origin` are rejected. On 401 the user goes to `/login?next=…` (relative paths only, no open redirect)

### 6.2 Pages

| Route | Contents |
|---|---|
| `/login`, `/register` | Forms; registration logs the user in immediately. Next to the form there is an animated panel: the product logo with database and folder icons orbiting around it and ripples in the background (`OrbitingCircles`, `Ripple`, Magic UI) |
| `/` | **Overview**: 4 KPIs with an animated counter (`NumberTicker`, Magic UI) (questions, answers with data, clarifications, blocked SQL); an activity chart with a period selector (7, 14 or 30 days) and a summary of the four outcomes with the change against the previous period; where the validator stopped queries; recent dialogues; sources and like/dislike ratings |
| `/chat` | Choice of a source, sample questions; the first question creates a session |
| `/chat/[sessionId]` | Chat + analysis panel |
| `/datasources` | Source cards with status (polling during indexing); for admin: connection, reindexing, deletion |
| `/datasources/[id]` | Schema browser: search, PKs, FKs, comments, values of categorical columns |

### 6.3 Chat screen: chat + analysis panel
- [x] Two columns with a draggable divider; the panel can be hidden with a button in the header. On a phone the panel opens as a bottom sheet
- [x] The chat shows only the answer text, clarifications, refusals and a compact answer card ("10 rows" + five validation icons). A click opens the answer in the panel; with nothing selected the panel shows the latest answer, and while the agent works it shows its progress
- [x] **`AgentThinking`** in the chat: the current agent step as a shimmering label (`Shimmer`, AI Elements) in a "pill" with a beam running along its border (`BorderBeam`, Magic UI)
- [x] **`AgentTrace`** in the panel: an expandable chain of graph steps (`ChainOfThought`, AI Elements) with an icon for each node, the found tables as badges, and the reasons for the guard and ambiguity detector decisions as captions
- [x] **`ClarificationCard`**: options as buttons with a description and a "custom option" field for each ambiguity; question input is locked until the user answers
- [x] **Analysis panel** with the tabs:
  - Chart (`ChartView`: bars, horizontal for long labels; area or lines; donut; scatter) or Summary, with large numbers if the answer has one row
  - Table (`ResultTable`: sorting, pages of 50 rows, a notice on truncation, CSV with a BOM for Excel)
  - SQL (`SqlPanel`: shiki highlighting, copying, **self-correction history**: each rejected attempt with the validator level, reason and hint)
  - Validation (`ValidationReport`: 5 levels with an icon and a label; the level where the query stopped is highlighted, and the following ones are marked "not checked")
- [x] Refusals and errors are a separate card with a clear title by code (`refused`, `unsafe_sql`, `max_attempts`, `cancelled`…), not a toast
- [x] like/dislike + an optional comment → `POST /feedback` (the score goes to Langfuse)
- [x] History: `GET /sessions/{id}/messages` renders the same components. An unfinished clarification stays active; a refusal card is restored (the `error` field of the message, migration 0002)

### 6.4 SSE and the turn life cycle
- [x] `useAgentStream`: `fetch` + `ReadableStream`, an own SSE parser (`EventSource` cannot do POST). UTF-8 across chunk boundaries, CRLF, comments; unknown events are skipped
- [x] The `applyEvent` reducer is one turn model for the stream and the history (`turnFromMessage`); a stable turn key keeps the selected panel tab when the answer moves from the stream to the history
- [x] **The turn does not depend on the connection** (a backend change): the agent runs as a separate task, and SSE only reads its queue. If the tab is closed in the middle of an answer, the answer is still saved. Stop calls `POST /sessions/{id}/stop`: the turn is cancelled and saved with the `cancelled` error
- [x] A dropped connection → a "Connection lost" card with a Retry button

### 6.5 Quality
- [x] Widths from 375 px: the table scrolls inside its card, and the page has no horizontal scroll (checked in e2e)
- [x] Accessibility: `aria-label` on icon buttons, `aria-pressed`, `aria-sort`, `role=status` on progress; status is never conveyed by colour alone. The chart palette was checked for colour blindness with the dataviz validator in both themes
- [x] Unit tests (Vitest, 17): SSE parser, turn reducer, chart data preparation, CSV, Russian plural forms
- [x] E2E tests (Playwright, 9): redirect without login, registration (the token is not visible from JS), wrong password, clarification → answer → chart/table/SQL/validation → reload, refusal and its restoration, rating and the Overview update, the sheet on a phone, axe without serious/critical WCAG 2.1 AA violations. The agent is a stub (`AGENT_MODE=fake`), so the answers are deterministic
- [x] CI: `frontend.yml` (lint, prettier, types, unit, build), `e2e.yml` (the whole stack in Docker + Playwright)

## Results

| Check | Result |
|---|---|
| Lighthouse `/chat/[id]` | Accessibility **96**, Best Practices 100, Performance 82 |
| axe (WCAG 2.1 AA, serious/critical) | 0 violations on login, Overview, an answer and a clarification |
| E2E | 9 tests, two runs in a row without failures |
| Real agent through the UI | clarification of "sales for last quarter" → 5.61 billion ₸; monthly trend (area); top 5 regions (donut); refusal for "delete the orders" |

## Brand style
- **Accent colour**: the logo blue `#256abf` (`--primary` in both themes) for buttons, the active menu item, focus and links. White text on it has a contrast of 5.4:1 (WCAG AA); accent text uses a separate token `--brand-text` (`#1c5cab` in the light theme, `#86b6ef` in the dark one).
- **Logo** ([docs/brand](../brand)): a speech bubble + a database cylinder with the "қошқар мүйіз" ornament; the dividers and the ornament are a mask, not a white fill, so the background shows through in the dark theme. The favicon is a simplified silhouette.
- **Login and the application share one style** (DIP-38): the same icon tiles, the glowing input border and the card style. On Overview there is a "01 · 02 · 03" getting-started block for a new user, a service availability indicator in the header and a "Read only" card in the sidebar.

## Decisions and deviations from the plan
- **Chat + analysis panel** instead of the whole answer in the feed: charts and tables are large, and one screen shows the dialogue, the SQL and the validation ([ADR-018](../../ARCHITECTURE.md#adr-018-chat-screen-chat--analysis-panel)).
- **BFF and an httpOnly cookie** instead of `localStorage` and `@microsoft/fetch-event-source` ([ADR-017](../../ARCHITECTURE.md#adr-017-backend-for-frontend-and-jwt-in-an-httponly-cookie)). The library has not been updated since 2021, and the own parser is 60 lines long and covered by tests.
- **The Overview page** (`GET /api/stats`) is new: the dashboard is built from the query log and the dialogue history.
- Chart animation is turned off: Recharts stopped it halfway when the chart was redrawn during an answer.
- Components from the registries were adapted: `chain-of-thought` uses one `Collapsible` for the header and the content (axe found a wrong `aria-controls`), `shimmer` does not create components during render, `number-ticker` uses Russian digit separators. All animations respect the system "reduce motion" setting (`MotionConfig reducedMotion="user"`), and the animated components render the same markup on the server and the client, so hydration does not break with reduced motion. `dot-pattern` was not used: it calls `Math.random()` during render and draws hundreds of SVG nodes, so the dotted background is one line of CSS.
- Next 16 with `cacheComponents` keeps the previous page hidden in `<Activity>`. For this reason login and logout do a full reload (the cache and the previous user's data do not stay in memory), and `useParams`/`usePathname` are wrapped in `Suspense`.

## Definition of Done
- [x] The full demo scenario works through the UI with the real agent
- [x] E2E tests in CI (`e2e.yml`)
- [x] Lighthouse Accessibility ≥ 90 on `/chat/[id]`: **96**
- [x] Screenshots of the main screens in the README

## Knowledge base
- `ai_engineering.md` §7 (HITL in the UI: confirmation and editing are a strong demo moment)
- `ai_security.md` §8 (the agent's answer is rendered as plain text: no Markdown, links or images)
