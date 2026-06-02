"use client";

import { useState } from "react";

import { API_BASE } from "@/shared/lib/api";
import { logger } from "@/shared/lib/logger";

type IngestStatus = "idle" | "loading" | "done" | "error";

interface Ingest {
  ingest: (source: string) => Promise<void>;
  status: IngestStatus;
  message: string;
}

// POSTs a file path or URL to /api/ingest and reports how many chunks landed.
export function useIngest(): Ingest {
  const [status, setStatus] = useState<IngestStatus>("idle");
  const [message, setMessage] = useState("");

  const ingest = async (source: string): Promise<void> => {
    setStatus("loading");
    setMessage("");
    try {
      const response = await fetch(`${API_BASE}/api/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source }),
      });
      if (!response.ok) throw new Error(`ingest failed: HTTP ${response.status}`);
      const data = (await response.json()) as {
        source_uri: string;
        chunks_written: number;
      };
      setStatus("done");
      setMessage(`ingested ${data.chunks_written} chunks from ${data.source_uri}`);
    } catch (caught) {
      logger.error("ingest failed", caught);
      setStatus("error");
      setMessage(caught instanceof Error ? caught.message : "unknown error");
    }
  };

  return { ingest, status, message };
}
