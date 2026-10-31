import type { ThemePreference } from "../theme/resolve";
import type { Locale, LocalePreference } from "../i18n/resolve";

export type { ThemePreference, Locale, LocalePreference };
export type Role = "admin" | "user";
export type DashboardStatus = "available" | "coming_soon" | "hidden";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_superuser: boolean;
  is_active: boolean;
  must_change_password: boolean;
  locked_until: string | null;
  last_login_at: string | null;
  created_at: string;
  mfa_enabled: boolean;
  theme: ThemePreference;
  locale?: LocalePreference;
  mfa_required?: boolean;
  reauth_valid_until?: string | null;
  recovery_codes_left?: number;
  /** Feature 024: when the user accepted the "images go to the provider" notice. */
  attachments_notice_at?: string | null;
}

/** POST /api/auth/login. With a second factor pending the response carries no user; under the
 * internet profile an administrator who has not enrolled gets `mfa_enrollment_required` and the
 * pending session may only enrol. */
export interface LoginResult {
  user?: User;
  mfa_required?: boolean;
  mfa_enrollment_required?: boolean;
}

export interface Dashboard {
  code: string;
  name: string;
  description: string;
  name_en?: string;
  description_en?: string;
  icon: string;
  status: DashboardStatus;
  path: string;
}

export interface UserDashboard {
  code: string;
  name: string;
  status: DashboardStatus;
  granted?: boolean;
}

export interface UserDetail {
  user: User;
  dashboards: UserDashboard[];
  telegram_linked?: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
}

export interface AuditItem {
  id: number;
  occurred_at: string;
  kind: string;
  actor: { id: number; email: string } | null;
  target: { id: number; email: string } | null;
  ip: string | null;
  detail: Record<string, unknown>;
}

export interface PublicConfig {
  product_name: string;
  organization_name: string;
  logo_url: string | null;
  version: string;
  source_url: string | null;
  license: string;
  ai_enabled: boolean;
  /** Who publishes this installation (`FOOTER_CREDIT`): shown after the license in the footer. */
  footer_credit?: string;
  /** Feature 024: whether the configured model reads images (the composer shows the hint). */
  vision_enabled?: boolean;
  /** Feature 024: the limits the composer states and enforces before uploading. */
  attachments_max_mb?: number;
  attachments_max_per_message?: number;
  telegram_sign_in: boolean;
  telegram_bot: string | null;
  /** Feature 027: whether this installation offers Google as an additional sign-in method. */
  google_auth: boolean;
  default_locale?: Locale;
  /** Feature 030: the installation's palette preset (default "impacto") and the ids it may use. */
  palette_preset?: PaletteId;
  palette_presets?: PaletteId[];
}

export type AIProvider = "none" | "anthropic" | "openai_compatible";

export interface AIStatus {
  enabled: boolean;
  provider: AIProvider;
  model: string | null;
  base_url: string | null;
  key_configured: boolean;
  timeout_seconds: number;
  missing: string[];
  /** Feature 035: how the last call went (no key, no provider text beyond the redacted detail). */
  last_ok_at: string | null;
  last_error_code: string | null;
  last_error_at: string | null;
  last_error_detail: string | null;
  last_model: string | null;
  healthy: boolean;
  blocking_code: string | null;
}

/** 035: the unauthenticated AI block of `/api/health`, read by the pills. */
export interface AIHealth {
  configured: boolean;
  provider: AIProvider;
  model: string | null;
  last_ok_at: string | null;
  last_error_code: string | null;
  last_error_at: string | null;
}

export interface AITestResult {
  ok: boolean;
  provider: AIProvider;
  model: string | null;
  latency_ms: number | null;
  reply: string | null;
  error: { code: string; message: string; detail?: string | null;
           action?: "admin_ai" | "retry" | null } | null;
  tool_call?: { ok: boolean; name: string | null; latency_ms: number | null;
                error?: { code: string; message: string; detail?: string | null } | null } | null;
  models?: string[] | null;
}

// --- feature 004: data sources and security -----------------------------------------------

export type SourceKind = "postgresql" | "soap" | "rest" | "supabase";

