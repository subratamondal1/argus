"use client";

import { useEffect, useRef, useState } from "react";

import { API_BASE, friendlyError } from "@/shared/lib/api";
import { logger } from "@/shared/lib/logger";

import { useChatStore } from "../store";

type IngestStatus = "idle" | "loading" | "done" | "error";

// Cap the per-conversation document set: each doc is RAG-indexed and its name is
// listed in the agent's system prompt, so an unbounded pile bloats the prompt and
// the chip strip. 10 is generous for a focused research session; bump if needed.
export const MAX_SOURCES = 10;

export interface IngestedSource {
  label: string;
  chunks: number;
  /** A blob: URL (uploaded files) or the http(s) URL — used to preview the source. */
  previewUrl: string | null;
}

interface Ingest {
  ingestUrl: (source: string) => Promise<void>;
  uploadFile: (file: File) => Promise<void>;
  removeSource: (label: string) => void;
  cancel: () => void;
  clearError: () => void;
  status: IngestStatus;
  /** Display name of the in-flight ingest, or null when nothing is loading. */
  pending: string | null;
  atLimit: boolean;
  error: string | null;
  sources: IngestedSource[];
}

interface IngestResponse {
  source_uri: string;
  chunks_written: number;
}

function revoke(source: IngestedSource): void {
  if (source.previewUrl?.startsWith("blob:")) URL.revokeObjectURL(source.previewUrl);
}

function basename(source: string): string {
  const last = source.split(/[/\\]/).filter(Boolean).at(-1);
  return last ?? source;
}

// Ingest by URL/path (JSON) or by uploading a file (multipart). Successful
// ingests accumulate as removable chips the UI can show and preview.
export function useIngest(): Ingest {
  const activeId = useChatStore((state) => state.activeId);
  const [status, setStatus] = useState<IngestStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [sources, setSources] = useState<IngestedSource[]>([]);
  const controllerRef = useRef<AbortController | null>(null);

  // Ingest chips are scoped to the active conversation — starting or switching
  // chats aborts any in-flight upload, clears the chips (and frees their preview
  // URLs) so a doc added in one chat never lingers in another.
  // biome-ignore lint/correctness/useExhaustiveDependencies: activeId is the reset trigger, not a value read inside the effect.
  useEffect(() => {
    controllerRef.current?.abort();
    setSources((prev) => {
      for (const source of prev) revoke(source);
      return [];
    });
    setStatus("idle");
    setPending(null);
    setError(null);
  }, [activeId]);

  async function record(response: Response, makePreview: () => string | null): Promise<void> {
    if (!response.ok) {
      let detail = `Ingest failed (HTTP ${response.status})`;
      try {
        const body = (await response.json()) as { detail?: string };
        if (body.detail) detail = body.detail;
      } catch {
        // no JSON body — keep the status-based message
      }
      throw new Error(detail);
    }
    const data = (await response.json()) as IngestResponse;
    setSources((prev) => [
      { label: data.source_uri, chunks: data.chunks_written, previewUrl: makePreview() },
      ...prev,
    ]);
    setStatus("done");
  }

  // Single-flight: one ingest at a time, abortable via the stored controller.
  // Cancelling resolves back to idle (not error) — a cancel isn't a failure.
  async function guard(label: string, run: (signal: AbortSignal) => Promise<void>): Promise<void> {
    if (sources.length >= MAX_SOURCES) {
      setError(`Document limit reached (${MAX_SOURCES}) — remove one to add another.`);
      setStatus("error");
      return;
    }
    const controller = new AbortController();
    controllerRef.current = controller;
    setStatus("loading");
    setPending(basename(label));
    setError(null);
    try {
      await run(controller.signal);
    } catch (caught) {
      if (controller.signal.aborted) {
        setStatus("idle");
        return;
      }
      logger.error("ingest failed", caught);
      setError(friendlyError(caught));
      setStatus("error");
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
      setPending(null);
    }
  }

  const ingestUrl = (source: string): Promise<void> =>
    guard(source, async (signal) => {
      const response = await fetch(`${API_BASE}/api/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source }),
        signal,
      });
      await record(response, () => (/^https?:\/\//.test(source) ? source : null));
    });

  const uploadFile = (file: File): Promise<void> => {
    // The ingest pipeline extracts TEXT (pdf/docx/pptx/md/txt/html). It has no
    // OCR or vision path, so an image would hit the UTF-8 text fallback and fail
    // with a decode error — short-circuit with a clear message instead.
    if (file.type.startsWith("image/")) {
      setError(
        "Images aren't supported yet — Argus reads text, not pixels (no OCR). " +
          "Paste or attach a PDF, DOCX, or text document.",
      );
      setStatus("error");
      return Promise.resolve();
    }
    return guard(file.name, async (signal) => {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${API_BASE}/api/ingest/upload`, {
        method: "POST",
        body: form,
        signal,
      });
      await record(response, () => URL.createObjectURL(file));
    });
  };

  const removeSource = (label: string): void =>
    setSources((prev) => {
      const target = prev.find((source) => source.label === label);
      if (target) revoke(target);
      return prev.filter((source) => source.label !== label);
    });

  const cancel = (): void => controllerRef.current?.abort();

  const clearError = (): void => setError(null);

  return {
    ingestUrl,
    uploadFile,
    removeSource,
    cancel,
    clearError,
    status,
    pending,
    atLimit: sources.length >= MAX_SOURCES,
    error,
    sources,
  };
}
