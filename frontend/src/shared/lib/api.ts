// The FastAPI backend base URL. Overridable for non-local deploys.
export const API_BASE: string =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
