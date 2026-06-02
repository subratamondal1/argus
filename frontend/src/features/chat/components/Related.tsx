import { Plus } from "lucide-react";

export function Related({
  questions,
  onPick,
}: {
  questions: string[];
  onPick: (question: string) => void;
}) {
  if (questions.length === 0) return null;
  return (
    <div className="mt-7">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
        Related
      </div>
      <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
        {questions.map((question, index) => (
          <button
            key={question}
            type="button"
            onClick={() => onPick(question)}
            className={`flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm text-zinc-700 transition hover:bg-zinc-50 dark:text-zinc-200 dark:hover:bg-zinc-900 ${
              index > 0 ? "border-t border-zinc-200/70 dark:border-zinc-800/70" : ""
            }`}
          >
            <span>{question}</span>
            <Plus className="h-4 w-4 shrink-0 text-zinc-400" />
          </button>
        ))}
      </div>
    </div>
  );
}
