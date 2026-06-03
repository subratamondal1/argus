"use client";

import { Check, Copy, FileText, Pencil, Share2 } from "lucide-react";
import { type ComponentType, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/shared/lib/cn";

import type { Artifact as ArtifactModel } from "../store";

export function Artifact({ artifact }: { artifact: ArtifactModel }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(artifact.content);
  const [copied, setCopied] = useState(false);

  function flash(): void {
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  async function copy(): Promise<void> {
    await navigator.clipboard.writeText(draft);
    flash();
  }

  async function share(): Promise<void> {
    if (typeof navigator.share === "function") {
      await navigator.share({ title: artifact.title, text: draft }).catch(() => undefined);
      return;
    }
    await navigator.clipboard.writeText(`${artifact.title}\n\n${draft}`);
    flash();
  }

  return (
    <div className="overflow-hidden rounded-md border border-foreground/15 bg-surface">
      <header className="flex items-center justify-between gap-3 border-b border-foreground/10 px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <FileText className="h-4 w-4 shrink-0 text-accent" />
          <span className="font-mono text-[10px] uppercase tracking-widest text-foreground/45">
            {artifact.kind}
          </span>
          <span className="truncate text-sm font-semibold">{artifact.title}</span>
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          <Action onClick={() => setEditing((value) => !value)} icon={Pencil} label="Edit" active={editing} />
          <Action onClick={() => void copy()} icon={copied ? Check : Copy} label="Copy" />
          <Action onClick={() => void share()} icon={Share2} label="Share" />
        </div>
      </header>
      <div className="px-5 py-4">
        {editing ? (
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            className="h-80 w-full resize-y bg-transparent font-mono text-[13px] leading-relaxed text-foreground outline-none"
            spellCheck={false}
          />
        ) : (
          <div className="answer-prose text-foreground/90">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{draft}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

function Action({
  onClick,
  icon: Icon,
  label,
  active,
}: {
  onClick: () => void;
  icon: ComponentType<{ className?: string }>;
  label: string;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={cn(
        "flex items-center gap-1.5 rounded px-2 py-1 text-xs transition",
        active
          ? "bg-accent/15 text-accent"
          : "text-foreground/55 hover:bg-foreground/10 hover:text-foreground",
      )}
    >
      <Icon className="h-3.5 w-3.5" /> {label}
    </button>
  );
}
