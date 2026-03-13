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

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    throw new Error("Unauthorized");
  }

  if (response.status === 403) {
    const data = await response.json();
    throw new TierLimitError(data.detail || "Tier limit reached");
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
