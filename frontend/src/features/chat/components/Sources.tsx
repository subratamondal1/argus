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
      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
        <Globe className="h-3.5 w-3.5" /> {urls.length} sources
      </div>
      <div className="flex flex-wrap gap-2">
        {urls.map((url, index) => (
          <a
            key={url}
            href={url}
            target="_blank"
            rel="noreferrer"
            className="group flex max-w-[230px] items-center gap-2 rounded-xl border border-zinc-200 bg-white px-3 py-2 text-xs transition hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800"
            title={url}
          >
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-zinc-100 text-[10px] font-semibold text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
              {index + 1}
            </span>
            <span className="truncate text-zinc-600 dark:text-zinc-300">{domainOf(url)}</span>
            <ExternalLink className="h-3 w-3 shrink-0 text-zinc-300 transition group-hover:text-zinc-500 dark:text-zinc-600" />
          </a>
        ))}
      </div>
    </div>
  );
}
