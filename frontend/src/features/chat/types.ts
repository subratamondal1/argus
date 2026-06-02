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
    | "answer"
    | "error"
    | "done";
  sub_question?: string;
  sub_questions?: string[];
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
