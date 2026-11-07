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


# --- Feature 058: recipients a sender types, pastes or keeps in a list -------------------------

#: Splits a pasted block: commas, semicolons, tabs and newlines all separate addresses.
_SPLIT = re.compile(r"[,;\t\r\n]+")
#: `Nombre <correo>` — the display name the dial shows for a contact.
_NAMED = re.compile(r"^\s*(?P<name>[^<>]*?)\s*<(?P<address>[^<>]+)>\s*$")


def mask(address: str) -> str:
    """`ana@cliente.com` → `a***@cliente.com`: what a log line or another sender may see."""
    local, _, domain = address.partition("@")
    if not domain:
        return "***"
    keep = local[:1]
    return f"{keep}***@{domain}"


def parse_recipients(text: str) -> tuple[list[tuple[str, str | None]], list[str]]:
    """Addresses out of a pasted block: `(valid [(address, name)], invalid [raw])`.

    Accepts `Nombre <correo>` and bare addresses, drops the empty pieces, lowercases the address,
    and keeps the first spelling of a name when an address repeats. The order of appearance is kept,
    so the dialog's chips match what the sender typed."""
    valid: list[tuple[str, str | None]] = []
    invalid: list[str] = []
    seen: set[str] = set()
    for piece in _SPLIT.split(text or ""):
        raw = piece.strip()
        if not raw:
            continue
        named = _NAMED.match(raw)
        name = None
        candidate = raw
        if named:
            name = " ".join(named.group("name").split()) or None
            candidate = named.group("address").strip()
        address = normalize_email(candidate)
        if address is None:
            invalid.append(raw)
            continue
        if address in seen:
            continue
        seen.add(address)
        valid.append((address, name))
    return valid, invalid
