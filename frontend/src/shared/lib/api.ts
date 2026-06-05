// The FastAPI backend base URL. Overridable for non-local deploys.
export const API_BASE: string = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Auth lives in an httpOnly session cookie the browser sends automatically; every
// API call must opt into credentials so that cookie rides along on the cross-origin
// (different-port) request. Spread into each fetch's RequestInit.
export const WITH_CREDENTIALS: RequestCredentials = "include";

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

// Mutating requests (POST/PUT/DELETE) echo the readable CSRF cookie back as a
// header — the server checks header == cookie AND its HMAC signature. GETs don't
// need it. Returns {} when there's no CSRF cookie (anonymous / not signed in).
export function csrfHeaders(): Record<string, string> {
  const token = readCookie("argus_csrf");
  return token ? { "X-CSRF-Token": token } : {};
}

// Turn a thrown fetch error into a message a user can act on. The browser's
// generic "Failed to fetch" usually means the backend isn't reachable.
export function friendlyError(caught: unknown): string {
  const message = caught instanceof Error ? caught.message : String(caught);
  if (/failed to fetch|networkerror|load failed/i.test(message)) {
    return "Can't reach the Argus backend — is it running on :8000?";
  }
  return message;
}
