import { ChevronsLeft, ChevronsRight, CircleHelp, FolderKanban, Home, LayoutDashboard, LayoutGrid, LogOut, Moon, Sun, User as UserIcon, type LucideIcon } from "lucide-react";
import {
  useCallback, useEffect, useMemo, useRef, useState,
  type CSSProperties, type ReactNode,
} from "react";
import { Link, NavLink, Outlet } from "react-router";
import { useAuth } from "../auth/AuthContext";
import { useBranding } from "../config/BrandingContext";
import { useT } from "../i18n";
import { APP_CONTAINER, APP_GUTTER } from "../lib/layout";
import { initials } from "../lib/format";
import { readNavCollapsed, writeNavCollapsed } from "../lib/navPrefs";
import { useTheme } from "../theme/ThemeContext";
import { Logo } from "./Logo";
import { ShellChromeContext } from "./ShellChrome";
import { SourceFooter } from "./SourceFooter";
import { UpdateBanner } from "./UpdateBanner";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { ViewHost } from "./ViewHost";
import { AssistantPanel } from "./assistant/AssistantPanel";
import { AssistantPanelProvider, useAssistantPanel } from "./assistant/AssistantPanelContext";
import { AssistantToggle } from "./assistant/AssistantToggle";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

function ThemeToggle() {
  const t = useT();
  const { resolved, setPreference } = useTheme();
  const isDark = resolved === "dark";
  return (
    <button
      type="button"
      onClick={() => void setPreference(isDark ? "light" : "dark")}
      aria-label={isDark ? t.theme.toggleToLight : t.theme.toggleToDark}
      className="inline-flex min-h-tap min-w-tap items-center justify-center rounded-xl text-on-primary hover:bg-white/10 lg:text-ink-muted lg:hover:bg-subtle lg:hover:text-ink"
    >
      {isDark ? <Sun className="h-5 w-5" aria-hidden /> : <Moon className="h-5 w-5" aria-hidden />}
    </button>
  );
}

/** Desktop sidebar: every section. Phones: a short bottom bar (Inicio · Administración · Perfil). */
function useNavItems(): { full: NavItem[]; compact: NavItem[] } {
  const t = useT();
  const { user } = useAuth();
  const home: NavItem = { to: "/", label: t.nav.home, icon: Home, end: true };
  const dashboards: NavItem = { to: "/tableros", label: t.nav.dashboards, icon: LayoutDashboard };
  const profile: NavItem = { to: "/perfil", label: t.nav.profile, icon: UserIcon };
  const full: NavItem[] = [home, dashboards];
  // Every admin section is reached from the Administración page; the item stays highlighted
  // on all of them.
  if (user?.is_superuser) full.push({ to: "/proyectos", label: t.nav.projects, icon: FolderKanban });
  if (user?.role === "admin") full.push({ to: "/admin", label: t.nav.admin, icon: LayoutGrid });
  full.push(profile);
  full.push({ to: "/ayuda", label: t.nav.help, icon: CircleHelp });
  const compact: NavItem[] = [home, dashboards];
  if (user?.role === "admin") compact.push({ to: "/admin", label: t.nav.admin, icon: LayoutGrid });
  compact.push(profile);
  return { full, compact };
}

function AccountMenu() {
  const t = useT();
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent | TouchEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("touchstart", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("touchstart", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  if (!user) return null;
  const firstName = user.full_name.trim().split(/\s+/)[0];
  const roleLabel = t.roles[user.is_superuser ? "superuser" : user.role] ?? user.role;
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t.nav.menu}
        className="inline-flex min-h-tap min-w-tap items-center justify-center rounded-full lg:pl-1 lg:pr-3 lg:hover:bg-subtle"
      >
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-white/15 text-sm font-semibold text-on-primary ring-1 ring-white/30 lg:hidden">
          {initials(user.full_name)}
        </span>
        <span className="hidden items-center lg:inline-flex">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-accent-soft text-sm font-semibold text-accent ring-1 ring-line-accent">
            {initials(user.full_name)}
          </span>
          <span className="ml-3 flex flex-col items-start justify-center">
            <span className="text-sm font-semibold text-ink">{firstName}</span>
            <span className="text-xs text-ink-muted">{roleLabel}</span>
          </span>
        </span>
      </button>
      {open ? (
        <div role="menu" className="absolute right-0 z-40 mt-2 w-64 overflow-hidden rounded-xl bg-surface text-ink-2 shadow-raised ring-1 ring-line">
          <div className="border-b border-line-soft px-4 py-3">
            <p className="truncate font-semibold">{user.full_name}</p>
            <p className="truncate text-sm text-ink-soft">{user.email}</p>
          </div>
          <div className="border-b border-line-soft px-3 py-2">
            <ThemeSwitcher inMenu />
          </div>
          <div className="border-b border-line-soft px-3 py-2">
            <LanguageSwitcher inMenu />
          </div>
          <Link role="menuitem" to="/perfil" onClick={() => setOpen(false)} className="flex min-h-tap items-center px-4 hover:bg-subtle">
            <UserIcon className="mr-3 h-5 w-5 text-ink-soft" aria-hidden />
            {t.nav.profile}
          </Link>
          <Link role="menuitem" to="/ayuda" onClick={() => setOpen(false)} className="flex min-h-tap items-center px-4 hover:bg-subtle">
            <CircleHelp className="mr-3 h-5 w-5 text-ink-soft" aria-hidden />
            {t.nav.help}
          </Link>
          <button role="menuitem" type="button" onClick={() => void logout()} className="flex min-h-tap w-full items-center px-4 text-left text-danger hover:bg-danger-soft">
            <LogOut className="mr-3 h-5 w-5" aria-hidden />
            {t.nav.signOut}
          </button>
        </div>
      ) : null}
    </div>
  );
}

