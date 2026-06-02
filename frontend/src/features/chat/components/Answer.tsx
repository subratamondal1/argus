import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Drop a trailing "Sources" / "References" section — those URLs are rendered as
// source tiles above the answer, so keeping the list here would duplicate them.
function stripSources(text: string): string {
  const lines = text.split("\n");
  for (let index = 0; index < lines.length; index += 1) {
    if (/^\s*\**#{0,6}\s*(sources?|references?)\s*:?\s*\**\s*$/i.test(lines[index])) {
      return lines.slice(0, index).join("\n").trimEnd();
    }
  }
  return text;
}

export function Answer({ text, streaming }: { text: string; streaming: boolean }) {
  if (text.length === 0) return null;
  const body = streaming ? text : stripSources(text);
  return (
    <div className="answer-prose text-[15px] leading-7 text-zinc-800 dark:text-zinc-200">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ node, ...props }) {
            void node;
            return (
              <a
                className="text-indigo-600 dark:text-indigo-400"
                target="_blank"
                rel="noreferrer"
                {...props}
              />
            );
          },
        }}
      >
        {body}
      </ReactMarkdown>
      {streaming && <span className="argus-cursor" aria-hidden />}
    </div>
  );
}
