"""Throwaway certificate authority and local HTTP(S) servers for connector tests."""
import datetime
import http.server
import ssl
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


class TestCA:
    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        now = datetime.datetime.now(datetime.UTC)
        self.cert = (x509.CertificateBuilder().subject_name(_name("Bizview Test CA"))
                     .issuer_name(_name("Bizview Test CA")).public_key(self.key.public_key())
                     .serial_number(x509.random_serial_number())
                     .not_valid_before(now - datetime.timedelta(days=1))
                     .not_valid_after(now + datetime.timedelta(days=2))
                     .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                     .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True,
                                                  crl_sign=True, content_commitment=False,
                                                  key_encipherment=False, data_encipherment=False,
                                                  key_agreement=False, encipher_only=False,
                                                  decipher_only=False), critical=True)
                     .add_extension(x509.SubjectKeyIdentifier.from_public_key(
                         self.key.public_key()), critical=False)
                     .sign(self.key, hashes.SHA256()))
        self.pem = self.cert.public_bytes(serialization.Encoding.PEM).decode()

    def issue(self, hostname: str) -> tuple[str, str]:
        key = ec.generate_private_key(ec.SECP256R1())
        now = datetime.datetime.now(datetime.UTC)
        cert = (x509.CertificateBuilder().subject_name(_name(hostname))
                .issuer_name(self.cert.subject).public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now - datetime.timedelta(days=1))
                .not_valid_after(now + datetime.timedelta(days=2))
                .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]),
                               critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(
                    self.key.public_key()), critical=False)
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                               critical=False)
                .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
                               critical=False)
                .sign(self.key, hashes.SHA256()))
        return (cert.public_bytes(serialization.Encoding.PEM).decode(),
                key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()).decode())

    def client_context(self) -> ssl.SSLContext:
        ctx = ssl.create_default_context(cadata=self.pem)
        return ctx


Handler = Callable[[http.server.BaseHTTPRequestHandler], None]


class StubServer:
    """HTTP(S) server on 127.0.0.1 with a pluggable handler; records requests."""

    def __init__(self, handler: Handler, *, tls: tuple[str, str] | None = None):
        self.requests: list[dict] = []
        outer = self

        class _H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _record(self):
                length = int(self.headers.get("content-length") or 0)
                body = self.rfile.read(length) if length else b""
                outer.requests.append({"method": self.command, "path": self.path,
                                       "headers": dict(self.headers), "body": body})
                handler(self)

            do_GET = do_POST = do_PUT = _record

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
        if tls:
            cert_pem, key_pem = tls
            self._tmp = tempfile.TemporaryDirectory()
            cert_file = Path(self._tmp.name, "cert.pem")
            key_file = Path(self._tmp.name, "key.pem")
            cert_file.write_text(cert_pem)
            key_file.write_text(key_pem)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(cert_file, key_file)
            self.httpd.socket = ctx.wrap_socket(self.httpd.socket, server_side=True)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def reply(status: int = 200, body: bytes = b"ok", headers: dict | None = None) -> Handler:
    def _handle(h):
        h.send_response(status)
        for k, v in (headers or {"content-type": "text/plain"}).items():
            h.send_header(k, v)
        h.send_header("content-length", str(len(body)))
        h.end_headers()
        h.wfile.write(body)
    return _handle
