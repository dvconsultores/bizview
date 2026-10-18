"""Destination address guard for data sources (feature 004, research R3).

Every connection to an origin resolves the host, checks EVERY resolved address, and then dials
the checked address (pinning), so a name cannot resolve to an allowed address when checked and to
a forbidden one when connecting (DNS rebinding). Always refused: loopback, unspecified,
link-local, cloud metadata, multicast/reserved, and the product's own service names. Private
networks are allowed unless the installation disables them.
"""
import ipaddress
import socket
from dataclasses import dataclass, field

import httpcore
import httpx

from app.i18n import M

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

ALWAYS_BLOCKED = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "127.0.0.0/8", "169.254.0.0/16", "224.0.0.0/4", "240.0.0.0/4",
    "255.255.255.255/32", "100.100.100.200/32",            # Alibaba Cloud metadata
    "::/128", "::1/128", "fe80::/10", "ff00::/8", "fd00:ec2::254/128",  # AWS IMDS over IPv6
)]
PRIVATE = [ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "fc00::/7",
)]
# Names of the product's own containers and the local machine.
BLOCKED_NAMES = {"localhost", "backend", "web", "caddy", "worker", "host.docker.internal"}


class BlockedAddress(Exception):
    code = "blocked_address"

    def __init__(self, host: str, reason: "M | str", *, unresolved: bool = False):
        # unresolved: the name did not resolve here; it may resolve on the worker's network
        super().__init__(f"{host}: {reason}")
        self.host, self.reason, self.unresolved = host, reason, unresolved


@dataclass(frozen=True)
class Policy:
    allow_private: bool = True
    # Only tests set this; no setting exposes it.
    allow_loopback_for_tests: bool = False
    extra_blocked_names: frozenset[str] = field(default_factory=frozenset)


def _unwrap(ip: IPAddress) -> IPAddress:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def classify(ip: IPAddress, policy: Policy) -> "M | None":
    """Reason the address is refused, or None when allowed."""
    ip = _unwrap(ip)
    if policy.allow_loopback_for_tests and ip.is_loopback:
        return None
    if any(ip in net for net in ALWAYS_BLOCKED if net.version == ip.version) or ip.is_reserved:
        return M("network.local_metadata_blocked")
    if any(ip in net for net in PRIVATE if net.version == ip.version) and not policy.allow_private:
        return M("network.private_networks_disabled")
    return None


def _own_names() -> set[str]:
    names = {socket.gethostname().lower()}
    try:
        names.add(socket.getfqdn().lower())
    except OSError:
        pass
    return names


def resolve_checked(host: str, port: int, policy: Policy) -> list[str]:
    """Resolve and check every address; return the allowed addresses to dial (in order)."""
    name = host.strip().rstrip(".").lower()
    if not name:
        raise BlockedAddress(host, M("network.empty_address"))
    if (name in BLOCKED_NAMES or name.endswith(".localhost") or name in policy.extra_blocked_names
            or (name in _own_names() and not policy.allow_loopback_for_tests)):
        raise BlockedAddress(host, M("network.internal_hostname_blocked"))
    try:
        infos = socket.getaddrinfo(name, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise BlockedAddress(host, M("network.unresolvable"), unresolved=True) from None
    addresses: list[str] = []
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%", 1)[0])
        reason = classify(ip, policy)
        if reason:
            raise BlockedAddress(host, reason)
        if str(ip) not in addresses:
            addresses.append(str(ip))
    if not addresses:
        raise BlockedAddress(host, M("network.no_addresses"))
    return addresses


class PinnedNetworkBackend(httpcore.NetworkBackend):
    """httpcore backend that dials only checked addresses. TLS still uses the original host name
    for SNI and certificate verification (httpcore passes it to start_tls separately)."""

    def __init__(self, policy: Policy):
        self._policy = policy
        self._inner = httpcore.SyncBackend()

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        last_error: Exception | None = None
        for address in resolve_checked(host, port, self._policy):
            try:
                return self._inner.connect_tcp(address, port, timeout=timeout,
                                               local_address=local_address,
                                               socket_options=socket_options)
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as e:
                last_error = e
        assert last_error is not None
        raise last_error

    def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise BlockedAddress(path, "sockets locales no permitidos")

    def sleep(self, seconds):
        self._inner.sleep(seconds)


def guarded_client(*, policy: Policy, timeout: float, verify=True, cert=None,
                   **kwargs) -> httpx.Client:
    """httpx client for origins: pinned checked addresses, no environment proxies (they would
    bypass the check), no automatic redirects (credentials must never follow them)."""
    transport = httpx.HTTPTransport(verify=verify, cert=cert, trust_env=False)
    ssl_context = transport._pool._ssl_context  # httpx 0.28: keep its verified TLS context
    transport._pool = httpcore.ConnectionPool(ssl_context=ssl_context, max_connections=10,
                                              network_backend=PinnedNetworkBackend(policy))
    return httpx.Client(transport=transport, timeout=timeout, follow_redirects=False,
                        trust_env=False, **kwargs)


def policy_from_settings(settings) -> Policy:
    return Policy(allow_private=settings.sources_allow_private_networks)
