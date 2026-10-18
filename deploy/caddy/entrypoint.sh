#!/bin/sh
# Chooses how Caddy obtains its certificate, then runs it (deploy/caddy/Caddyfile imports the
# resulting snippet). Needed on hosts where 80 and 443 belong to other services, so the ACME
# challenges cannot work:
#   auto      automatic HTTPS (default; unchanged behaviour)
#   internal  Caddy's local CA. Pair with a proxy that forwards to this container and does not
#             validate the origin certificate (e.g. Cloudflare "Full", not "Full (strict)").
#   file      a certificate you supply, e.g. a Cloudflare Origin CA pair, mounted at /certs.
#             Required for Cloudflare "Full (strict)".
set -eu

snippet=/etc/caddy/tls.snippet
mode="${CADDY_TLS:-auto}"

case "$mode" in
auto | "")
    # A comment keeps the file non-empty: Caddy warns on importing an empty file.
    printf '# automatic HTTPS (ACME); no explicit certificate\n' >"$snippet"
    ;;
internal)
    printf 'tls internal\n' >"$snippet"
    ;;
file)
    cert="${CADDY_TLS_CERT:-/certs/origin.pem}"
    key="${CADDY_TLS_KEY:-/certs/origin-key.pem}"
    if [ ! -r "$cert" ] || [ ! -r "$key" ]; then
        echo "CADDY_TLS=file but the certificate is unreadable: $cert / $key" >&2
        echo "Mount the pair at /certs (CADDY_TLS_DIR, default ./deploy/caddy/certs)." >&2
        exit 1
    fi
    printf 'tls %s %s\n' "$cert" "$key" >"$snippet"
    ;;
*)
    echo "CADDY_TLS must be auto, internal or file (got: $mode)" >&2
    exit 1
    ;;
esac

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
