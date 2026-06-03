// A retrieved source the answer can cite. The backend numbers the deduplicated
// set [1..N]; `id` is that citation number. `origin` is "web" or "doc"; `score`
// is a relevance score when the source carries one (RAG), else null.
export interface Source {
  id: number;
  title: string;
  url: string;
  snippet: string;
  origin: string;
  score: number | null;
}

// The shape of a Server-Sent event from the backend agent. The backend emits a
// flat object with a `type` discriminator and event-specific fields; only the
// fields relevant to each kind are present.
export interface AgentEvent {
  type:
    | "plan"
    | "search_start"
    | "search_done"
    | "turn"
    | "tool"
    | "synthesize"
    | "reflect"
    | "token"
    | "triage"
    | "answer"
    | "artifact"
    | "sources"
    | "related"
    | "error"
    | "done";
  items?: Source[];
  sub_question?: string;
  sub_questions?: string[];
  questions?: string[];
  strategy?: string;
  reasoning?: string;
  title?: string;
  kind?: string;
  content?: string;
  name?: string;
  query?: string;
  n?: number;
  tool_calls?: number;
  cost_usd?: number;
  complete?: boolean;
  missing?: string[];
  findings?: number;
  text?: string;
  message?: string;
}

export type ChatStatus = "idle" | "streaming" | "done" | "error";
