import { ArrowUpRight } from "lucide-react";

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
      <div className="mb-2 font-mono text-[10px] uppercase tracking-widest text-foreground/45">
        Related
      </div>
      <div className="overflow-hidden rounded-md border border-foreground/15">
        {questions.map((question, index) => (
          <button
            key={question}
            type="button"
            onClick={() => onPick(question)}
            className={`group flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-foreground/[0.03] ${
              index > 0 ? "border-t border-foreground/10" : ""
            }`}
          >
            <span className="font-serif text-[14px] italic leading-snug text-foreground/80">
              {question}
            </span>
            <ArrowUpRight className="h-4 w-4 shrink-0 text-foreground/30 transition group-hover:text-accent" />
          </button>
        ))}
      </div>
    </div>
  );
}