export interface FieldDef {
  name: string;
  label: string;
  type: "string" | "integer" | "enum" | "url" | "pem" | "headers";
  required: boolean;
  secret: boolean;
  default: unknown;
  options: string[];
  show_if: Record<string, string[]>;
  min: number | null;
  max: number | null;
  help: string;
}

export type SourceTypes = Record<SourceKind, { label: string; fields: FieldDef[]; http_allowed: boolean }>;

export interface HeaderDef {
  name: string;
  secret: boolean;
  value?: string;
}

export interface SourceTest {
  ok: boolean;
  code: string | null;
  message: string;
  latency_ms: number | null;
  warnings: string[];
  warning_messages: string[];
  details: Record<string, unknown>;
}

export interface DataSource {
  id: number;
  name: string;
  kind: SourceKind;
  description: string;
  enabled: boolean;
  direct_reports: boolean;
  settings: Record<string, unknown>;
  secret_fields: string[];
  imported: boolean;
  last_test: (Partial<SourceTest> & { at: string; ok: boolean }) | null;
  created_at: string;
  updated_at: string;
}

export interface DirectReadCount {
  source: string;
  total: number;
  failed: number;
}

export interface SecurityOverview {
  profile: "private" | "internet";
  profile_source: string;
  http_allowed: boolean;
  checks: { id: string; ok: boolean | null; detail?: string }[];
  legacy_origin_notice: boolean;
  legacy_origin_variable_present: boolean;
  direct_reads?: DirectReadCount[];
  /** Feature 024: what the chat has sent to the provider (counts and sizes, never images). */
  attachments?: {
    total: number;
    bytes: number;
    conversations: number;
    provider: string;
    model: string;
  };
}

export interface MfaSetup {
  otpauth_uri: string;
  secret: string;
  qr_svg: string;
}

// --- Feature 005: vibe reporting -----------------------------------------------------------------

export type MetricFormat = "currency" | "integer" | "number" | "percent" | "text";
export type PeriodPreset =
  | "today" | "yesterday" | "last_7_days" | "mtd" | "last_month" | "qtd" | "ytd" | "last_12_months" | "custom";
export type CompareMode = "none" | "previous_period" | "previous_year";

export interface ReportDefinition {
  id: string;
  title: string;
  description: string;
  title_en?: string;
  description_en?: string;
  icon: string | null;
  currency: string;
  metrics: Record<
    string,
    {
      label: string;
      label_en?: string;
      format: MetricFormat;
      better: "higher" | "lower";
      description?: string | null;
      description_en?: string;
    }
  >;
  dimensions: Record<string, { label: string; label_en?: string }>;
  periods: { default: PeriodPreset; allowed: PeriodPreset[] };
  compare: { default: CompareMode; allowed: CompareMode[] };
  filters: string[];
  pdf: boolean;
  /** Deprecated and ignored since 0.2.0: the narrative generator is gone. The key stays so
   *  a project written for an older installation still validates. */
  ai_narrative?: boolean;
  direct?: { source: string; cache_seconds: number };
  /** The declared views, in payload order (`report.yaml` → `views`); `layout.web[].view` binds to
   * their `id` (feature 026). */
  views?: DeclaredView[];
  /** Feature 026: the declared dashboard/PDF composition; absent → today's behaviour (FR-009). */
  layout?: LayoutDocument;
  /** Feature 026: the layout warnings, sent with the definition; a warning never blocks the run. */
  layout_problems?: LayoutProblem[];
  /** Feature 044: the declared `images:` sets, with the URL prefix the server resolved for them. */
  images?: Record<string, ReportImageSet>;
}

/** Feature 044: one `images:` set as the report payload reads it. `url` is the report-scoped asset
 * prefix — the client appends the row key, never a file name. */
export interface ReportImageSet {
  /** The dimension or column the key comes from. */
  key: string;
  fallback: "initial" | "none";
  /** Present for a folder set: `/api/reports/<id>/assets/<set>/`. */
  url?: string;
  /** Present for a cached-URL set: the column holding the addresses. */
  column?: string;
  /** Present for a cached-URL set: the prefix a cached value (`<sha256>.<ext>`) is read from. */
  cached_url?: string;
}

