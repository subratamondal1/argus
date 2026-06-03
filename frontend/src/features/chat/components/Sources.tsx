import { ExternalLink, Globe } from "lucide-react";

function extractUrls(text: string): string[] {
  const matches = text.match(/https?:\/\/[^\s)<>\]"']+/g) ?? [];
  const seen = new Set<string>();
  const urls: string[] = [];
  for (const raw of matches) {
    const url = raw.replace(/[.,;:]+$/, "");
    if (!seen.has(url)) {
      seen.add(url);
      urls.push(url);
    }
  }
  return urls;
}

function domainOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function Sources({ text }: { text: string }) {
  const urls = extractUrls(text);
  if (urls.length === 0) return null;
  return (
    <div className="mb-5">
      <div className="mb-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-foreground/45">
        <Globe className="h-3.5 w-3.5" /> {urls.length} sources
      </div>
      <div className="flex flex-wrap gap-2">
        {urls.map((url, index) => (
          <a
            key={url}
            href={url}
            target="_blank"
            rel="noreferrer"
            className="group flex max-w-[230px] items-center gap-2 rounded-md border border-foreground/15 bg-surface px-3 py-2 text-xs transition hover:border-accent/55"
            title={url}
          >
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-foreground/10 font-mono text-[10px] font-semibold text-foreground/55">
              {index + 1}
            </span>
            <span className="truncate text-foreground/70">{domainOf(url)}</span>
            <ExternalLink className="h-3 w-3 shrink-0 text-foreground/30 transition group-hover:text-accent" />
          </a>
        ))}
      </div>
    </div>
  );
}
