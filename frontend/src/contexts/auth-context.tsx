import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { supabase } from "@/lib/supabase";
import type { UserMe } from "@/types/api";
import { API_BASE_URL, BETA_DISABLED_MSG } from "@/lib/constants";

interface AuthContextValue {
  user: UserMe | null;
  token: string | null;
  isLoading: boolean;
  authError: string | null;
  clearAuthError: () => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const DEBUG = true;
const PROFILE_LOAD_ERROR = "Signed in, but we could not load your account profile.";

function log(...args: unknown[]) {
  if (DEBUG) console.log("[SageAuth]", ...args);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserMe | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const initRef = useRef(false);
  const userRef = useRef<UserMe | null>(null);

  // Fetch app-specific user data from backend
  const fetchUser = useCallback(async (
    accessToken: string,
  ): Promise<{ user: UserMe | null; errorMessage: string | null }> => {
    log("fetchUser: calling /auth/me");
    try {
      const res = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
      });
      if (res.ok) {
        const me: UserMe = await res.json();
        log("fetchUser: success", me.email);
        return { user: me, errorMessage: null };
      }

      const rawBody = await res.text().catch(() => "");
      let detail = "";
      if (rawBody) {
        try {
          const parsed = JSON.parse(rawBody) as { detail?: unknown; error?: { message?: unknown } };
          const errMsg = parsed.error && typeof parsed.error.message === "string" ? parsed.error.message : null;
          detail = errMsg || (typeof parsed.detail === "string" ? parsed.detail : rawBody.slice(0, 160));
        } catch {
          detail = rawBody.slice(0, 160);
        }
      }

      // Show friendly beta message for disabled accounts instead of generic error
      if (res.status === 403 && /beta|banned|disabled/i.test(detail)) {
        await supabase.auth.signOut();
        return { user: null, errorMessage: detail };
      }

      const statusText = detail ? `${res.status}: ${detail}` : `${res.status}`;
      log("fetchUser: failed with status", statusText);

      return {
        user: null,
        errorMessage: `${PROFILE_LOAD_ERROR} Session validation failed (${statusText}).`,
      };
    } catch (err) {
      log("fetchUser: error", err);
      return {
        user: null,
        errorMessage: `${PROFILE_LOAD_ERROR} Network error while validating session.`,
      };
    }
  }, []);

  const clearAuthError = useCallback(() => {
    setAuthError(null);
  }, []);

  const hydrateSession = useCallback(async (accessToken: string) => {
    const { user: me, errorMessage } = await fetchUser(accessToken);
    if (me) {
      setToken(accessToken);
      setUser(me);
      userRef.current = me;
      setAuthError(null);
      return;
    }

    setToken(null);
    setUser(null);
    userRef.current = null;
    setAuthError(errorMessage || PROFILE_LOAD_ERROR);
  }, [fetchUser]);

  // Initialize auth — runs once
  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;

    log("init: starting, url =", window.location.href);

    // Get initial session
    supabase.auth.getSession().then(({ data: { session }, error }) => {
      log("init: getSession result", { hasSession: !!session, error: error?.message });
      if (session?.access_token) {
        hydrateSession(session.access_token).finally(() => setIsLoading(false));
      } else {
        setIsLoading(false);
      }
    }).catch((err) => {
      log("init: getSession error", err);
      setIsLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      log("onAuthStateChange:", event, { hasSession: !!session });

      // Skip initial — handled above
      if (event === "INITIAL_SESSION") return;

      // Defer to prevent sync render loops
      setTimeout(() => {
        if (session?.access_token) {
          // Supabase fires multiple events on tab focus: TOKEN_REFRESHED,
          // and sometimes SIGNED_IN when it re-detects the session from
          // storage. Only do full hydration (loading spinner + /auth/me)
          // when we don't already have a user — i.e. actual sign-in.
          // Otherwise just silently update the token.
          if (userRef.current) {
            log("auth event while user exists:", event, "— silent token update");
            setToken(session.access_token);
            return;
          }
          log("auth event with no user:", event, "— full hydration");
          setIsLoading(true);
          hydrateSession(session.access_token).finally(() => setIsLoading(false));
        } else {
          setToken(null);
          setUser(null);
          setAuthError(null);
          setIsLoading(false);
        }
      }, 0);
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [hydrateSession]);

  const login = useCallback(async (email: string, password: string) => {
    log("login:", email);
    setAuthError(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      const msg = /banned/i.test(error.message) ? BETA_DISABLED_MSG : error.message;
      throw new Error(msg);
    }
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    log("register:", email);
    setAuthError(null);
    const { error } = await supabase.auth.signUp({ email, password });
    if (error) throw new Error(error.message);
  }, []);

  const logout = useCallback(async () => {
    log("logout");
    await supabase.auth.signOut();
    localStorage.removeItem("sgm_setup_complete");
    setToken(null);
    setUser(null);
    userRef.current = null;
    setAuthError(null);
  }, []);

  const value = useMemo(
    () => ({ user, token, isLoading, authError, clearAuthError, login, register, logout }),
    [user, token, isLoading, authError, clearAuthError, login, register, logout],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