export interface Change {
  pct: number | null;
  new: boolean;
}

export interface KpiItem {
  metric: string;
  label: string;
  label_en?: string;
  format: MetricFormat;
  better: "higher" | "lower";
  value: number | null;
  previous: number | null;
  change: Change | null;
  /** Feature 038: this metric could not be computed; the tile shows its card, the row goes on. */
  error?: RenderErrorCard;
}

export interface TrendPoint {
  bucket: string;
  value: number | null;
  previous?: number | null;
  previous_bucket?: string;
}

/** Feature 038: the code of a report failure and the piece that failed — never a row value. */
export interface RenderErrorCard {
  code:
    | "preview_expired"
    | "dataset_missing"
    | "join_failed"
    | "empty_dataset"
    | "metric_error"
    | "layout_component_unknown"
    | "format_unknown"
    | "pdf_render";
  message: string;
  /** The id of the report the failing piece belongs to. */
  report?: string;
  /** Short reference of the payload: the same one the server logged. */
  reference?: string;
  dataset?: string;
  datasets?: string;
  column?: string;
  sets?: string;
  key?: string;
  metric?: string;
  view?: string;
  component?: string;
  type?: string;
  block?: string;
  reason?: string;
  format?: string;
  version?: number;
}

/** Facts the engine derives per request (feature 026, data-model §7): `summary` is always sent,
 * `totals` only when a layout asks for them on that view. `id` is the declared view id, which is
 * what a `layout.web` component binds to. */
interface DerivedViewFacts {
  id?: string;
  summary: string;
  summary_en?: string;
  totals?: Record<string, number>;
  /** Feature 038: the view could not be built; it carries the card and nothing else. */
  error?: RenderErrorCard;
  /** Feature 038: the period has no data; the tile says «Sin datos» instead of failing. */
  empty?: RenderErrorCard;
}

export type ReportView =
  | ({ type: "kpis"; items: KpiItem[] } & DerivedViewFacts)
  | ({ type: "trend"; metric: string; label: string; label_en?: string; format: MetricFormat; grain: "day" | "week" | "month"; points: TrendPoint[] } & DerivedViewFacts)
  | ({
      type: "ranking";
      metric: string;
      dimension: string;
      title: string;
      title_en?: string;
      label: string;
      label_en?: string;
      dimension_label: string;
      dimension_label_en?: string;
      format: MetricFormat;
      items: { key: string | number | null; value: number | null; share: number | null; previous: number | null; change: Change | null }[];
    } & DerivedViewFacts)
  | ({
      type: "table";
      title: string | null;
      title_en?: string;
      columns: {
        id: string;
        label: string;
        label_en?: string;
        kind: "dimension" | "metric";
        format?: MetricFormat;
      }[];
      rows: Record<string, string | number | null>[];
    } & DerivedViewFacts);

export interface Range {
  from: string;
  to: string;
}

export interface ReportFreshness {
  updated_at: string | null;
  data_version: string;
  mode?: "dataset" | "direct";
  source?: string;
  queried_at?: string | null;
  stale?: boolean;
  stale_reason?: "timeout" | "unreachable" | "busy" | null;
}

export interface ReportData {
  selection: { period: PeriodPreset; current: Range; compare: CompareMode; previous: Range | null; partial: boolean; grain: string };
  filters: Record<string, string[]>;
  freshness: ReportFreshness;
  views: ReportView[];
  /** Feature 038: the reference this payload's error cards carry in the server log. */
  render_reference?: string;
  /** Advisory layout warnings (feature 026); errors are refused before a version is applied. */
  layout_problems?: LayoutProblem[];
}

// --- Feature 026: declarative layouts ---------------------------------------------------------
// Field names, enums and optionality come from specs/026-declarative-layouts/data-model.md §1–§6.

/** data-model §6: a layout carries semantic roles, never colours; a hex value fails validation. */
export type ColorRole =
  | "primary"
  | "positive"
  | "negative"
  | "neutral"
  | "muted"
  | "series1"
  | "series2"
  | "series3"
  | "series4"
  | "series5"
  | "series6"
  | "series7"
  | "series8";

