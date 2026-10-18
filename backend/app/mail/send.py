"""Email delivery of dashboards (feature 018): message building and SMTP transport."""

import contextlib
import html
import smtplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from app.config import Settings, get_settings
from app.i18n import current, t, use_locale

TIMEOUT = 20
MAX_ATTACHMENT = 10 * 1024 * 1024

_FONT = "font-family:Arial,sans-serif;"


def _p(inner: str, style: str = "margin:0 0 8px;") -> str:
    return f'<p style="{style}{_FONT}">{inner}</p>'


REASONS: dict[str, str] = {
    "connection_failed": "No fue posible conectar con el servidor de correo.",
    "timeout": "El servidor de correo no respondió a tiempo.",
    "tls_failed": "No fue posible establecer una conexión cifrada con el servidor de correo.",
    "tls_unavailable": "El servidor de correo no ofrece STARTTLS.",
    "auth_failed": "El servidor de correo rechazó el usuario o la contraseña.",
    "sender_refused": "El servidor de correo rechazó la dirección del remitente.",
    "recipient_refused": "El servidor de correo rechazó el destinatario.",
    "smtp_error": "El servidor de correo devolvió un error.",
    "not_configured": "El correo no está configurado.",
    "too_large": "El PDF supera 10 MB y no se pidió un enlace.",
    "nothing_to_send": "No hay PDF ni enlace para enviar.",
    "no_access": "El destinatario ya no tiene acceso al tablero.",
    "unavailable": "El tablero ya no está disponible.",
    "requester_no_access": "Quien pidió el envío ya no tiene acceso al tablero.",
    "internal": "Ocurrió un error inesperado al preparar el correo.",
    "link_failed": "No fue posible crear el enlace del tablero.",
    "link_unavailable": (
        "El enlace del tablero ya no está disponible (venció, fue revocado o los "
        "enlaces están desactivados)."
    ),
    "tls_required": (
        "El perfil internet exige una conexión cifrada con el servidor de correo; "
        "cambia la seguridad a STARTTLS o SSL."
    ),
}


class MailError(Exception):
    def __init__(self, code: str, permanent: bool = False):
        self.code = code
        self.permanent = permanent
        self.message = reason(code)
        super().__init__(self.code)

    def __str__(self) -> str:
        return self.code


def reason(code: str) -> str:
    return t(f"mail.reason.{code if code in REASONS else 'smtp_error'}")


def pdf_date(value: str) -> str:
    """Format an ISO date using pdf.fmt_date, passing legacy strings through."""
    from app.reports import pdf
    try:
        date.fromisoformat(value)
    except ValueError:
        return value
    return pdf.fmt_date(value)


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    security: str
    username: str | None
    password: str | None
    sender_name: str | None
    sender_address: str

    def __repr__(self) -> str:
        return f"SmtpConfig(host={self.host!r}, port={self.port!r}, security={self.security!r})"


def safe_header(value: str) -> str:
    return value.replace("\r", " ").replace("\n", " ").strip()


def config_from(settings: Settings) -> SmtpConfig:
    if not settings.email_enabled:
        raise MailError("not_configured", permanent=True)
    return SmtpConfig(
        host=settings.smtp_host,
        port=settings.smtp_port,
        security=settings.smtp_security_effective,
        username=settings.smtp_user,
        password=settings.smtp_password.get_secret_value() if settings.smtp_password else None,
        sender_name=settings.smtp_from_name,
        sender_address=settings.smtp_from,
    )


def logo_src(logo_url: str | None, base: str | None) -> str | None:
    if not logo_url:
        return None
    logo_url = logo_url.strip()
    if not logo_url:
        return None
    if logo_url.startswith("https://") or logo_url.startswith("http://"):
        return logo_url
    if logo_url.startswith("/") and not logo_url.startswith("//") and base:
        base = base.strip()
        if base.startswith("https://") or base.startswith("http://"):
            return base.rstrip("/") + logo_url
    return None


def build_message(
    *,
    cfg: SmtpConfig,
    to: str,
    subject: str,
    organization: str,
    product: str,
    dashboard_name: str,
    period_label: str | None,
    note: str | None,
    link_url: str | None,
    link_expires: str | None,
    attachment: tuple[str, bytes] | None,
    logo_url: str | None = None,
    locale: str | None = None,
) -> EmailMessage:
    with use_locale(locale or current()):
        return _compose(
            cfg=cfg,
            to=to,
            subject=subject,
            organization=organization,
            product=product,
            dashboard_name=dashboard_name,
            period_label=period_label,
            note=note,
            link_url=link_url,
            link_expires=link_expires,
            attachment=attachment,
            logo_url=logo_url,
        )


