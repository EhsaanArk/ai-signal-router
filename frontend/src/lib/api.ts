import { getToken } from "./auth";
import { API_BASE_URL } from "./constants";

export class TierLimitError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TierLimitError";
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    });
  } catch {
    throw new Error(
      "Unable to connect to the server. Please check your internet connection and try again."
    );
  }

  if (response.status === 401) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "Session expired. Please sign in again.");
  }

  if (response.status === 403) {
    const data = await response.json();
    throw new TierLimitError(data.detail || "Tier limit reached");
  }

  if (response.status === 429) {
    throw new Error("Too many attempts. Please wait a moment and try again.");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed: ${response.status}`);
  }

  return response.json();
}

export async function deleteAccount(password: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>("/auth/account/delete", {
    method: "POST",
    body: JSON.stringify({ current_password: password }),
  });
}

export async function exportAccountData(): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>("/auth/account/export");
}