/** Content column of the shell. The docked chat takes its own column instead of floating over the
 * page: with the panel open the content keeps its room, so nothing under the panel becomes
 * unreachable (feature 024 polish). That holds in full screen too (feature 025): the chrome steps
 * aside, but the chat's column stays reserved so the project's own controls remain reachable.
 * `children` receives whether the chat is docked, because the content's own padding is tighter next
 * to the panel — the seam between the page and the chat was the widest blank space on the screen. */
function ShellContent({ hidden, chat, collapsed, children }: {
  hidden: boolean;
  chat: boolean;
  collapsed: boolean;
  children: (docked: boolean) => ReactNode;
}) {
  const { mode, width } = useAssistantPanel();
  const docked = chat && mode === "docked";
  return (
    <div
      style={docked ? ({ "--assistant-width": `${width}px` } as CSSProperties) : undefined}
      className={`${hidden ? "" : collapsed ? "lg:pl-[5rem]" : "lg:pl-64"} ${
        docked ? "lg:pr-[var(--assistant-width)]" : ""
      }`}
      data-assistant-width={docked ? width : undefined}
    >
      {children(docked)}
    </div>
  );
}

/** Gradient top strip + bottom tab bar on phones/tablets; from 1024 px a full-height sidebar with
 * the gradient logo block and a white top bar over the content (feature 010). */
