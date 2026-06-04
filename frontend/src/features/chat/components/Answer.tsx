import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { rehypeCitations } from "@/shared/lib/rehype-citations";

import type { Source } from "../types";
import { Citation } from "./Citation";

// Drop a trailing "Sources" / "References" section — those are rendered as the
// sources strip above the answer, so keeping the list here would duplicate them.
function stripSources(text: string): string {
  const lines = text.split("\n");
  for (let index = 0; index < lines.length; index += 1) {
    if (/^\s*\**#{0,6}\s*(sources?|references?)\s*:?\s*\**\s*$/i.test(lines[index])) {
      return lines.slice(0, index).join("\n").trimEnd();
    }
  }
  return text;
}

function citeId(children: ReactNode): number {
  const raw = Array.isArray(children) ? children.join("") : String(children ?? "");
  return Number.parseInt(raw, 10);
}

export function Answer({
  text,
  streaming,
  refining = false,
  sources,
  highlighted,
  onCitationEnter,
  onCitationLeave,
}: {
  text: string;
  streaming: boolean;
  refining?: boolean;
  sources: Source[];
  highlighted: number | null;
  onCitationEnter: (id: number) => void;
  onCitationLeave: () => void;
}) {
  if (text.length === 0) return null;
  const body = streaming ? text : stripSources(text);
  const byId = new Map(sources.map((source) => [source.id, source]));

  return (
    <div className="answer-prose text-foreground/90">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeCitations]}
        components={{
          a({ node, ...props }) {
            void node;
            return (
              <a
                className="text-accent hover:underline"
                target="_blank"
                rel="noreferrer"
                {...props}
              />
            );
          },
          cite({ children }) {
            const source = byId.get(citeId(children));
            if (source === undefined) return <>[{children}]</>;
            return (
              <Citation
                source={source}
                highlighted={highlighted === source.id}
                onEnter={() => onCitationEnter(source.id)}
                onLeave={onCitationLeave}
              />
            );
          },
        }}
      >
        {body}
      </ReactMarkdown>
      {/* No blinking cursor during the refine gap — tokens have paused, so a lone
          cursor reads as "stuck". The Reviewer Agent indicator below carries it. */}
      {streaming && !refining && <span className="argus-cursor" aria-hidden />}
    </div>
  );
}
