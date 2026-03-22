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
import type { Session } from "@supabase/supabase-js";
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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserMe | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const fetchingRef = useRef(false);
  const mountedRef = useRef(true);

  // Fetch app-specific user data from backend — direct fetch, no loops
  const fetchUser = useCallback(async (accessToken: string) => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    try {
      const res = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
      });
      if (res.ok && mountedRef.current) {
        const me: UserMe = await res.json();
        setUser(me);
      }
    } catch (err) {
      console.error("fetchUser failed:", err);
    } finally {
      fetchingRef.current = false;
    }
  }, []);

  // Handle session update — deferred to avoid synchronous render loops
  const handleSession = useCallback((s: Session | null) => {
    if (!mountedRef.current) return;
    const newToken = s?.access_token ?? null;
    setToken(newToken);
    if (newToken) {
      fetchUser(newToken).finally(() => {
        if (mountedRef.current) setIsLoading(false);
      });
    } else {
      setUser(null);
      setIsLoading(false);
    }
  }, [fetchUser]);

  useEffect(() => {
    mountedRef.current = true;

    // 1. Get initial session
    supabase.auth.getSession().then(({ data: { session: s } }) => {
      if (mountedRef.current) handleSession(s);
    }).catch(() => {
      if (mountedRef.current) setIsLoading(false);
    });

    // 2. Listen for auth changes — use setTimeout to defer and prevent sync loops
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, s) => {
      if (event === "INITIAL_SESSION") return;
      // Defer to next tick to prevent synchronous render loops
      setTimeout(() => {
        if (mountedRef.current) handleSession(s);
      }, 0);
    });

    return () => {
      mountedRef.current = false;
      subscription.unsubscribe();
    };
  }, [handleSession]);

  const login = useCallback(async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw new Error(error.message);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({ email, password });
    if (error) throw new Error(error.message);
  }, []);

  const logout = useCallback(async () => {
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