/** data-model §6: a closed set of named families; no font file is shipped. */
export type FontName = "sans" | "sans_bold" | "serif" | "mono";

export type LayoutGutter = "sm" | "md" | "lg";
export type LayoutProblemLevel = "error" | "warning";
export type WebComponentType =
  | "kpi"
  | "line"
  | "area"
  | "bar"
  | "pie"
  | "donut"
  | "table"
  | "gauge"
  | "share"
  | "index"
  | "asset"
  | "text"
  | "filters"
  | "spacer";
export type TextStyle = "heading" | "paragraph" | "caption";
export type SpacerSize = "sm" | "md" | "lg";
export type BarOrientation = "vertical" | "horizontal";
export type SortDirection = "asc" | "desc";

/** A declared view (`report.yaml` → `views[]`), in the order the payload returns them. */
export interface DeclaredView {
  id?: string;
  type: string;
  [key: string]: unknown;
}

/** data-model §3: every web component shares these binding fields; the rest are per type. */
export interface WebComponent {
  id: string;
  type: WebComponentType;
  /** A declared `views[].id`; required for every type except `text`, `filters` and `spacer`. */
  view?: string;
  /** Grid columns from the desktop breakpoint, 1–12; default 12 (phones stack in declared order). */
  span?: number;
  title?: string;
  title_en?: string;
  colors?: ColorRole | ColorRole[];
  /** Default true: announce and show the engine's text summary (accessibility). */
  summary?: boolean;

  // kpi
  metric?: string;
  delta?: "previous_period" | "none";
  sparkline?: boolean;

  // gauge | index (042)
  min?: number;
  max?: number;
  low_label?: string;
  low_label_en?: string;
  high_label?: string;
  high_label_en?: string;

  // share (042): metric ids live in `items`; the remainder segment is computed to 100.
  items?: string[];
  remainder_label?: string;
  remainder_label_en?: string;

  // asset (042): `columns` is the positional role list [image, title, subtitle, value, delta].
  limit?: number;

  // table | kpi | asset (044): a declared image set; the row key picks the file.
  image?: string;

  // line | area | bar
  x?: string;
  series?: string[];
  orientation?: BarOrientation;
  stacked?: boolean;

  // pie | donut
  category?: string;
  value?: string;
  top_n?: number;
  other_label?: string;
  other_label_en?: string;

  // table
  columns?: string[];
  totals?: boolean;
  sort?: { by: string; dir: SortDirection };
  page_size?: number;

  // text
  text?: string;
  text_en?: string;
  style?: TextStyle;
  /** data-model §6 FontName; honoured inside a `text` block only. */
  font_name?: FontName;

  // filters
  only?: string[];

  // spacer
  size?: SpacerSize;
}

/** data-model §2: declared order is the phone order and the desktop reading order. */
export interface WebLayout {
  components: WebComponent[];
  gutter?: LayoutGutter;
}

export type PdfPageSize = "a4" | "letter";
export type PdfOrientation = "portrait" | "landscape";
export type PdfOverflow = "continue" | "truncate";
export type PdfBlockType =
  | "header"
  | "kpi_row"
  | "chart"
  | "table"
  | "text"
  | "page_break"
  | "footer";

export interface PdfPage {
  size?: PdfPageSize;
  orientation?: PdfOrientation;
  margins?: { top: number; right: number; bottom: number; left: number };
}

/** data-model §5. */
export interface PdfBlock {
  id: string;
  type: PdfBlockType;
  view?: string;
  // header
  title?: boolean;
  subtitle?: boolean;
  period?: boolean;
  logo?: boolean;
  logo_role?: "brand" | "none";
  // kpi_row
  items?: string[];
  delta?: boolean;
  // chart
  kind?: WebComponentType;
  x?: string;
  series?: string[];
  height_mm?: number;
  category?: string;
  value?: string;
  top_n?: number;
  colors?: ColorRole | ColorRole[];
  // table
  columns?: string[];
  widths?: number[];
  totals?: boolean;
  overflow?: PdfOverflow;
  // text
  text?: string;
  text_en?: string;
  style?: TextStyle;
  align?: "left" | "center" | "right";
  font_name?: FontName;
  // footer
  generated_at?: boolean;
  page_numbers?: boolean;
  legal?: string;
  legal_en?: string;
}

