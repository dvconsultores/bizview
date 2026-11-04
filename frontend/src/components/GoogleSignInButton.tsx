import { useT } from "../i18n";
import { useTheme } from "../theme/ThemeContext";

/**
 * Feature 054: "Continuar con Google" with Google's own mark and the two variants its brand terms
 * publish — white surface with a grey outline on a light page, near-black with a light outline on a
 * dark one. The mark keeps its four brand colours in both; it is never recoloured, which is why this
 * one component is listed in the colour gate's per-file exceptions.
 *
 * The SVG is inlined: the sign-in screen must work with no request to Google (and no CSP exception
 * for one) before the person has signed in anywhere.
 */

const G_PATHS: { fill: string; d: string }[] = [
  {
    fill: "#EA4335",
    d: "M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 "
      + "2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z",
  },
  {
    fill: "#4285F4",
    d: "M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 "
      + "6c4.51-4.18 7.09-10.36 7.09-17.65z",
  },
  {
    fill: "#FBBC05",
    d: "M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 "
      + "0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z",
  },
  {
    fill: "#34A853",
    d: "M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 "
      + "0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z",
  },
];

const LIGHT = "border-[#747775] bg-[#FFFFFF] text-[#1F1F1F] hover:bg-[#F7F8F8] active:bg-[#F1F3F4]";
const DARK = "border-[#8E918F] bg-[#131314] text-[#FFFFFF] hover:bg-[#1F1F1F] active:bg-[#2A2A2A]";

export function GoogleMark({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden focusable="false">
      {G_PATHS.map((path) => (
        <path key={path.fill} fill={path.fill} d={path.d} />
      ))}
    </svg>
  );
}

interface GoogleSignInButtonProps {
  onClick: () => void;
  /** Rendered on the sign-in screen; a spec or a test can override it (English, a fixture). */
  label?: string;
}

export function GoogleSignInButton({ onClick, label }: GoogleSignInButtonProps) {
  const t = useT();
  const { resolved } = useTheme();
  const text = label ?? t.google.signIn;
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid="google-sign-in"
      data-variant={resolved}
      className={`inline-flex min-h-tap w-full items-center justify-center gap-3 rounded-btn border px-4 text-base font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${
        resolved === "dark" ? DARK : LIGHT
      }`}
    >
      <GoogleMark />
      <span>{text}</span>
    </button>
  );
}
