import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { apiFetch } from "@/lib/api";
import { getToken, getTokenExpiry, removeToken, setToken } from "@/lib/auth";
import { toast } from "sonner";
import type { TokenResponse, UserMe } from "@/types/api";

interface AuthContextValue {
  user: UserMe | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserMe | null>(null);
  const [token, setTokenState] = useState<string | null>(getToken);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    try {
      const me = await apiFetch<UserMe>("/auth/me");
      setUser(me);
    } catch {
      removeToken();
      setTokenState(null);
      setUser(null);
    }
  }, []);

  useEffect(() => {
    if (token) {
      fetchUser().finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [token, fetchUser]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiFetch<TokenResponse>("/auth/login-json", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setToken(res.access_token);
    setTokenState(res.access_token);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const res = await apiFetch<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setToken(res.access_token);
    setTokenState(res.access_token);
  }, []);

  const logout = useCallback(() => {
    removeToken();
    localStorage.removeItem("sgm_setup_complete");
    setTokenState(null);
    setUser(null);
  }, []);

  // Session expiry warning
  useEffect(() => {
    if (!token) return;
    const expiry = getTokenExpiry();
    if (!expiry) return;

    const now = Date.now();
    const WARNING_BEFORE = 5 * 60 * 1000; // 5 minutes
    const timeUntilWarning = expiry - now - WARNING_BEFORE;
    const timeUntilExpiry = expiry - now;

    if (timeUntilExpiry <= 0) {
      logout();
      return;
    }

    const timers: ReturnType<typeof setTimeout>[] = [];

    if (timeUntilWarning > 0) {
      timers.push(
        setTimeout(() => {
          toast.warning(
            "Your session expires soon. Please save your work and sign in again."
          );
        }, timeUntilWarning)
      );
    } else if (timeUntilExpiry > 0) {
      toast.warning(
        "Your session expires soon. Please save your work and sign in again."
      );
    }

    timers.push(
      setTimeout(() => {
        logout();
        toast.error("Your session has expired. Please sign in again.");
      }, timeUntilExpiry)
    );

    return () => timers.forEach(clearTimeout);
  }, [token, logout]);

  return (
    <AuthContext.Provider
      value={{ user, token, isLoading, login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
