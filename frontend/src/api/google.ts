import { api } from "./client";
import type {
  GoogleAccess,
  GoogleAdminState,
  GoogleCondition,
  GoogleRule,
  GoogleSettings,
  Role,
} from "./types";

/** What the card sends for a new or edited rule; the id comes from the path. */
export interface GoogleRuleInput {
  condition: GoogleCondition;
  value: string[];
  role: Role;
  access: GoogleAccess;
  enabled: boolean;
}

const BASE = "/api/admin/google";

/** The rule body as the API reads it; the client wants a plain record. */
const payload = (rule: GoogleRuleInput): Record<string, unknown> => ({ ...rule });

/**
 * The installation's Google sign-in policy (feature 054). Settings and rules are read in one go —
 * the card shows both, and the callback obeys what is saved here.
 */
export const googleAdmin = {
  async state(): Promise<GoogleAdminState> {
    const body = await api.get<GoogleAdminState>(BASE);
    return { settings: body.settings, dashboards: body.dashboards };
  },

  async saveSettings(settings: Omit<GoogleSettings, "domains_from_env" | "updated_at">)
    : Promise<GoogleAdminState> {
    return api.put<GoogleAdminState>(BASE, {
      allowed_domains: settings.allowed_domains,
      auto_provision: settings.auto_provision,
      default_role: settings.default_role,
      default_access: settings.default_access,
      apply_rules_to_existing: settings.apply_rules_to_existing,
    });
  },

  async rules(): Promise<GoogleRule[]> {
    const body = await api.get<{ items: GoogleRule[] }>(`${BASE}/rules`);
    return body.items;
  },

  createRule: (rule: GoogleRuleInput) => api.post<GoogleRule>(`${BASE}/rules`, payload(rule)),

  updateRule: (id: number, rule: GoogleRuleInput) =>
    api.put<GoogleRule>(`${BASE}/rules/${id}`, payload(rule)),

  deleteRule: (id: number) => api.del<void>(`${BASE}/rules/${id}`),

  async reorder(ids: number[]): Promise<GoogleRule[]> {
    const body = await api.put<{ items: GoogleRule[] }>(`${BASE}/rules/reorder`, { ids });
    return body.items;
  },
};

/** The access picker's options: the catalogue the server sends with the settings. */
export type GoogleDashboardOption = GoogleAdminState["dashboards"][number];
