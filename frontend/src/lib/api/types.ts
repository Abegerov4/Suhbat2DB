/**
 * Типы REST API — из OpenAPI бэкенда (`npm run gen:api` → schema.d.ts).
 * События SSE в OpenAPI не попадают, поэтому описаны вручную по docs/CONTRACTS.md §2.
 */
import type { components } from "./schema";

type Schemas = components["schemas"];

export type User = Schemas["UserOut"];
export type Datasource = Schemas["DatasourceOut"];
export type SchemaSnapshot = Schemas["SchemaSnapshot"];
export type TableInfo = Schemas["TableInfo"];
export type ColumnInfo = Schemas["ColumnInfo"];
export type Session = Schemas["SessionOut"];
export type ChartSpec = Schemas["ChartSpec"];
export type ClarificationRequest = Schemas["ClarificationRequest"];
export type ClarificationAnswer = Schemas["ClarificationAnswer"];
export type Ambiguity = Schemas["Ambiguity"];
export type QueryResult = Schemas["QueryResult"];
export type AgentError = Schemas["ErrorEvent"];
export type Stats = Schemas["StatsOut"];
export type DailyActivity = Schemas["DailyActivity"];

export type Message = Omit<Schemas["MessageOut"], "validation_report"> & {
  validation_report?: ValidationReport | null;
};

export type NodeName =
  | "guard_input"
  | "schema_linking"
  | "detect_ambiguity"
  | "clarify"
  | "generate_sql"
  | "validate_sql"
  | "self_correct"
  | "execute"
  | "explain_and_visualize"
  | "refuse";

export type LevelName =
  "syntax" | "readonly_policy" | "schema" | "explain" | "execution";

export type ValidationLevelResult = {
  level: 1 | 2 | 3 | 4 | 5;
  name: LevelName;
  passed: boolean;
  message?: string | null;
  hint?: string | null;
  fatal?: boolean;
};

export type ValidationReport = {
  passed: boolean;
  levels: ValidationLevelResult[];
  normalized_sql?: string | null;
};

export type AgentEvent =
  | {
      event: "step";
      data: {
        node: NodeName;
        status: "started" | "finished";
        detail?: string | null;
      };
    }
  | { event: "clarification"; data: ClarificationRequest }
  | { event: "sql"; data: { sql: string; attempt: number } }
  | { event: "validation"; data: ValidationLevelResult }
  | { event: "result"; data: QueryResult }
  | { event: "answer"; data: { text: string } }
  | { event: "chart"; data: ChartSpec }
  | { event: "error"; data: AgentError }
  | {
      event: "done";
      data: {
        message_id?: string | null;
        trace_id?: string | null;
        awaiting_clarification: boolean;
      };
    };

export type ApiErrorBody = { error: { code: string; message: string } };
