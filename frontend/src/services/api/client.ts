const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  /** Machine-readable code when the server sends one (e.g. "email_not_verified"). */
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.name = "ApiError";
  }
}

let authToken: string | null = null;
let refreshRequest: Promise<string> | null = null;
let onAuthenticationFailure: (() => void) | null = null;
let authStateVersion = 0;

/** Keep access tokens in memory only. */
export function setAuthToken(token: string | null): void {
  authStateVersion += 1;
  authToken = token;
}

export function invalidateAuthState(): void {
  authStateVersion += 1;
}

export function setAuthenticationFailureHandler(handler: (() => void) | null): void {
  onAuthenticationFailure = handler;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  /** Send body as application/x-www-form-urlencoded instead of JSON (needed for OAuth2 login). */
  form?: boolean;
}

function isAuthEndpoint(path: string): boolean {
  return /^\/api\/auth\/(login|register|refresh|logout)(?:$|[?#])/.test(path);
}

async function readResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = data?.detail;
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      // Structured error: {"code": "...", "message": "..."}.
      throw new ApiError(
        response.status,
        (detail.message as string) || response.statusText,
        detail.code as string | undefined,
      );
    }
    const message = (typeof detail === "string" && detail) || response.statusText;
    throw new ApiError(response.status, message);
  }

  return data as T;
}

async function refreshAuthToken(): Promise<string> {
  if (!refreshRequest) {
    const refreshStateVersion = authStateVersion;
    refreshRequest = (async () => {
      const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      const result = await readResponse<{ access_token: string }>(response);
      if (!result?.access_token) {
        throw new ApiError(response.status, "Refresh response did not contain an access token");
      }
      if (refreshStateVersion !== authStateVersion) {
        throw new Error("Authentication state changed while refreshing the token");
      }
      authToken = result.access_token;
      return result.access_token;
    })()
      .catch((error: unknown) => {
        if (refreshStateVersion === authStateVersion) {
          authStateVersion += 1;
          authToken = null;
          onAuthenticationFailure?.();
        }
        throw error;
      })
      .finally(() => {
        refreshRequest = null;
      });
  }
  return refreshRequest;
}

export function restoreAuthToken(): Promise<string> {
  return refreshAuthToken();
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
  retried = false,
): Promise<T> {
  const headers: Record<string, string> = {};
  const tokenUsed = authToken;
  const requestStateVersion = authStateVersion;
  if (tokenUsed) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }

  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    if (options.form) {
      headers["Content-Type"] = "application/x-www-form-urlencoded";
      body = new URLSearchParams(options.body as Record<string, string>).toString();
    } else {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    credentials: "include",
    body,
  });

  if (response.status === 401 && !retried && tokenUsed && !isAuthEndpoint(path)) {
    if (requestStateVersion !== authStateVersion) {
      return readResponse<T>(response);
    }
    if (authToken === tokenUsed) {
      try {
        await refreshAuthToken();
      } catch {
        throw await readResponse<T>(response);
      }
      if (requestStateVersion !== authStateVersion) {
        return readResponse<T>(response);
      }
    }
    return request<T>(path, options, true);
  }

  return readResponse<T>(response);
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown, form = false) =>
    request<T>(path, { method: "POST", body, form }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
