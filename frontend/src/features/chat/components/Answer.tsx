import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function Answer({ text, streaming }: { text: string; streaming: boolean }) {
  if (text.length === 0) return null;
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
        {text}
      </ReactMarkdown>
      {streaming && <span className="argus-cursor" aria-hidden />}
    </div>
  );
}
