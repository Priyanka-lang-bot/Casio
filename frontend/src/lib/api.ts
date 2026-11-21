// Small helper for calling the CASIO backend from the browser.

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; message: string; fields: Record<string, string> };

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export async function api<T>(path: string, body?: unknown, method?: Method): Promise<ApiResult<T>> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method: method ?? (body === undefined ? "GET" : "POST"),
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
    });
  } catch {
    return { ok: false, status: 0, message: "Can't reach CASIO right now. Check your connection and try again.", fields: {} };
  }
  const json = res.status === 204 ? null : await res.json().catch(() => null);
  if (res.ok) return { ok: true, data: json as T };
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/")) {
    // Session expired while the page was open: go back to login.
    // (A full page load is intended here: it clears all in-memory data.)
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
  }
  const message =
    typeof json?.detail === "string"
      ? json.detail
      : res.status >= 500
        ? "Something went wrong on our side. Please try again."
        : "Something went wrong. Please try again.";
  return { ok: false, status: res.status, message, fields: json?.fields ?? {} };
}

// File uploads (multipart). Same result shape and error handling as api().
export async function apiUpload<T>(path: string, form: FormData): Promise<ApiResult<T>> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { method: "POST", body: form, credentials: "same-origin" });
  } catch {
    return { ok: false, status: 0, message: "Can't reach CASIO right now. Check your connection and try again.", fields: {} };
  }
  const json = await res.json().catch(() => null);
  if (res.ok) return { ok: true, data: json as T };
  if (res.status === 401 && typeof window !== "undefined") {
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
  }
  const message =
    typeof json?.detail === "string"
      ? json.detail
      : res.status === 413
        ? "The file is too big. The limit is 10 MB."
        : "The upload didn't work. Please try again.";
  return { ok: false, status: res.status, message, fields: {} };
}

export type User = { id: string; email: string; full_name: string };

// Only allow redirects to pages inside CASIO (blocks "?next=https://evil.com").
export function safeNext(next: string | undefined | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/overview";
}