/** data-model §4. */
export interface PdfLayout {
  page?: PdfPage;
  blocks: PdfBlock[];
  overflow?: PdfOverflow;
}

/** data-model §1: both compositions are optional; absent → today's behaviour on that output. */
export interface LayoutDocument {
  web?: WebLayout;
  pdf?: PdfLayout;
  /** Feature 030: the report's own palette, overriding the installation's (026 FR-005 holds — a
   * preset id, never a colour). */
  theme?: { palette?: PaletteId };
}

/** Feature 030: the palette presets shipped with the product (`frontend/src/theme/palettes/`). */
export type PaletteId = "impacto" | "clasico" | "monocromo" | "contraste" | "daltonico";

/** Feature 030: Administración → Apariencia (contracts/appearance-api.md). */
export interface AppearanceSettings {
  palette_preset: PaletteId;
  presets: PaletteId[];
}

/** data-model §8: the CLI's `Issue` shape, as the engine sends it in `layout_problems`. */
export interface LayoutProblem {
  entry?: string;
  level: LayoutProblemLevel;
  code: string;
  file?: string;
  path: string;
  message: string;
  expected?: string;
  fix?: string;
}

export interface WorkspaceSpec {
  key: string;
  /** Legacy keys: integration | report; feature 020 keys: fuente | integracion | reporte | distribucion. */
  kind: string;
  project?: string | null;
  folder: string | null;
  title: string | null;
  status: string | null;
  sha256: Record<string, string> | null;
}

export type WorkspaceSpecFile = "spec.md" | "plan.md" | "tasks.md";

export interface WorkspaceSpecDocument extends WorkspaceSpec {
  documents: Record<WorkspaceSpecFile, string> | null;
}

export interface WorkspaceVersion {
  id: number;
  commit: string | null;
  checksum: string;
  applied_at: string;
  applied_by: number | null;
  workspace: string | null;
  integrations: string[];
  reports: string[];
  specs?: WorkspaceSpec[];
  /** Feature 020: artifacts per owning project. */
  distributions?: string[];
  projects?: Record<string, {
    project_id: number | null; name: string; origin: string;
    integrations: string[]; reports: string[]; distributions: string[];
  }>;
}

export interface WorkspaceReportDetail {
  id: string;
  mode: "dataset" | "direct";
  source: string | null;
  tables: string[];
  status: "ok" | "broken" | "failing" | null;
  last_read_at: string | null;
}

export interface WorkspaceState {
  mounted: { path: string; commit: string | null; checksum: string | null; read_at: string } | null;
  active: WorkspaceVersion | null;
  previous: WorkspaceVersion | null;
  report_details?: WorkspaceReportDetail[];
}

export interface WorkspaceIssue {
  entry: string;
  code: string;
  message: string;
}

export interface WorkspaceValidation {
  ok: boolean;
  errors: WorkspaceIssue[];
  warnings: WorkspaceIssue[];
  changes: {
    added?: string[];
    changed?: string[];
    removed?: string[];
    dataset_changes?: { integration: string; dataset: string; changed: string[]; removed: string[]; key_changed: boolean }[];
  };
}

export type RunPath = "copy" | "rows" | "copy+polars" | "rows+polars" | "bulk";

export interface IntegrationRunDataset {
  extracted: number;
  written: number;
  full: boolean;
  path?: RunPath;
  fallback?: string;
  transform_mode?: "rows" | "whole";
  rows_in?: number;
  transform_ms?: number;
}

export interface RollupOutcome {
  ok: boolean;
  mode?: "full" | "window";
  days?: number;
  rows?: number | null;
  ms?: number;
  error?: string;
}

