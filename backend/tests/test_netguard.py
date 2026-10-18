"""Feature 004: destination address guard, pinning, rebinding (FR-008, FR-010, SC-007)."""
import ipaddress
import socket

import httpx
import pytest

from app.security import netguard
from app.security.netguard import BlockedAddress, Policy, guarded_client, resolve_checked
from tests.tls_helpers import StubServer, TestCA, reply

STRICT = Policy(allow_private=False)
DEFAULT = Policy()


@pytest.mark.parametrize("ip", ["127.0.0.1", "127.8.9.1", "0.0.0.0", "169.254.169.254",
                                "169.254.10.1", "224.0.0.1", "255.255.255.255", "100.100.100.200",
                                "::1", "::", "fe80::1", "fd00:ec2::254", "::ffff:127.0.0.1",
                                "::ffff:169.254.169.254", "240.0.0.1"])
def test_always_blocked(ip):
    assert netguard.classify(ipaddress.ip_address(ip), DEFAULT)


@pytest.mark.parametrize("ip", ["10.1.2.3", "172.16.0.5", "192.168.1.10", "100.64.0.1", "fd12::1"])
def test_private_depends_on_policy(ip):
    addr = ipaddress.ip_address(ip)
    assert netguard.classify(addr, DEFAULT) is None
    assert netguard.classify(addr, STRICT)


@pytest.mark.parametrize("ip", ["203.0.113.9", "203.0.113.9", "2606:4700::1111"])
def test_public_allowed(ip):
    assert netguard.classify(ipaddress.ip_address(ip), STRICT) is None


@pytest.mark.parametrize("host", ["localhost", "LOCALHOST.", "backend", "web", "worker",
                                  "api.localhost", "host.docker.internal", socket.gethostname()])
def test_internal_names_blocked(host):
    with pytest.raises(BlockedAddress):
        resolve_checked(host, 443, DEFAULT)


def fake_dns(monkeypatch, table: dict[str, list[str]]):
    real = socket.getaddrinfo

    def _getaddrinfo(host, port, *args, **kwargs):
        if host in table:
            answer = table[host]
            ips = answer() if callable(answer) else answer
            return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "",
                     (ip, port)) for ip in ips]
        return real(host, port, *args, **kwargs)
    monkeypatch.setattr(netguard.socket, "getaddrinfo", _getaddrinfo)


def test_any_blocked_address_blocks_the_name(monkeypatch):
    fake_dns(monkeypatch, {"mixed.test": ["203.0.113.9", "127.0.0.1"]})
    with pytest.raises(BlockedAddress):
        resolve_checked("mixed.test", 443, DEFAULT)


def test_unresolvable_name(monkeypatch):
    with pytest.raises(BlockedAddress, match="resolver"):
        resolve_checked("does-not-exist.invalid", 443, DEFAULT)


@pytest.fixture
def tls_stub():
    ca = TestCA()
    server = StubServer(reply(200, b"hola"), tls=ca.issue("stub.test"))
    yield ca, server
    server.close()


LOOPBACK_OK = Policy(allow_loopback_for_tests=True)


def test_pinned_dial_keeps_sni_and_verification(monkeypatch, tls_stub):
    ca, server = tls_stub
    fake_dns(monkeypatch, {"stub.test": ["127.0.0.1"]})
    with guarded_client(policy=LOOPBACK_OK, timeout=5, verify=ca.client_context()) as c:
        r = c.get(f"https://stub.test:{server.port}/x")
    assert (r.status_code, r.text) == (200, "hola")
    assert server.requests[0]["headers"]["Host"] == f"stub.test:{server.port}"


def test_certificate_for_other_name_is_rejected(monkeypatch, tls_stub):
    ca, server = tls_stub
    fake_dns(monkeypatch, {"other.test": ["127.0.0.1"]})
    with guarded_client(policy=LOOPBACK_OK, timeout=5, verify=ca.client_context()) as c, \
            pytest.raises(httpx.ConnectError):
        c.get(f"https://other.test:{server.port}/")


def test_unknown_ca_is_rejected(monkeypatch, tls_stub):
    _, server = tls_stub
    fake_dns(monkeypatch, {"stub.test": ["127.0.0.1"]})
    with guarded_client(policy=LOOPBACK_OK, timeout=5) as c, pytest.raises(httpx.ConnectError):
        c.get(f"https://stub.test:{server.port}/")


def test_loopback_is_blocked_by_default(monkeypatch, tls_stub):
    ca, server = tls_stub
    fake_dns(monkeypatch, {"stub.test": ["127.0.0.1"]})
    with guarded_client(policy=DEFAULT, timeout=5, verify=ca.client_context()) as c, \
            pytest.raises(BlockedAddress):
        c.get(f"https://stub.test:{server.port}/")
    assert server.requests == []


def test_dns_rebinding_is_caught_at_connect(monkeypatch):
    answers = iter([["203.0.113.9"], ["127.0.0.1"]])
    fake_dns(monkeypatch, {"rebind.test": lambda: next(answers)})
    # when the source is saved
    assert resolve_checked("rebind.test", 80, DEFAULT) == ["203.0.113.9"]
    with guarded_client(policy=DEFAULT, timeout=5) as c, pytest.raises(BlockedAddress):
        c.get("http://rebind.test/")                                   # at connection time


def test_redirects_not_followed_and_env_proxy_ignored(monkeypatch):
    server = StubServer(reply(302, b"", {"location": "http://elsewhere.test/steal"}))
    try:
        fake_dns(monkeypatch, {"stub.test": ["127.0.0.1"]})
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")    # would fail if used
        with guarded_client(policy=LOOPBACK_OK, timeout=5) as c:
            r = c.get(f"http://stub.test:{server.port}/", headers={"Authorization": "Bearer t"})
        assert r.status_code == 302 and len(server.requests) == 1
    finally:
        server.close()
