import { Database, FolderKanban, History, KeyRound, ShieldCheck, Sparkles, Users, Workflow } from "lucide-react";
import type { Catalogue } from "../../i18n";

/** The Administración tiles (feature 023 drift test: every `to` has a guide topic). */
export interface AdminTile {
  to: string;
  title: (t: Catalogue) => string;
  text: (t: Catalogue) => string;
  icon: typeof Users;
  superOnly?: boolean;
}

export const ADMIN_TILES: AdminTile[] = [
  { to: "/admin/usuarios", title: (t) => t.nav.users, text: (t) => t.admin.home.usersText, icon: Users },
  { to: "/admin/fuentes", title: (t) => t.admin.sources.title, text: (t) => t.admin.home.sourcesText, icon: Database, superOnly: true },
  { to: "/admin/integraciones", title: (t) => t.admin.home.integrations, text: (t) => t.admin.home.integrationsText, icon: Workflow, superOnly: true },
  { to: "/admin/tokens", title: (t) => t.admin.tokens.title, text: (t) => t.admin.home.tokensText, icon: KeyRound, superOnly: true },
  { to: "/admin/seguridad", title: (t) => t.admin.security.security, text: (t) => t.admin.home.securityText, icon: ShieldCheck, superOnly: true },
  { to: "/admin/auditoria", title: (t) => t.nav.audit, text: (t) => t.admin.home.auditText, icon: History, superOnly: true },
  { to: "/proyectos", title: (t) => t.projects.title, text: (t) => t.admin.home.projectsText, icon: FolderKanban, superOnly: true },
  { to: "/admin/ia", title: (t) => t.ai.title, text: (t) => t.admin.home.aiText, icon: Sparkles, superOnly: true },
];
