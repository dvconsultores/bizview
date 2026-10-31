/** Who can open each route of App.tsx (feature 023): in-app links of the guide and of chat
 * answers are shown only when the viewer can open them. The drift test keeps this table equal
 * to App.tsx (patterns and guards). */
export type RouteAccess = "public" | "user" | "admin" | "superuser";

export const ROUTES: { pattern: string; access: RouteAccess }[] = [
  { pattern: "/ingresar", access: "public" },
  { pattern: "/s/:token", access: "public" },
  { pattern: "/cambiar-clave", access: "user" },
  { pattern: "/", access: "user" },
  { pattern: "/tableros", access: "user" },
  { pattern: "/d/:code", access: "user" },
  { pattern: "/r/:id", access: "user" },
  { pattern: "/perfil", access: "user" },
  { pattern: "/ayuda", access: "user" },
  { pattern: "/admin/usuarios", access: "admin" },
  { pattern: "/admin/usuarios/nuevo", access: "admin" },
  { pattern: "/admin/usuarios/:id", access: "admin" },
  { pattern: "/admin/auditoria", access: "superuser" },
  { pattern: "/admin/ia", access: "superuser" },
  { pattern: "/admin", access: "admin" },
  { pattern: "/admin/fuentes", access: "superuser" },
  { pattern: "/admin/fuentes/nueva", access: "superuser" },
  { pattern: "/admin/fuentes/:id", access: "superuser" },
  { pattern: "/admin/apariencia", access: "superuser" },
  { pattern: "/admin/seguridad", access: "superuser" },
  { pattern: "/admin/espacio", access: "superuser" },
  { pattern: "/admin/integraciones", access: "superuser" },
  { pattern: "/admin/tokens", access: "superuser" },
  { pattern: "/proyectos", access: "superuser" },
  { pattern: "/proyectos/:slug", access: "superuser" },
  { pattern: "/proyectos/:slug/historial", access: "superuser" },
  { pattern: "/seguridad/doble-factor", access: "user" },
  { pattern: "/no-autorizado", access: "user" },
  { pattern: "*", access: "user" },
];

function segments(path: string): string[] {
  return path.split(/[?#]/)[0].split("/").filter(Boolean);
}

function matches(pattern: string, path: string): boolean {
  const want = segments(pattern);
  const have = segments(path);
  if (want.length !== have.length) return false;
  return want.every((part, i) => (part.startsWith(":") ? have[i].length > 0 : part === have[i]));
}

/** The route a path opens (`:param` = one non-empty segment; query and hash ignored). The
 * catch-all `*` matches only when asked for explicitly. */
export function matchRoute(path: string): { pattern: string; access: RouteAccess } | null {
  if (path === "*") return ROUTES.find((r) => r.pattern === "*") ?? null;
  return ROUTES.find((r) => r.pattern !== "*" && matches(r.pattern, path)) ?? null;
}

export interface Viewer {
  role: string;
  is_superuser: boolean;
}

/** A superuser passes admin; an admin passes user; public routes need no account. */
export function canAccess(access: RouteAccess, user: Viewer | null): boolean {
  if (access === "public") return true;
  if (!user) return false;
  if (access === "user") return true;
  if (access === "admin") return user.role === "admin" || user.is_superuser;
  return user.is_superuser;
}

export function canOpen(path: string, user: Viewer | null): boolean {
  const route = matchRoute(path);
  return route !== null && canAccess(route.access, user);
}