export interface IntegrationRun {
  id: number;
  kind: "incremental" | "full" | "manual_incremental" | "manual_full";
  status: "running" | "succeeded" | "failed" | "skipped" | "stopped";
  started_at: string;
  finished_at: string | null;
  rows: Record<string, IntegrationRunDataset>;
  checks: { dataset: string; type: string; ok: boolean; detail: string }[];
  message: string | null;
  stop_requested_at?: string | null;
  rollups?: Record<string, RollupOutcome>;
}

export interface IntegrationControl {
  paused: boolean;
  schedule: string;
  schedule_source: "spec" | "override";
  schedule_words: string | null;
  spec_schedule: string;
  full_rebuild_cron: string | null;
  full_rebuild_crons: string[];
  full_rebuild_source: "spec" | "override";
  spec_full_rebuild_crons: string[];
  window: { start: string; end: string } | null;
  next_run: string | null;
  updated_at: string | null;
}

// A type alias (not an interface) so it is assignable to the API client's JSON body type.
export type IntegrationControlUpdate = {
  paused?: boolean;
  schedule?: string | null;
  full_rebuild_cron?: string | null;
  window_start?: string | null;
  window_end?: string | null;
};

export interface Integration {
  id: string;
  source: string;
  schedule: string;
  datasets: string[];
  spec: string | null;
  paused: boolean;
  last_run: IntegrationRun | null;
  last_success_at: string | null;
  next_run: string | null;
  control: IntegrationControl;
  running_run_id: number | null;
}

export interface AccessToken {
  id: number;
  name: string;
  scopes: string[];
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
  active: boolean;
}

// --- feature 007: sign in with Telegram ------------------------------------------------------
export interface TelegramStart {
  match_code: number;
  deep_link: string;
  qr_svg: string;
  expires_at: string;
}

export type TelegramStatus =
  | { status: "pending" }
  | { status: "signed_in"; user: User }
  | { status: "mfa_required"; enrollment_required?: boolean }
  | { status: "refused"; reason: string; message: string }
  | { status: "expired" };

export interface TelegramLinkStart {
  deep_link: string;
  qr_svg: string;
  expires_at: string;
}

export interface MeTelegram {
  available: boolean;
  linked: boolean;
  username: string | null;
  display_name: string | null;
  linked_at: string | null;
  pending: boolean;
}

export interface TelegramAdminState {
  enabled: boolean;
  bot_username: string | null;
  token_configured: boolean;
  token_changed_at: string | null;
  last_check_at: string | null;
  last_check_ok: boolean | null;
  last_check: { reason?: string; bot_name?: string } | null;
}

export interface TelegramCheck {
  ok: boolean;
  reason?: string;
  bot_name?: string;
}

// Feature 021: Spec Kit commands in the chat.
/** Feature 039: the run report card the last message of a pipeline carries. */
// Feature 017 (agentic chat)
export interface ProjectReadiness {
  ready: boolean;
  pending: { code: string; file: string | null; message: string }[];
}

export interface ShareLinksState {
  items: ShareLink[];
  sharing_enabled: boolean;
  max_active: number;
  active_count: number;
  days: { min: number; max: number; default: number };
}

export interface CreatedShareLink extends ShareLink {
  token: string;
  url: string;
}

export interface ShareLink {
  id: number;
  note: string | null;
  created_by: { id: number; name: string | null };
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
  visits: number;
  last_visit_at: string | null;
  active: boolean;
  origin: ShareLinkOrigin;
  counted: boolean;
  /** Feature 030: the first-load theme chosen when the link was created. */
  theme?: ShareTheme | null;
}
export interface ShareLinksState {
  items: ShareLink[];
  sharing_enabled: boolean;
  max_active: number;
  active_count: number;
  days: { min: number; max: number; default: number };
}
export interface CreatedShareLink extends ShareLink {
  token: string;
  url: string;
}
export type ShareLinkOrigin = "manual" | "email" | "subscription";

export type EmailDeliveryStatus = "queued" | "sent" | "failed" | "skipped";
export type EmailSendStatus = "queued" | "sending" | "sent" | "partial" | "failed";

