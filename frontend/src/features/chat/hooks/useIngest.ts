"use client";

import { useState } from "react";

import { API_BASE, friendlyError } from "@/shared/lib/api";
import { logger } from "@/shared/lib/logger";

type IngestStatus = "idle" | "loading" | "done" | "error";

export interface IngestedSource {
  label: string;
  chunks: number;
}

interface Ingest {
  ingestUrl: (source: string) => Promise<void>;
  uploadFile: (file: File) => Promise<void>;
  clearError: () => void;
  status: IngestStatus;
  error: string | null;
  sources: IngestedSource[];
}

interface IngestResponse {
  source_uri: string;
  chunks_written: number;
}

// Ingest by URL/path (JSON) or by uploading a file (multipart). Successful
// ingests accumulate as chips the UI can show.
export function useIngest(): Ingest {
  const [status, setStatus] = useState<IngestStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<IngestedSource[]>([]);

  async function record(response: Response): Promise<void> {
    if (!response.ok) throw new Error(`ingest failed: HTTP ${response.status}`);
    const data = (await response.json()) as IngestResponse;
    setSources((prev) => [{ label: data.source_uri, chunks: data.chunks_written }, ...prev]);
    setStatus("done");
  }

  async function guard(run: () => Promise<void>): Promise<void> {
    setStatus("loading");
    setError(null);
    try {
      await run();
    } catch (caught) {
      logger.error("ingest failed", caught);
      setError(friendlyError(caught));
      setStatus("error");
    }
  }

  const ingestUrl = (source: string): Promise<void> =>
    guard(async () => {
      const response = await fetch(`${API_BASE}/api/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source }),
      });
      await record(response);
    });

  const uploadFile = (file: File): Promise<void> =>
    guard(async () => {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${API_BASE}/api/ingest/upload`, {
        method: "POST",
        body: form,
      });
      await record(response);
    });

  const clearError = (): void => setError(null);

  return { ingestUrl, uploadFile, clearError, status, error, sources };
}
