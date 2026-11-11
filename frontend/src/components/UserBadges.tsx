import { Ban, Check, Globe, KeyRound, Lock, Send, Shield, ShieldCheck, User as UserIcon } from "lucide-react";
import type { User } from "../api/types";
import { useT } from "../i18n";
import { isLocked } from "../lib/format";
import { Badge } from "./Badge";

const ICON = "h-3.5 w-3.5";

export function RoleBadge({ user }: { user: User }) {
  const t = useT();
  if (user.is_superuser) return <Badge tone="blue" icon={<ShieldCheck className={ICON} aria-hidden />}>{t.roles.superuser}</Badge>;
  if (user.role === "admin") return <Badge tone="blue" icon={<Shield className={ICON} aria-hidden />}>{t.roles.admin}</Badge>;
  return <Badge tone="gray" icon={<UserIcon className={ICON} aria-hidden />}>{t.roles.user}</Badge>;
}

/** Status as text + icon (never colour alone). Inactive hides the other states. */
export function StatusBadges({ user }: { user: User }) {
  const t = useT();
  const badges = [];
  if (!user.is_active) {
    badges.push(<Badge key="inactive" tone="gray" icon={<Ban className={ICON} aria-hidden />}>{t.status.inactive}</Badge>);
  } else {
    const locked = isLocked(user.locked_until);
    const passwordless = !user.has_password;
    if (locked) badges.push(<Badge key="locked" tone="red" icon={<Lock className={ICON} aria-hidden />}>{t.status.locked}</Badge>);
    if (passwordless) {
      // Convergence 054b: an account without a password signs in with Google or Telegram only.
      const telegram = user.auth_provider === "telegram";
      badges.push(
        <Badge key="provider" tone="blue" icon={telegram ? <Send className={ICON} aria-hidden /> : <Globe className={ICON} aria-hidden />}>
          {telegram ? t.status.onlyTelegram : t.status.onlyGoogle}
        </Badge>,
      );
    } else if (user.must_change_password) {
      badges.push(<Badge key="temp" tone="amber" icon={<KeyRound className={ICON} aria-hidden />}>{t.status.temporary}</Badge>);
    }
    if (!locked && !passwordless && !user.must_change_password)
      badges.push(<Badge key="active" tone="green" icon={<Check className={ICON} aria-hidden />}>{t.status.active}</Badge>);
  }
  return (
    <>
      {badges.map((b) => (
        <span key={b.key} className="mr-1.5 mt-1.5 inline-flex">
          {b}
        </span>
      ))}
    </>
  );
}