def _compose(
    *,
    cfg,
    to,
    subject,
    organization,
    product,
    dashboard_name,
    period_label,
    note,
    link_url,
    link_expires,
    attachment,
    logo_url,
) -> EmailMessage:
    msg = EmailMessage()
    sender_name = cfg.sender_name or organization or product
    msg["From"] = formataddr((safe_header(sender_name), cfg.sender_address))
    msg["To"] = to
    msg["Subject"] = safe_header(subject)
    msg["Date"] = formatdate(usegmt=True)
    domain = cfg.sender_address.rsplit("@", 1)[-1]
    msg["Message-ID"] = make_msgid(domain=domain)
    msg["Auto-Submitted"] = "auto-generated"

    text_lines: list[str] = [dashboard_name]
    if period_label:
        text_lines.append(t("mail.period", label=period_label))
    text_lines.append("")
    if note:
        text_lines.append(note)
        text_lines.append("")
    if attachment:
        text_lines.append(t("mail.attached"))
    if link_url:
        text_lines.append(t("mail.view_online", url=link_url))
        if link_expires:
            text_lines.append(t("mail.link_expires", date=pdf_date(link_expires)))
    text_lines.append("")
    text_lines.append(t("mail.footer", sender=organization or product, product=product))
    msg.set_content("\n".join(text_lines))

    heading_style = "margin:0 0 8px;"
    html_parts: list[str] = []
    if logo_url:
        alt = html.escape(organization or product, quote=True)
        html_parts.append(
            '<p style="margin:0 0 12px;">'
            f'<img src="{html.escape(logo_url, quote=True)}" alt="{alt}" '
            'style="max-height:48px;max-width:200px;border:0;"></p>'
        )
    html_parts.append(
        f'<h2 style="{heading_style}{_FONT}">{html.escape(dashboard_name)}</h2>'
    )
    if period_label:
        html_parts.append(_p(t("mail.period", label=html.escape(period_label))))
    if note:
        note_html = html.escape(note).replace("\r\n", "\n").replace("\r", "\n")
        note_html = note_html.replace("\n", "<br>")
        html_parts.append(_p(note_html))
    if attachment:
        html_parts.append(_p(t("mail.attached")))
    if link_url:
        link_html = (
            f'<a href="{html.escape(link_url, quote=True)}">{html.escape(link_url)}</a>'
        )
        if link_expires:
            link_html += " " + t("mail.link_expires",
                                 date=html.escape(pdf_date(link_expires)))
        html_parts.append(_p(t("mail.view_online", url=link_html)))
    footer_style = "margin:16px 0 0;color:#666;font-size:12px;"
    html_parts.append(
        _p(
            t(
                "mail.footer",
                sender=html.escape(organization or product),
                product=html.escape(product),
            ),
            style=footer_style,
        )
    )
    msg.add_alternative(
        "<html><body>" + "".join(html_parts) + "</body></html>",
        subtype="html",
    )

    if attachment:
        filename, data = attachment
        msg.add_attachment(
            data,
            maintype="application",
            subtype="pdf",
            filename=filename,
        )
    return msg


def smtp_transport(cfg: SmtpConfig, msg: EmailMessage) -> None:
    ctx = ssl.create_default_context()
    conn: smtplib.SMTP | smtplib.SMTP_SSL | None = None
    try:
        if cfg.security == "ssl":
            conn = smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=TIMEOUT, context=ctx)
        else:
            conn = smtplib.SMTP(cfg.host, cfg.port, timeout=TIMEOUT)
        conn.ehlo()
        if cfg.security == "starttls":
            conn.starttls(context=ctx)
            conn.ehlo()
        if cfg.username:
            try:
                conn.login(cfg.username, cfg.password or "")
            except (UnicodeError, ValueError):
                raise MailError("auth_failed", permanent=True) from None
        conn.send_message(msg, from_addr=cfg.sender_address, to_addrs=[msg["To"]])
    except smtplib.SMTPAuthenticationError:
        raise MailError("auth_failed", permanent=True) from None
    except smtplib.SMTPRecipientsRefused:
        raise MailError("recipient_refused", permanent=True) from None
    except smtplib.SMTPSenderRefused:
        raise MailError("sender_refused", permanent=True) from None
    except smtplib.SMTPNotSupportedError:
        raise MailError("tls_unavailable") from None
    except smtplib.SMTPException:
        raise MailError("smtp_error") from None
    except ssl.SSLError:
        raise MailError("tls_failed") from None
    except TimeoutError:
        raise MailError("timeout") from None
    except OSError:
        raise MailError("connection_failed") from None
    except (UnicodeError, ValueError):
        raise MailError("smtp_error", permanent=True) from None
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.quit()


transport: Callable[[SmtpConfig, EmailMessage], None] = smtp_transport


def deliver(cfg: SmtpConfig, msg: EmailMessage) -> None:
    if cfg.security == "none" and get_settings().profile == "internet":
        raise MailError("tls_required", permanent=True)
    transport(cfg, msg)
