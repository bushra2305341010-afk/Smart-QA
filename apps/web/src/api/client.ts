/**
 * Typed fetch wrapper for the FastAPI backend (docs/06-api.md).
 *
 * - Cookie session: the browser sends `saq_access`; state-changing requests echo the
 *   `saq_csrf` cookie in `X-CSRF-Token` (double submit, docs/10 §3).
 * - A 401 triggers one `POST /auth/refresh` and a retry, so short access tokens stay invisible.
 * - Every failure becomes an `ApiError` built from the `{"error": {...}}` envelope.
 */

export const API_BASE = "/api/v1";
const CSRF_COOKIE = "saq_csrf";
const CSRF_HEADER = "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export type ErrorBody = {
  code: string;
  message: string;
  details: Record<string, unknown>;
  trace_id: string | null;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly traceId: string | null;

  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.details = body.details;
    this.traceId = body.trace_id;
  }
}

export function readCookie(name: string): string | null {
  for (const part of document.cookie.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function toError(response: Response): Promise<ApiError> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  const err = isRecord(payload) && isRecord(payload.error) ? payload.error : null;
  return new ApiError(response.status, {
    code: typeof err?.code === "string" ? err.code : `HTTP_${response.status}`,
    message: typeof err?.message === "string" ? err.message : response.statusText || "Request failed",
    details: isRecord(err?.details) ? err.details : {},
    trace_id: typeof err?.trace_id === "string" ? err.trace_id : null,
  });
}

export type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** JSON body (serialised) or FormData (sent as multipart). */
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
  signal?: AbortSignal;
};

function buildUrl(path: string, query: RequestOptions["query"]): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  return `${API_BASE}${path}${qs ? `?${qs}` : ""}`;
}

function send(path: string, opts: RequestOptions): Promise<Response> {
  const method = opts.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (opts.body instanceof FormData) {
    body = opts.body;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  if (!SAFE_METHODS.has(method)) {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) headers[CSRF_HEADER] = csrf;
  }
  return fetch(buildUrl(path, opts.query), {
    method,
    headers,
    body,
    credentials: "same-origin",
    signal: opts.signal,
  });
}

const NO_REFRESH = new Set(["/auth/login", "/auth/login/mfa", "/auth/register", "/auth/refresh"]);
let refreshing: Promise<boolean> | null = null;

function refreshOnce(): Promise<boolean> {
  refreshing ??= send("/auth/refresh", { method: "POST" })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

/** Call the API and parse JSON. Returns `undefined` for 204 responses. */
export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  let response = await send(path, opts);
  if (response.status === 401 && !NO_REFRESH.has(path) && (await refreshOnce())) {
    response = await send(path, opts);
  }
  if (!response.ok) throw await toError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** URL for a file download (the browser sends the session cookie itself). */
export function downloadUrl(path: string): string {
  return `${API_BASE}${path}`;
}