export function AppShell() {
  const t = useT();
  const { product_name, organization_name } = useBranding();
  const { full, compact } = useNavItems();
  const [chrome, setChrome] = useState<{ hidden: boolean; chat: boolean }>({ hidden: false, chat: true });
  const chromeHidden = chrome.hidden;
  const chromeState = useMemo(() => ({ ...chrome, setHidden: setChrome }), [chrome]);
  const [navCollapsed, setNavCollapsed] = useState(readNavCollapsed);
  const toggleNav = useCallback((next: boolean) => {
    writeNavCollapsed(next);
    setNavCollapsed(next);
  }, []);

  return (
    <ShellChromeContext.Provider value={chromeState}>
      <AssistantPanelProvider>
      <div className="min-h-screen bg-canvas">
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2">
          {t.common.skipToContent}
        </a>

        {!chromeHidden ? (
          <aside
            className={`fixed inset-y-0 left-0 z-20 hidden flex-col border-r border-line bg-surface lg:flex ${
              navCollapsed ? "w-[5rem]" : "w-64"
            }`}
          >
            <div className={`flex h-20 shrink-0 items-center gap-3 bg-brand-gradient ${navCollapsed ? "justify-center px-2" : "px-5"}`}>
              <Logo inverted className="h-10 w-10 shrink-0" />
              {!navCollapsed ? (
                <div className="min-w-0">
                  <p className="truncate text-base font-bold leading-tight text-on-primary">{product_name}</p>
                  {organization_name ? <p className="truncate text-xs text-on-primary">{organization_name}</p> : null}
                </div>
              ) : null}
            </div>
            {/* The menu: labels when there is room, an icon rail when collapsed (feature 025). The
                label stays in the DOM behind `sr-only`, so the accessible name never changes. */}
            <nav id="app-nav" aria-label={t.nav.main}
                 className={`flex-1 overflow-y-auto pt-3 ${navCollapsed ? "px-1.5" : "px-3"}`}>
              <ul className="space-y-1">
                {full.map((it) => {
                  const Icon = it.icon;
                  return (
                    <li key={it.to}>
                      <NavLink
                        to={it.to}
                        end={it.end}
                        title={navCollapsed ? it.label : undefined}
                        className={({ isActive }) =>
                          `flex min-h-tap items-center rounded-xl text-base font-medium ${
                            navCollapsed ? "min-w-tap justify-center px-2" : "px-4"
                          } ${
                            isActive ? "bg-gradient-to-r from-primary to-primary-hover text-on-primary shadow-card" : "text-ink-2 hover:bg-subtle"
                          }`
                        }
                      >
                        <Icon className={`h-[18px] w-[18px] shrink-0 ${navCollapsed ? "" : "mr-3"}`} aria-hidden />
                        <span className={navCollapsed ? "sr-only" : undefined}>{it.label}</span>
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
              {/* The control stays next to the menu it acts on, so the space left below is one
                  clean block instead of being split by a pinned row. */}
              <button
                type="button"
                onClick={() => toggleNav(!navCollapsed)}
                aria-controls="app-nav"
                aria-expanded={!navCollapsed}
                aria-label={navCollapsed ? t.nav.expand : t.nav.collapse}
                title={navCollapsed ? t.nav.expand : t.nav.collapse}
                className={`flex min-h-tap w-full items-center rounded-xl text-base font-medium text-ink-muted transition-colors hover:bg-subtle hover:text-ink ${
                  navCollapsed ? "justify-center px-2" : "px-4"
                }`}
              >
                {navCollapsed ? <ChevronsRight className="h-[18px] w-[18px] shrink-0" aria-hidden />
                              : <ChevronsLeft className="mr-3 h-[18px] w-[18px] shrink-0" aria-hidden />}
                {!navCollapsed ? <span>{t.nav.collapse}</span> : null}
              </button>
            </nav>
          </aside>
        ) : null}

        <ShellContent hidden={chromeHidden} chat={chrome.chat} collapsed={navCollapsed}>
          {(docked) => (
            <>
            {!chromeHidden ? (
            <header className="sticky top-0 z-30 bg-brand-gradient pt-safe text-on-primary shadow-md lg:border-b lg:border-line lg:bg-surface lg:bg-none lg:pt-0 lg:shadow-none">
              <div className={`flex h-14 items-center justify-between px-4 sm:h-16 sm:px-5 ${
                  docked ? "lg:pl-4 lg:pr-3" : "lg:px-4"
                }`}>
                <Link to="/" className="flex min-w-0 items-center lg:hidden">
                  <Logo className="h-9 w-9 shrink-0" inverted />
                  <span className="ml-3 min-w-0">
                    <span className="block truncate font-semibold leading-tight">{product_name}</span>
                    {organization_name ? <span className="block truncate text-xs text-on-primary">{organization_name}</span> : null}
                  </span>
                </Link>
                <div className="hidden lg:block" />
                <div className="flex shrink-0 items-center gap-1 sm:gap-2">
                  <AssistantToggle />
                  <ThemeToggle />
                  <AccountMenu />
                </div>
              </div>
            </header>
          ) : null}

          <UpdateBanner />

          <main
            id="main"
            className={
              chromeHidden
                ? "px-4 py-4 sm:px-5 lg:px-5"
                : `px-4 pb-10 pt-4 sm:pt-5 lg:pb-10 ${
                    // With the chat docked the content already lost the panel's column, so it uses
                    // all of what is left: the centered cap would leave canvas in front of the
                    // panel on a wide screen (the same "exaggerated space" the owner reported).
                    docked ? "lg:pl-4 lg:pr-0" : `${APP_CONTAINER} ${APP_GUTTER}`
                  }`
            }
          >
            <ViewHost>
              <Outlet />
            </ViewHost>
          </main>

            {!chromeHidden ? <SourceFooter className="px-4 pb-28 lg:pb-8" /> : null}
            </>
          )}
        </ShellContent>

        {!chromeHidden ? (
          <nav aria-label={t.nav.main} className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 pb-safe backdrop-blur lg:hidden">
            <ul className="mx-auto flex max-w-lg">
              {compact.map((it) => {
                const Icon = it.icon;
                return (
                  <li key={it.to} className="flex-1">
                    <NavLink
                      to={it.to}
                      end={it.end}
                      className={({ isActive }) =>
                        `flex min-h-[56px] flex-col items-center justify-center text-xs font-medium ${
                          isActive ? "text-accent" : "text-ink-soft"
                        }`
                      }
                    >
                      <Icon className="h-6 w-6" aria-hidden />
                      <span className="mt-0.5">{it.label}</span>
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          </nav>
        ) : null}

        {/* The chat stays available in full screen too (feature 025): the chrome steps aside, the
            panel does not. Kiosk-like modes (the report's TV mode) ask for it to step aside as well. */}
        {chrome.chat ? <AssistantPanel /> : null}
      </div>
      </AssistantPanelProvider>
    </ShellChromeContext.Provider>
  );
}
