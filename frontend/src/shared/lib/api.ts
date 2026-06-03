// The FastAPI backend base URL. Overridable for non-local deploys.
export const API_BASE: string = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Turn a thrown fetch error into a message a user can act on. The browser's
// generic "Failed to fetch" usually means the backend isn't reachable.
export function friendlyError(caught: unknown): string {
  const message = caught instanceof Error ? caught.message : String(caught);
  if (/failed to fetch|networkerror|load failed/i.test(message)) {
    return "Can't reach the Argus backend — is it running on :8000?";
  }
  return message;
}
