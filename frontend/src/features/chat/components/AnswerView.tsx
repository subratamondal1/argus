import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function AnswerView({ answer }: { answer: string }) {
  if (answer.length === 0) return null;
  return (
    <div className="answer-prose rounded-2xl border border-black/10 bg-white p-5 dark:border-white/15 dark:bg-white/5">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ node, ...props }) {
            void node;
            return <a target="_blank" rel="noreferrer" {...props} />;
          },
        }}
      >
        {answer}
      </ReactMarkdown>
    </div>
  );
}
