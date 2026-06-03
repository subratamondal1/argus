import type { Source } from "../types";

// Short, human-readable label for a source's location: the bare domain for a
// web URL, or the trailing path segment for an ingested document URI.
export function sourceLabel(source: Source): string {
  if (source.origin === "doc") {
    const tail = source.url.split(/[\\/]/).filter(Boolean).pop();
    return tail ?? source.url;
  }
  try {
    return new URL(source.url).hostname.replace(/^www\./, "");
  } catch {
    return source.url;
  }
}

// The right-aligned meta chip on a source card / popover: origin plus the
// relevance score when the source carries one (RAG chunks do; web hits don't).
export function sourceMeta(source: Source): string {
  const origin = source.origin.toUpperCase();
  return source.score === null ? origin : `${origin} · ${source.score.toFixed(2)}`;
}
