import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { api, ApiError, setUnauthenticatedHandler } from "../api/client";
import type { LoginResult, User } from "../api/types";
import { FullPageSpinner } from "../components/Spinner";

interface AuthState {
  user: User | null;
  loading: boolean;
  /** Resolves with the user, or with "mfa" when the second step is required. */
  login: (email: string, password: string) => Promise<User | "mfa">;
  completeMfa: (input: { code?: string; recovery_code?: string }) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  setUser: (u: User | null) => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  const refresh = useCallback(async () => {
    try {
      setUser(await api.get<User>("/api/me"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setUser(null);
      else throw e;
    }
  }, []);

  useEffect(() => {
    refresh()
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, [refresh]);

  // Any 401 from the API (expired or revoked session) → back to sign-in, keeping the page.
  useEffect(() => {
    setUnauthenticatedHandler(() => {
      setUser(null);
      // The public shared-dashboard page (/s/<token>, feature 018) never redirects to sign-in.
      if (!location.pathname.startsWith("/ingresar") && !location.pathname.startsWith("/s/")) {
        const next = location.pathname + location.search;
        navigate(`/ingresar?expirada=1&next=${encodeURIComponent(next)}`, { replace: true });
      }
    });
    return () => setUnauthenticatedHandler(null);
  }, [location, navigate]);

  const login = useCallback(async (email: string, password: string): Promise<User | "mfa"> => {
    const res = await api.post<LoginResult>("/api/auth/login", { email, password });
    if (res.mfa_enrollment_required) {
      // Password accepted but two-step sign-in is not enrolled yet: the pending session may only
      // enrol it, and /api/me reports the user so RequireAuth sends them to the setup screen.
      const me = await api.get<User>("/api/me");
      setUser(me);
      return me;
    }
    if (res.mfa_required || !res.user) return "mfa";
    setUser(res.user);
    return res.user;
  }, []);

  const completeMfa = useCallback(async (input: { code?: string; recovery_code?: string }) => {
    const res = await api.post<{ user: User }>("/api/auth/mfa", input);
    setUser(res.user);
    return res.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/api/auth/logout");
    } finally {
      setUser(null);
      navigate("/ingresar", { replace: true });
    }
  }, [navigate]);

  const value = useMemo(
    () => ({ user, loading, login, completeMfa, logout, refresh, setUser }),
    [user, loading, login, completeMfa, logout, refresh],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}

/** The signed-in user, or null outside the provider (components also rendered standalone). */
export function useOptionalUser(): AuthState["user"] | null {
  return useContext(AuthContext)?.user ?? null;
}

/** Only same-origin relative paths are accepted as redirect targets (no open redirect). */
export function safeNext(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return "/";
  return next;
}

export const MFA_SETUP_PATH = "/seguridad/doble-factor";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <FullPageSpinner />;
  if (!user) {
    const next = location.pathname + location.search;
    return <Navigate to={`/ingresar?next=${encodeURIComponent(next)}`} replace />;
  }
  if (user.must_change_password && location.pathname !== "/cambiar-clave") {
    return <Navigate to="/cambiar-clave" replace />;
  }
  // Internet profile: administrators enroll two-step sign-in before anything else.
  if (!user.must_change_password && user.mfa_required && !user.mfa_enabled && location.pathname !== MFA_SETUP_PATH) {
    return <Navigate to={MFA_SETUP_PATH} replace />;
  }
  return <>{children}</>;
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (user?.role !== "admin") return <Navigate to="/no-autorizado" replace />;
  return <>{children}</>;
}

export function RequireSuperuser({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (!user?.is_superuser) return <Navigate to="/no-autorizado" replace />;
  return <>{children}</>;
}
