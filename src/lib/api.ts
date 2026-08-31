// Central backend base URL.
//
// FIX (deployment): every page used to hardcode `http://127.0.0.1:8000`
// directly in its fetch() calls. That works only when the frontend and the
// FastAPI backend are running on the same machine (local dev) — once this
// app is built and deployed (e.g. to Netlify), a visitor's own browser has
// nothing listening on its own port 8000, so every API call failed with
// "Failed to fetch". Set NEXT_PUBLIC_API_URL at build time (Netlify env
// vars) to your deployed backend's public URL to fix this in production;
// it still falls back to localhost for local development.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://127.0.0.1:8000';
