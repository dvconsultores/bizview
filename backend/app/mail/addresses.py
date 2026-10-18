"""Address formats for email (feature 018): host names, domains and single addresses."""
import re

HOST = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$")
DOMAIN = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
EMAIL = re.compile(
    r"^(?=.{1,64}@)"
    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@[^@\s]{3,253}$"
)


def normalize_email(value: str) -> str | None:
    value = value.strip().lower()
    if not EMAIL.match(value):
        return None
    if not DOMAIN.match(email_domain(value)):
        return None
    return value


def email_domain(addr: str) -> str:
    return addr.rsplit("@", 1)[-1]


def normalize_domains(raw: str) -> list[str]:
    parts: list[str] = []
    for part in raw.split(","):
        part = part.strip().lower()
        if part.startswith("@"):
            part = part[1:]
        if not part:
            continue
        if not DOMAIN.match(part):
            raise ValueError(f"invalid domain {part!r}")
        parts.append(part)
    domains = sorted(set(parts))
    if len(domains) > 50:
        raise ValueError("at most 50 domains")
    return domains
