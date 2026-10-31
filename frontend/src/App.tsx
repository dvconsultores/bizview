import { lazy, Suspense, type ReactElement } from "react";
import { Route, Routes } from "react-router";
import { AuthProvider, RequireAdmin, RequireAuth, RequireSuperuser } from "./auth/AuthContext";
import { AppShell } from "./components/AppShell";
import { ToastProvider } from "./components/Toast";
import { BrandingProvider } from "./config/BrandingContext";
import { ReauthProvider } from "./components/ReauthDialog";
import { ViewHost } from "./components/ViewHost";
import { AdminHome } from "./pages/admin/AdminHome";
import { Appearance } from "./pages/admin/Appearance";
import { AI } from "./pages/admin/AI";
import { Security } from "./pages/admin/Security";
import { SourceForm } from "./pages/admin/SourceForm";
import { Sources } from "./pages/admin/Sources";
import { TwoFactorSetup } from "./pages/TwoFactorSetup";
import { Audit } from "./pages/admin/Audit";
import { UserDetail } from "./pages/admin/UserDetail";
import { UserForm } from "./pages/admin/UserForm";
import { Users } from "./pages/admin/Users";
import { Integrations } from "./pages/admin/Integrations";
import { Tokens } from "./pages/admin/Tokens";
import { Workspace } from "./pages/admin/Workspace";
import { ReportView } from "./pages/ReportView";
import { ChangePassword } from "./pages/ChangePassword";
import { DashboardGate } from "./pages/DashboardGate";
import { Forbidden } from "./pages/Forbidden";
import { Dashboards } from "./pages/Dashboards";
import { Home } from "./pages/Home";
import { NotFound } from "./pages/NotFound";
import { Profile } from "./pages/Profile";
import { Help } from "./pages/Help";
import { SharedDashboard } from "./pages/SharedDashboard";
import { SignIn } from "./pages/SignIn";
import { LocaleProvider } from "./i18n";
import { ThemeProvider } from "./theme/ThemeContext";

// Feature 020: the project pages (editor libraries included) load on demand.
const Projects = lazy(() => import("./pages/projects/Projects").then((m) => ({ default: m.Projects })));
const ProjectWorkspace = lazy(() =>
  import("./pages/projects/ProjectWorkspace").then((m) => ({ default: m.ProjectWorkspace })));
const ProjectHistory = lazy(() =>
  import("./pages/projects/ProjectHistory").then((m) => ({ default: m.ProjectHistory })));
const lazyPage = (page: ReactElement) => <Suspense fallback={null}>{page}</Suspense>;

export function App() {
  return (
    <BrandingProvider>
      <AuthProvider>
        <ToastProvider>
          <ThemeProvider>
            <LocaleProvider>
              <ReauthProvider>
              <ViewHost>
                <Routes>
                  <Route path="/ingresar" element={<SignIn />} />
                  {/* Feature 018: public, read-only shared dashboard (outside the authenticated shell). */}
                  <Route path="/s/:token" element={<SharedDashboard />} />
                  <Route path="/cambiar-clave" element={<RequireAuth><ChangePassword /></RequireAuth>} />
                  <Route element={<RequireAuth><AppShell /></RequireAuth>}>
                    <Route index element={<Home />} />
                    <Route path="tableros" element={<Dashboards />} />
                    <Route path="d/:code" element={<DashboardGate />} />
                    <Route path="r/:id" element={<ReportView />} />
                    <Route path="perfil" element={<Profile />} />
                    <Route path="ayuda" element={<Help />} />
                    <Route path="admin/usuarios" element={<RequireAdmin><Users /></RequireAdmin>} />
                    <Route path="admin/usuarios/nuevo" element={<RequireAdmin><UserForm /></RequireAdmin>} />
                    <Route path="admin/usuarios/:id" element={<RequireAdmin><UserDetail /></RequireAdmin>} />
                    <Route path="admin/auditoria" element={<RequireSuperuser><Audit /></RequireSuperuser>} />
                    <Route path="admin/ia" element={<RequireSuperuser><AI /></RequireSuperuser>} />
                    <Route path="admin" element={<RequireAdmin><AdminHome /></RequireAdmin>} />
                    <Route path="admin/fuentes" element={<RequireSuperuser><Sources /></RequireSuperuser>} />
                    <Route path="admin/fuentes/nueva" element={<RequireSuperuser><SourceForm /></RequireSuperuser>} />
                    <Route path="admin/fuentes/:id" element={<RequireSuperuser><SourceForm /></RequireSuperuser>} />
                    <Route path="admin/apariencia" element={<RequireSuperuser><Appearance /></RequireSuperuser>} />
                  <Route path="admin/seguridad" element={<RequireSuperuser><Security /></RequireSuperuser>} />
                    <Route path="admin/espacio" element={<RequireSuperuser><Workspace /></RequireSuperuser>} />
                    <Route path="admin/integraciones" element={<RequireSuperuser><Integrations /></RequireSuperuser>} />
                    <Route path="admin/tokens" element={<RequireSuperuser><Tokens /></RequireSuperuser>} />
                    <Route path="proyectos" element={<RequireSuperuser>{lazyPage(<Projects />)}</RequireSuperuser>} />
                    <Route path="proyectos/:slug" element={<RequireSuperuser>{lazyPage(<ProjectWorkspace />)}</RequireSuperuser>} />
                    <Route path="proyectos/:slug/historial" element={<RequireSuperuser>{lazyPage(<ProjectHistory />)}</RequireSuperuser>} />
                    <Route path="seguridad/doble-factor" element={<TwoFactorSetup />} />
                    <Route path="no-autorizado" element={<Forbidden />} />
                    <Route path="*" element={<NotFound />} />
                  </Route>
                </Routes>
              </ViewHost>
              </ReauthProvider>
            </LocaleProvider>
          </ThemeProvider>
        </ToastProvider>
      </AuthProvider>
    </BrandingProvider>
  );
}
