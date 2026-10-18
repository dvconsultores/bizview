from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage


class SmtpRecorder:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self.envelopes: list[dict] = []
        self.connections: list[dict] = []
        self.mode = "ok"
        self.fail_for: dict[str, str] = {}
        self.fail_times = 0

    def install(self, monkeypatch) -> None:
        recorder = self

        class FakeSMTPBase:
            def __init__(self, host: str, port: int, timeout=None, context=None):
                recorder.connections.append(
                    {
                        "host": host,
                        "port": port,
                        "ssl": isinstance(self, FakeSMTP_SSL),
                        "starttls": False,
                        "login": None,
                    }
                )
                if recorder.mode == "refused":
                    raise ConnectionRefusedError("refused by smtp.cliente.com")
                if recorder.mode == "timeout":
                    raise TimeoutError()

            def ehlo(self) -> None:
                pass

            def starttls(self, context=None) -> None:
                if recorder.mode == "tls":
                    raise ssl.SSLError("bad cert")
                if recorder.mode == "no_starttls":
                    raise smtplib.SMTPNotSupportedError(
                        "STARTTLS extension not supported by server."
                    )
                recorder.connections[-1]["starttls"] = True

            def login(self, user: str, password: str) -> None:
                user.encode("ascii")
                password.encode("ascii")
                if recorder.mode == "auth":
                    raise smtplib.SMTPAuthenticationError(
                        535, b"5.7.8 Bad credentials for " + password.encode()
                    )
                recorder.connections[-1]["login"] = (user, password)

            def send_message(self, msg: EmailMessage, from_addr=None, to_addrs=None) -> None:
                to = msg["To"]
                recorder.envelopes.append(
                    {"from": from_addr, "to": list(to_addrs) if to_addrs is not None else None}
                )
                mode = recorder.fail_for.get(to, recorder.mode)
                if mode == "recipient":
                    raise smtplib.SMTPRecipientsRefused({to: (550, b"no such user")})
                if mode == "server_text":
                    raise smtplib.SMTPDataError(
                        451, b"temporary failure, password=..."
                    )
                if recorder.fail_times > 0:
                    recorder.fail_times -= 1
                    raise smtplib.SMTPDataError(451, b"try again")
                recorder.sent.append(msg)

            def quit(self) -> None:
                pass

        class FakeSMTP(FakeSMTPBase):
            pass

        class FakeSMTP_SSL(FakeSMTPBase):
            pass

        monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
        monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP_SSL)

    def recipients(self) -> list[str]:
        return [msg["To"] for msg in self.sent]

    def attachments(self, msg: EmailMessage) -> list[tuple[str, bytes]]:
        result = []
        for part in msg.iter_attachments():
            payload = part.get_payload(decode=True) or b""
            result.append((part.get_filename() or "", payload))
        return result

    def text(self, msg: EmailMessage) -> str:
        return msg.get_body(preferencelist=("plain",)).get_content()
