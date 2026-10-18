# UI contract: views, layout, font

## `View` (frontend/src/components/View.tsx) — replaces `Modal`

```ts
function View(props: {
  open: boolean;
  title: string;
  onClose: () => void;          // cancel, back button, browser/phone back, Esc
  children: ReactNode;
  footer?: ReactNode;           // action buttons
  autoFocus?: boolean;          // focus the first field instead of the title
}): ReactPortal | null
```

Rendering (inside the innermost view host, in normal flow):

```html
<section aria-labelledby="{titleId}" class="space-y-5">
  <div class="flex items-center gap-2">
    <button type="button" aria-label="Volver">‹ arrow icon</button>   <!-- calls onClose -->
    <h1 id="{titleId}" tabindex="-1">{title}</h1>
  </div>
  <div>{children}</div>
  <div class="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">{footer}</div>
</section>
```

Rules: no `role="dialog"`, no `aria-modal`, no `fixed`/backdrop, no scroll lock, no focus trap.
Tokens only (feature 006 guard). Width: the host's width (forms inside a view may use
`max-w-2xl` for line length).

## View hosts (frontend/src/components/ViewHost.tsx)

```ts
function ViewHost({ children }: { children: ReactNode }): JSX.Element
```

- Renders `<div hidden={viewOpen}>{children}</div><div ref=slot />`.
- Registers itself in `ViewHostContext` (stack; innermost wins). `View` portals into the top
  host's slot.
- Mounted in `AppShell` around `<Outlet />` and in `App` around `<Routes>` (fallback).
- Several open views: only the most recently opened is visible; closing it reveals the previous.

## History (R3)

- Open: push same path/search/hash with `state.view` = list of open view ids.
- Location change that drops the id → `onClose()` of that view.
- UI close while its entry is on top → `navigate(-1)`; otherwise just close.
- Entry with a view id and no open view (reload/forward) → ignored.

## Focus and scroll (R5)

Open: save active element and `scrollY`; `scrollTo(0, 0)`; focus first field (`autoFocus`) or
the `<h1>`. Close: restore `scrollY`; focus the saved element if still in the document.

## Step-up (`ReauthProvider`)

`ask(): Promise<boolean>` unchanged for the API client. Renders
`<View title="Confirma tu contraseña" autoFocus>` with `PasswordField` label "Contraseña",
buttons "Confirmar" (submit) and "Cancelar". Concurrent `ask()` calls share one promise.
Wrong password: error shown, field cleared, view stays. 423/429: view closes, `false`.

## Call sites (all `Modal` → `View`)

| Screen | View title | Actions |
|---|---|---|
| UserForm | "Usuario creado." | Crear otro · Ver usuario (secret, copy) |
| UserDetail | reset password ("Restablecer contraseña") | Cancelar · Restablecer → result with secret · Cerrar |
| UserDetail | Telegram unlink | Cancelar · Desvincular |
| UserDetail | two-step reset | Cancelar · Restablecer |
| UserDetail | deactivate / reactivate | Cancelar · Desactivar / Reactivar |
| TwoFactorCard | recovery codes | Listo (secret, copy) |
| TwoFactorCard | disable two-step | Cancelar · Desactivar |
| Workspace | "¿Volver a la versión anterior?" | Cancelar · Volver a la anterior |
| SourceForm | delete source | Cancelar · Eliminar |
| ReauthProvider | "Confirma tu contraseña" | Cancelar · Confirmar |

Titles and button labels keep today's strings (i18n `es.ts`).

## Layout

- `AppShell` main: `mx-auto max-w-screen-2xl px-4 pb-10 pt-5 sm:px-6 sm:pt-8 lg:px-8 lg:pb-12`.
- Admin pages and Profile: no `max-w-*` cap on the page wrapper.
- Forms (UserForm, SourceForm, Profile cards): `xl:grid-cols-2` for short paired fields.
- ReportView: `max-w-7xl`.
- SignIn, ChangePassword: unchanged.

## Font

- `@font-face { font-family: "Ubuntu"; font-weight: 400|500|700; font-style: normal;
  font-display: swap; src: url(./assets/fonts/ubuntu/ubuntu-<subset>-<weight>-normal.woff2)
  format("woff2"); unicode-range: <subset range>; }` for subsets latin and latin-ext.
- Tailwind `fontFamily.sans: ["Ubuntu", "system-ui", "-apple-system", "Segoe UI", "Roboto",
  "Helvetica Neue", "Arial", "Noto Sans", "sans-serif"]`;
  `fontFamily.mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"]`.
- `SecretBox` and the temporary-password input use `font-mono` (inline `MONO` style removed).
- `frontend/src/assets/fonts/ubuntu/LICENCE.txt` = Ubuntu Font Licence 1.0.