export interface EmailDelivery {
  id: number;
  recipient: string;
  user_id: number | null;
  status: EmailDeliveryStatus;
  attempts: number;
  error: string | null;
  sent_at: string | null;
}

export interface EmailSend {
  id: number;
  subject: string;
  status: EmailSendStatus;
  created_at: string;
  finished_at: string | null;
  attach_pdf: boolean;
  link_days: number | null;
  subscription_id: number | null;
  requested_by: { id: number; name: string | null } | null;
  deliveries: EmailDelivery[];
}

export interface EmailOptions {
  available: boolean;
  can_link: boolean;
  allowed_domains: string[];
  max_recipients: number;
  link_days: { min: number; max: number; default: number };
  links_active?: number; // administrators only
  links_max?: number; // administrators only
  items: EmailSend[];
}

export interface RecipientOption {
  id: number;
  name: string;
  email?: string;
}

export type SubscriptionFrequency = "daily" | "weekly" | "monthly";

export type SubscriptionRecipient =
  | { user_id: number; name: string | null }
  | { email: string }
  | { role: string };

export interface Subscription {
  id: number;
  frequency: SubscriptionFrequency;
  hour: number;
  weekday: number | null;
  monthday: number | null;
  period: PeriodPreset;
  period_label: string;
  attach_pdf: boolean;
  link_days: number | null;
  paused: boolean;
  last_due_at: string | null;
  next_due_at: string;
  created_at: string;
  updated_at: string;
  created_by: { id: number; name: string | null };
  recipients: SubscriptionRecipient[];
  /** Feature 020: owned by a project distribution (only pause/resume here). */
  managed_by?: { project: string | null; slug: string | null; distribution: string } | null;
}

export interface SubscriptionsState {
  items: Subscription[];
  available: boolean;
  can_link: boolean;
  timezone: string;
}

export interface SharedDashboard {
  dashboard: { code: string; name: string; name_en?: string };
  expires_at: string;
  report: ReportDefinition;
  /** Feature 030: the theme the sharer chose for the first load; `null` follows the viewer. */
  theme?: ShareTheme | null;
}

export type ShareTheme = "light" | "dark";

// Feature 020: BI projects (one folder per project, cloud editor, history).
export type ProjectStatus = "borrador" | "aplicado" | "cambios" | "retirado";
export type ProjectOrigin = "app" | "git" | "import";
export type SpecKind = "fuente" | "integracion" | "reporte" | "distribucion";
export type SpecStage =
  | "especificada" | "aclarada" | "planificada" | "tareas" | "implementada" | "aplicada";

export interface ProjectRef { id: number; slug: string; name: string }

/** Feature 020 plan §4: integration, report and distribution ids of a project. */
export interface ProjectArtifacts {
  integrations: string[];
  reports: string[];
  distributions: string[];
}

export interface ProjectSummary {
  id: number;
  slug: string;
  name: string;
  description: string;
  origin: ProjectOrigin;
  spec_seq: number;
  status: ProjectStatus;
  spec_count: number;
  conversations: number;
  created_at: string | null;
  updated_at: string | null;
  last_activity_at: string | null;
  first_applied_at: string | null;
  withdrawn_at: string | null;
  /** In the folder and in the active version (list only). */
  artifacts: ProjectArtifacts;
  applied: ProjectArtifacts;
  /** Errors of the last validation; null before the first one. */
  problems: number | null;
}

export interface ProjectLastApplied { version: number; at: string; by: string | null }

export interface SpecInfo {
  folder: string;
  number: number;
  kind: SpecKind | null;
  stage: SpecStage | null;
  title?: string | null;
  status?: string | null;
  converged: boolean;
  linked?: Partial<Record<SpecKind, string[]>>;
  source_missing?: { source: string | null; link: string };
}

export interface ProjectConversation {
  id: number;
  title: string;
  status: string;
  read_only: boolean;
  current_spec: string | null;
  updated_at: string | null;
}

export interface ChangedFiles { added: string[]; changed: string[]; removed: string[] }

