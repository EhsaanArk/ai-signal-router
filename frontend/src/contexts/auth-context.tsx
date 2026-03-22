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
import { API_BASE_URL } from "@/lib/constants";

interface AuthContextValue {
  user: UserMe | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const DEBUG = true;
function log(...args: unknown[]) {
  if (DEBUG) console.log("[SageAuth]", ...args);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserMe | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const initRef = useRef(false);

  // Fetch app-specific user data from backend
  const fetchUser = useCallback(async (accessToken: string): Promise<boolean> => {
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
        setUser(me);
        return true;
      }
      log("fetchUser: failed with status", res.status);
      return false;
    } catch (err) {
      log("fetchUser: error", err);
      return false;
    }
  }, []);

  // Initialize auth — runs once
  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;

    log("init: starting, url =", window.location.href);

    // Get initial session
    supabase.auth.getSession().then(({ data: { session }, error }) => {
      log("init: getSession result", { hasSession: !!session, error: error?.message });
      if (session?.access_token) {
        setToken(session.access_token);
        fetchUser(session.access_token).finally(() => setIsLoading(false));
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
          setToken(session.access_token);
          fetchUser(session.access_token).finally(() => setIsLoading(false));
        } else {
          setToken(null);
          setUser(null);
          setIsLoading(false);
        }
      }, 0);
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [fetchUser]);

  const login = useCallback(async (email: string, password: string) => {
    log("login:", email);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw new Error(error.message);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    log("register:", email);
    const { error } = await supabase.auth.signUp({ email, password });
    if (error) throw new Error(error.message);
  }, []);

  const logout = useCallback(async () => {
    log("logout");
    await supabase.auth.signOut();
    localStorage.removeItem("sgm_setup_complete");
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, token, isLoading, login, register, logout }),
    [user, token, isLoading, login, register, logout],
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