export interface ProjectDetail
  extends Omit<ProjectSummary, "spec_count" | "conversations" | "artifacts" | "applied" | "problems"> {
  changed_files: ChangedFiles;
  last_applied: ProjectLastApplied | null;
  specs: SpecInfo[];
  conversations: ProjectConversation[];
}

export interface TreeEntry { path: string; size: number; sha256: string }

export interface ProjectTree {
  files: TreeEntry[];
  folders: string[];
  ignored: string[];
  specs: Record<string, { kind: SpecKind | null; stage: SpecStage | null; converged: boolean }>;
  status: ProjectStatus;
}

export interface ProjectFile { path: string; content: string; sha256: string; revision_id: number | null }

export interface ProjectIssue {
  code: string;
  message: string;
  file: string | null;
  path?: string | null;
  line: number | null;
  project?: string | null;
  entry?: string;
  fix?: string | null;
  expected?: unknown;
  /** Feature 035: the machine-applicable half of the correction, when the validator knows it. */
  fix_data?: ProjectFix | null;
  problem_id?: string | null;
}

/** Feature 035: a JSON Pointer operation the product applies without an AI. */
export interface ProjectFix {
  file: string;
  json_path: string;
  op: "set" | "append" | "insert" | "remove";
  value?: unknown;
}

export interface FixResult {
  results: { file: string; revision_id: number | null; diff: string; problems: string[] }[];
  validation: ProjectValidation;
  readiness: ProjectCheck["readiness"];
}

export interface ProjectValidation {
  valid: boolean;
  errors: ProjectIssue[];
  warnings: ProjectIssue[];
  base_version?: number | null;
  fingerprint?: string;
  project_ok?: boolean;
  /** Feature 037: issues found in *other* projects of the composition, as counts (never fixable). */
  other_projects?: Record<string, { errors: number; warnings: number }>;
  workspace_errors?: number;
  workspace_warnings?: number;
  composed_valid?: boolean;
}

export interface ProjectCheck { validation: ProjectValidation; readiness: ProjectReadiness }

export interface SaveResult extends ProjectCheck {
  file: { path: string; sha256: string; revision_id: number | null };
}

export interface FileChangedCurrent {
  revision_id: number | null;
  sha256: string | null;
  author: string | null;
  time: string | null;
}

export interface ProjectChange {
  id: number;
  path: string;
  op: string;
  actor: string;
  actor_id: number | null;
  command: string;
  session_id: number | null;
  time: string;
}

export interface ProjectChanges { items: ProjectChange[]; latest: number; busy: boolean }

export interface Revision {
  id: number;
  path: string;
  op: string;
  actor: string;
  actor_name: string | null;
  command: string;
  session_id: number | null;
  restored_from: number | null;
  renamed_from: string | null;
  size: number;
  sha256: string | null;
  time: string;
}

export interface RevisionGroup {
  group_id: string;
  actor: string;
  actor_name: string | null;
  command: string;
  session_id: number | null;
  time: string;
  files: Revision[];
}

export interface HistoryEvent { event: string; time: string; actor_name: string | null; version: number | null }

export type HistoryItem = RevisionGroup | HistoryEvent;

export interface ProjectHistory { items: HistoryItem[]; next_before: number | null }

export interface DiffLine { t: " " | "+" | "-"; text: string }
export interface DiffHunk { a_start: number; b_start: number; lines: DiffLine[] }
export interface ProjectDiff { path: string; hunks: DiffHunk[]; truncated: boolean }

export interface SpecTimeline {
  folder: string;
  stages: { stage: SpecStage; time: string; version?: number }[];
  conversations: { id: number; title: string }[];
}

export interface ProjectImportResult {
  project: ProjectSummary;
  ignored: string[];
  validation: ProjectValidation;
}

// Feature 023: the app guide (Ayuda).
export interface GuideTopicSummary {
  id: string;
  section: string;
  title: string;
  summary: string;
  roles: string[];
  related: string[];
}
export interface GuideIndex {
  version: number;
  sections: { id: string; title: string }[];
  topics: GuideTopicSummary[];
}
export interface GuideTopic {
  id: string;
  title: string;
  body: string;
  roles: string[];
  routes: string[];
  related: { id: string; title: string }[];
}
